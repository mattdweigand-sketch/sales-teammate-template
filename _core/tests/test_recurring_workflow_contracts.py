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
    def test_pipeline_keeps_deal_permissions_and_forecasting_exception(self):
        text = (ROOT / "workspaces/pipeline/AGENTS.md").read_text()
        self.assertIn("with its source, ownership and approval gates", text)
        self.assertIn("Outside deal threads, the one-deal command routes through the triage contract", text)
        self.assertIn("For Task or next-step commands, use triage's one-deal mechanics", text)
        self.assertIn("Other owners' Tasks keep current behavior", text)
        self.assertIn("Deal threads do not ask Operator about triage items", text)
        self.assertIn("Forecasting keeps its approved ForecastCategoryName sync.", text)

    def test_write_protocol_stops_stale_proposals_without_changing_exceptions(self):
        text = (ROOT / "_core/rules.md").read_text()
        bullet = "- If that read shows a field or Task the proposal changes now differs from what it displayed, stop and re-propose from the current record. Approval never covers a change made after the proposal."
        self.assertEqual(text.count(bullet), 1)
        self.assertIn("- Fresh read immediately before each write.\n" + bullet, text)
        for name, digest in (
            ("event_sequence", "5b99ca62d0df4b069c7b867cb2fc8911f6361315ec5f89a2d0005399d5d1331c"),
        ):
            block = re.search(r'<a id="' + name + r'"></a>.*?(?=\n<a id=|\Z)', text, re.S).group()
            self.assertEqual(hashlib.sha256(block.encode()).hexdigest(), digest)

    def test_pipeline_review_routes_to_verified_threads_without_local_proposals(self):
        collect = reference("pipeline-review", "collect.md")
        for phrase in ("pplx project sessions list <project> --limit <L> --offset <O>", "starting at 0",
                       "`offset` and `sessions`", "deal_thread_match --input", "exact normalized names",
                       "`owner` routes", "`local` keeps", "`needs_input` or `incomplete` holds proposals"):
            self.assertIn(phrase, collect)
        self.assertNotIn("sessions list --search", collect)
        proposals = reference("pipeline-review", "proposals.md")
        for phrase in ("route only stage, close date, Amount and required-field findings", "Propose nothing", "pplx tm mail send",
                       "actual transport and delivery outcome", "never claimed delivered", "failed or ambiguous send is needs-input"):
            self.assertIn(phrase, proposals)
        self.assertIn("Every run", "\n".join(sections(proposals)["Friday"]))
        report = reference("pipeline-review", "report-format.md")
        self.assertIn("## Routed to deal threads", report)
        self.assertNotIn("Top 3", report)

    def test_triage_deal_context_and_unthreaded_opportunities_precede_local_groups(self):
        text = reference("task-triage-speed-run", "grouping.md")
        self.assertLess(text.index("## Pipeline ownership"), text.index("## Unthreaded Opportunity Tasks"))
        self.assertLess(text.index("## Unthreaded Opportunity Tasks"), text.index("## Other Tasks"))
        self.assertIn("read-only, without a message or wait", text)
        self.assertIn("Under `rules#task_date_coordination`", text)

    def test_scheduled_triage_does_not_send_before_approval(self):
        collect = reference("task-triage-speed-run", "collect.md")
        self.assertIn("Send no message and wait for no reply before proposals", collect)
        self.assertIn("An unread or incomplete thread is a blocker", collect)

    def test_scheduled_triage_deal_rows_are_pairs_or_blockers_not_date_moves(self):
        text = reference("task-triage-speed-run", "daily.md")
        self.assertIn("this one triage message, including eligible follow-up drafts", text)
        self.assertIn("Never send email. Deal context never receives a Task proposal", text)

    def test_scheduled_triage_receipt_failure_cannot_repeat_customer_writes(self):
        daily = reference("task-triage-speed-run", "daily.md")
        self.assertIn('per `references/writes.md` "Writes" receipt instructions', daily)
        text = reference("task-triage-speed-run", "writes.md")
        self.assertIn("List undelivered receipts in a follow-up line", text)
        self.assertIn("never claim delivery without success", text)
        self.assertIn("does not undo verified writes or authorize replay", text)

    def test_triage_non_deal_date_maps_keep_source_and_proposal_baseline_stale_guard(self):
        text = reference("task-triage-speed-run", "writes.md")
        for expected in ("with its quoted source per `rules#task_date_coordination`", "baseline, baseline_links and exact payload", "Immediately prewrite require fresh native reads and ready", "Never repeat verified draft creation or a verified record write"):
            self.assertIn(expected, text)

    def test_task_coordination_gives_matt_due_queue_to_triage_and_preserves_other_owner_behavior(self):
        rules = (ROOT / "_core/rules.md").read_text()
        block = rules.split('<a id="task_date_coordination">', 1)[1].split('<a id="next_steps">', 1)[0]
        for phrase in ("Triage never automatically moves dates", "same approval", "Triage changes a Task date only", "OwnerId equal to the run user", "Other writers neither create nor change them", "Other owners' Tasks keep their current workflow behavior", "Status, ActivityDate, LastModifiedDate, Description, Subject, IsClosed, WhatId and WhoId", "Triage and interaction-sync use `task_reschedule_check`", "baseline_links", "new approval", "not an atomic lock"):
            self.assertIn(phrase, block)
        self.assertIn("rules#task_date_coordination", CONTRACT_PATHS["pipeline-review"].read_text())

    def test_existing_call_close_and_pipeline_reschedules_require_nontriage_task_ownership(self):
        for skill, phrase in (("close", "Only native other-owner Tasks may be rescheduled"),):
            self.assertIn(phrase, reference(skill, "proposals.md"))
            self.assertIn("Triage owns Task <Id>", reference(skill, "proposals.md"))
        renderer = (PIPELINE / "pipeline-review/scripts/pipeline_render.py").read_text()
        self.assertIn("reuse or reschedule by exact ID before creating another", reference("interaction-sync", "proposals.md"))
        self.assertIn("pipeline-review cannot propose a Task change", renderer)
        for stale in ("CREATE_FIELDS", "TASK_KINDS", "TASK_FIELD_KINDS", "task_kinds_for", '"Next_Steps__c"))'):
            self.assertNotIn(stale, renderer)

    def test_future_dates_stale_proposals_and_satisfied_states_prevent_repeat_handling(self):
        collect = reference("task-triage-speed-run", "collect.md")
        writes = reference("task-triage-speed-run", "writes.md")
        for expected in ("IsClosed = false AND (ActivityDate <= TODAY OR ActivityDate = null)", "excludes future-dated Tasks", "Exclude it if now closed or future-dated", "Save the complete native baseline", "run `task_reschedule_check --phase proposal` before display"):
            self.assertIn(expected, collect)
        self.assertIn("Stop on changed Status, ActivityDate, LastModifiedDate, Subject or Description", writes)
        self.assertIn("Skip an already-satisfied change without another note", writes)

    def test_known_overdue_actions_and_buyer_dates_are_not_erased_to_clear_queue(self):
        grouping = reference("task-triage-speed-run", "grouping.md")
        writes = reference("task-triage-speed-run", "writes.md")
        self.assertIn("Keep the Task due or overdue when its action has not happened", grouping)
        self.assertIn("Quote the buyer's new date or moved Event", grouping)
        self.assertIn("A failing closeout", CONTRACT_PATHS["task-triage-speed-run"].read_text())
        self.assertIn("Never loosen the helper or push dates to make it pass", writes)

    def test_deal_tasks_get_one_approved_pair_or_blocker_without_delegation(self):
        daily = reference("task-triage-speed-run", "daily.md")
        walk = reference("task-triage-speed-run", "walk.md")
        self.assertIn("Never ask it to act on triage items or ask Operator", reference("task-triage-speed-run", "writes.md"))
        self.assertIn("Only a quoted buyer date or moved meeting can support a date proposal", daily)
        self.assertIn("this one triage message, including eligible follow-up drafts", daily)
        self.assertIn("`all` covers every numbered proposed row", walk)
        self.assertIn("LastModifiedDate", reference("task-triage-speed-run", "collect.md"))

    def test_watch_sync_route_and_propose_only_scope(self):
        self.assertEqual(SKILLS["watch-sync"], "pipeline")
        contract = CONTRACT_PATHS["watch-sync"].read_text()
        self.assertIn("writes: nothing", contract)
        self.assertIn("A scheduled run cannot edit other automations", contract)
        self.assertIn("No automation edit, thread create or archive, Salesforce, Gmail, or Slack write", contract)
        self.assertIn("watch-sync", (ROOT / "AGENTS.md").read_text())

    def test_watch_sync_standing_approval_excludes_deal_thread_changes(self) -> None:
        contract = CONTRACT_PATHS["watch-sync"].read_text()
        self.assertIn(
            "next: Pipeline applies watch configuration add/drop proposals after exact approval, Operator approves deal-thread create/archive proposals",
            contract,
        )
        process = "\n".join(sections(contract)["Process"])
        for expected in (
            "Pipeline applies buyer-email watch domain and channel-watch Account-list add or drop proposals after exact approval only under the adopter's verified approval.",
            "It reports one line per change and reads each one back.",
            "Deal-thread create or archive proposals still need Operator's approval and are never applied on receipt.",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, process)
        self.assertIn("Thread changes are labeled for Operator approval and are never applied on receipt", contract)

    def test_watch_scope_and_retained_thread_evidence(self):
        text = reference("watch-sync", "reconcile.md")
        for expected in ("in S1 and `policy.pipeline.stages`", "Contact Roles", "Customer_Point_of_Contact__c",
                         "policy.tooling.generic_email_domains", "same approved inventory", "all four",
                         "do not propose any archive", "Deal threads, needs Operator approval", "not applied on receipt",
                         "owned by the verified run user, the `userId` from `rules#run_start`"):
            self.assertIn(expected, text)
        # V13. watch-sync scopes by the verified run user, never by a policy-stored user id.
        self.assertNotIn("prospecting.identity.sfdc_user_id", text)
        self.assertNotIn("prospecting.identity.sfdc_user_id", (PIPELINE / "watch-sync/CONTEXT.md").read_text())

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
        for expected in ("every external call today", "same supported read", "Generate no audio", "full summary, not a shorter recap",
                         "hypothesis label", "evidence limitation", "`voice`", "without music", "without changing playback speed",
                         "configured filename", "ending is not cut off", "explicitly report the audio failure"):
            self.assertIn(expected, text)

    def test_existing_interaction_sweep_routing_keeps_verified_delivery(self):
        text = reference("interaction-sync", "sweep.md")
        for expected in ('once with `pplx tm mail send <deal-thread session id> "<message>"`',
                         "Record delivery or failure", "Never wait, sleep or poll", "Failed or ambiguous routing", "Never claim delivery without a successful send"):
            self.assertIn(expected, text)

    def test_pipeline_routing_uses_mail_once_without_wait_or_nested_commands(self):
        text = "\n".join(sections(reference("pipeline-review", "proposals.md"))["Every run"])
        for expected in ('Send once with `pplx tm mail send <deal-thread session id> "<message>"`',
                         "Never wait, sleep or poll",
                         "Run every `pplx` command as its own top-level line",
                         "never inside a script, function, loop or conditional",
                         "actual transport and delivery outcome", "failed or ambiguous send", "never claimed delivered"):
            self.assertIn(expected, text)

    def test_triage_receipts_follow_approved_writes_and_preserve_meeting_prep(self):
        text = reference("task-triage-speed-run", "daily.md")
        for expected in ("After approved writes", 'before deal receipts per `references/writes.md` "Writes" receipt instructions', "meeting_lookahead_business_days", "prep_lead_business_days", "verified Opportunity, Contact, Subject", "explicit record approval", "No reply writes nothing"):
            self.assertIn(expected, text)
        self.assertIn("receipt of at most 3 lines", reference("task-triage-speed-run", "writes.md"))
        self.assertIn("No write is automatic", reference("task-triage-speed-run", "writes.md"))

    def test_triage_meeting_prep_loads_only_on_explicit_typed_request(self):
        daily = reference("task-triage-speed-run", "daily.md")
        prep = daily.split("## Meeting preparation", 1)[1].split("## Approval and delivery", 1)[0]
        for expected in ('This section loads only on an explicit typed request such as "prep tasks". Scheduled Morning pass and delivery inputs stay as today.',
                         "Unrequested prep is not applicable, not a not-checked result, and not a notification trigger. The existing Task approval and duplicate check stay."):
            self.assertIn(expected, prep)
        contract = CONTRACT_PATHS["task-triage-speed-run"].read_text()
        row = next(line for line in contract.splitlines() if line.startswith("| Reference | `references/daily.md` |"))
        self.assertIn('"Morning pass" and "Approval and delivery", scheduled run only.', row)
        self.assertIn('"Meeting preparation" only on an explicit typed request such as `prep tasks`', row)
        self.assertNotIn("Full file, scheduled run only", row)
        self.assertNotIn("meeting_prep_tasks", (ROOT / "_core/policy.yaml").read_text())

    def test_triage_calendar_reuses_each_distinct_search_within_one_run(self):
        collect = reference("task-triage-speed-run", "collect.md")
        self.assertIn("Within one run, collect each distinct term, window, and calendar identity once and reuse the result. "
                      "Per-Task review, cap splitting, and fresh prewrite rereads stay.", collect)

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
