"""Run from the repo root: python3 -m unittest discover -s _core/tests"""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
SCRIPTS = ROOT / "workspaces/prospecting/scripts"
sys.path.insert(0, str(SCRIPTS))
import prospect_evidence_gate as gate  # noqa: E402

TODAY = date(2026, 9, 21)
PAGE = ("Acme Corp today announced the appointment of Jane Doe as Chief AI Officer.\n"
        "\u201cWe will deploy generative AI across every research workflow,\u201d Doe said.")


def receipt(**over):
    base = {"account_name": "Acme Corp", "account_aliases": ["Acme", "Jane Doe"], "account_domain": "acme.test",
            "source_url": "https://acme.test/news", "published_date": "2026-09-01",
            "quote": "appointment of Jane Doe as Chief AI Officer", "evidence_subject": "Acme Corp",
            "signal_type": "ai_exec_appointment", "quote_speaker": "account",
            "classification": "active_initiative", "relevance": "employee_use"}
    base.update(over)
    return base


class EvidenceGate(unittest.TestCase):
    def setUp(self):
        self.policy, self.types = gate.load_rules(CORE)

    def run_gate(self, r, page=PAGE, today=TODAY):
        return gate.grade(r, page, self.policy, self.types, today)

    def test_qualified(self):
        code, out = self.run_gate(receipt())
        self.assertEqual(code, 0)
        self.assertEqual(out["bundle"]["tier"], "tier1")
        self.assertEqual(out["bundle"]["date_basis"], "published")

    def test_quote_with_curly_quotes_and_line_break_matches(self):
        r = receipt(quote='"We will deploy generative AI across every research workflow," Doe said.',
                    evidence_subject="Jane Doe")
        self.assertEqual(self.run_gate(r)[0], 0)

    def test_quote_not_in_page(self):
        code, out = self.run_gate(receipt(quote="Acme is buying Example Product Enterprise next week"))
        self.assertEqual((code, out["reason"]), (1, "quote_not_in_page"))

    def test_quote_too_short(self):
        code, out = self.run_gate(receipt(quote="Chief AI Officer"))
        self.assertEqual((code, out["reason"]), (1, "quote_too_short"))

    def test_subject_not_account_owned(self):
        code, out = self.run_gate(receipt(evidence_subject="Globex"))
        self.assertEqual((code, out["reason"]), (1, "evidence_subject_not_account_owned"))

    def test_alias_is_owned(self):
        self.assertEqual(self.run_gate(receipt(evidence_subject="acme"))[0], 0)

    def test_stale_by_signal_type_window(self):
        code, out = self.run_gate(receipt(published_date="2026-05-01"))
        self.assertEqual((code, out["reason"]), (1, "stale"))
        self.assertEqual(out["freshness_days"], 90)

    def test_tier3_never_qualifies(self):
        code, out = self.run_gate(receipt(signal_type="generic_ai_marketing"))
        self.assertEqual((code, out["reason"]), (1, "tier3_never_qualifies"))

    def test_undated_page_without_event_date_fails(self):
        code, out = self.run_gate(receipt(published_date=None))
        self.assertEqual((code, out["reason"]), (1, "undated_page_without_event_date"))

    def test_undated_page_with_event_date_named_in_page(self):
        page = PAGE + "\nThe appointment takes effect Sept. 1, 2026."
        code, out = self.run_gate(receipt(published_date=None, event_date="2026-09-01"), page=page)
        self.assertEqual(code, 0)
        self.assertEqual(out["bundle"]["date_basis"], "page_event")
        self.assertEqual(out["bundle"]["published_date"], "2026-09-01")

    def test_undated_page_event_date_not_in_page_fails(self):
        code, out = self.run_gate(receipt(published_date=None, event_date="2026-09-01"))
        self.assertEqual((code, out["reason"]), (1, "event_date_not_in_page"))

    def test_undated_page_stale_event_fails(self):
        page = PAGE + "\nAnnounced 1 May 2026."
        code, out = self.run_gate(receipt(published_date=None, event_date="2026-05-01"), page=page)
        self.assertEqual((code, out["reason"]), (1, "stale"))

    def test_quote_speaker_required_and_constrained(self):
        code, out = self.run_gate(receipt(quote_speaker="vendor"))
        self.assertEqual((code, out["reason"]), (2, "quote_speaker_not_allowed"))

    def test_third_party_exec_statement_warns(self):
        r = receipt(signal_type="exec_ai_statements", quote_speaker="third_party", evidence_subject="Jane Doe",
                    quote="We will deploy generative AI across every research workflow")
        code, out = self.run_gate(r)
        self.assertEqual(code, 0)
        self.assertEqual(out["bundle"]["warnings"], ["third_party_paraphrase"])

    def test_third_party_other_type_no_warning(self):
        code, out = self.run_gate(receipt(quote_speaker="third_party"))
        self.assertEqual(code, 0)
        self.assertNotIn("warnings", out["bundle"])

    def test_future_date_unusable(self):
        code, out = self.run_gate(receipt(published_date="2026-10-01"))
        self.assertEqual((code, out["reason"]), (2, "published_date_in_future"))

    def test_unknown_signal_type_unusable(self):
        code, out = self.run_gate(receipt(signal_type="vibes"))
        self.assertEqual((code, out["reason"]), (2, "signal_type_not_in_taxonomy"))

    def test_missing_key_unusable(self):
        r = receipt()
        del r["account_aliases"]
        code, out = self.run_gate(r)
        self.assertEqual((code, out["reason"]), (2, "missing_keys"))

    def test_discovery_classification_cannot_qualify_for_employee_outreach(self):
        for classification in ("early_indication", "general_mention"):
            code, out = self.run_gate(receipt(classification=classification))
            self.assertEqual((code, out["reason"]), (1, "discovery_only"))
        for relevance in ("customer_product", "unclear"):
            code, out = self.run_gate(receipt(relevance=relevance))
            self.assertEqual((code, out["reason"]), (1, "discovery_only"))
        for signal_type in ("single_job_post", "discovery_only"):
            code, out = self.run_gate(receipt(signal_type=signal_type))
            self.assertEqual((code, out["reason"]), (1, "tier3_never_qualifies"))

    def test_missing_or_invalid_interpretation_is_unusable(self):
        for field in ("classification", "relevance"):
            missing = receipt(); del missing[field]
            code, out = self.run_gate(missing)
            self.assertEqual((code, out["reason"]), (2, "missing_keys"))
            code, out = self.run_gate(receipt(**{field: "unsupported"}))
            self.assertEqual((code, out["reason"]), (2, "invalid_" + field))


def synthetic_post_id(instant, low=12345):
    """Snowflake-style id: ms since epoch in the top 41 bits, arbitrary low 22 bits. Synthetic, no real post."""
    return (int(instant.timestamp() * 1000) << 22) | low


# 2026-09-10 02:30 UTC is 2026-09-09 19:30 Pacific: the identity.timezone date differs from the UTC date.
EDGE = datetime(2026, 9, 10, 2, 30, tzinfo=ZoneInfo("UTC"))
NOON = datetime(2026, 9, 10, 19, 0, tzinfo=ZoneInfo("UTC"))  # 12:00 Pacific on the 10th
PACIFIC_CHECK = datetime(2026, 9, 21, 9, 0, tzinfo=ZoneInfo("America/Los_Angeles"))


class LinkedInPostDates(unittest.TestCase):
    def setUp(self):
        self.policy, self.types = gate.load_rules(CORE)

    def grade(self, r):
        return gate.grade(r, PAGE, self.policy, self.types, TODAY, checked_at=PACIFIC_CHECK)

    def test_url_forms_decode(self):
        i = synthetic_post_id(NOON)
        for url in (f"https://www.linkedin.com/posts/acme-corp_ai-leadership-activity-{i}-AbCd",
                    f"https://www.linkedin.com/posts/acme-corp_ai-ugcPost-{i}-x_Yz",
                    f"https://www.linkedin.com/feed/update/urn:li:activity:{i}/",
                    f"https://www.linkedin.com/feed/update/urn:li:ugcPost:{i}?commentUrn=x",
                    f"https://linkedin.com/feed/update/urn%3Ali%3Ashare%3A{i}",
                    f"https://www.linkedin.com/embed/feed/update/urn:li:share:{i}"):
            self.assertEqual(gate.linkedin_post_instant(url), NOON.astimezone(timezone.utc), url)

    def test_non_post_urls_do_not_decode(self):
        i = synthetic_post_id(NOON)
        for url in ("https://acme.test/news", f"https://acme.test/posts/x-activity-{i}-AbCd",
                    f"https://notlinkedin.com/feed/update/urn:li:activity:{i}",
                    "https://www.linkedin.com/company/acme/", "https://www.linkedin.com/pulse/acme-ai-plan-jane-doe",
                    "https://www.linkedin.com/feed/update/urn:li:activity:1234567890123456"):  # decodes to 1970
            self.assertIsNone(gate.linkedin_post_instant(url), url)

    def test_null_date_uses_post_id_in_identity_timezone(self):
        url = f"https://www.linkedin.com/feed/update/urn:li:activity:{synthetic_post_id(EDGE)}"
        code, out = self.grade(receipt(source_url=url, published_date=None))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["bundle"]["published_date"], "2026-09-09")
        self.assertEqual(out["bundle"]["date_basis"], "linkedin_post_id")

    def test_post_id_date_drives_staleness(self):
        url = f"https://www.linkedin.com/feed/update/urn:li:activity:{synthetic_post_id(datetime(2026, 5, 1, 19, tzinfo=ZoneInfo('UTC')))}"
        code, out = self.grade(receipt(source_url=url, published_date=None))
        self.assertEqual((code, out["reason"], out["date_basis"]), (1, "stale", "linkedin_post_id"))

    def test_matching_date_passes_across_timezone_edge(self):
        url = f"https://www.linkedin.com/posts/acme_ai-activity-{synthetic_post_id(EDGE)}-AbCd"
        for given in ("2026-09-09", "2026-09-10"):  # Pacific date and UTC date of the same instant
            code, out = self.grade(receipt(source_url=url, published_date=given))
            self.assertEqual(code, 0, out)
            self.assertEqual(out["bundle"]["date_basis"], "published")

    def test_mismatched_date_is_unusable(self):
        url = f"https://www.linkedin.com/posts/acme_ai-activity-{synthetic_post_id(EDGE)}-AbCd"
        for given in ("2026-09-08", "2026-09-11", "2026-08-10"):
            code, out = self.grade(receipt(source_url=url, published_date=given))
            self.assertEqual((code, out["reason"]), (2, "published_date_disagrees_with_post_id"), given)
            self.assertEqual(out["post_id_date"], "2026-09-09")

    def test_future_post_id_is_unusable(self):
        url = f"https://www.linkedin.com/feed/update/urn:li:ugcPost:{synthetic_post_id(datetime(2026, 12, 1, tzinfo=ZoneInfo('UTC')))}"
        code, out = self.grade(receipt(source_url=url, published_date=None))
        self.assertEqual((code, out["reason"]), (2, "published_date_in_future"))

    def test_non_linkedin_null_date_still_needs_event_date(self):
        code, out = self.grade(receipt(published_date=None))
        self.assertEqual((code, out["reason"]), (1, "undated_page_without_event_date"))


class TimezoneAndSource(unittest.TestCase):
    def setUp(self):
        self.policy, self.types = gate.load_rules(CORE)

    def test_utc_today_page_passes_late_pacific_evening(self):
        # 18:00 Pacific on the 21st is 01:00 UTC on the 22nd. A page dated 2026-09-22 is not future.
        checked_at = datetime(2026, 9, 21, 18, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        page = PAGE + " Published 2026-09-22."
        code, out = gate.grade(receipt(published_date="2026-09-22"), page, self.policy, self.types, TODAY, checked_at=checked_at)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["bundle"]["checked_on"], "2026-09-21")

    def test_two_days_ahead_still_future(self):
        checked_at = datetime(2026, 9, 21, 18, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        code, out = gate.grade(receipt(published_date="2026-09-23"), PAGE, self.policy, self.types, TODAY, checked_at=checked_at)
        self.assertEqual((code, out["reason"]), (2, "published_date_in_future"))

    def test_tomorrow_pacific_before_utc_rollover_is_future(self):
        # 10:00 Pacific on the 21st is 17:00 UTC on the 21st. A page dated the 22nd is future in both.
        checked_at = datetime(2026, 9, 21, 10, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        code, out = gate.grade(receipt(published_date="2026-09-22"), PAGE, self.policy, self.types, TODAY, checked_at=checked_at)
        self.assertEqual((code, out["reason"]), (2, "published_date_in_future"))

    def test_taxonomy_keeps_source(self):
        self.assertEqual(self.types["paid_individuals_present"]["source"], "warehouse")
        self.assertIsNone(self.types["ai_exec_appointment"]["source"])

    def test_warehouse_sourced_type_never_qualifies_from_a_page(self):
        code, out = gate.grade(receipt(signal_type="paid_individuals_present"), PAGE, self.policy, self.types, TODAY)
        self.assertEqual((code, out["reason"]), (1, "signal_type_not_web_sourced"))

    def test_non_string_alias_is_unusable_not_traceback(self):
        code, out = gate.grade(receipt(account_aliases=[1]), PAGE, self.policy, self.types, TODAY)
        self.assertEqual((code, out["reason"], out["keys"]), (2, "fields_not_strings", ["account_aliases[0]"]))

    def test_null_quote_is_unusable_not_traceback(self):
        code, out = gate.grade(receipt(quote=None), PAGE, self.policy, self.types, TODAY)
        self.assertEqual((code, out["reason"]), (2, "fields_not_strings"))


def run_cli(r, page=PAGE, *args, raw=None):
    with tempfile.TemporaryDirectory() as d:
        rp, pp = Path(d) / "r.json", Path(d) / "p.txt"
        rp.write_text(raw if raw is not None else json.dumps(r))
        pp.write_text(page)
        p = subprocess.run([sys.executable, str(SCRIPTS / "prospect_evidence_gate.py"), "--receipt", str(rp), "--page", str(pp), *args],
                           capture_output=True, text=True)
    return p


class Cli(unittest.TestCase):
    NOW = "2026-09-22T03:00:00+00:00"   # 20:00 Pacific on the 21st

    def test_now_sets_checked_at_and_pacific_today(self):
        p = run_cli(receipt(published_date="2026-09-22"), PAGE, "--now", self.NOW)
        self.assertEqual(p.returncode, 0, p.stdout)
        b = json.loads(p.stdout)["bundle"]
        self.assertEqual(b["checked_on"], "2026-09-21")
        self.assertEqual(datetime.fromisoformat(b["checked_at"]), datetime.fromisoformat(self.NOW))
        self.assertTrue(b["checked_at"].endswith("-07:00"))

    def test_now_drives_staleness(self):
        p = run_cli(receipt(published_date="2026-06-01"), PAGE, "--now", self.NOW)
        self.assertEqual((p.returncode, json.loads(p.stdout)["reason"]), (1, "stale"))

    def test_cli_linkedin_null_date_bundle(self):
        url = f"https://www.linkedin.com/feed/update/urn:li:activity:{synthetic_post_id(EDGE)}"
        p = run_cli(receipt(source_url=url, published_date=None), PAGE, "--now", self.NOW)
        self.assertEqual(p.returncode, 0, p.stdout)
        b = json.loads(p.stdout)["bundle"]
        self.assertEqual((b["published_date"], b["date_basis"]), ("2026-09-09", "linkedin_post_id"))

    def test_now_without_offset_is_unusable(self):
        for bad in ("2026-09-22T03:00:00", "2026-09-22", "yesterday"):
            p = run_cli(receipt(), PAGE, "--now", bad)
            self.assertEqual(p.returncode, 2, bad)
            self.assertEqual(json.loads(p.stdout)["outcome"], "unusable")

    def test_core_flag_and_default_agree(self):
        p = run_cli(receipt(), PAGE, "--core", str(CORE), "--now", self.NOW)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_bad_inputs_are_json_not_tracebacks(self):
        cases = [dict(raw="{not json"), dict(r=["a", "list"]), dict(r=receipt(quote=None)),
                 dict(r=receipt(account_aliases=[1])), dict(r=receipt(account_aliases="Acme"))]
        for c in cases:
            p = run_cli(c.get("r"), PAGE, raw=c.get("raw"))
            self.assertEqual(p.returncode, 2, p.stdout)
            self.assertEqual(p.stderr, "")
            self.assertEqual(json.loads(p.stdout)["outcome"], "unusable")

    def test_missing_core_dir_is_unusable(self):
        p = run_cli(receipt(), PAGE, "--core", "/nonexistent")
        self.assertEqual(p.returncode, 2)
        out = json.loads(p.stdout)
        self.assertEqual((out["outcome"], out["reason"]), ("unusable", "input_error"))


if __name__ == "__main__":
    unittest.main()
