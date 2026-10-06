import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
SCRIPTS = ROOT / "workspaces" / "prospecting" / "workflows" / "signal-prospecting" / "03-followup" / "scripts"
sys.path.insert(0, str(ROOT / "workspaces/prospecting/scripts"))
sys.path.insert(0, str(SCRIPTS))
import prospect_common  # noqa: E402
import prospect_followup_gate as fg  # noqa: E402

POLICY = prospect_common.load_policy()
OPERATOR = POLICY["identity"]["sfdc_user_id"]
TODAY = date(2026, 9, 21)

BASE = {
    "sent": [{"message_id": "m1", "thread_id": "t1", "subject": "Context engineering inside Acme",
              "sent_at": "2026-09-21T14:05:00-07:00", "to": "casey@example.com"}],
    "account": {"id": "001A", "owner_id": OPERATOR},
    "contacts": [{"id": "003A", "email": "Casey@Example.com"}],
    "tasks": [{"id": "00T1", "subject": "LinkedIn - Connected", "description": ""}],
    "signal": {"signal_type": "ai_exec_appointment", "angle": "Model flexibility"},
}


def run(**over):
    p = copy.deepcopy(BASE)
    p.update(over)
    return fg.check(p, POLICY, today=TODAY)


class Allow(unittest.TestCase):
    def test_allow_fields(self):
        out = fg.check(copy.deepcopy(BASE), POLICY, today=TODAY)
        self.assertEqual(out["verdict"], "allow")
        t = out["task"]
        self.assertEqual(t["Subject"], "Follow up: Context engineering inside Acme")
        self.assertEqual(t["WhoId"], "003A")
        self.assertEqual(t["WhatId"], "001A")
        self.assertEqual(t["OwnerId"], OPERATOR)
        self.assertEqual(t["Status"], "Not Started")
        self.assertEqual(t["TaskSubtype"], "Task")
        self.assertEqual(t["ActivityDate"], "2026-09-28")
        self.assertTrue(t["Description"].startswith("9/21/26 SR - "))
        self.assertIn("m1", t["Description"])
        self.assertIn("t1", t["Description"])
        self.assertIn("signal_type ai_exec_appointment", t["Description"])
        self.assertIn("angle Model flexibility.", t["Description"])
        self.assertNotIn("Type", t)

    def test_historical_labels_survive_catalog_changes(self):
        out = run(signal={"signal_type": "retired_signal", "angle": "Previous approved angle"})
        self.assertEqual(out["verdict"], "allow")
        self.assertIn("Previous approved angle", out["task"]["Description"])

    def test_missing_historical_labels_block(self):
        for signal in ({"signal_type": "", "angle": "Context"}, {"signal_type": "ai_exec_appointment", "angle": " "}):
            out = run(signal=signal)
            self.assertEqual(out["verdict"], "block")

    def test_angle_is_the_only_label_key(self):
        out = run(signal={"signal_type": "ai_exec_appointment", "unit": "Q2"})
        self.assertIn("signal angle must be a nonempty label from the approved outreach verdict", out["reasons"])

    def test_missing_signal_blocks(self):
        p = copy.deepcopy(BASE); del p["signal"]
        out = fg.check(p, POLICY, today=TODAY)
        self.assertEqual(out["verdict"], "block")

    def test_contact_email_case_insensitive(self):
        self.assertEqual(run()["verdict"], "allow")


class DueDate(unittest.TestCase):
    def test_pacific_date_from_utc(self):
        # 2026-09-22T05:30Z is still 2026-09-21 in Pacific
        d = fg.due_date(prospect_common.parse_iso("2026-09-22T05:30:00Z"), POLICY)
        self.assertEqual(d.isoformat(), "2026-09-28")





    def test_naive_timestamp_blocks(self):
        p = copy.deepcopy(BASE)
        p["sent"][0]["sent_at"] = "2026-09-21T10:00:00"
        out = fg.check(p, POLICY, today=TODAY)
        self.assertEqual(out["verdict"], "block")


class Block(unittest.TestCase):
    def test_no_proof(self):
        out = run(sent=[])
        self.assertEqual(out["reasons"], ["no sent proof"])

    def test_ambiguous(self):
        out = run(sent=BASE["sent"] * 2)
        self.assertIn("ambiguous", out["reasons"][0])

    def test_missing_field(self):
        p = copy.deepcopy(BASE)
        del p["sent"][0]["thread_id"]
        self.assertEqual(fg.check(p, POLICY, today=TODAY)["reasons"], ["sent hit missing thread_id"])

    def test_missing_fields_accumulate_with_other_reasons(self):
        p = copy.deepcopy(BASE)
        del p["sent"][0]["thread_id"]
        del p["sent"][0]["to"]
        p["account"]["owner_id"] = "005OTHER"
        p["signal"]["angle"] = ""
        out = fg.check(p, POLICY, today=TODAY)
        self.assertEqual(out["verdict"], "block")
        self.assertIn("signal angle must be a nonempty label from the approved outreach verdict", out["reasons"])
        self.assertIn("sent hit missing thread_id", out["reasons"])
        self.assertIn("sent hit missing to", out["reasons"])
        self.assertIn("account owner is not identity.sfdc_user_id", out["reasons"])

    def test_wrong_owner(self):
        out = run(account={"id": "001A", "owner_id": "005OTHER"})
        self.assertIn("account owner is not identity.sfdc_user_id", out["reasons"])

    def test_zero_contacts(self):
        self.assertIn("contact match count 0, need exactly 1", run(contacts=[])["reasons"])

    def test_two_contacts(self):
        c = BASE["contacts"][0]
        self.assertIn("contact match count 2, need exactly 1", run(contacts=[c, dict(c, id="003B")])["reasons"])

    def test_contact_email_mismatch(self):
        out = run(contacts=[{"id": "003A", "email": "other@example.com"}])
        self.assertIn("contact email does not equal recipient", out["reasons"])

    def test_missing_or_unusable_contact_id_never_proposes_task(self):
        for value in (None, "", "  ", False, 12):
            out = run(contacts=[{"id": value, "email": "casey@example.com"}])
            self.assertEqual(out["verdict"], "block")
            self.assertIn("contact needs a nonempty string id", out["reasons"])
            self.assertNotIn("task", out)
        out = run(contacts=[{"email": "casey@example.com"}])
        self.assertIn("contact needs a nonempty string id", out["reasons"])

    def test_duplicate_by_subject(self):
        out = run(tasks=[{"id": "00T9", "subject": "Follow up: Context engineering inside Acme", "description": ""}])
        self.assertEqual(out["reasons"], ["duplicate Task 00T9"])

    def test_duplicate_by_message_id(self):
        out = run(tasks=[{"id": "00T8", "subject": "anything", "description": "Gmail message m1; thread t1."}])
        self.assertEqual(out["reasons"], ["duplicate Task 00T8"])

    def test_open_followup_task_blocks(self):
        out = run(tasks=[{"id": "00T7", "subject": "Follow up: check reply from Casey", "description": "", "status": "Not Started"}])
        self.assertEqual(out["reasons"], ["open follow-up Task already exists 00T7"])

    def test_completed_followup_task_does_not_block(self):
        out = run(tasks=[{"id": "00T6", "subject": "Follow up: check reply from Casey", "description": "", "status": "Completed"}])
        self.assertEqual(out["verdict"], "allow")

    def test_due_before_today_blocks(self):
        p = copy.deepcopy(BASE)
        p["sent"][0]["sent_at"] = "2026-09-11T13:44:47-07:00"
        out = fg.check(p, POLICY, today=TODAY)
        self.assertIn("due date 2026-09-18 is before today", out["reasons"][0])

    def test_due_today_allows(self):
        p = copy.deepcopy(BASE)
        p["sent"][0]["sent_at"] = "2026-09-14T10:00:00-07:00"
        self.assertEqual(fg.check(p, POLICY, today=TODAY)["verdict"], "allow")

    def test_multiple_reasons_reported(self):
        out = run(account={"id": "001A", "owner_id": "005OTHER"}, contacts=[])
        self.assertEqual(len(out["reasons"]), 2)


class TasksAndTimestamp(unittest.TestCase):
    def test_tasks_missing_blocks(self):
        p = copy.deepcopy(BASE); del p["tasks"]
        out = fg.check(p, POLICY, today=TODAY)
        self.assertEqual(out["verdict"], "block")
        self.assertTrue(any(r.startswith("tasks missing or not a list") for r in out["reasons"]))

    def test_tasks_null_blocks(self):
        out = run(tasks=None)
        self.assertEqual(out["verdict"], "block")
        self.assertTrue(any(r.startswith("tasks missing or not a list") for r in out["reasons"]))

    def test_tasks_wrong_type_blocks(self):
        out = run(tasks={"id": "00T1"})
        self.assertEqual(out["verdict"], "block")

    def test_tasks_empty_list_allows(self):
        self.assertEqual(run(tasks=[])["verdict"], "allow")

    def test_sent_at_later_today_blocks(self):
        p = copy.deepcopy(BASE)
        p["sent"][0]["sent_at"] = "2026-09-21T18:00:00-07:00"
        now = datetime(2026, 9, 21, 14, 0, tzinfo=ZoneInfo(POLICY["identity"]["timezone"]))
        out = fg.check(p, POLICY, today=TODAY, now=now)
        self.assertEqual(out["verdict"], "block")
        self.assertIn("is after now", out["reasons"][0])

    def test_sent_at_earlier_today_allows(self):
        p = copy.deepcopy(BASE)
        p["sent"][0]["sent_at"] = "2026-09-21T13:00:00-07:00"
        now = datetime(2026, 9, 21, 14, 0, tzinfo=ZoneInfo(POLICY["identity"]["timezone"]))
        self.assertEqual(fg.check(p, POLICY, today=TODAY, now=now)["verdict"], "allow")

    def test_sent_at_future_day_blocks(self):
        p = copy.deepcopy(BASE)
        p["sent"][0]["sent_at"] = "2026-09-25T09:00:00-07:00"
        out = fg.check(p, POLICY, today=TODAY)
        self.assertEqual(out["verdict"], "block")
        self.assertIn("is after now", out["reasons"][0])

    def test_sent_at_offset_compared_as_instant(self):
        # 22:00 UTC on the 21st is 15:00 Pacific. now is 14:00 Pacific, so it is in the future.
        p = copy.deepcopy(BASE)
        p["sent"][0]["sent_at"] = "2026-09-21T22:00:00Z"
        now = datetime(2026, 9, 21, 14, 0, tzinfo=ZoneInfo(POLICY["identity"]["timezone"]))
        self.assertEqual(fg.check(p, POLICY, today=TODAY, now=now)["verdict"], "block")

    def test_default_clock_is_policy_now(self):
        # 2026-09-29T04:00Z is 2026-09-28 21:00 Pacific. The due date 2026-09-28 is still today there, so it allows.
        fixed = datetime(2026, 9, 29, 4, 0, tzinfo=ZoneInfo("UTC"))
        with mock.patch.object(prospect_common, "policy_now", return_value=fixed.astimezone(prospect_common.policy_tz(POLICY))):
            self.assertEqual(fg.check(copy.deepcopy(BASE), POLICY)["verdict"], "allow")


class UnusableInput(unittest.TestCase):
    def test_account_null_is_input_error(self):
        with self.assertRaises(ValueError):
            run(account=None)

    def test_sent_not_a_list_is_input_error(self):
        with self.assertRaises(ValueError):
            run(sent={"message_id": "m1"})


class Cli(unittest.TestCase):
    def run_gate(self, packet, *extra):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "packet.json"
            f.write_text(json.dumps(packet))
            return subprocess.run([sys.executable, str(SCRIPTS / "prospect_followup_gate.py"), "--packet", str(f), "--today", "2026-09-21", *extra],
                                  cwd=td, capture_output=True, text=True)

    def test_exit_codes_and_envelopes(self):
        p = self.run_gate(BASE)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertEqual(json.loads(p.stdout)["verdict"], "allow")
        p = self.run_gate(dict(BASE, sent=[]))
        self.assertEqual(p.returncode, 1)
        self.assertEqual(json.loads(p.stdout)["reasons"], ["no sent proof"])
        p = self.run_gate(dict(BASE, account=None))
        self.assertEqual(p.returncode, 2, p.stdout)
        self.assertEqual(p.stderr, "")
        out = json.loads(p.stdout)
        self.assertEqual(out["verdict"], "error")
        self.assertIn("account must be an object", out["reason"])

if __name__ == "__main__":
    unittest.main()
