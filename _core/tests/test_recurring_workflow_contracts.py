"""Regression coverage for migrated recurring-run contracts and safe handoffs."""
import unittest
from pathlib import Path

from test_icm_contracts import sections
from test_skill_contracts import CONTRACT_PATHS, SKILLS

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "workspaces/pipeline/workflows"


def reference(skill, name):
    return (PIPELINE / skill / "references" / name).read_text()


class RecurringWorkflowContractTests(unittest.TestCase):
    def test_watch_sync_route_and_propose_only_scope(self):
        self.assertEqual(SKILLS["watch-sync"], "pipeline")
        contract = CONTRACT_PATHS["watch-sync"].read_text()
        self.assertIn("writes: nothing", contract)
        self.assertIn("A scheduled run cannot edit other automations", contract)
        self.assertIn("No automation edit, thread create or archive, Salesforce, Gmail, or Slack write", contract)
        self.assertIn("watch-sync", (ROOT / "AGENTS.md").read_text())

    def test_watch_scope_and_retained_thread_evidence(self):
        text = reference("watch-sync", "reconcile.md")
        for expected in ("in S1 and `policy.pipeline.stages`", "Contact Roles", "Customer_Point_of_Contact__c",
                         "policy.tooling.generic_email_domains", "same approved inventory", "all four",
                         "do not propose any archive", "Deal threads, needs Operator approval", "not applied on receipt"):
            self.assertIn(expected, text)

    def test_sweep_release_gate_precedes_enumeration(self):
        text = reference("interaction-sync", "sweep.md")
        self.assertLess(text.index("## Release gate"), text.index("## Find every call"))
        self.assertIn("shared Momentum exception pending approval", text)
        self.assertIn("Do not execute an Account-free search under the old rule", text)
        contract = sections(CONTRACT_PATHS["interaction-sync"].read_text())
        self.assertIn("stop after its handoff", "\n".join(contract["Process"]))

    def test_sweep_complete_reads_identity_dedupe_and_approval(self):
        text = reference("interaction-sync", "sweep.md")
        for expected in ("previous business day", "page_size", "window_hours", "Recursively split",
                         "read every window", "deduplicate by meeting Id", "identity unverified",
                         "Description cannot be filtered in SOQL", "first line exactly matches",
                         "no writes until Operator approves", "No Salesforce or Gmail writes",
                         "incomplete retrieval", "notify-source"):
            self.assertIn(expected, text)

    def test_daily_call_prep_preserves_full_audio_and_failure_delivery(self):
        text = reference("sales-call-prep", "daily.md")
        for expected in ("every external call today", "same handle", "Generate no audio", "full summary, not a shorter recap",
                         "hypothesis label", "evidence limitation", "`voice`", "without music", "without changing playback speed",
                         "configured filename", "ending is not cut off", "explicitly report the audio failure"):
            self.assertIn(expected, text)

    def test_triage_routing_precedes_local_moves_and_preserves_approval(self):
        text = reference("task-triage-speed-run", "daily.md")
        for expected in ("Gmail sent mail, Calendar, and Momentum", "buyer actually stated", "instead of proposing",
                         "Do not auto-move", "meeting_lookahead_business_days", "prep_lead_business_days", "Subject names the asset",
                         "WhoId", "own explicit record approval", "only after approval", "Auto-moved",
                         "No reply writes nothing else", "incomplete-source warnings"):
            self.assertIn(expected, text)
        process = "\n".join(sections(CONTRACT_PATHS["task-triage-speed-run"].read_text())["Process"])
        self.assertLess(process.index("Route deal-thread rows"), process.index("5. Apply qualifying automatic"))

    def test_pilot_usage_is_on_demand_without_a_recurring_branch(self):
        contract = CONTRACT_PATHS["pilot-usage"].read_text()
        self.assertIn("cadence: one-off", contract)
        self.assertIn("Run only when requested", contract)
        self.assertIn("Mode `report` (default)", contract)
        self.assertIn("Mode `pdf`", contract)
        self.assertNotIn("references/weekly.md", contract)
        self.assertFalse((PIPELINE / "pilot-usage/references/weekly.md").exists())

    def test_missing_proposed_policy_values_are_not_invented(self):
        for skill, name, expected in (
            ("interaction-sync", "sweep.md", "Missing settings stop enumeration"),
            ("sales-call-prep", "daily.md", "Missing settings are an audio failure"),
            ("task-triage-speed-run", "daily.md", "report meeting preparation not checked"),
        ):
            with self.subTest(skill=skill):
                self.assertIn(expected, reference(skill, name))

    def test_migrated_references_do_not_store_live_identity(self):
        paths = [PIPELINE / skill / "references" / name for skill, name in (
            ("watch-sync", "reconcile.md"), ("interaction-sync", "sweep.md"), ("sales-call-prep", "daily.md"),
            ("task-triage-speed-run", "daily.md"),
        )]
        for path in paths:
            with self.subTest(path=path):
                text = path.read_text()
                self.assertNotIn("custom-cred:", text)
                self.assertNotRegex(text, r"\b005[A-Za-z0-9]{12,15}\b")
                self.assertNotRegex(text, r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
