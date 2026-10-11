"""Guard the two repo-owned Slack draft procedures and their entry routes."""
from pathlib import Path
import unittest

import yaml

from test_skill_contracts import inputs_rows, loaded_contract_text


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "workspaces/pipeline"
FORECAST = ROOT / "workspaces/forecasting/workflows/forecast-weekly"
INTERNAL_ASKS = PIPELINE / "references/internal-asks.md"
MANAGER_UPDATE = FORECAST / "references/manager-update.md"


class RecurringSlackProcedureTests(unittest.TestCase):
    def procedure(self, path):
        self.assertTrue(path.is_file(), f"Missing procedure {path.relative_to(ROOT)}")
        return path.read_text()

    def test_internal_ask_poll_is_routed_without_entering_salesforce_triage(self):
        routes = (PIPELINE / "CONTEXT.md").read_text()
        self.assertIn("## Internal ask poll", routes)
        poll = routes.split("## Internal ask poll\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn('`references/internal-asks.md`', poll)
        self.assertIn("Full file", poll)
        self.assertIn("poll-mode", poll)
        self.assertIn("policy.pipeline.schedule.ask_nudges", poll)
        self.assertNotIn("task-triage-speed-run", poll)
        self.assertIn("Internal ask poll", (PIPELINE / "AGENTS.md").read_text())

    def test_internal_ask_inventory_and_answer_handoff_keep_current_scope(self):
        text = self.procedure(INTERNAL_ASKS)
        for required in (
            "pplx tm tasks list", "`internal-ask`", "open Teammate tasks",
            "Slack DM or thread named by the task", "colleague's reply",
            "two-line summary", "related deal thread", "pplx tm mail send",
            "otherwise summarize for Operator in the run thread", "mark the Teammate task done",
            "rules#handoff_delivery", "failed handoff leaves the task open",
            "not Salesforce Tasks",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_internal_ask_nudge_uses_its_own_business_day_policy(self):
        policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.assertEqual(policy["pipeline"].get("internal_ask_nudge_business_days"), 2)
        text = self.procedure(INTERNAL_ASKS)
        self.assertIn("policy.pipeline.internal_ask_nudge_business_days", text)
        self.assertIn("sent time recorded in the task", text)
        self.assertIn("business days", text)
        self.assertIn("one or two sentences", text)
        self.assertNotIn("2 business days", text)
        self.assertNotIn("policy.followup", text)
        self.assertNotIn("policy.pipeline.triage", text)

    def test_internal_ask_silence_requires_verified_waiting_not_missing_reads(self):
        text = self.procedure(INTERNAL_ASKS)
        for required in (
            "rules#absence_conclusions", "rules#not_checked_means",
            "answered", "nudge drafted", "waiting", "not checked",
            "every task is verified inside its nudge window",
            "pplx automation suppress-run-notification",
            "Never suppress a failed handoff or a not-checked task",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_internal_ask_voice_is_explicit_and_external_review_is_advisory(self):
        text = self.procedure(INTERNAL_ASKS)
        for required in (
            "one or two sentences in Operator's voice",
            "no colons inside sentences, no em dashes and no semicolons",
            "If available, use `draft-anti-slop` for advisory Slack voice review",
            "Report unavailable style review",
            "Never block or skip a draft because of this style review",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertNotIn("Apply its unattended draft checks", text)
        self.assertNotIn("voice rules loaded above", text)

    def test_manager_update_is_an_explicit_terminal_branch_with_bounded_inputs(self):
        contract = (FORECAST / "CONTEXT.md").read_text()
        self.assertIn("Manager update follows", contract)
        self.assertIn("then stops before forecast or tracking steps", contract)
        rows = inputs_rows(contract)
        manager = [row for row in rows if "`references/manager-update.md`" in row[1]]
        self.assertEqual(len(manager), 1)
        self.assertIn("Manager update only", manager[0][2])
        self.assertIn("Full file", manager[0][2])
        self.assertIn(self.procedure(MANAGER_UPDATE), loaded_contract_text(FORECAST))
        routes = (ROOT / "workspaces/forecasting/CONTEXT.md").read_text()
        self.assertIn("manager update", routes.lower())
        self.assertIn("policy.forecast.manager_update", contract)

    def test_manager_update_uses_revised_call_prior_week_and_all_three_sources(self):
        text = self.procedure(MANAGER_UPDATE)
        for required in (
            "this week's forecast report", "latest call", "later turns",
            "prior week's forecast report", "Salesforce Opportunities owned by Operator",
            "changed this week", "deal-thread status messages in the Pipeline thread",
            "forecast call and change vs last week", "key deal moves",
            "deals at risk", "asks for help", "five bullets or fewer",
            "Amounts come from current source reports", "no emojis",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertNotRegex(text, r"\$\s*\d|\b\d{5,}\b")

    def test_manager_existing_draft_is_reported_never_overwritten(self):
        text = self.procedure(MANAGER_UPDATE)
        for required in (
            "If a draft already exists", "report it instead of overwriting",
            "draft text and the DM link", "draft lookup is unavailable",
            "do not create", "rules#absence_conclusions", "rules#not_checked_means",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertLess(text.index("If a draft already exists"), text.index("slack_send_message_draft"))

    def test_manager_voice_is_explicit_and_external_review_is_advisory(self):
        text = self.procedure(MANAGER_UPDATE)
        for required in (
            "terse, fact-led and in Operator's voice",
            "no colons inside sentences, no em dashes, no semicolons and no emojis",
            "If available, use `draft-anti-slop` for advisory Slack voice review",
            "Report unavailable style review",
            "Never block or skip a draft because of this style review",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertNotIn("Apply its unattended draft checks", text)
        self.assertNotIn("Follow the loaded voice rules", text)

    def test_both_procedures_reuse_thread_and_voice_authorities_without_sending(self):
        for path in (INTERNAL_ASKS, MANAGER_UPDATE):
            text = self.procedure(path)
            with self.subTest(path=path.relative_to(ROOT)):
                for required in (
                    '`_core/thread-locators.md` "Teammate thread lookup"',
                    "`draft-anti-slop`", "Slack voice", "slack_send_message_draft",
                    "Never send Slack or email", "No Salesforce writes", "no semicolons",
                ):
                    self.assertIn(required, text)
                self.assertNotIn("session_download_content", text)
                self.assertNotRegex(text, r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b")
                self.assertNotRegex(text, r"\b[UDC][A-Z0-9]{8,}\b")
                self.assertNotRegex(text, r"\bslack_send_message\b")
                self.assertNotIn("rules#email_body", text)


if __name__ == "__main__":
    unittest.main()
