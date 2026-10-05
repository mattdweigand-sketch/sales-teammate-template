import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "workspaces" / "prospecting" / "workflows" / "event-sequence" / "scripts" / "make_batches.py"


def run(clean_dir, out, *extra):
    subprocess.run([sys.executable, str(SCRIPT), str(clean_dir), "--code", "T", "--output-dir", str(out), *extra],
                   check=True, capture_output=True)
    path = out / "T 1.csv"
    return [r["Email"] for r in csv.DictReader(open(path))] if path.exists() else []


class MakeBatchesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        clean = self.tmp / "clean"
        clean.mkdir()
        with open(clean / "clean_part_001.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["First Name", "Last Name", "Company Name", "Website", "Email"])
            w.writerow(["Ann", "Lee", "Acme", "https://www.acme.test/", "ann@acme.test"])
            w.writerow(["Bo", "Ng", "Acme", "acme.test", "bo@mail.acme.test"])
            w.writerow(["Cy", "Po", "Beta", "beta.test", "cy@other.test"])
            w.writerow(["Di", "", "Beta", "beta.test", "di@beta.test"])
        self.clean = clean

    def test_domain_mismatch_held_and_subdomain_kept(self):
        emails = run(self.clean, self.tmp / "o1")
        self.assertEqual(["ann@acme.test", "bo@mail.acme.test"], emails)
        held = list(csv.DictReader(open(self.tmp / "o1" / "domain_mismatch.csv")))
        self.assertEqual(["cy@other.test"], [r["Email"] for r in held])

    def test_allow_overrides_domain_check(self):
        allow = self.tmp / "allow.txt"
        allow.write_text("cy@other.test\n")
        self.assertIn("cy@other.test", run(self.clean, self.tmp / "o2", "--allow", str(allow)))


if __name__ == "__main__":
    unittest.main()
