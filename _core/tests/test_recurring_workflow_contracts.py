"""Regression coverage for migrated recurring-run contracts and safe handoffs."""
import unittest
import hashlib
import re
from pathlib import Path

from test_icm_contracts import sections
from test_skill_contracts import CONTRACT_PATHS, SKILLS

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "workspaces/pipeline/workflows"


def reference(skill, name):
    return (PIPELINE / skill / "references" / name).read_text()


class RecurringWorkflowContractTests(unittest.TestCase):
    def test_pipeline_has_one_proposing_owner_and_forecasting_exception(self):
        text = (ROOT / "workspaces/pipeline/AGENTS.md").read_text()
        approved = (
            "Each Opportunity and its Tasks have one proposing owner. An active deal thread owns its Opportunity's next step, fields, and Tasks.\n"
            "pipeline-review owns other Opportunities in its scope. Task triage owns every remaining due Task. Other runs report such a record as owned elsewhere and propose nothing on it.\n"
            "Forecasting keeps its approved ForecastCategoryName sync."
        )
        self.assertIn(approved, text)

    def test_write_protocol_stops_stale_proposals_without_changing_exceptions(self):
        text = (ROOT / "_core/rules.md").read_text()
        bullet = "- If that read shows a field or Task the proposal changes now differs from what it displayed, stop and re-propose from the current record. Approval never covers a change made after the proposal."
        self.assertEqual(text.count(bullet), 1)
        self.assertIn("- Fresh read immediately before each write.\n" + bullet, text)
        for name, digest in (
            ("auto_date_move", "29fd400a36d7c39402aa452e03f5eb3258e087c05931b4fb6345cca299ebac4d"),
            ("event_sequence", "5b99ca62d0df4b069c7b867cb2fc8911f6361315ec5f89a2d0005399d5d1331c"),
        ):
            block = re.search(r'<a id="' + name + r'"></a>.*?(?=\n<a id=|\Z)', text, re.S).group()
            self.assertEqual(hashlib.sha256(block.encode()).hexdigest(), digest)

    def test_pipeline_review_routes_to_verified_threads_without_local_proposals(self):
        collect = reference("pipeline-review", "collect.md")
        for phrase in ("pplx project sessions list --search", "exact title `<Account> deal`", "same title check used in Task triage"):
            self.assertIn(phrase, collect)
        proposals = reference("pipeline-review", "proposals.md")
        for phrase in ("merge with any open proposal", "Propose nothing", "pplx session send", "pplx tm mail send",
                       "Record which command delivered", "Never claim delivery without a successful send", "Failed or ambiguous routing is needs-input"):
            self.assertIn(phrase, proposals)
        self.assertIn("Propose nothing", "\n".join(sections(proposals)["Friday"]))
        report = reference("pipeline-review", "report-format.md")
        self.assertIn("## Routed to deal threads", report)
        self.assertIn('marked "in deal thread"', report)

    def test_triage_ownership_order_and_customer_deal_thread_first_handoffs(self):
        grouping = reference("task-triage-speed-run", "grouping.md")
        phrases = ("1. An active deal thread owns the Task, so route it.",
                   "2. A current-action Task on an in-scope Opportunity with no deal thread belongs to pipeline-review and is excluded.",
                   "3. Triage owns everything else.")
        self.assertLess(grouping.index(phrases[0]), grouping.index(phrases[1]))
        self.assertLess(grouping.index(phrases[1]), grouping.index(phrases[2]))
        for name in ("collect.md", "daily.md"):
            self.assertIn('`references/grouping.md` "Pipeline ownership"', reference("task-triage-speed-run", name))
        for name in ("collect.md", "proposals.md"):
            self.assertIn("active deal thread first, otherwise to Pipeline hygiene", reference("customer-review", name))

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

    def test_deal_thread_routing_uses_one_mail_fallback_and_verified_delivery(self):
        for skill, name in (("task-triage-speed-run", "daily.md"), ("interaction-sync", "sweep.md")):
            with self.subTest(skill=skill):
                text = reference(skill, name)
                self.assertIn("`pplx tm mail send <deal-thread session id>`", text)
                self.assertLess(text.index("`pplx session send`"), text.index("`pplx tm mail send <deal-thread session id>`"))
                self.assertIn("On confirmed failure with no delivery, retry once", text)
                self.assertIn("An ambiguous send needs native reconciliation", text)
                self.assertIn("Record which command delivered", text)
                self.assertIn("Failed or ambiguous routing", text)
                self.assertIn("needs-input", text)
                self.assertIn("Never claim delivery without a successful send", text)

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
