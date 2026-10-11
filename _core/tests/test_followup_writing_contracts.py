"""Pin approved follow-up copy and resolve triage boundaries from canonical policy."""
import re
import unittest
from pathlib import Path

import yaml

from test_skill_contracts import CONTRACT_PATHS, policy_input_scopes

ROOT = Path(__file__).resolve().parents[2]
TRIAGE = CONTRACT_PATHS["task-triage-speed-run"].parent


class FollowupWritingContractTests(unittest.TestCase):
    def test_email_body_matches_approved_ladder_including_security_tail(self):
        rules = (ROOT / "_core/rules.md").read_text()
        block = re.search(r'<a id="email_body"></a>.*?(?=\n\n|\Z)', rules, re.S).group()
        expected = '''<a id="email_body"></a>**email_body**
- One or two short sentences and one concrete ask tied to the open thread or Task.
- Continue the prior email: name its claim or ask in plain words and move it forward. Clear in five seconds without the thread.
- A follow-up to Operator's unanswered email picks one type. Count his emails and each repeated ask since the buyer's last substantive reply.
  A reply restarts both counts.
  - Specific ask. The same ask goes out at most twice.
  - Timing note when the draft would repeat an ask or fact already sent.
    A contact who engaged before gets "Let me know if the timing is right to continue the conversation."
    A contact who never engaged gets a variant like "Is there any interest in a conversation?"
  - Break-up note after `policy.followup.breakup_after_unanswered` unanswered emails.
    "If this is not a priority, let me know. We can table the conversation for the time being."
- No phrase in `policy.email_voice.banned`.
- Re-read linked security threads before drafting customer security answers, rather than relying on notifications.'''
        self.assertEqual(block, expected)

    def test_followup_thresholds_and_approved_comments_are_canonical(self):
        source = (ROOT / "_core/policy.yaml").read_text()
        followup = yaml.safe_load(source)["followup"]
        self.assertEqual(followup["breakup_after_unanswered"], 8)
        self.assertEqual(followup["recycle_after_unanswered"], 9)
        followup_block = source.split("\nfollowup:\n", 1)[1].split("\n\n", 1)[0]
        self.assertRegex(followup_block, r"(?m)^\s+breakup_after_unanswered:\s*8\s+# unanswered sent emails since the last substantive reply before the break-up note$")
        self.assertRegex(followup_block, r"(?m)^\s+recycle_after_unanswered:\s*9\s+# cold Contacts only: unanswered emails, including the break-up note, before a Recycle decision$")

    def test_triage_drafts_defer_timing_and_breakup_to_shared_ladder(self):
        drafts = (TRIAGE / "references/drafts.md").read_text()
        anchor = "Follow `policy.email_voice` and `rules#email_body`."
        sentence = ("It names one specific claim, offer, or question from that email and moves it forward with one new fact or a sharper ask. "
                    "`rules#email_body` decides when a timing or break-up note replaces the ask.")
        self.assertIn(anchor, drafts)
        self.assertIn(sentence, drafts.split(anchor, 1)[1])
        self.assertIn("Do not create it until its displayed row is approved.", drafts)
        self.assertIn("Never send.", drafts)

    def test_triage_breakup_at_eight_precedes_cold_push_or_recycle_at_nine(self):
        rules = (ROOT / "_core/rules.md").read_text()
        grouping = (TRIAGE / "references/grouping.md").read_text()
        policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        breakup_key = re.search(r"Break-up note after `policy\.followup\.([a-z_]+)`", rules).group(1)
        recycle_key = re.search(r"Cold Contact and unanswered count at least `policy\.followup\.([a-z_]+)`", grouping).group(1)
        for count, breakup_due, recycle_due in ((7, False, False), (8, True, False), (9, True, True)):
            with self.subTest(unanswered=count):
                self.assertEqual(count >= policy["followup"][breakup_key], breakup_due)
                self.assertEqual(count >= policy["followup"][recycle_key], recycle_due)
        self.assertLess(grouping.index("4. **Recycle decisions.**"), grouping.index("5. **Hold or prepare.**"))
        self.assertIn("No Push option.", grouping)
        self.assertIn("remains needs-input, and an active Contact never recycles", grouping)

    def test_active_contact_never_recycles_and_hold_still_precedes_draft(self):
        rules = (ROOT / "_core/rules.md").read_text()
        grouping = (TRIAGE / "references/grouping.md").read_text()
        self.assertIn("an active Contact never recycles (`rules#contact_status`).", grouping)
        self.assertIn("An active Contact never recycles.", rules)
        self.assertIn("according to Contact status", grouping)
        self.assertIn("No new draft during `policy.followup.sent_mail_hold_days_active`", grouping)

    def test_triage_stuck_action_switch_preserves_approved_wording_and_gates(self):
        grouping = (TRIAGE / "references/grouping.md").read_text()
        anchor = ("   For an eligible email action, prepare the full draft. Only after approval and verified triage creation "
                  "does that draft qualify for complete plus next Task.\n")
        expected = (
            "   When the stated action cannot be prepared but retrieved evidence supports a different action toward the same outcome, "
            "prepare that action's full draft as a numbered row, not a blocker.\n"
            "   Name the original action, the evidence and the change in one line.\n"
            "   A switch that changes legal terms is a recommended question row with the draft ready, so one answer approves it. "
            "The recipient, hold and existing-draft gates above still apply.\n"
            "   When the Task's recipient bounced, propose a first email to another Contact on the same Account whose role fits the action, "
            "flagged `First email to this address`.\n"
            "   This is the only exception to the verified-recipient gate.\n"
        )
        self.assertIn(anchor + expected, grouping)
        self.assertIn("A recipient requires a verified address Operator sent to without a bounce.", grouping)
        self.assertIn("Existing draft, Lead linkage, future cooldown marker, unconfirmed recipient or LinkedIn-only channel is a blocker", grouping)
        self.assertIn("No new draft during `policy.followup.sent_mail_hold_days_active` or `policy.followup.sent_mail_hold_days_cold`", grouping)

    def test_outreach_loads_only_the_new_followup_key_for_email_body(self):
        contract = CONTRACT_PATHS["signal-outreach"].read_text()
        scopes = policy_input_scopes(contract)
        self.assertIn("followup.breakup_after_unanswered", scopes)
        self.assertNotIn("followup", scopes)
        self.assertIn("rules#email_body", contract)


if __name__ == "__main__":
    unittest.main()
