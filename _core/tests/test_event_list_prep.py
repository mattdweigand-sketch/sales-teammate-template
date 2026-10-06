"""Synthetic event intake, exclusion mechanics, per-list overrides, and CLI."""
import contextlib
import csv
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workspaces/prospecting/workflows/event-sequence/scripts/event_list_prep.py"
spec = importlib.util.spec_from_file_location("event_list_prep", SCRIPT)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class EventListPrep(unittest.TestCase):
    def setUp(self):
        self.as_of = datetime(2026, 10, 4, 10, tzinfo=timezone.utc)
        self.policy = {"prospecting": {
            "identity": {"sfdc_user_id": "synthetic-operator"},
            "event": {"exclude": ["open_opportunity", "outside_named_accounts", "recent_reply", "unverified_email", "catch_all_email",
                                  "active_sequence", "event_app_invite"],
                      "recent_reply_days": 14,
                      "outreach_owner_scope": {"house_owner_ids": ["synthetic-house"], "include_missing_account": True}}}, "tooling": {"generic_email_domains": ["personal.example"]}}

    def row(self, **changes):
        result = {"first_name": "Aster", "last_name": "Sample", "email": "aster.sample@synthetic.example",
                  "company": "Synthetic Example", "website": "synthetic.example", "contact_id": "synthetic-contact",
                  "account_checked": True, "account_id": "synthetic-account", "account_owner_id": "synthetic-operator",
                  "opportunities_checked": True, "open_opportunity": False, "replies_checked": True,
                  "last_reply_at": None, "email_provider": "apollo", "email_status": "verified", "catchall_domain": False,
                  "email_operation": "apollo_match", "run_start": self.as_of.isoformat(),
                  "apollo_contacts_checked": True, "apollo_contact_id": "", "apollo_contact_email": "",
                  "apollo_crm_linked": False, "apollo_crm_owner_id": "", "active_sequence": False,
                  "event_app_invite_export_supplied": False, "event_app_invite_checked": False, "event_app_invite": None}
        result.update(changes)
        return result

    def no_email_row(self, **changes):
        result = self.row(email="", email_provider="", email_status="", catchall_domain=None,
                          apollo_contacts_checked=None, active_sequence=None,
                          event_app_invite_export_supplied=True, event_app_invite_checked=None, event_app_invite=None,
                          replies_checked=None)
        result.pop("last_reply_at")
        result.update(changes)
        return result

    def prepare(self, rows, **kwargs):
        return prep.prepare(rows, self.policy, self.as_of, **kwargs)

    def test_intake_normalizes_and_deduplicates_without_silently_losing_rows(self):
        result = self.prepare([self.row(email="  ASTER.SAMPLE@SYNTHETIC.EXAMPLE  ", first_name="  Aster  "), self.row()])
        self.assertEqual(result["input_rows"], 2)
        self.assertEqual(result["unique_contacts"], 1)
        self.assertEqual(result["duplicate_rows"], 1)
        self.assertEqual(result["contacts"][0]["source_rows"], [1, 2])
        self.assertEqual(result["contacts"][0]["label"], "enroll")
        self.assertIn("never approval", result["authorization"])

    def test_conflicting_duplicate_evidence_is_needs_input(self):
        result = self.prepare([self.row(), self.row(open_opportunity=True)])
        self.assertEqual(result["contacts"][0]["label"], "needs_input")
        self.assertTrue(result["contacts"][0]["duplicate_conflict"])
        self.assertEqual(result["pipeline_handoff"], ["event-1"])

    def test_same_contact_id_with_different_emails_is_held_in_both_orders(self):
        rows = [self.row(), self.row(email="aster.alt@synthetic.example", open_opportunity=True)]
        for ordered in (rows, list(reversed(rows))):
            with self.subTest(first_email=ordered[0]["email"]):
                result = self.prepare(ordered)
                self.assertEqual(result["unique_contacts"], 1)
                self.assertEqual(result["duplicate_rows"], 1)
                self.assertEqual(result["counts"], {"needs_input": 1})
                self.assertEqual(result["contacts"][0]["source_rows"], [1, 2])
                self.assertTrue(result["contacts"][0]["duplicate_conflict"])
                self.assertEqual(result["pipeline_handoff"], ["event-1"])

    def test_duplicate_bridge_holds_both_conflicting_identities(self):
        rows = [self.row(), self.row(email="boris.reed@synthetic.example", contact_id="synthetic-second"),
                self.row(email="boris.reed@synthetic.example", open_opportunity=True)]
        result = self.prepare(rows)
        self.assertEqual(result["counts"], {"needs_input": 2})
        self.assertEqual(result["duplicate_rows"], 1)
        self.assertEqual(sum(len(contact["source_rows"]) for contact in result["contacts"]), 3)
        self.assertTrue(all(contact["duplicate_conflict"] for contact in result["contacts"]))
        self.assertEqual(set(result["pipeline_handoff"]), {"event-1", "event-2"})

    def test_all_configured_exclusions_have_reasons(self):
        cases = [("open_opportunity", {"open_opportunity": True}),
                 ("outside_named_accounts", {"account_owner_id": "synthetic-other"}),
                 ("recent_reply", {"last_reply_at": self.as_of.isoformat()}),
                 ("unverified_email", {"email_status": "unavailable"}),
                 ("catch_all_email", {"catchall_domain": True})]
        for expected, changes in cases:
            with self.subTest(expected=expected):
                contact = self.prepare([self.row(**changes)])["contacts"][0]
                self.assertEqual(contact["label"], expected)
                self.assertTrue(contact["reason"])

    def test_house_owner_and_completed_no_account_match_are_excluded(self):
        for changes in ({"account_owner_id": "synthetic-house"}, {"account_id": "", "account_owner_id": ""}):
            self.assertEqual(self.prepare([self.row(**changes)])["counts"], {"outside_named_accounts": 1})

    def scoped(self, row, **kwargs):
        return self.prepare([row], outreach_owner_column="Outreach Owner", outreach_owner_value="Operator", **kwargs)

    def test_flagged_house_owned_row_is_in_scope_and_roundtrips_its_marker(self):
        result = self.scoped(self.row(account_owner_id="synthetic-house", **{"Outreach Owner": "Operator"}))
        contact = result["contacts"][0]
        self.assertEqual(contact["scope"], "outreach_owner")
        self.assertEqual(contact["label"], "enroll")
        self.assertEqual(contact["Outreach Owner"], "Operator")
        self.assertEqual(self.scoped(contact)["counts"], {"enroll": 1})
        self.assertEqual(result["outreach_owner_column"], "Outreach Owner")
        self.assertEqual(result["outreach_owner_value"], "Operator")

    def test_flagged_missing_account_requires_completed_lookup_and_policy_permission(self):
        row = self.row(account_id="", account_owner_id="", **{"Outreach Owner": "Operator"})
        self.assertEqual(self.scoped(row)["contacts"][0]["scope"], "outreach_owner")
        self.assertEqual(self.scoped(row)["counts"], {"enroll": 1})
        self.policy["prospecting"]["event"]["outreach_owner_scope"]["include_missing_account"] = False
        self.assertEqual(self.scoped(row)["counts"], {"outside_named_accounts": 1})
        self.policy["prospecting"]["event"]["outreach_owner_scope"]["include_missing_account"] = True
        row["account_checked"] = False
        contact = self.scoped(row)["contacts"][0]
        self.assertEqual(contact["label"], "needs_input")
        self.assertIsNone(contact["scope"])

    def test_outreach_marker_never_admits_other_sellers_inactive_owners_or_unflagged_house_rows(self):
        for owner, marker in (("synthetic-other", "Operator"), ("synthetic-inactive", "Operator"),
                              ("synthetic-house", "Other seller")):
            with self.subTest(owner=owner, marker=marker):
                row = self.row(account_owner_id=owner, **{"Outreach Owner": marker})
                self.assertEqual(self.scoped(row)["counts"], {"outside_named_accounts": 1})
        row = self.row(account_owner_id="synthetic-house", **{"Outreach Owner": "Operator"})
        self.assertEqual(self.prepare([row])["counts"], {"outside_named_accounts": 1})

    def test_flagged_open_opportunity_retains_pipeline_handoff(self):
        result = self.scoped(self.row(account_owner_id="synthetic-house", open_opportunity=True, **{"Outreach Owner": "Operator"}))
        self.assertEqual(result["contacts"][0]["scope"], "outreach_owner")
        self.assertEqual(result["counts"], {"open_opportunity": 1})
        self.assertEqual(result["pipeline_handoff"], ["event-1"])

    def test_house_owner_scope_and_marker_values_come_from_policy_and_per_run_arguments(self):
        self.policy["prospecting"]["event"]["outreach_owner_scope"]["house_owner_ids"] = ["synthetic-custom-house"]
        row = self.row(account_owner_id="synthetic-custom-house", Assigned="Designated owner")
        result = self.prepare([row], outreach_owner_column="Assigned", outreach_owner_value="Designated owner")
        self.assertEqual(result["contacts"][0]["scope"], "outreach_owner")
        row["account_owner_id"] = "synthetic-house"
        self.assertEqual(self.prepare([row], outreach_owner_column="Assigned", outreach_owner_value="Designated owner")["counts"],
                         {"outside_named_accounts": 1})

    def test_missing_ambiguous_columns_and_conflicting_duplicate_markers_are_held(self):
        for marker in (None, ["Operator", "Other seller"], {"owner": "Operator"}):
            row = self.row(account_owner_id="synthetic-house", **{"Outreach Owner": marker})
            contact = self.scoped(row)["contacts"][0]
            self.assertEqual(contact["label"], "needs_input")
            self.assertIn("Outreach-owner column is missing or ambiguous", contact["needs_input"])
        self.assertEqual(self.scoped(self.row(account_owner_id="synthetic-house"))["counts"], {"needs_input": 1})
        rows = [self.row(account_owner_id="synthetic-house", **{"Outreach Owner": marker}) for marker in ("Operator", "Other seller")]
        for ordered in (rows, list(reversed(rows))):
            result = self.prepare(ordered, outreach_owner_column="Outreach Owner", outreach_owner_value="Operator")
            self.assertEqual(result["counts"], {"needs_input": 1})
            self.assertTrue(result["contacts"][0]["duplicate_conflict"])

    def test_account_ambiguity_and_enrichment_gates_are_not_bypassed(self):
        for changes in ({"account_checked": None}, {"account_id": "", "account_owner_id": "synthetic-house"}):
            row = self.row(**changes, **{"Outreach Owner": "Operator"})
            self.assertEqual(self.scoped(row)["counts"], {"needs_input": 1})
        row = self.no_email_row(account_owner_id="synthetic-house", **{"Outreach Owner": "Operator"})
        result = self.scoped(row)
        self.assertEqual(result["counts"], {"needs_input": 1})
        self.assertEqual(result["enrichment_candidates"], ["event-1"])
        self.assertEqual(result["contacts"][0]["scope"], "outreach_owner")

    def test_scope_loss_at_launch_is_outside_and_never_overridable(self):
        row = self.row(account_owner_id="synthetic-house", **{"Outreach Owner": "Operator"})
        self.assertEqual(self.scoped(row)["counts"], {"enroll": 1})
        row["account_owner_id"] = "synthetic-other"
        self.assertEqual(self.scoped(row)["counts"], {"outside_named_accounts": 1})
        with self.assertRaisesRegex(ValueError, "scope cannot be overridden"):
            self.scoped(row, overrides={"event-1": ["outside_named_accounts"]})

    def test_outreach_owner_arguments_are_paired(self):
        with self.assertRaisesRegex(ValueError, "supplied together"):
            self.prepare([self.row()], outreach_owner_column="Outreach Owner")
        with self.assertRaisesRegex(ValueError, "supplied together"):
            self.prepare([self.row()], outreach_owner_value="Operator")

    def test_cli_scope_and_duplicate_csv_headers_fail_closed(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            policy_path, input_path, output_path = root / "policy.yaml", root / "input.csv", root / "result.json"
            policy_path.write_text(yaml.safe_dump(self.policy))
            row = self.row(account_owner_id="synthetic-house", **{"Outreach Owner": "Operator"})
            arguments = [str(input_path), "--policy", str(policy_path), "--as-of", self.as_of.isoformat(),
                         "--outreach-owner-column", "Outreach Owner", "--outreach-owner-value", "Operator", "--output", str(output_path)]
            for duplicate in (False, True):
                fields = list(row) + (["Outreach Owner"] if duplicate else [])
                with input_path.open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerow(row)
                prep.main(arguments)
                result = json.loads(output_path.read_text())
                self.assertEqual(result["counts"], {"needs_input": 1} if duplicate else {"enroll": 1})
                if duplicate:
                    self.assertIn("missing or ambiguous", result["contacts"][0]["reason"])

    def test_disabled_and_legacy_scope_preserve_owned_account_only_behavior(self):
        for scope in ({'house_owner_ids': [], 'include_missing_account': False}, None):
            if scope is None:
                self.policy['prospecting']['event'].pop('outreach_owner_scope', None)
            else:
                self.policy['prospecting']['event']['outreach_owner_scope'] = scope
            for changes in ({'account_owner_id': 'synthetic-house'}, {'account_id': '', 'account_owner_id': ''}):
                self.assertEqual(self.scoped(self.row(**changes, **{'Outreach Owner': 'Operator'}))['counts'],
                                 {'outside_named_accounts': 1})
            self.assertEqual(self.prepare([self.row()])['counts'], {'enroll': 1})

    def test_invalid_scope_policy_types_reject(self):
        for scope in (None, [], {'house_owner_ids': 'synthetic-house'}, {'house_owner_ids': [1]},
                      {'include_missing_account': 'true'}, {'include_missing_account': 1}):
            self.policy['prospecting']['event']['outreach_owner_scope'] = scope
            with self.subTest(scope=scope), self.assertRaisesRegex(ValueError, 'scope policy types'):
                self.scoped(self.row())

    def test_account_scope_cannot_be_overridden_or_omitted_by_old_configuration(self):
        for changes in ({"account_owner_id": "synthetic-other"}, {"account_owner_id": "synthetic-house"},
                        {"account_id": "", "account_owner_id": ""}):
            with self.subTest(changes=changes):
                row = self.row(**changes)
                with self.assertRaisesRegex(ValueError, "scope cannot be overridden"):
                    self.prepare([row], overrides={"event-1": ["outside_named_accounts"]})
                self.policy["prospecting"]["event"]["exclude"] = ["open_opportunity", "recent_reply", "unverified_email", "catch_all_email"]
                self.assertEqual(self.prepare([row], overrides={"event-1": ["open_opportunity"]})["counts"], {"outside_named_accounts": 1})
                self.policy["prospecting"]["event"]["exclude"].insert(1, "outside_named_accounts")

    def test_changed_account_owner_drops_previously_eligible_contact_and_preserves_handoff(self):
        self.assertEqual(self.prepare([self.row()])["counts"], {"enroll": 1})
        result = self.prepare([self.row(account_owner_id="synthetic-other", open_opportunity=True)],
                              overrides={"event-1": ["open_opportunity"]})
        self.assertEqual(result["counts"], {"outside_named_accounts": 1})
        self.assertEqual(result["pipeline_handoff"], ["event-1"])

    def test_missing_guard_evidence_cannot_be_overridden(self):
        for field in ("account_checked", "opportunities_checked", "replies_checked", "open_opportunity"):
            with self.subTest(field=field):
                result = self.prepare([self.row(**{field: None})], overrides={"event-1": ["open_opportunity"]})
                self.assertEqual(result["contacts"][0]["label"], "needs_input")
        row = self.row()
        del row["last_reply_at"]
        self.assertEqual(self.prepare([row])["contacts"][0]["label"], "needs_input")

    def test_recent_reply_boundary_and_offsets_use_instants(self):
        boundary = self.as_of - timedelta(days=14)
        for difference, expected in ((0, "recent_reply"), (-1, "enroll")):
            replied = (boundary + timedelta(seconds=difference)).astimezone(timezone(timedelta(hours=-7)))
            self.assertEqual(self.prepare([self.row(last_reply_at=replied.isoformat())])["contacts"][0]["label"], expected)
        self.policy["prospecting"]["event"]["recent_reply_days"] = 1
        self.assertEqual(self.prepare([self.row(last_reply_at=boundary.isoformat())])["counts"], {"enroll": 1})

    def test_bad_future_and_naive_reply_dates_never_enroll(self):
        for replied in ("bad", "2026-10-03T10:00:00", False, 0, (self.as_of + timedelta(seconds=1)).isoformat()):
            self.assertEqual(self.prepare([self.row(last_reply_at=replied)])["contacts"][0]["label"], "needs_input")

    def test_verified_status_requires_explicit_non_catchall_apollo_evidence(self):
        for provider, status, catchall, expected in (
            ("apollo", "verified", False, "enroll"), ("external", "valid", False, "unverified_email"),
            ("apollo", "valid", False, "unverified_email"), ("external", "verified", False, "unverified_email"),
            ("apollo", "verified", None, "unverified_email"), ("apollo", "error", False, "unverified_email"),
            ("apollo", "verified", True, "catch_all_email")):
            with self.subTest(provider=provider, status=status, catchall=catchall):
                contact = self.prepare([self.row(email_provider=provider, email_status=status, catchall_domain=catchall)])["contacts"][0]
                self.assertEqual(contact["label"], expected)
                self.assertEqual(contact["enrichment_needed"], expected == "unverified_email")

    def test_catchall_override_does_not_clear_failed_provider_verification(self):
        for provider, status in (("apollo", "error"), ("external", "invalid"), ("unknown", "")):
            with self.subTest(provider=provider, status=status):
                row = self.row(email_provider=provider, email_status=status, catchall_domain=True)
                contact = self.prepare([row], overrides={"event-1": ["catch_all_email"]})["contacts"][0]
                self.assertEqual(contact["label"], "unverified_email")
                self.assertEqual({item["label"] for item in contact["exclusions"]}, {"unverified_email", "catch_all_email"})
                self.assertEqual(contact["overrides_applied"], ["catch_all_email"])

    def test_verified_provider_catchall_needs_only_its_named_override(self):
        row = self.row(email_provider="apollo", email_status="verified", catchall_domain=True)
        self.assertEqual(self.prepare([row])["counts"], {"catch_all_email": 1})
        self.assertEqual(self.prepare([row], overrides={"event-1": ["catch_all_email"]})["counts"], {"enroll": 1})

    def test_non_apollo_verification_never_becomes_verified_even_with_catchall_override(self):
        for provider in ("external", "unknown", "", None):
            for status in ("valid", "verified"):
                with self.subTest(provider=provider, status=status):
                    row = self.row(email_provider=provider, email_status=status, catchall_domain=True)
                    contact = self.prepare([row], overrides={"event-1": ["catch_all_email"]})["contacts"][0]
                    self.assertEqual(contact["label"], "unverified_email")
                    self.assertFalse(contact["enrichment_needed"])
                    self.assertEqual(contact["reason"], "No Apollo verified non-catch-all evidence")

    def test_both_verification_exclusions_require_both_named_overrides(self):
        row = self.row(email_provider="apollo", email_status="error", catchall_domain=True)
        self.assertEqual(self.prepare([row], overrides={"event-1": ["unverified_email"]})["counts"], {"catch_all_email": 1})
        self.assertEqual(self.prepare([row], overrides={"event-1": ["unverified_email", "catch_all_email"]})["counts"], {"enroll": 1})

    def test_all_open_opportunity_or_held_contacts_reconcile_without_enrollment(self):
        for changes, label, expected_handoff in (({"open_opportunity": True}, "open_opportunity", ["event-1"]),
                                                ({"account_checked": None}, "needs_input", [])):
            result = self.prepare([self.row(**changes)])
            self.assertEqual(result["input_rows"], 1)
            self.assertEqual(result["counts"], {label: 1})
            self.assertEqual(result["counts"].get("enroll", 0), 0)
            self.assertEqual(result["pipeline_handoff"], expected_handoff)

    def test_override_is_per_list_and_preserves_pipeline_handoff(self):
        row = self.row(open_opportunity=True)
        result = self.prepare([row], overrides={"event-1": ["open_opportunity"]})
        self.assertEqual(result["contacts"][0]["label"], "enroll")
        self.assertEqual(len(result["contacts"][0]["exclusions"]), 1)
        self.assertEqual(result["pipeline_handoff"], ["event-1"])
        self.assertEqual(self.prepare([row])["contacts"][0]["label"], "open_opportunity")

    def test_override_does_not_supply_missing_email_or_unknown_exclusions(self):
        result = self.prepare([self.row(email="")], overrides={"event-1": ["unverified_email"]})
        self.assertEqual(result["contacts"][0]["label"], "needs_input")
        for overrides in ({"event-2": []}, {"event-1": ["invented"]}, {"event-1": "all"}, []):
            with self.assertRaises(ValueError):
                self.prepare([self.row()], overrides=overrides)

    def test_missing_email_rows_are_kept_and_deduped_by_explicit_identity(self):
        rows = [self.no_email_row(), self.no_email_row(), self.no_email_row(contact_id="synthetic-second")]
        result = self.prepare(rows)
        self.assertEqual(result["unique_contacts"], 2)
        self.assertEqual(result["counts"], {"needs_input": 2})
        self.assertTrue(all(contact["enrichment_needed"] for contact in result["contacts"]))

    def test_no_email_can_reach_enrichment_but_never_enrollment_with_unknown_address_checks(self):
        result = self.prepare([self.no_email_row()])
        self.assertEqual(result["enrichment_candidates"], ["event-1"])
        contact = result["contacts"][0]
        self.assertEqual(contact["label"], "needs_input")
        self.assertEqual([reason["label"] for reason in contact["exclusions"]], ["unverified_email"])
        self.assertEqual(contact["needs_input"], ["Apollo existing-contact and active-sequence evidence not completely checked",
                                                 "Supplied event invite export not completely matched",
                                                 "Recent substantive reply evidence not completely checked"])
        self.assertEqual(result["status"], "needs-input")
        self.assertIn("never approval", result["authorization"])

    def test_no_email_non_address_guards_and_existing_apollo_conflicts_still_block_enrichment(self):
        cases = ({"account_checked": None}, {"account_id": ""}, {"account_owner_id": "other"},
                 {"account_owner_id": ""}, {"open_opportunity": True}, {"opportunities_checked": None},
                 {"open_opportunity": None}, {"first_name": ""}, {"last_name": ""},
                 {"apollo_contact_id": "native", "apollo_contact_email": "other@synthetic.example"},
                 {"apollo_crm_linked": True, "apollo_crm_owner_id": "other"},
                 {"event_app_invite_export_supplied": None}, {"active_sequence": True},
                 {"event_app_invite_checked": True, "event_app_invite": True},
                 {"replies_checked": True, "last_reply_at": self.as_of.isoformat()})
        for changes in cases:
            with self.subTest(changes=changes):
                result = self.prepare([self.no_email_row(**changes)])
                self.assertFalse(result["contacts"][0]["enrichment_needed"])
                self.assertEqual(result["enrichment_candidates"], [])

    def test_malformed_email_defers_only_address_checks_like_a_missing_email(self):
        result = self.prepare([self.no_email_row(email="not-a-usable-address")])
        self.assertEqual(result["enrichment_candidates"], ["event-1"])
        self.assertEqual(result["contacts"][0]["label"], "needs_input")
        self.assertEqual(result["contacts"][0]["email"], "not-a-usable-address")

    def test_no_email_duplicate_conflict_blocks_enrichment(self):
        result = self.prepare([self.no_email_row(), self.no_email_row(account_owner_id="other")])
        self.assertEqual(result["duplicate_rows"], 1)
        self.assertTrue(result["contacts"][0]["duplicate_conflict"])
        self.assertEqual(result["enrichment_candidates"], [])

    def test_returned_email_requires_fresh_complete_address_checks_before_normal_label(self):
        for changes in ({"email": "aster.sample@synthetic.example", "email_provider": "apollo", "email_status": "verified",
                         "catchall_domain": False},
                        {"email": "aster.sample@synthetic.example", "email_provider": "apollo", "email_status": "unverified",
                         "catchall_domain": False}):
            with self.subTest(changes=changes):
                result = self.prepare([self.no_email_row(**changes)])
                self.assertEqual(result["contacts"][0]["label"], "needs_input")
                self.assertEqual(result["enrichment_candidates"], [])
        completed = self.no_email_row(email="aster.sample@synthetic.example", email_provider="apollo", email_status="verified",
                                      catchall_domain=False, apollo_contacts_checked=True, active_sequence=False,
                                      event_app_invite_checked=True, event_app_invite=False, replies_checked=True, last_reply_at=None)
        result = self.prepare([completed])
        self.assertEqual(result["contacts"][0]["label"], "enroll")
        self.assertEqual(result["contacts"][0]["needs_input"], [])
        self.assertEqual(result["enrichment_candidates"], [])

    def test_unlimited_list_size_empty_list_and_invalid_input(self):
        result = self.prepare([self.row(email=f"person{index}@synthetic.example", contact_id=f"synthetic-contact-{index}")
                               for index in range(1001)])
        self.assertEqual(result["counts"], {"enroll": 1001})
        self.assertEqual(self.prepare([])["input_rows"], 0)
        for rows in ({}, [None]):
            with self.assertRaises(ValueError):
                self.prepare(rows)
        with self.assertRaises(ValueError):
            prep.prepare([], self.policy, datetime(2026, 10, 4))

    def test_enrichment_candidates_require_only_unverified_exclusion_and_complete_guards(self):
        cases = [{}, {"first_name": ""}, {"account_owner_id": "synthetic-other"}, {"open_opportunity": True},
                 {"last_reply_at": self.as_of.isoformat()}, {"catchall_domain": True}, {"active_sequence": True},
                 {"event_app_invite_export_supplied": True, "event_app_invite_checked": True, "event_app_invite": True},
                 {"apollo_contacts_checked": False}]
        rows = [self.row(email=f"candidate{index}@synthetic.example", contact_id=f"synthetic-{index}",
                         email_status="unavailable", **changes) for index, changes in enumerate(cases)]
        result = self.prepare(rows)
        self.assertEqual(result["enrichment_candidates"], ["event-1"])
        self.assertTrue(result["contacts"][0]["enrichment_needed"])
        self.assertTrue(all(not contact["enrichment_needed"] for contact in result["contacts"][1:]))
        self.assertEqual(result["contacts"][1]["label"], "needs_input")
        self.assertIn("outside_named_accounts", [item["label"] for item in result["contacts"][2]["exclusions"]])

    def test_enrichment_overrides_do_not_remove_other_original_exclusions(self):
        result = self.prepare([self.row(email_status="unavailable", active_sequence=True)],
                              overrides={"event-1": ["active_sequence"]})
        self.assertEqual(result["contacts"][0]["label"], "unverified_email")
        self.assertEqual(result["enrichment_candidates"], [])

    def test_waterfall_inherits_only_same_run_same_domain_match_and_records_source(self):
        for flag, expected in ((False, "enroll"), (True, "catch_all_email")):
            with self.subTest(flag=flag):
                row = self.row(email_operation="apollo_waterfall", catchall_domain=None,
                               apollo_match_email="prior.person@synthetic.example", apollo_match_catchall_domain=flag,
                               apollo_match_run_start=self.as_of.isoformat())
                contact = self.prepare([row])["contacts"][0]
                self.assertEqual(contact["label"], expected)
                self.assertIs(contact["catchall_domain"], flag)
                self.assertEqual(contact["catchall_source"], {"kind": "same_run_apollo_match",
                                 "email": "prior.person@synthetic.example", "domain": "synthetic.example",
                                 "run_start": self.as_of.isoformat()})

    def test_waterfall_recheck_preserves_immutable_run_start_for_catchall_source(self):
        row = self.row(email_operation="apollo_waterfall", catchall_domain=None,
                       apollo_match_email="prior.person@synthetic.example", apollo_match_catchall_domain=False,
                       apollo_match_run_start=self.as_of.isoformat())
        recheck = self.as_of + timedelta(hours=1)
        result = prep.prepare([row], self.policy, recheck)
        self.assertEqual(result["contacts"][0]["label"], "enroll")
        self.assertEqual(result["contacts"][0]["catchall_source"]["run_start"], self.as_of.isoformat())
        self.assertEqual(result["as_of"], recheck.isoformat())

    def test_waterfall_without_a_complete_same_run_same_domain_match_is_held(self):
        changes = [{"apollo_match_email": "prior@other.example"}, {"apollo_match_email": "prior@sub.synthetic.example"},
                   {"apollo_match_run_start": (self.as_of - timedelta(days=1)).isoformat()},
                   {"apollo_match_run_start": "bad"}, {"apollo_match_run_start": "2026-10-04T10:00:00"},
                   {"run_start": None}, {"apollo_match_catchall_domain": None}, {"apollo_match_email": ""}]
        for missing in changes:
            with self.subTest(missing=missing):
                evidence = {"email_operation": "apollo_waterfall", "catchall_domain": None,
                            "apollo_match_email": "prior@synthetic.example", "apollo_match_catchall_domain": False,
                            "apollo_match_run_start": self.as_of.isoformat()}
                evidence.update(missing)
                result = self.prepare([self.row(**evidence)])
                contact = result["contacts"][0]
                self.assertEqual(contact["label"], "needs_input")
                self.assertIsNone(contact["catchall_domain"])
                self.assertIsNone(contact["catchall_source"])
                self.assertEqual(result["enrichment_candidates"], [])
                self.assertIn("same-run same-domain", contact["reason"])

    def test_explicit_waterfall_flag_is_not_replaced_by_match_fallback(self):
        row = self.row(email_operation="apollo_waterfall", catchall_domain=False,
                       apollo_match_email="prior@synthetic.example", apollo_match_catchall_domain=True,
                       apollo_match_run_start=self.as_of.isoformat())
        contact = self.prepare([row])["contacts"][0]
        self.assertEqual(contact["label"], "enroll")
        self.assertEqual(contact["catchall_source"], {"kind": "native_apollo", "operation": "apollo_waterfall"})

    def test_website_hosts_normalize_scheme_www_path_but_not_subdomain_aliases(self):
        for value in ("HTTPS://WWW.SYNTHETIC.EXAMPLE/path", "www.synthetic.example/path", "synthetic.example", "http://synthetic.example/"):
            with self.subTest(value=value):
                self.assertEqual(prep.website_host(value), "synthetic.example")
                self.assertEqual(self.prepare([self.row(website=value)])["contacts"][0]["website_host"], "synthetic.example")
        self.assertEqual(prep.website_host("https://team.synthetic.example/path"), "team.synthetic.example")
        self.assertNotEqual(prep.website_host("team.synthetic.example"), prep.website_host("synthetic.example"))
        self.assertEqual(prep.email_domain("ASTER@SYNTHETIC.EXAMPLE"), "synthetic.example")
        self.assertEqual(prep.email_domain("malformed"), "")

    def test_existing_apollo_identity_holds_different_personal_and_other_owner_contacts(self):
        scenarios = [({"apollo_contact_email": "other@synthetic.example"}, "different email"),
                     ({"email": "aster@personal.example", "apollo_contact_email": "aster@personal.example"}, "personal email"),
                     ({"apollo_crm_linked": True, "apollo_crm_owner_id": "synthetic-other"}, "another owner's CRM record"),
                     ({"apollo_crm_linked": None}, "CRM linkage"),
                     ({"apollo_crm_linked": True, "apollo_crm_owner_id": ""}, "no checked owner")]
        for changes, reason in scenarios:
            with self.subTest(changes=changes):
                row = self.row(apollo_contact_id="synthetic-apollo", apollo_contact_email="aster.sample@synthetic.example")
                row.update(changes)
                result = self.prepare([row])
                self.assertEqual(result["contacts"][0]["label"], "needs_input")
                self.assertIn(reason, result["contacts"][0]["reason"])
                self.assertEqual(result["enrichment_candidates"], [])

    def test_existing_apollo_exact_email_and_owned_crm_link_are_eligible(self):
        row = self.row(apollo_contact_id="synthetic-apollo", apollo_contact_email="ASTER.SAMPLE@SYNTHETIC.EXAMPLE",
                       apollo_crm_linked=True, apollo_crm_owner_id="synthetic-operator")
        self.assertEqual(self.prepare([row])["contacts"][0]["label"], "enroll")

    def test_outreach_owner_house_crm_link_is_eligible_from_policy(self):
        for house_owner in ("synthetic-house", "synthetic-custom-house"):
            with self.subTest(house_owner=house_owner):
                self.policy["prospecting"]["event"]["outreach_owner_scope"]["house_owner_ids"] = [house_owner]
                row = self.row(account_owner_id=house_owner, apollo_contact_id="synthetic-apollo",
                               apollo_contact_email="aster.sample@synthetic.example", apollo_crm_linked=True,
                               apollo_crm_owner_id=house_owner, **{"Outreach Owner": "Operator"})
                contact = self.scoped(row)["contacts"][0]
                self.assertEqual(contact["scope"], "outreach_owner")
                self.assertEqual(contact["label"], "enroll")
                self.assertNotIn("another owner's CRM record", contact["reason"])

    def test_outreach_owner_other_seller_crm_link_is_held(self):
        row = self.row(account_owner_id="synthetic-house", apollo_contact_id="synthetic-apollo",
                       apollo_contact_email="aster.sample@synthetic.example", apollo_crm_linked=True,
                       apollo_crm_owner_id="synthetic-other", **{"Outreach Owner": "Operator"})
        contact = self.scoped(row)["contacts"][0]
        self.assertEqual(contact["scope"], "outreach_owner")
        self.assertEqual(contact["label"], "needs_input")
        self.assertIn("another owner's CRM record", contact["reason"])

    def test_named_account_house_crm_link_is_held_even_with_outreach_marker(self):
        row = self.row(apollo_contact_id="synthetic-apollo", apollo_contact_email="aster.sample@synthetic.example",
                       apollo_crm_linked=True, apollo_crm_owner_id="synthetic-house", **{"Outreach Owner": "Operator"})
        contact = self.scoped(row)["contacts"][0]
        self.assertEqual(contact["scope"], "named_account")
        self.assertEqual(contact["label"], "needs_input")
        self.assertIn("another owner's CRM record", contact["reason"])

    def test_unflagged_house_crm_link_is_unchanged(self):
        for account_owner in ("synthetic-operator", "synthetic-house"):
            with self.subTest(account_owner=account_owner):
                row = self.row(account_owner_id=account_owner, apollo_contact_id="synthetic-apollo",
                               apollo_contact_email="aster.sample@synthetic.example", apollo_crm_linked=True,
                               apollo_crm_owner_id="synthetic-house", **{"Outreach Owner": "Someone else"})
                original = self.prepare([row])
                result = self.scoped(row)
                for field in ("scope", "label", "reason"):
                    self.assertEqual(result["contacts"][0][field], original["contacts"][0][field])
                self.assertIn("another owner's CRM record", result["contacts"][0]["reason"])

    def test_active_sequence_requires_complete_native_evidence_and_explicit_override(self):
        row = self.row(active_sequence=True)
        self.assertEqual(self.prepare([row])["counts"], {"active_sequence": 1})
        self.assertEqual(self.prepare([row], overrides={"event-1": ["active_sequence"]})["counts"], {"enroll": 1})
        for changes in ({"active_sequence": None}, {"apollo_contacts_checked": False}):
            with self.subTest(changes=changes):
                row.update(changes)
                result = self.prepare([row], overrides={"event-1": ["active_sequence"]})
                self.assertEqual(result["contacts"][0]["label"], "needs_input")
                self.assertEqual(result["enrichment_candidates"], [])

    def test_invite_export_is_optional_but_supplied_export_requires_complete_matching(self):
        contact = self.prepare([self.row()])["contacts"][0]
        self.assertEqual(contact["label"], "enroll")
        self.assertEqual(contact["event_app_invite_status"], "none checked, no export supplied")
        row = self.row(event_app_invite_export_supplied=True, event_app_invite_checked=True, event_app_invite=True)
        self.assertEqual(self.prepare([row])["counts"], {"event_app_invite": 1})
        self.assertEqual(self.prepare([row], overrides={"event-1": ["event_app_invite"]})["counts"], {"enroll": 1})
        for changes in ({"event_app_invite_checked": False}, {"event_app_invite": None},
                        {"event_app_invite_export_supplied": None}):
            with self.subTest(changes=changes):
                pending = dict(row, **changes)
                result = self.prepare([pending], overrides={"event-1": ["event_app_invite"]})
                self.assertEqual(result["contacts"][0]["label"], "needs_input")
                self.assertEqual(result["contacts"][0]["event_app_invite_status"], "not checked")

    def test_new_overrides_never_expand_named_account_scope(self):
        row = self.row(account_owner_id="synthetic-other", active_sequence=True,
                       event_app_invite_export_supplied=True, event_app_invite_checked=True, event_app_invite=True)
        result = self.prepare([row], overrides={"event-1": ["active_sequence", "event_app_invite"]})
        self.assertEqual(result["contacts"][0]["label"], "outside_named_accounts")
        self.assertEqual(result["enrichment_candidates"], [])
        with self.assertRaisesRegex(ValueError, "scope cannot be overridden"):
            self.prepare([row], overrides={"event-1": ["outside_named_accounts", "active_sequence", "event_app_invite"]})

    def test_cli_json_and_csv_use_adjacent_repo_policy_and_sandbox_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            input_path = root / "input.json"
            input_path.write_text(json.dumps([{"First Name": "Aster", "Last Name": "Sample", "Email": "ASTER.SAMPLE@SYNTHETIC.EXAMPLE"}]))
            output_path = root / "reviewed.json"
            prep.main([str(input_path), "--as-of", self.as_of.isoformat(), "--output", str(output_path)])
            result = json.loads(output_path.read_text())
            self.assertEqual(result["contacts"][0]["label"], "needs_input")
            self.assertEqual(result["contacts"][0]["email"], "aster.sample@synthetic.example")
            input_path = root / "input.csv"
            row = self.row()
            row.update(account_checked="true", opportunities_checked="true", replies_checked="true", open_opportunity="false", catchall_domain="false")
            with input_path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                prep.main([str(input_path), "--as-of", self.as_of.isoformat()])
            self.assertEqual(json.loads(output.getvalue())["counts"], {"outside_named_accounts": 1})

    def test_reply_recheck_run_start_as_of_holds_new_reply_but_recheck_time_excludes_it(self):
        run_start_time = self.as_of
        recheck_time = run_start_time + timedelta(hours=1)
        reply_time = run_start_time + timedelta(minutes=30)
        row = self.row(last_reply_at=reply_time.isoformat())
        stale = prep.prepare([row], self.policy, run_start_time)["contacts"][0]
        fresh = prep.prepare([row], self.policy, recheck_time)["contacts"][0]
        self.assertEqual(stale["label"], "needs_input")
        self.assertIn("Reply timestamp is in the future", stale["needs_input"])
        self.assertEqual(fresh["label"], "recent_reply")
        self.assertEqual(fresh["needs_input"], [])

    def test_verified_open_opportunity_exits_without_enrichment_or_recheck(self):
        result = self.prepare([self.row(open_opportunity=True)])
        self.assertEqual(result["counts"], {"open_opportunity": 1})
        contact = result["contacts"][0]
        self.assertFalse(contact["enrichment_needed"])
        self.assertEqual(contact["needs_input"], [])
        self.assertEqual(result["pipeline_handoff"], [contact["row_id"]])
        self.assertIn("open Opportunity", contact["reason"])
        self.assertEqual(result["as_of"], self.as_of.isoformat())

    def test_reply_recheck_cli_requires_fresh_as_of_for_new_reply(self):
        recheck_time = self.as_of + timedelta(hours=1)
        reply_time = self.as_of + timedelta(minutes=30)
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            policy_path = root / "synthetic-policy.yaml"
            policy_path.write_text(yaml.safe_dump(self.policy))
            input_path = root / "reviewed.json"
            input_path.write_text(json.dumps([self.row(last_reply_at=reply_time.isoformat())]))
            output_path = root / "recheck.json"
            for as_of, expected in ((self.as_of, "needs_input"), (recheck_time, "recent_reply")):
                prep.main([str(input_path), "--policy", str(policy_path), "--as-of", as_of.isoformat(), "--output", str(output_path)])
                result = json.loads(output_path.read_text())
                self.assertEqual(result["as_of"], as_of.isoformat())
                self.assertEqual(result["contacts"][0]["label"], expected)

    def test_reply_recheck_subset_drops_replies_holds_incomplete_never_adds(self):
        recheck_time = self.as_of + timedelta(hours=1)
        reply_time = self.as_of + timedelta(minutes=30)
        rows = [self.row(last_reply_at=reply_time.isoformat()),
                self.row(email="briar@synthetic.example", contact_id="synthetic-second", replies_checked=False),
                self.row(email="cedar@synthetic.example", contact_id="synthetic-third"),
                self.row(email="dahlia@synthetic.example", contact_id="synthetic-unapproved")]
        approved = {"event-1", "event-2", "event-3"}
        result = prep.prepare(rows, self.policy, recheck_time)
        dropped = {contact["row_id"] for contact in result["contacts"] if contact["row_id"] in approved and contact["label"] == "recent_reply"}
        held = {contact["row_id"] for contact in result["contacts"] if contact["row_id"] in approved and contact["label"] == "needs_input"}
        remaining = {contact["row_id"] for contact in result["contacts"] if contact["row_id"] in approved and contact["label"] == "enroll"}
        self.assertEqual(dropped, {"event-1"})
        self.assertEqual(held, {"event-2"})
        self.assertEqual(remaining, {"event-3"})
        self.assertEqual(dropped | held | remaining, approved)
        self.assertTrue(remaining <= approved)
        self.assertTrue(all(contact["reason"] for contact in result["contacts"] if contact["row_id"] in dropped | held))

    def test_reply_recheck_does_not_inherit_old_recent_reply_override(self):
        old_reply = self.as_of - timedelta(days=1)
        self.assertEqual(self.prepare([self.row(last_reply_at=old_reply.isoformat())],
                                      overrides={"event-1": ["recent_reply"]})["contacts"][0]["label"], "enroll")
        new_reply = self.as_of + timedelta(minutes=30)
        recheck_time = self.as_of + timedelta(hours=1)
        row = self.row(last_reply_at=new_reply.isoformat())
        self.assertEqual(prep.prepare([row], self.policy, recheck_time)["contacts"][0]["label"], "recent_reply")
        row["replies_checked"] = False
        self.assertEqual(prep.prepare([row], self.policy, recheck_time,
                                     overrides={"event-1": ["recent_reply"]})["contacts"][0]["label"], "needs_input")

    def test_migrated_default_rules_cli_scrub_audit_and_batch_synthetic_fixture(self):
        folder = SCRIPT.parent.parent / "01-list-prep/scripts"
        fixture = ROOT / "_core/tests/prospecting-fixtures/event_risky.csv"
        rows = list(csv.DictReader(io.StringIO(fixture.read_text())))
        self.assertTrue(all(not row["Email Business"] or "@" not in row["Email Business"] or
                            row["Email Business"].endswith(".example") for row in rows))
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            prepared = root / "eligible.csv"
            for row in rows:
                row["Email"] = row.pop("Email Business")
            with prepared.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            scrubbed = root / "scrubbed"
            run = subprocess.run([sys.executable, str(folder / "scrub_leads.py"), "scrub", str(prepared),
                                  "--output-dir", str(scrubbed), "--clean-column-profile", "full"],
                                 check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(run.stdout)["status"], "PASS")
            audit = subprocess.run([sys.executable, str(folder / "scrub_leads.py"), "audit-clean-output",
                                    str(scrubbed / "clean_chunks"), "--report", str(root / "audit.json")],
                                   check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(audit.stdout)["status"], "PASS")
            batch = subprocess.run([sys.executable, str(folder / "make_batches.py"), str(scrubbed / "clean_chunks"),
                                    "--code", "SYNTHETIC", "--output-dir", str(root / "batches")],
                                   check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(batch.stdout)["final_rows"], 2)


if __name__ == "__main__":
    unittest.main()
