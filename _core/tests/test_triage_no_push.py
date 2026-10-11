"""Check evidence-gated triage pairs without changing other writers or queue checks."""
import unittest
from pathlib import Path

import yaml

from test_icm_contracts import sections

ROOT = Path(__file__).resolve().parents[2]
TRIAGE = ROOT / "workspaces/pipeline/workflows/task-triage-speed-run"


class TriageNoPushTests(unittest.TestCase):
    def test_due_completion_requires_positive_action_and_new_task_in_same_approval(self):
        rules = (ROOT / "_core/rules.md").read_text()
        self.assertIn("Triage never automatically moves dates", rules)
        self.assertIn("only on evidence that its action happened", rules)
        self.assertIn("In the same approval, create the next Task with a new Subject and date, or name a verified existing next-action Task", rules)
        self.assertIn("Evidence is a sent email, held call, reply, or a Gmail draft triage created after approval and verified by readback", rules)
        self.assertIn("Without it the Task stays due or overdue", rules)

    def test_missing_action_keeps_due_and_prepares_instead_of_push(self):
        grouping = (TRIAGE / "references/grouping.md").read_text()
        for expected in ("Keep the Task due or overdue", "Prepare a draft, call prep or a question",
                         "unchanged current date", "No Push option", "Those values date a new Task, never move the old one"):
            self.assertIn(expected, grouping)

    def test_existing_date_changes_include_deal_tasks_but_need_quoted_source(self):
        rules = (ROOT / "_core/rules.md").read_text()
        self.assertIn("Triage changes a Task date only on a buyer-stated new date or a moved meeting, with the source quoted.", rules)
        self.assertNotIn("Deal-thread Tasks get no triage date moves", rules)
        grouping = (TRIAGE / "references/grouping.md").read_text()
        writes = (TRIAGE / "references/writes.md").read_text()
        self.assertIn("Quote the buyer's new date or moved Event for any run Task, including a deal Task", grouping)
        self.assertIn("One-deal source permission follows `rules#task_date_coordination`", grouping)
        for expected in ("baseline, baseline_links and exact payload", "Immediately prewrite require fresh native reads and ready",
                         "native hasMore completeness"):
            self.assertIn(expected, writes)

    def test_draft_only_action_needs_verified_creation_then_send_check_not_new_followup(self):
        drafts = (TRIAGE / "references/drafts.md").read_text()
        collect = (TRIAGE / "references/collect.md").read_text()
        self.assertIn("Only a draft triage created after approval and verified by readback qualifies", drafts)
        self.assertIn("failed or unverified draft gets no next-step, completion or next-Task write", drafts)
        self.assertIn("The next Task records the draft id and thread link", drafts)
        self.assertIn("flag `Draft not sent`, never a new follow-up", drafts)
        self.assertIn("read the exact saved draft id and thread and check sent mail", collect)
        self.assertIn("ambiguous sent-message match is needs-input, never assumed sent", collect)

    def test_next_create_failure_preserves_old_task_and_completion_failure_is_partial(self):
        writes = (TRIAGE / "references/writes.md").read_text()
        self.assertLess(writes.index("Write and read the approved next step first"), writes.index("complete the old Task"))
        for expected in ("A failed create or readback leaves the old Task open and due", "completion failure after a verified create is partial",
                         "never imply rollback or retry automatically", "Re-propose completion with that Id for fresh approval",
                         "new Subject and date, correct OwnerId, WhatId and WhoId"):
            self.assertIn(expected, writes)

    def test_unthreaded_opportunity_ownership_is_explicit_with_separate_contract_branch(self):
        rules = (ROOT / "_core/rules.md").read_text()
        ownership_rule = [line for line in rules.splitlines() if line.startswith("- Triage fills current-action Task gaps")]
        self.assertEqual(len(ownership_rule), 1)
        self.assertIn("in-scope Opportunities", ownership_rule[0])
        self.assertIn("Pipeline-review leaves Task and next-step issues to triage, not deal threads", ownership_rule[0])
        contract = (TRIAGE / "CONTEXT.md").read_text()
        grouping = sections((TRIAGE / "references/grouping.md").read_text())
        self.assertIn("unthreaded Opportunity branch", contract)
        self.assertIn("Unthreaded Opportunity Tasks", grouping)
        self.assertIn("Under `rules#task_date_coordination`", "\n".join(grouping["Unthreaded Opportunity Tasks"]))
        self.assertIn("Build its paired next-step entry", "\n".join(grouping["Unthreaded Opportunity Tasks"]))

    def test_deal_context_is_self_read_readonly_no_message_or_wait_before_proposal(self):
        collect = (TRIAGE / "references/collect.md").read_text()
        for expected in ("calls `session_download_content`", "reads its `conversation.jsonl`", "read-only", "Save the exact session id, link and turns read",
                         "An unavailable or failed download tool leaves that thread context not checked", "Never infer its contents",
                         "Send no message and wait for no reply before proposals", "An unread or incomplete thread is a blocker"):
            self.assertIn(expected, collect)
        self.assertNotIn("pplx tm mail send", collect)

    def test_deal_tasks_share_main_message_and_receipts_follow_writes_without_questions(self):
        walk = (TRIAGE / "references/walk.md").read_text()
        writes = (TRIAGE / "references/writes.md").read_text()
        self.assertIn("Deal Tasks and unthreaded Opportunity Tasks stay in this same message", walk)
        self.assertEqual(walk.count("?"), 1)
        self.assertIn("Then send each affected deal thread a receipt of at most 3 lines", writes)
        self.assertIn("Never ask it to act on triage items or ask Operator", writes)
        self.assertIn("List undelivered receipts in a follow-up line", writes)
        self.assertIn("does not undo verified writes or authorize replay", writes)

    def test_run_receipt_precedes_once_only_mail_delivery_without_wait(self):
        writes = (TRIAGE / "references/writes.md").read_text()
        receipts = writes.split("**Receipts.**", 1)[1].split("## Close", 1)[0]
        self.assertLess(receipts.index("post the combined run receipt to Operator first"),
                        receipts.index("Then send each affected deal thread"))
        for expected in ('Send each deal receipt once with `pplx tm mail send <session id> "<message>"`',
                         "Never wait, sleep or poll for a rate limit",
                         "A deal receipt never delays the run receipt or any write",
                         "Run every `pplx` command as its own top-level line",
                         "never inside a script, function, loop or conditional",
                         "List undelivered receipts in a follow-up line",
                         "Record the transport and outcome, never claim delivery without success"):
            self.assertIn(expected, receipts)
        close = "\n".join(sections(writes)["Close"])
        self.assertIn('before deal receipts per "Writes" receipt instructions', close)

    def test_daily_and_walk_use_canonical_receipt_instructions(self):
        for reference in ("daily.md", "walk.md"):
            with self.subTest(reference=reference):
                text = (TRIAGE / "references" / reference).read_text()
                self.assertIn('before deal receipts per `references/writes.md` "Writes" receipt instructions', text)
                self.assertNotIn("pplx tm mail send", text)

    def test_weekly_review_never_proposes_tasks_for_any_owner(self):
        review = ROOT / "workspaces/pipeline/workflows/pipeline-review"
        proposals = (review / "references/proposals.md").read_text()
        self.assertIn('No Task or next-step change', proposals)
        renderer = (review / 'scripts/pipeline_render.py').read_text()
        self.assertIn('pipeline-review cannot propose a Task change', renderer)

    def test_retired_permission_helper_and_registry_are_absent_but_shared_dates_remain(self):
        retired_rule = "auto_" + "date_move"
        retired_helper = "auto_" + "move_check"
        rules = (ROOT / "_core/rules.md").read_text()
        policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.assertNotIn(retired_rule, rules)
        self.assertNotIn(retired_helper, policy["tooling"]["scripts"])
        self.assertFalse((TRIAGE / "scripts" / (retired_helper + ".py")).exists())
        self.assertIn("next_date_days_active", policy["followup"])
        self.assertIn("next_date_days_cold", policy["followup"])

    def test_closeout_keeps_nonempty_queue_failure_and_does_not_push_to_pass(self):
        close = "\n".join(sections((TRIAGE / "references/writes.md").read_text())["Close"])
        self.assertIn("nonempty due, overdue or undated queue still fails", close)
        self.assertIn("Never loosen the helper or push dates to make it pass", close)
        self.assertIn("Ownership or a prepared action is not completion", close)


if __name__ == "__main__":
    unittest.main()
