import csv
import contextlib
import io
import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "workspaces" / "prospecting" / "workflows" / "event-sequence" / "01-list-prep"
SCRIPT = ROOT / "scripts" / "scrub_leads.py"
RULES = ROOT / "scripts" / "email_rules.json"

spec = importlib.util.spec_from_file_location("scrub_leads", SCRIPT)
scrub_leads = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scrub_leads)


def classify(email, first="John", last="Doe", full=None):
    rules = scrub_leads.load_rules(RULES)
    row = {
        "First Name": first,
        "Last Name": last,
        "Full Name": full or f"{first} {last}",
        "Email Business": email,
    }
    return scrub_leads.classify(row, "Email Business", rules, True, set())


def write_csv(path, rows):
    fieldnames = ["First Name", "Last Name", "Full Name", "Email Business", "Company Name"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_quiet(func, *args):
    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args)


def run_scrub(args):
    return run_quiet(scrub_leads.scrub, args)


def run_audit(args):
    return run_quiet(scrub_leads.audit_clean_output, args)


class ScrubberTests(unittest.TestCase):
    def test_200_plus_risky_examples_are_never_clean(self):
        rules = scrub_leads.load_rules(RULES)
        role_locals = sorted(rules["exact_local_parts"])
        examples = []
        for role in role_locals[:60]:
            examples.extend(
                [
                    f"{role}@examplecorp.test",
                    f"{role}-team@examplecorp.test",
                    f"team-{role}@examplecorp.test",
                    f"{role}.us@examplecorp.test",
                ]
            )
        examples.extend(
            [
                "privacy.officer@examplecorp.test",
                "privacy_officer@examplecorp.test",
                "security-alerts@examplecorp.test",
                "sales.us@examplecorp.test",
                "support-emea@examplecorp.test",
                "info+web@examplecorp.test",
                "no.reply@examplecorp.test",
                "not-an-email",
                "missing-domain@",
                "@missing-local.com",
                "one@example.com,two@example.com",
                "person@example.com",
                "person@mailinator.com",
                "list@googlegroups.com",
            ]
        )

        self.assertGreaterEqual(len(examples), 200)
        failures = [email for email in examples if classify(email)["status"] == scrub_leads.STATUS_CLEAN]
        self.assertEqual([], failures)

    def test_50_plus_safe_person_style_examples_are_clean(self):
        names = [
            ("Alex", "Morgan"),
            ("Brianna", "Cole"),
            ("Carlos", "Rivera"),
            ("Dana", "Kim"),
            ("Elliot", "Stone"),
            ("Fatima", "Hassan"),
            ("Grace", "Miller"),
            ("Hannah", "Brooks"),
            ("Ivan", "Petrov"),
            ("Julia", "Reed"),
            ("Katelyn", "Donaldson"),
            ("Liam", "Nelson"),
            ("Maya", "Patel"),
            ("Noah", "Walker"),
            ("Olivia", "Bennett"),
            ("Patrick", "Brennan"),
            ("Quinn", "Taylor"),
            ("Renee", "Brody"),
            ("Sara", "Walker"),
            ("Thomas", "Wolf"),
            ("Uma", "Shah"),
            ("Victor", "Chen"),
            ("Wendy", "Lopez"),
            ("Xavier", "Perez"),
            ("Yara", "Nassar"),
            ("Zachary", "Price"),
            ("Monica", "Marsh"),
            ("Daniel", "Wolf"),
            ("Krystal", "Parker"),
            ("Gregory", "Porter"),
        ]
        examples = []
        for idx, (first, last) in enumerate(names):
            domain = f"company{idx}.com"
            examples.append((f"{first.lower()}.{last.lower()}@{domain}", first, last))
            examples.append((f"{first.lower()[0]}{last.lower()}@{domain}", first, last))

        self.assertGreaterEqual(len(examples), 50)
        failures = []
        for email, first, last in examples:
            decision = classify(email, first=first, last=last)
            if decision["status"] != scrub_leads.STATUS_CLEAN:
                failures.append((email, decision))
        self.assertEqual([], failures)

    def test_first_name_only_matching_row_is_clean(self):
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("sara@examplefish.test", first="Sara E.", last="Walker")["status"])
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("raj@examplemedia.test", first="Rajesh (Raj)", last="Kumar")["status"])
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("renee@examplelegal.test", first="Ren\u00e9e", last="Boucher")["status"])
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("meiling@examplesoft.test", first="Mei-Ling", last="Wong")["status"])
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("jiawei@examplecloud.test", first="Jia Wei", last="Tan")["status"])
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("ddemarco@examplenews.test", first="Daniel", last="de Marco")["status"])
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("jpmoreau@examplecad.test", first="Jean-Pierre", last="Moreau")["status"])
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("sabine.berg-hoffman@examplenergy.test", first="Sabine", last="Berg-Hoffman")["status"])
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("akowalski@examplewealth.test", first="Andrew Kowalski,", last="CPA")["status"])
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("sbrook@examplelearn.test", first="\u26a1\ufe0f", last="Steven Brook")["status"])

    def test_first_name_prefix_plus_last_name_is_clean(self):
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("damurray@exampleplaid.test", first="Dan", last="Murray")["status"])
        self.assertEqual(scrub_leads.STATUS_CLEAN, classify("chrjohnson@examplecorp.test", first="Christopher", last="Johnson")["status"])

    def test_non_name_prefix_plus_last_name_is_not_clean(self):
        self.assertNotEqual(scrub_leads.STATUS_CLEAN, classify("xymurray@examplecorp.test", first="Dan", last="Murray")["status"])
        self.assertNotEqual(scrub_leads.STATUS_CLEAN, classify("damur@examplecorp.test", first="Dan", last="Murray")["status"])

    def test_ambiguous_initial_role_is_quarantined_not_removed_when_it_matches_person(self):
        decision = classify("ar@examplegrowth.test", first="Aaron", last="Reyes")
        self.assertEqual(scrub_leads.STATUS_QUARANTINE, decision["status"])
        self.assertIn("AMBIGUOUS_ROLE_INITIALS", decision["reason_codes"])

    def test_audit_clean_output_fails_on_dirty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dirty_clean.csv"
            write_csv(
                path,
                [
                    {
                        "First Name": "Privacy",
                        "Last Name": "Team",
                        "Full Name": "Privacy Team",
                        "Email Business": "privacy@examplecorp.test",
                        "Company Name": "Example Corp",
                    }
                ],
            )
            code = run_audit(
                Namespace(
                    input=str(path),
                    email_column="Email Business",
                    rules=str(RULES),
                    strict=True,
                    max_failures=10,
                    report=None,
                )
            )
            self.assertEqual(2, code)

    def test_audit_clean_output_catches_duplicates_across_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            chunk_dir = Path(tmp) / "clean_chunks"
            chunk_dir.mkdir()
            row = {
                "First Name": "Alex",
                "Last Name": "Morgan",
                "Full Name": "Alex Morgan",
                "Email Business": "alex.morgan@examplecorp.test",
                "Company Name": "Example Corp",
            }
            write_csv(chunk_dir / "clean_part_001.csv", [row])
            write_csv(chunk_dir / "clean_part_002.csv", [row])
            code = run_audit(
                Namespace(
                    input=str(chunk_dir),
                    email_column="Email Business",
                    rules=str(RULES),
                    strict=True,
                    max_failures=10,
                    report=None,
                )
            )
            self.assertEqual(2, code)

    def test_audit_clean_output_reconstructs_full_name_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clean_upload.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["First Name", "Last Name", "Company Name", "Email"])
                writer.writeheader()
                writer.writerow(
                    {
                        "First Name": "Arjun",
                        "Last Name": "MS",
                        "Company Name": "ExampleSys",
                        "Email": "arjunms@examplesys.test",
                    }
                )

            code = run_audit(
                Namespace(
                    input=str(path),
                    email_column="Email",
                    rules=str(RULES),
                    strict=True,
                    max_failures=10,
                    report=None,
                )
            )
            self.assertEqual(0, code)

    def test_scrub_writes_25k_clean_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "large.csv"
            output_dir = tmp_path / "out"
            rows = []
            for idx in range(25005):
                rows.append(
                    {
                        "First Name": "Alex",
                        "Last Name": "Morgan",
                        "Full Name": "Alex Morgan",
                        "Email Business": f"alex.morgan@company{idx}.com",
                        "Company Name": f"Company {idx}",
                    }
                )
            write_csv(input_path, rows)
            code = run_scrub(
                Namespace(
                    input=str(input_path),
                    email_column="Email Business",
                    output_dir=str(output_dir),
                    rules=str(RULES),
                    chunk_size=25000,
                    max_clean_chunk_bytes=10 * 1024 * 1024,
                    strict=True,
                    output_profile="final",
                    clean_column_profile="upload",
                )
            )
            self.assertEqual(0, code)
            report = json.loads((output_dir / "audit_report.json").read_text(encoding="utf-8"))
            self.assertEqual("PASS", report["status"])
            manifest = json.loads((output_dir / "output_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(25005, manifest["deliverable_counts"]["clean"])
            self.assertEqual(3, len(manifest["output_files"]))
            counts = []
            for path in sorted((output_dir / "clean_chunks").glob("*.csv")):
                with open(path, newline="", encoding="utf-8-sig") as f:
                    counts.append(sum(1 for _ in csv.DictReader(f)))
            self.assertEqual([25000, 5], counts)
            with open(output_dir / "clean_chunks" / "clean_part_001.csv", newline="", encoding="utf-8-sig") as f:
                self.assertEqual(
                    ["First Name", "Last Name", "Company Name", "Email"],
                    csv.DictReader(f).fieldnames,
                )

    def test_clean_chunks_roll_before_size_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "size_limit.csv"
            output_dir = tmp_path / "out"
            rows = []
            for idx in range(10):
                rows.append(
                    {
                        "First Name": "Alex",
                        "Last Name": "Morgan",
                        "Full Name": "Alex Morgan",
                        "Email Business": f"alex.morgan@company{idx}.com",
                        "Company Name": "Company " + ("X" * 120),
                    }
                )
            write_csv(input_path, rows)
            max_bytes = 400
            code = run_scrub(
                Namespace(
                    input=str(input_path),
                    email_column="Email Business",
                    output_dir=str(output_dir),
                    rules=str(RULES),
                    chunk_size=25000,
                    max_clean_chunk_bytes=max_bytes,
                    strict=True,
                    output_profile="final",
                    clean_column_profile="upload",
                )
            )
            self.assertEqual(0, code)
            clean_files = sorted((output_dir / "clean_chunks").glob("*.csv"))
            self.assertGreater(len(clean_files), 1)
            for path in clean_files:
                self.assertLessEqual(path.stat().st_size, max_bytes)

    def test_repeated_runs_have_identical_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "repeatable.csv"
            rows = [
                {
                    "First Name": "Alex",
                    "Last Name": "Morgan",
                    "Full Name": "Alex Morgan",
                    "Email Business": "alex.morgan@examplecorp.test",
                    "Company Name": "Example Corp",
                },
                {
                    "First Name": "Privacy",
                    "Last Name": "Team",
                    "Full Name": "Privacy Team",
                    "Email Business": "privacy@examplecorp.test",
                    "Company Name": "Example Corp",
                },
                {
                    "First Name": "Tamsin",
                    "Last Name": "B.",
                    "Full Name": "Tamsin B.",
                    "Email Business": "tam@examplecorp.test",
                    "Company Name": "Example Corp",
                },
            ]
            write_csv(input_path, rows)
            manifests = []
            for index in [1, 2]:
                output_dir = tmp_path / f"out{index}"
                code = run_scrub(
                    Namespace(
                        input=str(input_path),
                        email_column="Email Business",
                        output_dir=str(output_dir),
                        rules=str(RULES),
                        chunk_size=25000,
                        max_clean_chunk_bytes=10 * 1024 * 1024,
                        strict=True,
                        output_profile="final",
                        clean_column_profile="upload",
                    )
                )
                self.assertEqual(0, code)
                manifests.append(json.loads((output_dir / "output_manifest.json").read_text(encoding="utf-8")))

            self.assertEqual(manifests[0], manifests[1])

    def test_full_and_default_upload_profiles_match_the_workflow_output_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "source.csv"
            source_fields = ["First Name", "Last Name", "Full Name", "Email Business", "Company Name", "Website", "Source Marker"]
            rows = [{"First Name": "Alex", "Last Name": "Morgan", "Full Name": "Alex Morgan",
                     "Email Business": email, "Company Name": "Synthetic Forge", "Website": "https://synthetic-forge.example",
                     "Source Marker": marker} for email, marker in (("alex.morgan@synthetic-forge.example", "clean"),
                                                                  ("noreply@synthetic-forge.example", "removed"))]
            with input_path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=source_fields)
                writer.writeheader()
                writer.writerows(rows)
            for profile in ("full", "upload"):
                output_dir = Path(tmp) / profile
                arguments = Namespace(input=str(input_path), email_column="Email Business", output_dir=str(output_dir),
                                      rules=str(RULES), chunk_size=25000, max_clean_chunk_bytes=10 * 1024 * 1024,
                                      strict=True, output_profile="final")
                if profile == "full":
                    arguments.clean_column_profile = "full"
                with self.subTest(profile=profile):
                    self.assertEqual(run_quiet(scrub_leads.scrub, arguments), 0)
                    with (output_dir / "clean_chunks" / "clean_part_001.csv").open(newline="", encoding="utf-8-sig") as stream:
                        reader = csv.DictReader(stream)
                        clean_rows = list(reader)
                        fields = reader.fieldnames
                    self.assertEqual(len(clean_rows), 1)
                    self.assertEqual(clean_rows[0]["Website"], rows[0]["Website"])
                    if profile == "full":
                        self.assertEqual(fields[:len(source_fields)], source_fields)
                        self.assertEqual(clean_rows[0]["Source Marker"], "clean")
                        self.assertEqual(clean_rows[0]["Email Business"], rows[0]["Email Business"])
                        self.assertEqual(clean_rows[0]["normalized_email"], rows[0]["Email Business"])
                        self.assertIn("validator_votes", fields)
                    else:
                        self.assertEqual(fields, ["First Name", "Last Name", "Company Name", "Website", "Email"])
                        self.assertEqual(clean_rows[0]["Email"], rows[0]["Email Business"])
                    with (output_dir / "removed_leads.csv").open(newline="", encoding="utf-8-sig") as stream:
                        removed_rows = list(csv.DictReader(stream))
                    self.assertEqual(removed_rows[0]["Source Marker"], "removed")
                    self.assertEqual(removed_rows[0]["scrub_status"], "REMOVED")
                    self.assertFalse((output_dir / "quarantine_leads.csv").exists())

    def test_final_output_profile_routes_quarantine_to_removed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "ambiguous.csv"
            output_dir = tmp_path / "out"
            write_csv(
                input_path,
                [
                    {
                        "First Name": "Tamsin",
                        "Last Name": "B.",
                        "Full Name": "Tamsin B.",
                        "Email Business": "tam@examplecorp.test",
                        "Company Name": "Example Corp",
                    }
                ],
            )
            code = run_scrub(
                Namespace(
                    input=str(input_path),
                    email_column="Email Business",
                    output_dir=str(output_dir),
                    rules=str(RULES),
                    chunk_size=25000,
                    max_clean_chunk_bytes=10 * 1024 * 1024,
                    strict=True,
                    output_profile="final",
                    clean_column_profile="upload",
                )
            )
            self.assertEqual(0, code)
            self.assertFalse((output_dir / "quarantine_leads.csv").exists())
            with open(output_dir / "removed_leads.csv", newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(1, len(rows))
            self.assertEqual("QUARANTINE", rows[0]["scrub_status"])
            self.assertIn("NO_CLEAR_PERSON_SIGNAL", rows[0]["reason_codes"])

    def test_rightmost_waterfall_email_column_wins_per_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "waterfall.csv"
            output_dir = tmp_path / "out"
            fieldnames = [
                "First Name",
                "Last Name",
                "Full Name",
                "Email Finder 1",
                "Company Website",
                "Email Finder 2",
                "Company Name",
            ]
            with open(input_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(
                    {
                        "First Name": "Jane",
                        "Last Name": "Person",
                        "Full Name": "Jane Person",
                        "Email Finder 1": "info@examplecorp.test",
                        "Company Website": "http://info@examplecorp.test",
                        "Email Finder 2": "jane.person@examplecorp.test",
                        "Company Name": "Example Corp",
                    }
                )
                writer.writerow(
                    {
                        "First Name": "Alex",
                        "Last Name": "Morgan",
                        "Full Name": "Alex Morgan",
                        "Email Finder 1": "alex.morgan@examplecorp.test",
                        "Company Website": "alex@examplecorp.test",
                        "Email Finder 2": "",
                        "Company Name": "Example Corp",
                    }
                )

            code = run_scrub(
                Namespace(
                    input=str(input_path),
                    email_column=None,
                    output_dir=str(output_dir),
                    rules=str(RULES),
                    chunk_size=25000,
                    max_clean_chunk_bytes=10 * 1024 * 1024,
                    strict=True,
                    output_profile="final",
                    clean_column_profile="upload",
                )
            )
            self.assertEqual(0, code)
            report = json.loads((output_dir / "audit_report.json").read_text(encoding="utf-8"))
            self.assertEqual(["Email Finder 1", "Email Finder 2"], report["email_columns"])

            with open(output_dir / "clean_chunks" / "clean_part_001.csv", newline="", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(2, len(rows))
            self.assertEqual("jane.person@examplecorp.test", rows[0]["Email"])
            self.assertEqual("alex.morgan@examplecorp.test", rows[1]["Email"])


if __name__ == "__main__":
    unittest.main()
