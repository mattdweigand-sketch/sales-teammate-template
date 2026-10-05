"""Recurring schedule intent and review coverage without activating any automation."""
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICY = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
WEEKDAYS = ["MO", "TU", "WE", "TH", "FR"]


def policy_value(key):
    value = POLICY
    for part in key.split("."):
        value = value[part]
    return value


class RecurringSchedulePolicyTests(unittest.TestCase):
    def test_exact_proposed_schedules(self):
        schedules = {
            "system_review.schedule": (["FR"], "14:00"),
            "pipeline.schedule.watch_sync": (WEEKDAYS, "06:15"),
            "pipeline.schedule.call_sweep": (WEEKDAYS, "06:45"),
            "pipeline.schedule.task_triage": (WEEKDAYS, "07:30"),
            "pipeline.schedule.ask_nudges": (WEEKDAYS, "09:00"),
            "call_prep.schedule": (WEEKDAYS, "06:30"),
            "forecast.manager_update": (["FR"], "12:00"),
        }
        review = (ROOT / "workspaces/systems/workflows/system-review/references/review.md").read_text()
        for key, (days, time) in schedules.items():
            with self.subTest(key=key):
                self.assertEqual(policy_value(key), {"days": days, "time": time, "tz": "America/Los_Angeles"})
                self.assertIn(f"policy.{key}", review)

    def test_preapproval_bar_is_not_write_authority(self):
        self.assertEqual(POLICY["system_review"]["preapproval"], {
            "window_weeks": 4, "min_proposals": 20, "min_unchanged": 19, "max_rejections": 0,
        })
        self.assertFalse(POLICY["prospecting"]["approval"]["unattended_writes"])
        self.assertTrue(POLICY["prospecting"]["approval"]["readback_required"])
        self.assertNotIn("prospector", POLICY["prospecting"])
        self.assertEqual(POLICY["prospecting"]["outreach"]["max_drafts_per_run"], 1)

    def test_existing_schedules_are_preserved(self):
        self.assertEqual(POLICY["pipeline"]["schedule"]["daily"], {
            "days": ["MO", "TU", "WE", "TH"], "time": "07:00", "tz": "America/Los_Angeles",
        })
        self.assertEqual(POLICY["pipeline"]["schedule"]["friday"]["time"], "09:00")
        self.assertEqual(POLICY["forecast"]["schedule"]["time"], "10:00")
        self.assertEqual(POLICY["pipeline"]["customer_review"]["schedule"], {
            "days": ["MO"], "week_of_month": 1, "time": "07:30", "tz": "America/Los_Angeles",
        })
        review = (ROOT / "workspaces/systems/workflows/system-review/references/review.md").read_text()
        self.assertIn("policy.pipeline.customer_review.schedule", review)

    def test_migrated_prompt_values_are_canonical(self):
        self.assertEqual(POLICY["momentum"]["sweep"], {"page_size": 50, "window_hours": 3})
        self.assertEqual(POLICY["pipeline"]["triage"], {
            "meeting_lookahead_business_days": 10, "prep_lead_business_days": 2,
        })
        self.assertEqual(POLICY["call_prep"]["audio"], {"voice": "charon", "filename": "daily-call-prep-{date}.mp3"})
        self.assertNotIn("schedule", POLICY["pilot_usage"])
        self.assertNotIn("weekly_health", POLICY["pilot_usage"])

    def test_momentum_exception_does_not_replace_single_call_guard(self):
        rules = (ROOT / "_core/rules.md").read_text().split('<a id="momentum"></a>', 1)[1].split('<a id=', 1)[0]
        self.assertIn("interaction-sync sweep branch may enumerate the previous business day's meetings", rules)
        self.assertIn("It must read every window, not stop at the first match", rules)
        self.assertIn("Always pass `salesforceAccountId=<18-char AccountId>`", rules)
        self.assertIn("Stop at the first match", rules)
