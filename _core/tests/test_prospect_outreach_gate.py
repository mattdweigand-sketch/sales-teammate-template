import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
SCRIPTS = ROOT / "workspaces" / "prospecting" / "workflows" / "outreach" / "scripts"
sys.path.insert(0, str(ROOT / "workspaces/prospecting/scripts"))
sys.path.insert(0, str(SCRIPTS))
import prospect_common  # noqa: E402
import prospect_outreach_gate as og  # noqa: E402

POLICY = prospect_common.load_policy(CORE)
TT = og.load_talk_track(CORE)
PT = timezone(timedelta(hours=-7))
NOW = datetime(2026, 9, 22, 14, 0, tzinfo=PT)


# Concise buyer-facing excerpts used in otherwise valid packet fixtures.
MESSAGE_LINE = "Example Product combines models from different providers with web research and company context."


PACKET = {
    "account": {"account_exists": True, "account_id": "001A000000AAAAA",
                "owner_id": POLICY["identity"]["sfdc_user_id"], "open_opportunity_ids": [], "account_domain": "acme.test"},
    "bundle": {"account_name": "Acme", "account_domain": "acme.test", "signal_type": "ai_exec_appointment",
               "source_url": "https://acme.test/news/cai", "published_date": "2026-09-10", "date_basis": "published",
               "checked_at": "2026-09-22T13:30:00-07:00", "gate": "evidence_gate",
               "classification": "active_initiative", "relevance": "employee_use",
               "quote": "Acme has appointed Jane Doe as Chief AI Officer to lead enterprise AI."},
    "talk_track": {"angle": "Model flexibility", "persona": "Owns the enterprise AI rollout",
                   "pick_reason": "The new AI lead owns rollout decisions, making model flexibility across teams relevant."},
    "recipient": {"email": "jane.doe@acme.test", "name": "Jane Doe", "source": "existing Salesforce Contact with Email",
                  "title": "Chief AI Officer", "contact_id": "003JANE"},
    "activity": [{"kind": "task", "subtype": "Email", "date": "2026-06-01", "status": "Completed", "subject": "old email"},
                 {"kind": "task", "subtype": "Task", "date": "2026-09-17", "status": "Completed", "subject": "LinkedIn - Connected"}],
    "draft": {"subject": "Chief AI Officer, first quarter",
              "body": "You named Jane Doe Chief AI Officer last week.\n\nThat usually creates a tooling review. "
                      + MESSAGE_LINE + "\n\nWorth a 20 minute call?"},
}


def pk(**changes):
    p = copy.deepcopy(PACKET)
    for k, v in changes.items():
        sect, key = k.split("__")
        p[sect][key] = v
    return p


def angle_packet(angle, signal_type, persona, title):
    return pk(bundle__signal_type=signal_type, talk_track__angle=angle,
              talk_track__persona=persona, recipient__title=title,
              draft__body="You named Jane Doe Chief AI Officer.\n\n" + MESSAGE_LINE + "\n\nWorth a call?")


def core_copy(mutate):
    """Copy the four files the gate reads into a temp dir, apply mutate(dir), return the Path. Caller removes it."""
    d = Path(tempfile.mkdtemp())
    for f in ("policy.yaml", "talk-track.md", "signals.md"):
        source = CORE / "tests/prospecting-fixtures/policy.yaml" if f == "policy.yaml" else og.TALK_TRACK if f == "talk-track.md" else prospect_common.REFERENCES / f
        shutil.copy(source, d / f)
    mutate(d)
    return d


def edit_meta(d, **fields):
    p = d / "talk-track.md"
    doc = prospect_common.markdown_document(p)
    for k, v in fields.items():
        if v is None: doc["meta"].pop(k, None)
        else: doc["meta"][k] = v
    p.write_text("---\n" + yaml.safe_dump(doc["meta"]) + "---\n\n" + doc["body"])


class OutreachGateTests(unittest.TestCase):
    def test_draft_gate_rejects_accounts_outside_named_scope_and_open_deals(self):
        for changes, expected in (({"owner_id": "synthetic-other"}, "owned_elsewhere"),
                                  ({"owner_id": "synthetic-house"}, "owned_elsewhere"),
                                  ({"account_exists": False, "account_id": None, "owner_id": None}, "outside_named_accounts"),
                                  ({"open_opportunity_ids": ["synthetic-opp"]}, "active_deal")):
            with self.subTest(changes=changes):
                packet = pk()
                packet["account"].update(changes)
                self.assertBlocks(packet, f"Account route {expected}")

    def test_draft_gate_rejects_missing_or_incomplete_account_reads(self):
        for receipt in (None, {}, dict(PACKET["account"], owner_id=None), dict(PACKET["account"], open_opportunity_ids=None)):
            with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                packet = pk()
                packet["account"] = receipt
                self.check(packet)
        packet = pk()
        del packet["account"]
        with self.assertRaises(KeyError):
            self.check(packet)

    def test_bundle_cannot_use_an_unrelated_owned_account_receipt(self):
        for current_domain in (None, "", "other.example"):
            self.assertBlocks(pk(account__account_domain=current_domain), "must match the verified current named Account domain")

    def test_load_talk_track_live_file(self):
        talk = og.load_talk_track(CORE)
        self.assertEqual(set(talk), {"meta", "body"})
        self.assertEqual(set(talk["meta"]), {"review_by"})
        self.assertRegex(str(talk["meta"]["review_by"]), r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("## Claim boundaries", talk["body"])

    def test_load_talk_track_missing_dir_raises_oserror(self):
        with self.assertRaises(OSError):
            og.load_talk_track(Path("/nonexistent"))

    def check(self, p, core=CORE, now=NOW):
        return og.check(p, POLICY, core, now)

    def assertBlocks(self, p, fragment, core=CORE, now=NOW):
        r = self.check(p, core, now)
        self.assertTrue(any(fragment in x for x in r), f"{fragment!r} not in {r}")

    def test_clean_packet_allows(self):
        self.assertEqual(self.check(PACKET), [])

    # check 1
    def test_unknown_signal_type_blocks(self):
        self.assertBlocks(pk(bundle__signal_type="generic_ai_marketing"), "bundle signal_type not a tier1 or tier2")

    # check 2
    def test_any_web_date_basis_passes(self):
        for basis in ("published", "page_event", "linkedin_post_id"):
            self.assertEqual(self.check(pk(bundle__date_basis=basis)), [], basis)

    def test_web_bundle_must_be_a_complete_gate_output(self):
        for key, fragment in (("gate", "must be an prospect_evidence_gate output"), ("source_url", "needs its source_url"),
                              ("date_basis", "needs date_basis")):
            p = pk(); del p["bundle"][key]
            self.assertBlocks(p, fragment)
        self.assertBlocks(pk(bundle__gate="hand_written"), "must be an prospect_evidence_gate output")
        self.assertBlocks(pk(bundle__source_url="acme.test/news"), "needs its source_url")
        self.assertBlocks(pk(bundle__date_basis=" "), "needs date_basis")

    def test_published_date_freshness_is_per_signal_type(self):
        self.assertEqual(self.check(pk(bundle__published_date="2026-06-24")), [])  # 90 days, ai_exec_appointment allows 90
        self.assertBlocks(pk(bundle__published_date="2026-06-23"), "91 days old, ai_exec_appointment freshness is 90 days")
        p = angle_packet("Workflow cost", "public_ai_initiative", "Owns the operating budget", "COO")
        p["bundle"]["published_date"] = "2026-07-24"  # 60 days
        self.assertEqual(self.check(p), [])
        p["bundle"]["published_date"] = "2026-07-23"  # 61 days
        self.assertBlocks(p, "61 days old, public_ai_initiative freshness is 60 days")

    # check 3
    def test_checked_at_elapsed_boundary(self):
        ok = (NOW - timedelta(hours=23, minutes=59)).isoformat()
        self.assertEqual(self.check(pk(bundle__checked_at=ok)), [])
        stale = (NOW - timedelta(hours=24, minutes=1)).isoformat()
        self.assertBlocks(pk(bundle__checked_at=stale), "checked_at older than policy")

    def test_checked_at_offset_is_honored(self):
        utc = (NOW - timedelta(hours=23, minutes=30)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        self.assertEqual(self.check(pk(bundle__checked_at=utc)), [])

    def test_missing_date_only_or_naive_checked_at_blocks(self):
        p = pk(); del p["bundle"]["checked_at"]
        self.assertBlocks(p, "needs an ISO timestamp with a timezone offset")
        self.assertBlocks(pk(bundle__checked_at="2026-09-22"), "needs an ISO timestamp with a timezone offset")
        self.assertBlocks(pk(bundle__checked_at="2026-09-22T13:30:00"), "needs an ISO timestamp with a timezone offset")

    def test_future_read_and_publication_block_independently(self):
        self.assertBlocks(pk(bundle__checked_at="2099-01-01T12:00:00-08:00"), "checked_at is in the future")
        self.assertBlocks(pk(bundle__published_date="2099-01-01"), "published_date is in the future")

    def test_publication_date_preserves_utc_rollover_allowance(self):
        late = datetime.fromisoformat("2026-09-22T20:00:00-07:00")
        self.assertEqual(self.check(pk(bundle__published_date="2026-09-23"), now=late), [])
        self.assertBlocks(pk(bundle__published_date="2026-09-24"), "published_date is in the future", now=late)
        self.assertEqual(self.check(pk(bundle__published_date="2026-09-23"), now=late.astimezone(timezone.utc)), [])

    def test_invalid_publication_dates_are_unusable(self):
        for value in ("2026-09-22garbage", "2026-09-22T12:00:00Z", "2026-02-30", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check(pk(bundle__published_date=value))

    # check 4
    def test_missing_pick_reason_blocks(self):
        self.assertBlocks(pk(talk_track__pick_reason=""), "talk_track.pick_reason must be a nonempty")
        self.assertBlocks(pk(talk_track__pick_reason=None), "talk_track.pick_reason must be a nonempty")

    def test_plain_language_judgment_and_unlisted_title_allow(self):
        p = pk(recipient__title="AI Adoption Program Lead", talk_track__persona="Owns delivery of the AI pilot",
               talk_track__angle="A prospect_common platform across teams")
        self.assertEqual(self.check(p), [])

    def test_missing_judgment_or_responsibility_blocks(self):
        for field in ("angle", "persona", "pick_reason"):
            self.assertBlocks(pk(**{f"talk_track__{field}": " "}), f"talk_track.{field}")
        self.assertBlocks(pk(recipient__title=None), "verified responsibility must be stated")

    def test_discovery_bundles_do_not_enter_outreach(self):
        for value in (None, "early_indication", "general_mention"):
            self.assertBlocks(pk(bundle__classification=value), "active_initiative")
        for value in (None, "customer_product", "unclear"):
            self.assertBlocks(pk(bundle__relevance=value), "employee_use")

    # check 5
    def test_review_by_in_the_past_blocks(self):
        d = core_copy(lambda d: edit_meta(d, review_by="2026-09-21"))
        try:
            self.assertBlocks(PACKET, "meta.review_by 2026-09-21 is past", core=d)
            edit_meta(d, review_by="2026-09-22")
            self.assertEqual(self.check(PACKET, core=d), [])  # today is not past
        finally:
            shutil.rmtree(d)

    def test_review_by_uses_policy_clock(self):
        d = core_copy(lambda d: edit_meta(d, review_by="2026-09-22"))
        try:
            self.assertEqual(self.check(PACKET, core=d), [])
            self.assertBlocks(PACKET, "meta.review_by 2026-09-22 is past", core=d, now=NOW + timedelta(days=1))
        finally:
            shutil.rmtree(d)

    def test_missing_review_by_blocks(self):
        d = core_copy(lambda d: edit_meta(d, review_by=None))
        try:
            self.assertBlocks(PACKET, "meta.review_by missing", core=d)
        finally:
            shutil.rmtree(d)

    def test_live_copy_is_in_review(self):
        self.assertTrue(TT["meta"]["review_by"])
        on_review_day = datetime.fromisoformat(str(TT["meta"]["review_by"]) + "T12:00:00-07:00")
        p = pk(bundle__checked_at=(on_review_day - timedelta(hours=1)).isoformat(),
               bundle__published_date=(on_review_day - timedelta(days=1)).date().isoformat())
        self.assertEqual(self.check(p, now=on_review_day), [])

    # check 6
    def test_recipient_domain_mismatch_blocks_and_subdomain_allows(self):
        self.assertIn("recipient domain does not match bundle account_domain", self.check(pk(recipient__email="jane@gmail.com")))
        self.assertEqual(self.check(pk(recipient__email="jane@corp.acme.test")), [])

    def test_unverified_recipient_source_blocks(self):
        self.assertBlocks(pk(recipient__source="guessed from name pattern"), "recipient source not in policy")

    def test_directly_supplied_recipient_preserves_other_boundaries(self):
        p = pk(recipient__source="Operator supplied in this conversation", recipient__contact_id=None)
        self.assertEqual(self.check(p), [])
        p["recipient"]["email"] = "jane@other.example"
        self.assertBlocks(p, "recipient domain does not match")

    def test_salesforce_recipient_requires_contact_id(self):
        for value in (None, "", "  ", False, 12):
            self.assertBlocks(pk(recipient__contact_id=value), "needs a nonempty contact_id")
        p = pk()
        del p["recipient"]["contact_id"]
        self.assertBlocks(p, "needs a nonempty contact_id")

    def test_unusable_identity_fields_block(self):
        for value in (None, "", "  "):
            self.assertBlocks(pk(bundle__account_name=value), "account_name must be a nonempty string")
        for value in (None, "", "https://acme.test", "acme.test/path", "@acme.test", "com"):
            self.assertBlocks(pk(bundle__account_domain=value), "account_domain must be a usable domain")
        for value in (None, "", "acme.test", "jane@@acme.test", "jane doe@acme.test"):
            self.assertBlocks(pk(recipient__email=value), "email must be a usable address")

    # check 7
    def test_suppression_rules(self):
        cases = [({"kind": "task", "subtype": "Email", "date": "2026-09-05", "status": "Completed", "subject": "Email: intro"}, True),
                 ({"kind": "task", "subtype": "Call", "date": "2026-09-05", "status": "Not Started", "subject": "Call"}, False),
                 ({"kind": "task", "subtype": "Call", "date": "2026-09-12", "status": "Completed", "subject": "Call"}, True),
                 ({"kind": "event", "subtype": None, "date": "2026-09-12", "status": None, "subject": "Meeting"}, True),
                 ({"kind": "gmail_sent", "date": "2026-09-15", "status": None, "subject": "Hello"}, True)]
        for a, suppressed in cases:
            p = pk(); p["activity"].append(a)
            self.assertEqual(any(x.startswith("suppressed") for x in self.check(p)), suppressed, a)

    def test_suppression_is_per_contact(self):
        row = {"kind": "task", "subtype": "Email", "date": "2026-09-15", "status": "Completed", "subject": "Email: intro"}
        other = dict(row, who="003OTHERPERSON")
        same_id = dict(row, who="003JANE")
        same_email = dict(row, who="Jane.Doe@acme.test")
        unknown = dict(row, who=None)
        for a, suppressed in ((other, False), (same_id, True), (same_email, True), (unknown, True)):
            p = pk(); p["recipient"]["contact_id"] = "003JANE"; p["activity"].append(a)
            self.assertEqual(any(x.startswith("suppressed") for x in self.check(p)), suppressed, a)
        p = pk(); p["activity"].append(dict(row, kind="gmail_sent", subtype=None, who="someone.else@acme.test"))
        self.assertFalse(any(x.startswith("suppressed") for x in self.check(p)))

    def test_empty_targets_are_unknown_and_suppress(self):
        for who in (None, "", "  "):
            p = pk()
            p["activity"] = [{"kind": "task", "subtype": "Email", "status": "Completed", "date": "2026-09-22", "who": who}]
            self.assertBlocks(p, "suppressed:")

    def test_malformed_activity_never_looks_like_no_activity(self):
        cases = [None, {}, [None], [{"kind": "unknown", "date": "2026-09-22"}],
                 [{"kind": "event", "date": "bad"}], [{"kind": "event", "date": "2026-09-22", "who": []}],
                 [{"kind": "event", "date": "2026-09-22", "who": "unknown"}],
                 [{"kind": "event", "date": "2026-09-22", "who": "jane@acme.test,bob@acme.test"}],
                 [{"kind": "task", "date": "2026-09-22", "status": None, "subtype": "Email"}],
                 [{"kind": "task", "date": "2026-09-22", "status": "Completed", "subtype": None}]]
        for activity in cases:
            p = pk()
            p["activity"] = activity
            with self.subTest(activity=activity), self.assertRaises(ValueError):
                self.check(p)

    def test_blank_drafts_are_unusable(self):
        for field in ("subject", "body"):
            with self.assertRaises(ValueError):
                self.check(pk(**{f"draft__{field}": "  "}))

    def test_wording_and_length_are_not_gated(self):
        p = pk(talk_track__angle="Research infrastructure",
               draft__body="Example Product does not train its own frontier models.\n\nWorth a call?")
        self.assertEqual(self.check(p), [])
        p = pk(draft__subject="An intentionally longer subject that the external style linter may flag",
               draft__body="\n\n".join(["This is editorial wording for human review."] * 5))
        self.assertEqual(self.check(p), [])

    # check 8
    def test_number_from_quote_allows_and_stray_blocks(self):
        p = pk(bundle__quote="Acme hired 40 AI engineers this quarter and named Jane Doe Chief AI Officer.")
        p["draft"]["body"] = "You hired 40 AI engineers.\n\nThat creates a tooling decision. " + MESSAGE_LINE + "\n\nWorth a call?"
        self.assertEqual(self.check(p), [])
        p["draft"]["body"] = "You hired 40 AI engineers.\n\nSome teams see a 30 percent lift. " + MESSAGE_LINE + "\n\nWorth a call?"
        self.assertBlocks(p, "numbers in body not in the bundle quote: 30")

    def test_invite_minutes_exempt_only_as_invitation_in_question(self):
        base = "You named a Chief AI Officer.\n\n" + MESSAGE_LINE + "\n\n"
        self.assertEqual(self.check(pk(draft__body=base + "Worth 20 minutes?")), [])
        self.assertEqual(self.check(pk(draft__body=base + "Would you have 20 minutes to discuss?\n\nSales Operator\nExample Product")), [])
        p = pk(draft__body="You named a Chief AI Officer.\n\nI have 20 minutes free this week. " + MESSAGE_LINE + "\n\nWorth a call?")
        self.assertBlocks(p, "numbers in body not in the bundle quote: 20")
        self.assertBlocks(pk(draft__body=base + "Worth 20 minutes, maybe 30?"), "the bundle quote: 30")

    def test_invite_minutes_do_not_authorize_same_number_elsewhere(self):
        p = pk(draft__body="You named a Chief AI Officer.\n\nThis cuts costs by 20%. " + MESSAGE_LINE + "\n\nWould you have 20 minutes to discuss?")
        self.assertBlocks(p, "numbers in body not in the bundle quote: 20")

    def test_minutes_claim_in_question_still_blocks(self):
        base = "You named a Chief AI Officer.\n\n" + MESSAGE_LINE + "\n\n"
        self.assertBlocks(pk(draft__body=base + "Could this save 20 minutes per report?"), "numbers in body not in the bundle quote: 20")
        self.assertBlocks(pk(draft__body=base + "Could this save you 20 minutes on each call?"), "numbers in body not in the bundle quote: 20")


    def test_allowed_names_pass(self):
        body = ("Hi Jane Doe,\n\nYou named Jane Doe Chief AI Officer at Acme last week.\n\n"
                "Example Product coordinates models and tools across an assignment, so one model never carries every step.\n\n"
                "Worth a 20 minute call?\n\nBest,\nSales Operator / Example Product")
        self.assertEqual(self.check(pk(draft__body=body)), [])

    # clock and CLI
    def test_parse_now_uses_policy_timezone(self):
        t = og.parse_now("2026-09-22", POLICY)
        self.assertEqual((t.hour, t.tzinfo.key), (12, POLICY["identity"]["timezone"]))
        self.assertEqual(og.parse_now(None, POLICY).tzinfo.key, POLICY["identity"]["timezone"])
        self.assertEqual(og.parse_now("2026-09-22T20:00:00Z", POLICY).isoformat(), "2026-09-22T20:00:00+00:00")
        with self.assertRaises(ValueError):
            og.parse_now("2026-09-22T13:30:00", POLICY)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as td:
            def run(packet, now=NOW.isoformat()):
                f = Path(td) / "packet.json"
                f.write_text(json.dumps(packet))
                return subprocess.run([sys.executable, str(SCRIPTS / "prospect_outreach_gate.py"), "--packet", str(f), "--now", now],
                                      capture_output=True, text=True)
            p = run(PACKET)
            self.assertEqual(p.returncode, 0, p.stdout)
            out = json.loads(p.stdout)
            self.assertEqual(out["verdict"], "allow")
            self.assertEqual((out["angle"], out["persona"]), ("Model flexibility", "Owns the enterprise AI rollout"))
            p = run(pk(bundle__published_date="2026-01-01"))
            self.assertEqual(p.returncode, 1)
            self.assertEqual(json.loads(p.stdout)["verdict"], "block")
            p = run({})
            self.assertEqual(p.returncode, 2)
            self.assertEqual(json.loads(p.stdout)["verdict"], "error")
            p = run(PACKET, now="2026-09-22T13:30:00")  # naive clock is unusable input, not a block
            self.assertEqual(p.returncode, 2, p.stdout)
            self.assertIn("timezone offset", json.loads(p.stdout)["reason"])


class WarehouseSourcedSignal(unittest.TestCase):
    """paid_individuals_present arrives as the signal-outreach wrapper around a privacy-checked signal-user-scan bundle."""

    ADOPTION = {
        "account_name": "Acme", "salesforce_account_id": "001A000000AAAAA", "account_domain": "acme.test",
        "data_through_date": "2026-09-21", "mapped_org_count": 1, "org_subscribed": False, "org_paying": False,
        "org_service_types": [], "org_platforms": [], "paid_individuals_exist": True, "adoption": "individuals_only",
    }

    def check(self, p):
        return og.check(p, POLICY, CORE, NOW)

    def user_scan_packet(self, adoption=None, **bundle_extra):
        ab = dict(self.ADOPTION, **(adoption or {}))
        p = pk(talk_track__angle="Team workflows", talk_track__persona="Owns AI adoption",
               talk_track__pick_reason="Verified individual use supports exploring a team workflow without assuming who paid or company sanction.",
               recipient__title="Head of AI",
               draft__subject="Example Product already in use at Acme",
               draft__body="Some of your team already pay for Example Product themselves.\n\n"
                           + MESSAGE_LINE + "\n\n"
                           "Worth a 20 minute call?")
        p["bundle"] = {
            "signal_type": "paid_individuals_present", "published_date": ab["data_through_date"],
            "checked_at": "2026-09-22T13:30:00-07:00", "quote": POLICY["user_scan"]["statements"]["individuals_only"],
            "date_basis": "warehouse", "account_domain": ab["account_domain"], "account_name": ab["account_name"],
            "adoption_bundle": ab,
        }
        p["bundle"].update(bundle_extra)
        return p

    def test_wrapped_user_scan_bundle_allows(self):
        self.assertEqual(self.check(self.user_scan_packet()), [])

    def test_adoption_bundle_must_belong_to_the_current_named_account(self):
        reasons = self.check(self.user_scan_packet(adoption={"salesforce_account_id": "001OtherSynthetic"}))
        self.assertIn("adoption_bundle salesforce_account_id must match the current named Account", reasons)

    def test_web_gate_bundle_blocks(self):
        reasons = self.check(self.user_scan_packet(gate="evidence_gate"))
        self.assertTrue(any("not the web" in x for x in reasons), reasons)

    def test_source_url_bundle_blocks(self):
        reasons = self.check(self.user_scan_packet(source_url="https://acme.test/news"))
        self.assertTrue(any("not the web" in x for x in reasons), reasons)

    def test_missing_adoption_bundle_blocks(self):
        p = self.user_scan_packet()
        del p["bundle"]["adoption_bundle"]
        reasons = self.check(p)
        self.assertTrue(any("needs adoption_bundle" in x for x in reasons), reasons)

    def test_adoption_bundle_privacy_problem_blocks(self):
        reasons = self.check(self.user_scan_packet(adoption={"user_emails": ["a@acme.test"]}))
        self.assertTrue(any("failed prospect_privacy_check" in x and "forbidden key: user_emails" in x for x in reasons), reasons)

    def test_adoption_not_individuals_only_blocks(self):
        reasons = self.check(self.user_scan_packet(adoption={"adoption": "org_adopted", "org_subscribed": True, "org_paying": True}))
        self.assertTrue(any("needs individuals_only" in x for x in reasons), reasons)

    def test_quote_must_equal_policy_statement(self):
        reasons = self.check(self.user_scan_packet(quote="Everyone at Acme uses Example Product."))
        self.assertIn("bundle quote must equal user_scan.statements.individuals_only", reasons)

    def test_exact_adoption_statement_in_body_allows(self):
        p = self.user_scan_packet()
        p["draft"]["body"] = POLICY["user_scan"]["statements"]["individuals_only"] + "\n\n" + p["draft"]["body"].split("\n\n", 1)[1]
        self.assertEqual(self.check(p), [])

    def test_stale_data_through_date_blocks(self):
        reasons = self.check(self.user_scan_packet(adoption={"data_through_date": "2026-09-20"}))
        self.assertTrue(any("2 days old, paid_individuals_present freshness is 1 days" in x for x in reasons), reasons)

    def test_wrapper_cannot_reassign_or_redate_embedded_adoption(self):
        for key, value in (("account_name", "Other Company"), ("account_domain", "other.example"),
                           ("data_through_date", "2020-01-01")):
            p = self.user_scan_packet()
            p["bundle"]["adoption_bundle"][key] = value
            self.assertTrue(any(f"must match adoption_bundle {key}" in x for x in self.check(p)), key)

    def test_warehouse_identity_cannot_be_blank(self):
        for key in ("account_name", "account_domain", "salesforce_account_id", "data_through_date"):
            p = self.user_scan_packet()
            p["bundle"]["adoption_bundle"][key] = ""
            self.assertTrue(any(f"adoption_bundle {key} must be a nonempty string" in x for x in self.check(p)), key)

    def test_web_type_with_evidence_gate_mark_not_blocked_on_source(self):
        reasons = self.check(pk())
        self.assertFalse(any("not the web" in x for x in reasons), reasons)
        self.assertFalse(any("adoption_bundle" in x for x in reasons), reasons)


if __name__ == "__main__":
    unittest.main()
