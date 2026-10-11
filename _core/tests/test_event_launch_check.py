"""Synthetic saved-snapshot comparisons at the Apollo enrollment boundary."""

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workspaces/prospecting/workflows/event-sequence/scripts/launch_check.py"
SPEC = importlib.util.spec_from_file_location("launch_check", SCRIPT)
launch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launch)


class EventLaunchCheck(unittest.TestCase):
    def setUp(self):
        self.bundle = {
            "approved": {
                "recipients": [{"row_id": "row-1", "email": "one@synthetic.example"},
                               {"row_id": "row-2", "email": "two@synthetic.example"}],
                "steps": [{"subject": "Synthetic {{first_name}}", "body": '<p>Synthetic <a href="https://synthetic.example">copy</a></p>',
                           "include_signature": False},
                          {"subject": "Synthetic second step", "body": "Synthetic second body", "include_signature": False}],
                "send_email_from_email_account_id": "mailbox-1", "stop_on_reply": True,
                "emailer_schedule_id": "schedule-1",
                "schedule_settings": {"mode": "interval", "step_waits": [0, 3], "timezone": "America/Los_Angeles"}},
            "recheck": {"contacts": [{"row_id": "row-1", "email": "one@synthetic.example", "label": "enroll", "apollo_contact_id": "contact-1"},
                                     {"row_id": "row-2", "email": "two@synthetic.example", "label": "enroll", "apollo_contact_id": "contact-2"}]},
            "native_contacts": {"contacts": [{"id": "contact-1", "email": "one@synthetic.example"},
                                             {"id": "contact-2", "email": "two@synthetic.example"}]},
            "native_sequence": {
                "emailer_campaign": {"id": "campaign-1", "mark_finished_if_reply": True,
                                     "emailer_schedule_id": "schedule-1", "sequence_by_exact_daytime": False,
                                     "emailer_steps": [{"id": "step-1", "wait_time": 0, "wait_mode": "day"},
                                                       {"id": "step-2", "wait_time": 3, "wait_mode": "day"}]},
                "emailer_steps": [{"id": "step-1", "emailer_campaign_id": "campaign-1", "position": 0,
                                   "type": "email", "wait_time": 0, "wait_mode": "day"},
                                  {"id": "step-2", "emailer_campaign_id": "campaign-1", "position": 1,
                                   "type": "email", "wait_time": 3, "wait_mode": "day"}],
                "emailer_touches": [{"id": "touch-1", "emailer_step_id": "step-1", "emailer_template_id": "template-1",
                                     "type": "email", "include_signature": False},
                                    {"id": "touch-2", "emailer_step_id": "step-2", "emailer_template_id": "template-2",
                                     "type": "email", "include_signature": False}],
                "emailer_templates": [], "sharing_accesses": [], "attachments": [], "team": {},
                "sequence_url": "https://synthetic.example/sequence"},
            "payload": {"id": "campaign-1", "emailer_campaign_id": "campaign-1",
                        "contact_ids": ["contact-1", "contact-2"], "send_email_from_email_account_id": "mailbox-1"}}
        self.bundle["native_sequence"]["emailer_templates"] = [
            {"id": f"template-{position + 1}", "subject": step["subject"], "body_html": step["body"]}
            for position, step in enumerate(self.bundle["approved"]["steps"])]

    def native_template(self):
        return self.bundle["native_sequence"]["emailer_templates"][0]

    def assert_stopped(self, missing=None):
        result = launch.check(self.bundle)
        self.assertEqual(result["status"], "STOP", result)
        self.assertIsNone(result["payload"])
        if missing:
            self.assertIn(missing, result["missing"])
        return result

    def assert_failed(self, field):
        result = launch.check(self.bundle)
        self.assertEqual(result["status"], "FAIL")
        self.assertIsNone(result["payload"])
        self.assertTrue(any(item["field"] == field for item in result["mismatches"]), result)
        return result

    def test_matching_snapshot_passes_and_returns_unchanged_payload(self):
        before = copy.deepcopy(self.bundle)
        result = launch.check(self.bundle)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["mismatches"], [])
        self.assertEqual(result["copy_matches"], [])
        self.assertEqual(result["payload"], self.bundle["payload"])
        self.assertIsNot(result["payload"], self.bundle["payload"])
        self.assertEqual(self.bundle, before)

    def test_added_missing_substituted_contact_ids_fail(self):
        for contact_ids in (["contact-1", "contact-2", "extra"], ["contact-1"], ["contact-1", "substitute"]):
            with self.subTest(contact_ids=contact_ids):
                self.bundle["payload"]["contact_ids"] = contact_ids
                self.assert_failed("payload.contact_ids")

    def test_duplicate_planned_contact_id_fails(self):
        self.bundle["payload"]["contact_ids"].append("contact-1")
        self.assert_failed("payload.contact_ids.duplicates")

    def test_order_does_not_change_recipient_set(self):
        self.bundle["payload"]["contact_ids"].reverse()
        self.assertEqual(launch.check(self.bundle)["status"], "PASS")

    def test_matching_signature_flags_pass_for_each_ordered_step(self):
        for flags in ((False, False), (True, True), (True, False), (False, True)):
            with self.subTest(flags=flags):
                for position, flag in enumerate(flags):
                    self.bundle["approved"]["steps"][position]["include_signature"] = flag
                    self.bundle["native_sequence"]["emailer_touches"][position]["include_signature"] = flag
                result = launch.check(self.bundle)
                self.assertEqual(result["status"], "PASS")
                self.assertEqual(result["payload"], self.bundle["payload"])
                self.assertFalse(any("include_signature" in field for field in result["not_checked"]))
        self.bundle["native_sequence"]["emailer_steps"].reverse()
        self.assertEqual(launch.check(self.bundle)["status"], "PASS")

    def test_signature_true_false_mismatch_fails_with_exact_values(self):
        for approved, actual in ((False, True), (True, False)):
            with self.subTest(approved=approved):
                self.bundle["approved"]["steps"][0]["include_signature"] = approved
                self.bundle["native_sequence"]["emailer_touches"][0]["include_signature"] = actual
                result = self.assert_failed("native_sequence.emailer_touches.0.include_signature")
                self.assertIn({"field": "native_sequence.emailer_touches.0.include_signature",
                               "expected": approved, "actual": actual}, result["mismatches"])

    def test_missing_approved_signature_value_raises(self):
        original = copy.deepcopy(self.bundle)
        for position in (0, 1):
            with self.subTest(position=position):
                self.bundle = copy.deepcopy(original)
                self.bundle["approved"]["steps"][position].pop("include_signature")
                with self.assertRaisesRegex(ValueError, "include_signature must be a bool"):
                    launch.check(self.bundle)

    def test_nonboolean_approved_signature_values_raise(self):
        for value in (None, 0, 1, "true", "false"):
            with self.subTest(value=value):
                self.bundle["approved"]["steps"][0]["include_signature"] = value
                with self.assertRaisesRegex(ValueError, "include_signature must be a bool"):
                    launch.check(self.bundle)

    def test_every_native_touch_signature_is_checked_even_with_shared_template(self):
        self.bundle["native_sequence"]["emailer_touches"].append(
            {"id": "extra-touch", "emailer_step_id": "step-1", "emailer_template_id": "template-1",
             "type": "email", "include_signature": True})
        self.assert_failed("native_sequence.emailer_touches.2.include_signature")

    def test_nonboolean_native_signature_values_fail_without_boolean_coercion(self):
        for value in (0, 1, "false", "true"):
            with self.subTest(value=value):
                self.bundle["native_sequence"]["emailer_touches"][0]["include_signature"] = value
                self.assert_failed("native_sequence.emailer_touches.0.include_signature")

    def test_dropped_or_held_contact_in_payload_fails(self):
        for label in ("recent_reply", "needs_input"):
            with self.subTest(label=label):
                self.bundle["recheck"]["contacts"][1]["label"] = label
                self.assert_failed("payload.contact_ids")

    def test_narrowed_set_passes_without_additions(self):
        self.bundle["recheck"]["contacts"][1]["label"] = "recent_reply"
        self.bundle["payload"]["contact_ids"] = ["contact-1"]
        self.assertEqual(launch.check(self.bundle)["status"], "PASS")

    def test_eligible_but_unapproved_contact_cannot_be_added(self):
        self.bundle["recheck"]["contacts"].append({"row_id": "row-3", "email": "three@synthetic.example", "label": "enroll"})
        self.bundle["native_contacts"]["contacts"].append({"id": "contact-3", "email": "three@synthetic.example"})
        self.bundle["payload"]["contact_ids"].append("contact-3")
        self.assert_failed("payload.contact_ids")

    def test_missing_recheck_is_not_a_silent_drop(self):
        self.bundle["recheck"]["contacts"].pop()
        self.assert_failed("recheck.row-2")

    def test_scope_loss_requires_revision(self):
        self.bundle["recheck"]["contacts"][1]["label"] = "outside_named_accounts"
        self.assert_failed("recheck.row-2.label")

    def test_empty_remaining_set_fails_before_enrollment(self):
        for contact in self.bundle["recheck"]["contacts"]:
            contact["label"] = "recent_reply"
        self.bundle["payload"]["contact_ids"] = []
        self.assert_failed("recipients")

    def test_changed_recheck_email_fails(self):
        self.bundle["recheck"]["contacts"][0]["email"] = "different@synthetic.example"
        self.assert_failed("recheck.row-1.email")

    def test_native_email_substitution_fails(self):
        self.bundle["native_contacts"]["contacts"][0]["email"] = "different@synthetic.example"
        self.assert_failed("contacts.row-1")

    def test_known_native_id_substitution_fails(self):
        self.bundle["native_contacts"]["contacts"][0]["id"] = "substitute"
        self.bundle["payload"]["contact_ids"][0] = "substitute"
        self.assert_failed("contacts.row-1.id")

    def test_new_contact_is_reconciled_by_exact_approved_email(self):
        for contact in self.bundle["recheck"]["contacts"]:
            contact["apollo_contact_id"] = ""
        self.assertEqual(launch.check(self.bundle)["status"], "PASS")

    def test_ambiguous_native_email_fails(self):
        self.bundle["native_contacts"]["contacts"].append({"id": "ambiguous", "email": "one@synthetic.example"})
        self.assert_failed("contacts.row-1")

    def test_subject_and_body_mismatch_fail(self):
        template = self.native_template()
        for field in ("subject", "body_html"):
            with self.subTest(field=field):
                original = template[field]
                template[field] = "changed"
                self.assert_failed(f"native_sequence.emailer_templates.0.{field}")
                template[field] = original

    def test_html_links_and_merge_variables_are_not_normalized_away(self):
        template = self.native_template()
        template["body_html"] = template["body_html"].replace("https://synthetic.example", "https://different.example")
        self.assert_failed("native_sequence.emailer_templates.0.body_html")
        template["subject"] = "Synthetic {{last_name}}"
        self.assert_failed("native_sequence.emailer_templates.0.subject")

    def test_html_wrapped_copy_matches_plain_approved_copy_with_note(self):
        self.bundle["approved"]["steps"][0]["body"] = "Synthetic & {{first_name}} copy"
        template = self.native_template()
        template["body_html"] = "<div><p>Synthetic &amp; <strong>{{first_name}}</strong> copy</p></div>"
        result = launch.check(self.bundle)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["copy_matches"], [{"field": "native_sequence.emailer_templates.0.body_html",
                                                  "note": "matched after HTML normalization"}])

    def test_html_wrapped_subject_is_normalized_too(self):
        template = self.native_template()
        template["subject"] = "<span>Synthetic {{first_name}}</span>"
        result = launch.check(self.bundle)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["copy_matches"][0]["field"], "native_sequence.emailer_templates.0.subject")

    def test_changed_word_in_html_copy_fails_with_exact_mismatch(self):
        self.bundle["approved"]["steps"][0]["body"] = "Synthetic copy"
        template = self.native_template()
        template["body_html"] = "<p>Different copy</p>"
        result = self.assert_failed("native_sequence.emailer_templates.0.body_html")
        mismatch = next(item for item in result["mismatches"] if item["field"].endswith(".body_html"))
        self.assertEqual(mismatch["expected"], "Synthetic copy")
        self.assertEqual(mismatch["actual"], "<p>Different copy</p>")

    def test_dropped_or_changed_hidden_variable_fails_even_when_text_matches(self):
        approved = '<span data-token="{{first_name}}">Synthetic copy</span>'
        self.bundle["approved"]["steps"][0]["body"] = approved
        template = self.native_template()
        for actual in ("<p>Synthetic copy</p>", '<p data-token="{{last_name}}">Synthetic copy</p>'):
            with self.subTest(actual=actual):
                template["body_html"] = actual
                self.assertEqual(launch.normalize_copy(approved), launch.normalize_copy(actual))
                self.assert_failed("native_sequence.emailer_templates.0.body_html")

    def test_changed_hidden_url_fails_even_when_text_matches(self):
        approved = '<a href="https://synthetic.example">Synthetic copy</a>'
        self.bundle["approved"]["steps"][0]["body"] = approved
        template = self.native_template()
        template["body_html"] = '<p><a href="https://different.example">Synthetic copy</a></p>'
        self.assertEqual(launch.normalize_copy(approved), launch.normalize_copy(template["body_html"]))
        self.assert_failed("native_sequence.emailer_templates.0.body_html")

    def test_variable_count_and_order_must_match(self):
        self.bundle["approved"]["steps"][0]["body"] = '<span data-token="{{first_name}}{{last_name}}">Synthetic copy</span>'
        template = self.native_template()
        for tokens in ("{{last_name}}{{first_name}}", "{{first_name}}{{last_name}}{{last_name}}"):
            with self.subTest(tokens=tokens):
                template["body_html"] = f'<p data-token="{tokens}">Synthetic copy</p>'
                self.assert_failed("native_sequence.emailer_templates.0.body_html")

    def test_url_count_and_order_must_match(self):
        self.bundle["approved"]["steps"][0]["body"] = '<a href="https://one.example">One</a><a href="https://two.example">Two</a>'
        template = self.native_template()
        for actual in ('<a href="https://two.example">One</a><a href="https://one.example">Two</a>',
                       '<a href="https://one.example">One</a><a href="https://two.example">Two</a><img src="https://two.example">'):
            with self.subTest(actual=actual):
                template["body_html"] = actual
                self.assert_failed("native_sequence.emailer_templates.0.body_html")

    def test_normalization_handles_breaks_blocks_entities_whitespace_and_line_endings(self):
        cases = (("  Synthetic\r\n  copy  ", "Synthetic\ncopy"),
                 ("<p>Synthetic</p><div>copy</div><li>last</li>", "Synthetic\ncopy\nlast"),
                 ("Synthetic&lt;br&gt;copy<br/>last", "Synthetic\ncopy\nlast"),
                 ("Synthetic &amp; copy&nbsp; text", "Synthetic & copy text"),
                 ("Synthetic  \t copy\n\n\n\nlast", "Synthetic copy\n\nlast"))
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(launch.normalize_copy(source), expected)

    def test_entity_encoded_url_still_matches_exact_url(self):
        self.bundle["approved"]["steps"][0]["body"] = '<a href="https://synthetic.example/?one=1&two=2">Synthetic copy</a>'
        template = self.native_template()
        template["body_html"] = '<p><a href="https://synthetic.example/?one=1&amp;two=2">Synthetic copy</a></p>'
        self.assertEqual(launch.check(self.bundle)["status"], "PASS")

    def test_normalization_does_not_decode_entities_twice(self):
        self.bundle["approved"]["steps"][0]["body"] = "Synthetic & copy"
        template = self.native_template()
        template["body_html"] = "<p>Synthetic &amp;amp; copy</p>"
        self.assertEqual(launch.normalize_copy(template["body_html"]), "Synthetic &amp; copy")
        self.assert_failed("native_sequence.emailer_templates.0.body_html")

    def test_every_returned_template_is_compared(self):
        native = self.bundle["native_sequence"]
        native["emailer_templates"].append({"id": "variant-1", "subject": "changed", "body_html": "changed"})
        native["emailer_touches"].append({"id": "variant-touch", "emailer_step_id": "step-1",
                                         "emailer_template_id": "variant-1", "type": "email", "include_signature": False})
        self.assert_failed("native_sequence.emailer_templates.2.subject")

    def test_missing_templates_fail_and_report_not_checked(self):
        self.bundle["native_sequence"]["emailer_templates"] = []
        result = self.assert_stopped()
        self.assertTrue(any(item["reason"] == "Dangling template ID" for item in result["structure_errors"]))

    def test_missing_step_or_extra_step_fails(self):
        original = copy.deepcopy(self.bundle)
        for count in (1, 3):
            with self.subTest(count=count):
                self.bundle = copy.deepcopy(original)
                native = self.bundle["native_sequence"]
                if count == 1:
                    native["emailer_steps"].pop()
                    native["emailer_touches"].pop()
                    native["emailer_campaign"]["emailer_steps"].pop()
                else:
                    native["emailer_steps"].append({"id": "step-3", "emailer_campaign_id": "campaign-1", "position": 2,
                                                    "type": "email", "wait_time": 3, "wait_mode": "day"})
                    native["emailer_campaign"]["emailer_steps"].append({"id": "step-3", "wait_time": 3, "wait_mode": "day"})
                self.assert_failed("native_sequence.emailer_steps.count")

    def test_different_planned_mailbox_fails(self):
        self.bundle["payload"]["send_email_from_email_account_id"] = "other-mailbox"
        self.assert_failed("payload.send_email_from_email_account_id")

    def test_stop_on_reply_false_or_wrong_type_fails(self):
        for value in (False, 1, "true"):
            with self.subTest(value=value):
                self.bundle["native_sequence"]["emailer_campaign"]["mark_finished_if_reply"] = value
                self.assert_failed("native_sequence.emailer_campaign.mark_finished_if_reply")

    def test_mismatched_schedule_id_fails(self):
        self.bundle["native_sequence"]["emailer_campaign"]["emailer_schedule_id"] = "different-schedule"
        self.assert_failed("native_sequence.emailer_campaign.emailer_schedule_id")

    def test_missing_campaign_settings_stop_and_are_not_not_checked(self):
        fields = ("mark_finished_if_reply", "emailer_schedule_id", "sequence_by_exact_daytime")
        for field in fields:
            self.bundle["native_sequence"]["emailer_campaign"].pop(field)
        result = self.assert_stopped()
        self.assertEqual(set(result["missing"]), {f"native_sequence.emailer_campaign.{field}" for field in fields})
        self.assertFalse(result["not_checked"])

    def test_only_settings_outside_connector_schema_remain_not_checked(self):
        result = launch.check(self.bundle)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["not_checked"], ["schedule_settings.timezone"])

    def test_documented_interval_mode_and_waits_mismatches_fail(self):
        native = self.bundle["native_sequence"]
        native["emailer_campaign"]["sequence_by_exact_daytime"] = True
        native["emailer_steps"][0]["wait_time"] = 10
        native["emailer_steps"][0]["wait_mode"] = "hour"
        self.assert_failed("native_sequence.emailer_campaign.sequence_by_exact_daytime")
        self.assert_failed("native_sequence.emailer_steps.0.wait_time")
        self.assert_failed("native_sequence.emailer_steps.0.wait_mode")

    def test_confirmed_saved_wrapper_passes_without_reshaping(self):
        self.bundle["native_sequence"] = {"tool": "apollo_sequences_create", "result": self.bundle["native_sequence"],
                                          "connector": "synthetic", "structure": "synthetic-sideloaded"}
        self.assertEqual(launch.check(self.bundle)["status"], "PASS")

    def test_server_html_document_wrapper_matches_plain_copy_with_note(self):
        self.bundle["approved"]["steps"][0]["body"] = "Synthetic {{first_name}} copy"
        self.native_template()["body_html"] = (
            "&lt;html&gt;&lt;head&gt;&lt;/head&gt;&lt;body&gt;"
            "&lt;p&gt;Synthetic {{first_name}} copy&lt;/p&gt;&lt;/body&gt;&lt;/html&gt;")
        result = launch.check(self.bundle)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["copy_matches"], [{"field": "native_sequence.emailer_templates.0.body_html",
                                                  "note": "matched after HTML normalization"}])

    def test_steps_are_ordered_by_position_not_array_order(self):
        self.bundle["native_sequence"]["emailer_steps"].reverse()
        self.assertEqual(launch.check(self.bundle)["status"], "PASS")

    def test_each_documented_native_field_missing_stops(self):
        original = copy.deepcopy(self.bundle)
        paths = [(field,) for field in ("emailer_campaign", "emailer_steps", "emailer_touches", "emailer_templates",
                                       "sharing_accesses", "attachments", "team", "sequence_url")]
        paths += [("emailer_campaign", field) for field in ("id", "mark_finished_if_reply", "emailer_schedule_id", "sequence_by_exact_daytime")]
        paths += [("emailer_steps", 0, field) for field in ("id", "emailer_campaign_id", "position", "type", "wait_time", "wait_mode")]
        paths += [("emailer_touches", 0, field) for field in ("id", "emailer_step_id", "emailer_template_id", "type", "include_signature")]
        paths += [("emailer_templates", 0, field) for field in ("id", "subject", "body_html")]
        paths += [("emailer_campaign", "emailer_steps", 0, field) for field in ("id", "wait_time", "wait_mode")]
        for path in paths:
            with self.subTest(path=path):
                self.bundle = copy.deepcopy(original)
                parent = self.bundle["native_sequence"]
                for key in path[:-1]:
                    parent = parent[key]
                parent.pop(path[-1])
                self.assert_stopped("native_sequence." + ".".join(str(key) for key in path))

    def test_unrecognized_or_nested_structure_stops(self):
        original = self.bundle["native_sequence"]
        for native in ({"steps": []}, {"data": original}, {"emailer_campaign": original["emailer_campaign"]},
                       {"result": original}, [], None):
            with self.subTest(native=native):
                self.bundle["native_sequence"] = native
                self.assert_stopped()

    def test_duplicate_sideloaded_ids_stop(self):
        original = copy.deepcopy(self.bundle)
        for field in ("emailer_steps", "emailer_touches", "emailer_templates"):
            with self.subTest(field=field):
                self.bundle = copy.deepcopy(original)
                self.bundle["native_sequence"][field].append(copy.deepcopy(self.bundle["native_sequence"][field][0]))
                self.assert_stopped()

    def test_dangling_step_template_and_campaign_links_stop(self):
        original = copy.deepcopy(self.bundle)
        for array, field in (("emailer_steps", "emailer_campaign_id"), ("emailer_touches", "emailer_step_id"),
                             ("emailer_touches", "emailer_template_id")):
            with self.subTest(field=field):
                self.bundle = copy.deepcopy(original)
                self.bundle["native_sequence"][array][0][field] = "unknown-id"
                self.assert_stopped()

    def test_step_without_a_touch_stops(self):
        self.bundle["native_sequence"]["emailer_touches"].pop(0)
        self.assert_stopped()

    def test_duplicate_or_noninteger_positions_stop(self):
        for position in (0, "1", True):
            with self.subTest(position=position):
                self.bundle["native_sequence"]["emailer_steps"][1]["position"] = position
                self.assert_stopped()

    def test_embedded_and_sideloaded_step_disagreement_fails(self):
        original = copy.deepcopy(self.bundle)
        for field, value in (("id", "other-step"), ("wait_time", 4), ("wait_mode", "hour")):
            with self.subTest(field=field):
                self.bundle = copy.deepcopy(original)
                self.bundle["native_sequence"]["emailer_campaign"]["emailer_steps"][0][field] = value
                result = launch.check(self.bundle)
                self.assertEqual(result["status"], "FAIL", result)
                self.assertIsNone(result["payload"])
                self.assertTrue(result["mismatches"])

    def test_embedded_step_list_is_optional(self):
        self.bundle["native_sequence"]["emailer_campaign"].pop("emailer_steps")
        self.assertEqual(launch.check(self.bundle)["status"], "PASS")

    def test_opaque_metadata_values_are_not_guessed(self):
        for field in ("sharing_accesses", "attachments", "team", "sequence_url"):
            self.bundle["native_sequence"][field] = None
        self.assertEqual(launch.check(self.bundle)["status"], "PASS")

    def test_payload_without_campaign_identifiers_fails(self):
        """The previous fixture carried only contact_ids and the mailbox. Both campaign identifiers are now bound."""
        original = copy.deepcopy(self.bundle)
        for field in ("id", "emailer_campaign_id"):
            with self.subTest(field=field):
                self.bundle = copy.deepcopy(original)
                self.bundle["payload"].pop(field)
                self.assert_failed(f"payload.{field}")
        self.bundle = copy.deepcopy(original)
        self.bundle["payload"].pop("id")
        self.bundle["payload"].pop("emailer_campaign_id")
        result = self.assert_failed("payload.id")
        self.assertTrue(any(item["field"] == "payload.emailer_campaign_id" for item in result["mismatches"]))

    def test_foreign_campaign_id_in_payload_fails(self):
        self.bundle["payload"]["id"] = "campaign-other"
        result = self.assert_failed("payload.id")
        self.assertIn({"field": "payload.id", "expected": "campaign-1", "actual": "campaign-other"}, result["mismatches"])

    def test_foreign_campaign_alias_in_payload_fails(self):
        self.bundle["payload"]["emailer_campaign_id"] = "campaign-other"
        result = self.assert_failed("payload.emailer_campaign_id")
        self.assertIn({"field": "payload.emailer_campaign_id", "expected": "campaign-1", "actual": "campaign-other"},
                      result["mismatches"])

    def test_unknown_payload_keys_fail_against_the_operation_list(self):
        self.bundle["payload"]["sequence_active_in_other_campaigns"] = True
        self.bundle["payload"]["sequence_id"] = "campaign-1"
        result = self.assert_failed("payload.keys")
        self.assertIn({"field": "payload.keys", "expected": list(launch.APPROVED_PAYLOAD_KEYS),
                       "actual": ["sequence_active_in_other_campaigns", "sequence_id"]}, result["mismatches"])

    def test_failure_envelopes_stop_on_wrapper_and_inner_response(self):
        original = copy.deepcopy(self.bundle)
        envelopes = ({"truncated": True}, {"error": "rate limited"}, {"authenticated": False}, {"isError": True})
        for envelope in envelopes:
            with self.subTest(envelope=envelope, where="bare"):
                self.bundle = copy.deepcopy(original)
                self.bundle["native_sequence"].update(envelope)
                result = self.assert_stopped()
                self.assertTrue(any(item["field"].startswith("native_sequence.") for item in result["structure_errors"]), result)
            with self.subTest(envelope=envelope, where="wrapper"):
                self.bundle = copy.deepcopy(original)
                self.bundle["native_sequence"] = {"tool": "apollo_sequences_create", "result": self.bundle["native_sequence"],
                                                  "connector": "synthetic", "structure": "synthetic-sideloaded", **envelope}
                result = self.assert_stopped()
                self.assertTrue(any(item["field"].startswith("native_sequence.") and ".result" not in item["field"]
                                    for item in result["structure_errors"]), result)
            with self.subTest(envelope=envelope, where="inner"):
                self.bundle = copy.deepcopy(original)
                inner = dict(self.bundle["native_sequence"], **envelope)
                self.bundle["native_sequence"] = {"tool": "apollo_sequences_create", "result": inner,
                                                  "connector": "synthetic", "structure": "synthetic-sideloaded"}
                result = self.assert_stopped()
                self.assertTrue(any(item["field"].startswith("native_sequence.result.") for item in result["structure_errors"]), result)
            with self.subTest(envelope=envelope, where="contacts"):
                self.bundle = copy.deepcopy(original)
                self.bundle["native_contacts"].update(envelope)
                self.assert_stopped()

    def test_negative_markers_are_not_failures_by_presence(self):
        self.bundle["native_sequence"].update({"isError": False, "error": None, "truncated": False, "authenticated": True})
        self.bundle["native_contacts"].update({"isError": False, "error": None, "truncated": False})
        result = launch.check(self.bundle)
        self.assertEqual(result["status"], "PASS", result)
        self.bundle["native_sequence"] = {"tool": "apollo_sequences_create", "result": self.bundle["native_sequence"],
                                          "connector": "synthetic", "structure": "synthetic-sideloaded",
                                          "isError": False, "error": None, "truncated": False}
        self.assertEqual(launch.check(self.bundle)["status"], "PASS")

    def test_snapshot_requires_schedule_id_not_just_name(self):
        self.bundle["approved"].pop("emailer_schedule_id")
        self.bundle["approved"]["schedule"] = "synthetic-weekdays"
        self.assert_stopped("approved.emailer_schedule_id")

    def test_cli_stop_has_missing_list_and_no_payload(self):
        self.bundle["native_sequence"]["emailer_campaign"].pop("emailer_schedule_id")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            source.write_text(json.dumps(self.bundle))
            result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            parsed = json.loads(result.stdout)
            self.assertEqual(parsed["status"], "STOP")
            self.assertEqual(parsed["missing"], ["native_sequence.emailer_campaign.emailer_schedule_id"])
            self.assertIsNone(parsed["payload"])

    def test_other_approved_fields_are_reported_not_checked(self):
        self.bundle["approved"]["first_send"] = "synthetic-local-time"
        self.bundle["approved"]["steps"][0]["unknown_wait_field"] = 10
        result = launch.check(self.bundle)
        self.assertEqual(result["status"], "PASS")
        self.assertIn("approved.first_send", result["not_checked"])
        self.assertIn("steps.0.unknown_wait_field", result["not_checked"])

    def test_malformed_approved_schedule_is_rejected(self):
        for waits in ([0], [False, 3], [0, -1], [0, "3"]):
            with self.subTest(waits=waits):
                self.bundle["approved"]["schedule_settings"]["step_waits"] = waits
                with self.assertRaises(ValueError):
                    launch.check(self.bundle)

    def test_duplicate_row_or_native_ids_are_rejected(self):
        for source, key in (("approved", "recipients"), ("recheck", "contacts"), ("native_contacts", "contacts")):
            with self.subTest(source=source):
                bundle = copy.deepcopy(self.bundle)
                bundle[source][key].append(copy.deepcopy(bundle[source][key][0]))
                with self.assertRaises(ValueError):
                    launch.check(bundle)

    def test_cli_pass_fail_and_malformed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "result.json"
            for expected_code, content in ((0, json.dumps(self.bundle)),
                                           (1, json.dumps({**self.bundle, "payload": {}})), (1, "{")):
                with self.subTest(content=content[:30]):
                    source.write_text(content)
                    result = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)],
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, expected_code, result.stderr)
                    parsed = json.loads(result.stdout)
                    self.assertEqual(parsed, json.loads(output.read_text()))
                    self.assertEqual(parsed["status"], "PASS" if expected_code == 0 else "FAIL")
                    if expected_code:
                        self.assertIsNone(parsed["payload"])


if __name__ == "__main__":
    unittest.main()
