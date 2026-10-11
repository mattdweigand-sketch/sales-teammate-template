"""pipeline_render.py: presentation is fixed, counts reconcile, labels stay unique, and status comes from inputs."""
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workspaces" / "pipeline" / "workflows" / "pipeline-review" / "scripts" / "pipeline_render.py"
EXPECTED = Path(__file__).resolve().parent / "fixtures" / "pipeline_render_weekly.txt"
URL = "https://example.test/run"

BIO, ROUX, ROYAL, CARY = "006AAA000000001AAA", "006AAA000000002AAA", "006AAA000000003AAA", "006AAA000000004AAA"
T_BIO, T_DUP, T_ROYAL = "00TAAA000000001AAA", "00TAAA000000002AAA", "00TAAA000000003AAA"
C_JIM, C_STEVE = "003AAA000000001AAA", "003AAA000000002AAA"
RUN_USER = "005AAA000000001AAA"
OTHER_OWNER = "005BBB000000001AAA"
READY = {"ready": True, "process_status": "complete",
         "lines": ["Coverage (pipeline) · 18 in scope. Inbox complete.", "Salesforce Events matched 6/6 eligible."]}
GAP = {"ready": False, "process_status": "incomplete", "lines": ["Calendar missing: Corvid Foods."],
       "affected": ["006AAA000000003AAA"]}
# Synthetic saved results. Retrieved evidence resolves against these by id.
SAVED = {"email_results": {"emails": [
    {"email_id": "1a0d", "subject": "Plan check-in", "date": "2026-09-25T17:00:00+00:00",
     "body": "Is the plan moving, or should we pause until Q1? Pat wrote signature by 10/15."},
    {"email_id": "1a0d5e", "subject": "Corvid and Example Product next steps", "date": "2026-09-24T17:00:00+00:00",
     "web_link": "https://mail.google.com/mail/u/0/#all/1a0d5e", "body": "<p>Order form attached for&nbsp;review.</p>"}]}}
SAVED_CAL = {"calendar_event_list": {"events": [
    {"event_id": "ev1", "title": "Corvid rollout session", "start": "2026-10-01T17:00:00+00:00"}]}}


def gmail(fact, **extra):
    return {"source": "Gmail", "who": "Operator to Pat Lee", "fact": fact, "source_id": "1a0d",
            "quote": "should we pause until Q1", **extra}


def base():
    return weekly({
        "run": {"id": "fixture", "user_id": RUN_USER, "date": "2026-09-28", "branch": "friday", "coverage_scope": "pipeline",
                "process_status": "complete", "thread_url": URL, "schedule": "Fridays · 9am"},
        "counts": {"open": 43, "reviewed": 18, "not_checked": 0},
        "deals": [{"id": BIO, "name": "Acme Devices", "flags": ["next_passed"]},
                  {"id": ROUX, "name": "Beacon Labs", "flags": ["blank_field"]},
                  {"id": ROYAL, "name": "Corvid Foods", "flags": ["blank_field"]}],
        "blocks": [
            {"label": "1", "deal": BIO, "status": "proposed",
             "next_step": {"current": "Next: Pat&#39;s presentation outcome · Operator · 9/26/26",
                           "proposed": None},
             "changes": [{"object":"Opportunity","id":BIO,"field":"Deal_Type__c","current":None,"proposed":"Annual Contract"}],
             "evidence": [gmail("Asked whether the plan is moving or should pause until Q1.")]},
            {"label": "2", "deal": ROYAL, "status": "proposed",
             "next_step": {"current": "<p>9/25/26 SR - Hold the 10/1 session.<br>Sam confirmed.</p>",
                           "proposed": None},
             "changes": [{"object":"Opportunity","id":ROYAL,"field":"Customer_Type__c","current":None,"proposed":"Enterprise"}],
             "evidence": [{"source": "Gmail", "who": "Operator to Sam Rivera", "source_id": "1a0d5e",
                           "quote": "Order form attached for review.", "fact": "Order form attached."}]}],
        "questions": [
            {"label": "Q1", "deal": ROUX, "status": "open", "context": "Deal_Type__c is blank.",
             "question": "Which deal type should Beacon Labs have?", "next_step_current": None,
             "options": [{"label": "Q1-a", "text": "Annual Contract", "status": "proposed",
                          "changes": [{"object": "Opportunity", "id": ROUX, "field": "Deal_Type__c", "current": None,
                                       "proposed": "Annual Contract"}]},
                         {"label": "Q1-b", "text": "Paid Trial", "status": "proposed",
                          "changes": [{"object": "Opportunity", "id": ROUX, "field": "Deal_Type__c", "current": None,
                                       "proposed": "Paid Trial"}]}],
             "evidence": [{"date": "9/25/26", "source": "Salesforce", "fact": "Deal_Type__c is blank."}]}],
        "writes": []})


def task_create():
    return {"object": "Task", "action": "create", "who_name": "Sam Rivera",
            "linkage_verified": True, "candidates_refreshed": True,
            "fields": {"Subject": "Confirm rollout and order form next steps", "ActivityDate": "2026-10-01",
                       "Status": "Not Started", "WhoId": C_STEVE, "WhatId": ROYAL}}


def friday(data):
    data["run"].update(branch="friday", coverage_scope="pipeline", schedule="Fridays · 9am")
    data["friday"] = {
        "qualification": [],
        "rollup": {"stages": [{"stage": "S2", "count": 3, "amount": 120000}, {"stage": "S4", "count": 1, "amount": 100000}],
                   "forecast": {"Commit": 100000, "Best Case": 50000, "Pipeline": 70000, "Omitted": 0},
                   "this_quarter": {"count": 2, "amount": 150000}, "later": {"count": 2, "amount": 70000}},
        "since": "9/25", "delta": [{"kind": "Stage", "deal": BIO, "text": "S2 → S3"}],
        "letters": [{"label": "A", "deal": BIO, "deal_name": "Acme Devices", "status": "proposed",
                     "basis": "Buyer named 10/15 signature.",
                     "change": {"object": "Opportunity", "id": BIO, "field": "CloseDate", "current": "2026-09-30",
                                "proposed": "2026-10-15"},
                     "evidence": [gmail("Pat wrote signature by 10/15.")]}]}
    return data


def weekly(data):
    data=friday(data)
    data['friday']['letters']=[]
    return data

class Render(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        self.pol = self.dir / "policy.yaml"
        self.pol.write_text(yaml.safe_dump(self.policy))
        self.sources = self.dir / "calls"
        self.sources.mkdir()
        (self.sources / "output_mail.json").write_text(json.dumps(SAVED))
        (self.sources / "output_cal.json").write_text(json.dumps(SAVED_CAL))

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, mode, data, coverage=READY, *extra):
        run = self.dir / "run.json"
        run.write_text(json.dumps(data))
        args = [sys.executable, str(SCRIPT), mode, "--run", str(run), "--sources", str(self.sources), "--policy", str(self.pol)]
        if coverage is not None:
            cov = self.dir / "coverage.json"
            cov.write_text(json.dumps(coverage))
            args += ["--coverage", str(cov)]
        return subprocess.run(args + list(extra), text=True, capture_output=True)

    def test_default_sources_select_live_session_and_reject_ambiguous_sessions(self):
        home = self.dir / "home"
        live = home / ".perplexity" / "sessions" / "live" / "tool_calls" / "call_external_tool"
        shutil.copytree(self.sources, live)
        stale = self.dir / "current_session_context" / "tool_calls" / "call_external_tool"
        stale.mkdir(parents=True)
        (stale / "output_wrong.json").write_text('{"email_results": {"emails": []}}')
        run = self.dir / "run.json"
        run.write_text(json.dumps(base()))
        coverage = self.dir / "coverage.json"
        coverage.write_text(json.dumps(READY))
        arguments = [sys.executable, str(SCRIPT), "report", "--run", str(run), "--coverage", str(coverage)]
        environment = {**os.environ, "HOME": str(home)}
        result = subprocess.run(arguments, cwd=self.dir, env=environment, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, EXPECTED.read_text())
        (home / ".perplexity" / "sessions" / "other" / "tool_calls" / "call_external_tool").mkdir(parents=True)
        ambiguous = subprocess.run(arguments, cwd=self.dir, env=environment, text=True, capture_output=True)
        self.assertEqual(ambiguous.returncode, 2)
        self.assertEqual(ambiguous.stdout, "")
        self.assertIn("Multiple saved tool-call session directories", ambiguous.stderr)
        explicit = subprocess.run(arguments + ["--sources", str(self.sources), "--policy", str(self.pol)], cwd=self.dir, env=environment,
                                  text=True, capture_output=True)
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        self.assertEqual(explicit.stdout, EXPECTED.read_text())

    def ok(self, mode, data, coverage=READY, *extra):
        r = self.call(mode, data, coverage, *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def fails(self, mode, data, needle, coverage=READY, *extra):
        r = self.call(mode, data, coverage, *extra)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertEqual(r.stdout, "")
        self.assertIn(needle, r.stderr)

    # presentation
    def test_weekly_report_matches_expected_output(self):
        self.assertEqual(self.ok("report", base()), EXPECTED.read_text())

    def test_routed_section_counts_separately_and_marks_top_priority(self):
        data = base()
        data["deals"] = [row for row in data["deals"] if row["id"] != BIO]
        data["blocks"] = [row for row in data["blocks"] if row["deal"] != BIO]
        data["routed"] = [{"kind": "deal_context", "deal": BIO, "name": "Acme Devices", "thread_url": "https://example.test/deal",
                           "reason": "Current action belongs to the deal thread",
                           "delivery": {"command": "mail_send", "status": "delivered"}}]
        data["today_actions"] = [{"deal": BIO, "name": "Acme Devices", "kind": "due", "date": "2026-09-28",
                                  "reason": "Review the overdue follow-up", "evidence": [
                                      {"source": "Salesforce", "date": "9/28/26", "who": "Operator",
                                       "title": "Open Task", "fact": "Follow-up is due today"}]}]
        out = self.ok("report", data)
        self.assertIn("18 reviewed · 2 flagged · 1 clear recommendation", out)
        self.assertIn("## Routed to deal threads\n\n1 routed · counted separately", out)
        self.assertIn("[Acme Devices](https://example.test/deal) · Current action belongs to the deal thread", out)
        self.assertIn("routed via mail_send", out)
        self.assertNotIn("Top 3", out)
        self.assertIn("15 reviewed deals had no trigger", out)
        self.assertNotIn("1. [Acme Devices]", out)

    def test_routed_records_reject_local_proposals_and_double_counts(self):
        data = base()
        data["routed"] = [{"kind": "deal_context", "deal": BIO, "name": "Acme Devices", "thread_url": "https://example.test/deal",
                           "reason": "Owned elsewhere", "delivery": {"command": "mail_send", "status": "delivered"}}]
        self.fails("report", data, "routed deals must be counted separately")
        data["deals"] = [row for row in data["deals"] if row["id"] != BIO]
        self.fails("report", data, "routed deal is owned elsewhere; propose nothing here")

    def test_routed_rows_require_unique_ids_links_and_complete_counts(self):
        data = base()
        row = {"kind": "deal_context", "deal": CARY, "name": "Delta Labs", "thread_url": "https://example.test/deal", "reason": "Owned elsewhere",
               "delivery": {"command": "mail_send", "status": "delivered"}}
        data["routed"] = [row, copy.deepcopy(row)]
        self.fails("report", data, "routed: each deal appears once")
        data["routed"] = [row]
        row["thread_url"] = ""
        self.fails("report", data, "routed needs an https deal-thread link")
        row["thread_url"] = "https://example.test/deal"
        data["counts"]["reviewed"] = 3
        self.fails("report", data, "plus routed 1")

    def test_routed_friday_records_reject_letters(self):
        data = friday(base())
        data["routed"] = [{"kind": "deal_context", "deal": data["friday"]["letters"][0]["deal"], "name": "Acme Devices",
                           "thread_url": "https://example.test/deal", "reason": "Owned elsewhere",
                           "delivery": {"command": "mail_send", "status": "delivered"}}]
        result = self.call("report", data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("routed deal is owned elsewhere; propose nothing here", result.stderr)

    def test_routed_delivery_requires_object_and_exact_command_and_status(self):
        data = base()
        row = {"kind": "deal_context", "deal": CARY, "name": "Delta Labs", "thread_url": "https://example.test/deal", "reason": "Owned elsewhere"}
        data["routed"] = [row]
        self.fails("report", data, "routed needs a delivery object")
        for delivery, error in ((None, "delivery object"), ([], "delivery object"),
                                ({}, "delivery.command"), ({"command": "unknown", "status": "delivered"}, "delivery.command"),
                                ({"command": "mail_send"}, "delivery.status"),
                                ({"command": "mail_send", "status": "pending"}, "delivery.status")):
            with self.subTest(delivery=delivery):
                row["delivery"] = delivery
                self.fails("report", data, error)
        for command in ("session_send", "pplx session send"):   # retired 10/10/26, never an active enum value
            with self.subTest(command=command):
                row["delivery"] = {"command": command, "status": "delivered"}
                self.fails("report", data, "delivery.command must be mail_send")
        row["delivery"] = {"command": "mail_send", "status": "delivered"}
        self.assertIn("routed via mail_send", self.ok("report", data))

    def test_failed_delivery_is_needs_input_not_routed_or_no_trigger(self):
        data = base()
        data["routed"] = [{"kind": "deal_context", "deal": CARY, "name": "Delta Labs", "thread_url": "https://example.test/deal",
                           "reason": "Both transports rejected delivery", "delivery": {"command": "mail_send", "status": "failed"}}]
        out = self.ok("report", data)
        routed, rest = out.split("## Routed to deal threads\n\n", 1)[1].split("## Clear recommendations", 1)
        self.assertEqual(routed, "None.\n\n")
        needs_input = rest.split("## Needs your input", 1)[1].split("## Coverage", 1)[0]
        self.assertIn("[Delta Labs](https://example.test/deal) · routing failed, needs input · mail_send", needs_input)
        self.assertIn("14 reviewed deals had no trigger", out)
        self.assertNotIn("routed via mail_send", out)
        data["counts"]["reviewed"] = 3
        self.fails("report", data, "plus routed 1")

    def test_mixed_delivery_statuses_count_only_successes_as_routed(self):
        data = base()
        data["routed"] = [{"kind": "deal_context", "deal": CARY, "name": "Delta Labs", "thread_url": "https://example.test/delta",
                           "reason": "Thread owns action", "delivery": {"command": "mail_send", "status": "delivered"}},
                          {"kind": "deal_context", "deal": "006AAA000000005AAA", "name": "Finch Systems", "thread_url": "https://example.test/finch",
                           "reason": "Send rejected", "delivery": {"command": "mail_send", "status": "failed"}}]
        out = self.ok("report", data)
        self.assertIn("1 routed · counted separately", out)
        self.assertIn("[Delta Labs](https://example.test/delta) · Thread owns action · routed via mail_send", out)
        self.assertIn("[Finch Systems](https://example.test/finch) · routing failed, needs input · mail_send", out)
        self.assertIn("13 reviewed deals had no trigger", out)

    def test_failed_delivery_never_suppresses_notification_on_either_branch(self):
        for branch in ("weekday", "friday"):
            with self.subTest(branch=branch):
                data = base() if branch == "weekday" else friday(base())
                data["deals"], data["blocks"], data["questions"] = [], [], []
                if branch == "friday":
                    data["friday"]["letters"] = []
                data["routed"] = [{"kind": "deal_context", "deal": CARY, "name": "Delta Labs", "thread_url": "https://example.test/deal",
                                   "reason": "Send rejected", "delivery": {"command": "mail_send", "status": "failed"}}]
                result = json.loads(self.ok("notification", data))
                self.assertTrue(result["send"])
                self.assertEqual(result["status"], "incomplete")
                self.assertIn("Needs input · 1 failed delivery", result["body"])
                self.assertIn("routing failed, needs input", self.ok("report", data))

    def test_failed_delivery_keeps_local_proposals_blocked(self):
        data = base()
        data["routed"] = [{"kind": "deal_context", "deal": BIO, "name": "Acme Devices", "thread_url": "https://example.test/deal",
                           "reason": "Send rejected", "delivery": {"command": "mail_send", "status": "failed"}}]
        data["deals"] = [row for row in data["deals"] if row["id"] != BIO]
        self.fails("report", data, "routed deal is owned elsewhere; propose nothing here")




    def test_readonly_task_finding_covers_flag_without_an_approval(self):
        data = base()
        data["blocks"] = [block for block in data["blocks"] if block["deal"] != BIO]
        data["triage"] = [{"deal": BIO, "name": "Acme Devices", "reason": "Missing current-action Task",
                           "triage_task_gap": True}]
        report = self.ok("report", data)
        self.assertIn("## Triage owns Tasks", report)
        self.assertIn("Triage owns the Task gap", report)
        self.assertIn("3 flagged · 1 clear recommendation · 1 question", report)
        self.assertNotIn("New Task", report)

    def test_mixed_context_delivery_and_task_finding_counts_deal_once(self):
        data = base()
        data["deals"] = [deal for deal in data["deals"] if deal["id"] != BIO]
        data["blocks"] = [block for block in data["blocks"] if block["deal"] != BIO]
        data["triage"] = [{"deal": BIO, "name": "Acme Devices", "reason": "Task date mismatch",
                           "triage_owned_task": {"Id": T_BIO, "OwnerId": RUN_USER, "IsClosed": False,
                                                 "ActivityDate": "2026-09-28"}}]
        data["routed"] = [{"kind": "deal_context", "deal": BIO, "name": "Acme Devices",
                           "thread_url": "https://example.test/deal", "reason": "Stage evidence",
                           "delivery": {"command": "mail_send", "status": "delivered"}}]
        report = self.ok("report", data)
        self.assertIn("1 routed · counted separately", report)
        self.assertIn("Triage owns Task " + T_BIO, report)
        self.assertIn("15 reviewed deals had no trigger", report)
        self.assertEqual(report.count("routed via mail_send"), 1)

    def test_task_findings_cannot_use_deal_thread_delivery(self):
        for kind in (None, "task", "task_gap", "deal_context\n"):
            with self.subTest(kind=kind):
                data = base()
                data["routed"] = [{"kind": kind, "deal": CARY, "name": "Delta Labs",
                                   "reason": "Task issue", "thread_url": "https://example.test/deal",
                                   "delivery": {"command": "mail_send", "status": "delivered"}}]
                self.fails("report", data, "routed.kind must be deal_context")

    def test_readonly_triage_findings_reject_write_approval_and_delivery_paths(self):
        for forbidden in ("changes", "label", "delivery"):
            with self.subTest(forbidden=forbidden):
                data = base()
                data["triage"] = [{"deal": BIO, "name": "Acme Devices", "reason": "Task gap",
                                   "triage_task_gap": True, forbidden: []}]
                self.fails("report", data, "no writes, delivery commands or approval labels")
        for rows, error in (({}, "read-only list"), ([None], "entries must be objects"),
                            ([{"deal": [], "name": "Acme", "reason": "Gap", "triage_task_gap": True}],
                             "not a valid Opportunity Id")):
            data = base()
            data["triage"] = rows
            self.fails("report", data, error)

    def test_triage_finding_rejects_future_foreign_and_unreadable_task_owner(self):
        for owner, due, error in ((RUN_USER, "2026-10-02", "future Tasks never enter triage findings"),
                                  (OTHER_OWNER, None, "must be a Operator-owned open Task"),
                                  (None, None, "needs-input")):
            with self.subTest(owner=owner, due=due):
                data = base()
                data["triage"] = [{"deal": BIO, "name": "Acme Devices", "reason": "Task issue",
                                   "triage_owned_task": {"Id": T_DUP, "OwnerId": owner,
                                                         "IsClosed": False, "ActivityDate": due}}]
                self.fails("report", data, error)

    def test_gap_handoff_rejects_false_marker_missing_user_and_existing_task(self):
        for patch, error in (({"triage_task_gap": False}, "triage_task_gap must be true"),
                             ({"triage_task_gap": True, "followup_task": T_DUP}, "alternative ownership paths")):
            data = base()
            data["blocks"][0].update(changes=[], **patch)
            self.fails("report", data, error)
        data = base()
        data["blocks"][0].update(changes=[], triage_task_gap=True)
        del data["run"]["user_id"]
        self.fails("report", data, "readable native run.user_id required")

    def test_evidence_labels_use_returned_links_only(self):
        out = self.ok("report", base())
        self.assertIn("· [Corvid and Example Product next steps](https://mail.google.com/mail/u/0/#all/1a0d5e) ·", out)
        self.assertIn('· "Plan check-in" ·', out)
        self.assertNotIn("1a0d ", out)
        data = base()
        data["blocks"][0]["evidence"] = [{"date": "9/25/26", "source": "Salesforce", "title": "Task",
                                          "link": "mail.google.com/constructed", "fact": "Logged."}]
        self.fails("report", data, "link must be a returned https URL")

    def test_retrieved_evidence_resolves_from_saved_records(self):
        out = self.ok("report", base())
        self.assertIn('- 9/25/26 · Gmail · Operator to Pat Lee · "Plan check-in" ·', out)
        self.assertNotIn("should we pause until Q1\"", out)
        for change, needle in (({"source_id": "nope"}, "is not in this run's saved Gmail results"),
                               ({"title": "Edited subject"}, "title must come from the saved Gmail record"),
                               ({"date": "9/25/26"}, "date must come from the saved Gmail record"),
                               ({"link": "https://example.test/forged"}, "link must come from the saved Gmail record"),
                               ({"quote": None}, "needs a quote of at least 12 characters"),
                               ({"quote": "we should sign today"}, "quote is not in the saved message body")):
            data = base()
            data["blocks"][0]["evidence"][0].update(change)
            self.fails("report", data, needle)
        data = base()
        data["blocks"][1]["evidence"].append({"source": "Calendar", "who": "Sam Rivera", "source_id": "ev1",
                                               "fact": "Session scheduled."})
        self.assertIn('- 10/1/26 · Calendar · Sam Rivera · "Corvid rollout session" · Session scheduled.',
                      self.ok("report", data))

    def test_caller_resolved_marker_cannot_bypass_saved_evidence_checks(self):
        for value in (True, False):
            for source in ("Gmail", "Calendar"):
                with self.subTest(value=value, source=source):
                    data = base()
                    data["blocks"][0]["evidence"][0].update(
                        source=source, _resolved=value, source_id="fabricated", quote="fabricated quote",
                        date="9/25/26", title="Forged title", link="https://example.test/forged")
                    self.fails("report", data, "_resolved is internal; remove it from the run file")

    def test_resolution_and_rerender_are_idempotent_without_mutating_input(self):
        spec = importlib.util.spec_from_file_location("pipeline_render_idempotency", SCRIPT)
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        policy = renderer.yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        sources = renderer.load_sources(self.sources)
        data = base()
        data["blocks"][1]["evidence"].append({"source": "Calendar", "who": "Sam Rivera", "source_id": "ev1",
                                               "fact": "Session scheduled."})
        original = copy.deepcopy(data)
        run = renderer.Run(data, policy, READY, sources)
        self.assertEqual(run.validate("report"), [])
        first = run.report()
        self.assertEqual(run.validate("report"), [])
        self.assertEqual(run.report(), first)
        self.assertEqual(data, original)
        rerun = renderer.Run(data, policy, READY, sources)
        self.assertEqual(rerun.validate("report"), [])
        self.assertEqual(rerun.report(), first)
        self.assertNotIn("_resolved", json.dumps(run.data))

    def test_empty_sections_and_no_action_run(self):
        data = base()
        data.update(deals=[], blocks=[], questions=[])
        out = self.ok("report", data)
        self.assertIn("## Clear recommendations\n\nNo clear recommendations.", out)
        self.assertIn("## Needs your input\n\nNo questions.", out)
        self.assertTrue(out.rstrip().endswith("No Salesforce changes proposed."))
        self.assertIn("18 reviewed deals had no trigger · 0 not checked", out)
        self.assertNotIn("Only the latest next-step entry", out)
        note = json.loads(self.ok("notification", data))
        self.assertEqual(note["send"], True)
        self.assertEqual(note["status"], "complete")

    def test_slack_evidence_renders_message_date_permalink_and_limitation(self):
        data = base()
        slack = {"source": "Slack", "date": "9/28/26", "who": "Pat Lee", "title": "Buyer status",
                 "link": "https://example.slack.com/archives/CEXAMPLE/p1790611200000000",
                 "fact": "Buyer confirmed legal review is complete."}
        data["blocks"][0]["evidence"] = [slack, dict(slack, fact="Buyer named the next action.")]
        out = self.ok("report", data)
        section = out.split("## Clear recommendations\n", 1)[1].split("## Needs your input", 1)[0]
        self.assertIn("9/28/26 · Slack · Pat Lee · [Buyer status](" + slack["link"] + ")", section)
        self.assertEqual(section.count("Email, Calendar, and Slack evidence is the retrieved set, not full history."), 1)
        data["questions"][0]["evidence"] = [slack]
        question = self.ok("question", data, READY, "--label", "Q1")
        self.assertIn(slack["link"], question)
        self.assertEqual(question.count("Email, Calendar, and Slack evidence is the retrieved set, not full history."), 1)
        friday(data)["friday"]["letters"][0]["evidence"] = [slack]
        section = self.ok("report", data).split("## Record proposals\n", 1)[1].split("## Coverage", 1)[0]
        self.assertIn(slack["link"], section)
        self.assertEqual(section.count("Email, Calendar, and Slack evidence is the retrieved set, not full history."), 1)

    def test_slack_evidence_requires_message_metadata(self):
        slack = {"source": "Slack", "date": "9/28/26", "who": "Pat Lee", "title": "Buyer status",
                 "link": "https://example.slack.com/archives/CEXAMPLE/p1790611200000000",
                 "fact": "Buyer confirmed legal review is complete."}
        for missing in ("who", "title", "link"):
            data = base()
            data["blocks"][0]["evidence"] = [{key: value for key, value in slack.items() if key != missing}]
            self.fails("report", data, "Slack evidence needs a sender, title, and returned permalink")
        for missing in ("date", "fact"):
            data = base()
            data["blocks"][0]["evidence"] = [{key: value for key, value in slack.items() if key != missing}]
            self.fails("report", data, "date and fact are required")
        data = base()
        data["blocks"][0]["evidence"] = [dict(slack, link="constructed/slack/link")]
        self.fails("report", data, "link must be a returned https URL")

    def test_required_evidence_gap_keeps_run_incomplete_even_when_checker_is_ready(self):
        data = base()
        gap = "Gmail body read for Acme Devices failed."
        data["run"].update(process_status="incomplete", process_gaps=[gap])
        data["withheld"] = [{"deal": BIO, "reason": gap}]
        data["blocks"] = data["blocks"][1:]
        out = self.ok("report", data)
        self.assertIn("Incomplete · 1 withheld", out)
        self.assertIn("Run incomplete · " + gap, out)
        self.assertNotIn("1. [Acme Devices]", out)
        note = json.loads(self.ok("notification", data))
        self.assertEqual((note["send"], note["status"]), (True, "incomplete"))
        self.assertIn("Incomplete · 1 withheld · Acme Devices", note["body"])
        self.assertIn("https://example.test/run", note["body"])

    def test_missing_slack_users_or_evidence_do_not_gate_proposals(self):
        for reason in ("No verified Slack users", "No Slack evidence in the retrieved window"):
            with self.subTest(reason=reason):
                data = base()
                before = self.ok("report", data)
                notification = self.ok("notification", data)
                data["run"]["slack_coverage_notes"] = [
                    {"deal": BIO, "name": "Acme Devices", "contacts": ["Pat Lee", "Alex Smith", "Pat Lee"],
                     "reason": reason}]
                out = self.ok("report", data)
                self.assertIn("1. [Acme Devices]", out)
                self.assertIn("2. [Corvid Foods]", out)
                self.assertNotIn("Incomplete", out)
                self.assertNotIn("Withheld", out)
                self.assertEqual(out.split("\n")[2], before.split("\n")[2])
                coverage = out.split("## Coverage\n", 1)[1]
                self.assertEqual(coverage.count("Slack not checked"), 1)
                self.assertIn("Pat Lee, Alex Smith · " + reason, coverage)
                self.assertIn("0 not checked", coverage)
                self.assertEqual(self.ok("notification", data), notification)

    def test_slack_coverage_notes_preserve_clean_notification(self):
        for branch in ("weekday", "friday"):
            with self.subTest(branch=branch):
                data = friday(base()) if branch == "friday" else base()
                data.update(deals=[], blocks=[], questions=[])
                if branch == "friday":
                    data["friday"]["letters"] = []
                notification = self.ok("notification", data)
                data["run"]["slack_coverage_notes"] = [
                    {"deal": BIO, "name": "Acme Devices", "contacts": ["Pat Lee"], "reason": "No Slack user"}]
                self.assertIn("Slack not checked", self.ok("report", data))
                self.assertEqual(self.ok("notification", data), notification)

    def test_verified_slack_search_error_holds_only_status_change(self):
        data = base()
        data["blocks"][0]["next_step"]["proposed"] = None
        limitation = "Buyer legal status is unverified because the verified Slack user's search errored."
        data["questions"].append(
            {"label": "Q2", "deal": BIO, "status": "open", "context": limitation,
             "question": "What is the buyer's current legal status after the Slack search is repaired?",
             "next_step_current": data["blocks"][0]["next_step"]["current"], "options": [],
             "evidence": [{"source": "Salesforce", "date": "9/28/26", "fact": "Saved next step needs a status check."}]})
        data["run"]["slack_coverage_notes"] = [
            {"deal": BIO, "name": "Acme Devices", "contacts": ["Pat Lee"], "reason": limitation}]
        out = self.ok("report", data)
        clear, needs = out.split("## Clear recommendations\n", 1)[1].split("## Needs your input", 1)
        self.assertIn("1. [Acme Devices]", clear)
        self.assertIn("Deal_Type__c", clear)
        self.assertIn("2. [Corvid Foods]", clear)
        self.assertNotIn(limitation, clear)
        self.assertIn("Q2 · [Acme Devices]", needs)
        self.assertIn(limitation, needs)
        self.assertNotIn("Withheld", out)
        self.assertNotIn("Incomplete", out)
        question = self.ok("question", data, READY, "--label", "Q2")
        self.assertIn(limitation, question)
        self.assertNotIn("Q2-a", question)
        self.assertEqual(json.loads(self.ok("notification", data))["status"], "incomplete")

    def test_fresh_slack_fact_supports_proposal_despite_other_missing_user(self):
        data=base()
        data['blocks'][0]['evidence']=[{'source':'Slack','date':'9/28/26','who':'Fixture buyer',
            'title':'Deal type confirmed','link':'https://example.test/slack/message','fact':'Buyer confirmed Annual Contract.'}]
        data['run']['slack_coverage_notes']=[{'deal':BIO,'name':'Acme Devices','contacts':['Other fixture contact'],'reason':'No Slack user'}]
        output=self.ok('report',data)
        self.assertIn('1. [Acme Devices]',output)
        self.assertIn('Buyer confirmed Annual Contract',output)
        self.assertIn('Slack not checked',output)

    def test_slack_coverage_notes_validate_shape_and_one_line_per_deal(self):
        valid = {"deal": BIO, "name": "Acme Devices", "contacts": ["Pat Lee"], "reason": "No Slack user"}
        cases = [({}, "must be a list"), ([None], "must be objects"),
                 ([dict(valid, deal="invalid")], "not a valid Opportunity Id"),
                 ([valid, valid], "one Slack coverage note per deal"),
                 ([dict(valid, name="Wrong deal")], "name must match"),
                 ([dict(valid, name="Acme\nDevices")], "one-line name"),
                 ([dict(valid, reason="")], "one-line reason"),
                 ([dict(valid, reason="No Slack\nuser")], "one-line reason"),
                 ([dict(valid, contacts=[])], "nonempty list"),
                 ([dict(valid, contacts=["Pat\nLee"])], "one-line names")]
        for notes, message in cases:
            with self.subTest(notes=notes):
                data = base()
                data["run"]["slack_coverage_notes"] = notes
                self.fails("report", data, message)

    def test_friday_report_sections_and_letters(self):
        out = self.ok("report", friday(base()))
        self.assertIn("## Rollup\nS2 3 · $120,000 | S4 1 · $100,000", out)
        self.assertIn("## Since 9/25\n- Stage · [Acme Devices]", out)
        self.assertIn("## Record proposals\nA. [Acme Devices](https://crm.example.invalid/lightning/r/Opportunity/"
                      "006AAA000000001AAA/view) · Opportunity · CloseDate · 2026-09-30 → 2026-10-15", out)
        self.assertTrue(out.rstrip().endswith("Each letter approves one record.**"))

    def test_letters_are_friday_only(self):
        data = friday(base())
        data["run"].update(branch="weekday", coverage_scope="pipeline-daily")
        self.fails("report", data, "lettered record proposals are Friday only")

    # counts
    def test_deal_with_clear_block_and_question(self):
        data = base()
        data["questions"].append({"label": "Q2", "deal": BIO, "status": "open", "context": "A second Task has the same action.",
                                  "question": "Close the duplicate Task?", "next_step_current": None,
                                  "options": [{"label": "Q2-a", "text": "Close it as superseded", "status": "proposed",
                                               "changes": []}],
                                  "evidence": [{"date": "9/28/26", "source": "Salesforce", "fact": "Two open Tasks."}]})
        out = self.ok("report", data)
        self.assertIn("3 flagged · 2 clear recommendations · 2 questions", out)

    def test_flagged_deal_without_block_or_question_fails(self):
        data = base()
        data["deals"].append({"id": CARY, "name": "Delta Holdings", "flags": ["next_passed"]})
        self.fails("report", data, "flagged deals with no clear recommendation")

    def test_depends_on_unknown_is_a_question(self):
        data = base()
        data["blocks"][0]["depends_on_unknown"] = True
        self.fails("report", data, "move it to Needs your input")

    # coverage and status
    def test_incomplete_coverage_requires_withheld_and_marks_report(self):
        data = base()
        self.fails("report", data, "list withheld proposals", GAP)
        data["withheld"] = [{"deal": ROYAL, "reason": "Calendar not read."}]
        data["blocks"] = data["blocks"][:1]
        out = self.ok("report", data, GAP)
        self.assertIn("Incomplete · 1 withheld · [Corvid Foods](", out)
        self.assertIn("## Coverage\n\nCalendar missing: Corvid Foods.  \nWithheld · [Corvid Foods]", out)
        note = json.loads(self.ok("notification", data, GAP))
        self.assertEqual((note["send"], note["status"]), (True, "incomplete"))
        self.assertIn("Incomplete · 1 withheld", note["body"])
        self.assertIn("Corvid Foods", note["body"])

    def test_incomplete_coverage_with_nothing_withheld_says_so(self):
        """The header states the withholding that happened, never a withholding that did not."""
        data = base()
        data["withheld"] = []
        out = self.ok("report", data, dict(GAP, affected=[]))
        self.assertIn("Incomplete · 0 withheld · Details under Coverage.", out)
        self.assertNotIn("affected proposals withheld", out)

    def test_coverage_receipts_stay_in_the_saved_file(self):
        cov = dict(READY, lines=READY["lines"] + ['Domain-matched email receipts: [{"email_id": "1a0d"}]',
                                                   "input_x.json: ignored non-collection Opportunity scope", "Coverage ready."])
        out = self.ok("report", base(), cov)
        self.assertIn("Salesforce Events matched 6/6 eligible.", out)
        for hidden in ("Domain-matched", "ignored non-collection", "Coverage ready."):
            self.assertNotIn(hidden, out)

    def test_per_file_coverage_lines_collapse_to_one_count(self):
        cov = dict(GAP, lines=GAP["lines"] + ["input_a.json: paginated query restarted before consuming its cursor",
                                               "input_b.json: paginated query restarted before consuming its cursor",
                                               "Email pagination incomplete", "Email pagination incomplete"])
        data = base()
        data["withheld"] = [{"deal": ROYAL, "reason": "Calendar not read."}]
        data["blocks"] = data["blocks"][:1]
        out = self.ok("report", data, cov)
        body = json.loads(self.ok("notification", data, cov))["body"]
        self.assertNotIn("input_a.json", out)
        self.assertEqual(out.count("Email pagination incomplete"), 1)
        self.assertIn("2 per-file diagnostics kept in the saved coverage file.", out)
        for checker_text in ("input_a.json", "Email pagination incomplete", "per-file"):
            self.assertNotIn(checker_text, body)

    def test_affected_deals_must_be_withheld(self):
        data = base()
        data["withheld"] = []
        self.fails("report", data, "coverage affects Corvid Foods", GAP)
        unknown = {k: v for k, v in GAP.items() if k != "affected"}
        data["withheld"] = [{"deal": ROYAL, "reason": "Calendar not read."}]
        data["blocks"] = data["blocks"][:1]
        self.fails("report", data, "coverage affects Acme Devices", unknown)

    def test_coverage_scope_must_match_branch(self):
        data = base()
        data["run"]["coverage_scope"] = "pipeline-daily"
        self.fails("report", data, "coverage_scope must be pipeline for friday")

    def test_weekday_notification_with_actions(self):
        note = json.loads(self.ok("notification", base()))
        self.assertEqual(note["send"], True)
        self.assertEqual(note["title"], "Friday pipeline review incomplete")
        self.assertEqual(note["body"], "Needs input · 1 open question · 43 open deals · 18 reviewed · 3 flagged · 2 clear recommendations · 1 question · "
                                       "0 records written · " + URL)
        self.assertEqual(note["schedule_description"], "Fridays · 9am")

    def test_friday_notification_states(self):
        data = friday(base())
        note = json.loads(self.ok("notification", data))
        self.assertEqual(note["title"], "Friday pipeline review incomplete")
        self.assertIn("Needs input · 1 open question", note["body"])
        data["questions"] = []
        data["deals"] = [d for d in data["deals"] if d["id"] != ROUX]
        self.assertEqual(json.loads(self.ok("notification", data))["title"], "Friday pipeline review ready for approval")
        data.update(deals=[], blocks=[])
        data["friday"]["letters"] = []
        self.assertEqual(json.loads(self.ok("notification", data))["title"], "Friday pipeline review complete")
        data["run"].update(process_status="incomplete", process_gaps=["Gmail thread read for Beacon Labs timed out twice."])
        note = json.loads(self.ok("notification", data))
        self.assertEqual(note["title"], "Friday pipeline review incomplete")
        self.assertIn("Run incomplete · Gmail thread read for Beacon Labs timed out twice.", note["body"])

    def test_render_success_never_makes_incomplete_process_ready(self):
        data = base()
        self.fails("report", dict(data, run=dict(data["run"], process_status="incomplete")), "process_gaps must name")

    # labels
    def test_duplicate_labels_fail(self):
        data = base()
        data["blocks"][1]["label"] = "1"
        self.fails("report", data, "label 1 is already used")
        data = base()
        data["questions"][0]["options"][1]["label"] = "Q1-a"
        self.fails("report", data, "label Q1-a is already used")

    def test_revised_option_gets_new_label_and_old_is_hidden(self):
        data = base()
        q = data["questions"][0]
        q["options"][0].update(status="superseded", superseded_by="Q1-c")
        q["options"].append({"label": "Q1-c", "text": "Annual Contract, 12 months", "status": "proposed",
                             "changes": [{"object": "Opportunity", "id": ROUX, "field": "Deal_Type__c", "current": None,
                                          "proposed": "Annual Contract"}]})
        out = self.ok("question", data, None, "--label", "Q1")
        self.assertIn("- Q1-c · Annual Contract, 12 months", out)
        self.assertNotIn("Q1-a", out)
        self.assertIn("**Reply Q1-b, Q1-c, or skip.", out)
        q["options"][0]["superseded_by"] = None
        self.fails("question", data, "superseded_by must name the new label", None, "--label", "Q1")

    def test_question_mode_shows_exact_changes_and_skip(self):
        out = self.ok("question", base(), None, "--label", "Q1")
        self.assertTrue(out.startswith("Q1 · 1 of 1 · [Beacon Labs]"))
        self.assertIn("- Q1-a · Annual Contract\n  - Opportunity · Deal_Type__c · Empty → Annual Contract", out)
        self.assertIn("- skip · Leave unchanged. Named at close.", out)
        self.assertIn("### Current next steps\nEmpty", out)

    def test_duplicate_record_and_field_across_block_and_letter(self):
        data = friday(base())
        data["friday"]["letters"][0]["change"] = copy.deepcopy(data["blocks"][0]["changes"][0])
        self.fails("report", data, "is already proposed in block 1")

    def test_block_deal_can_still_get_a_different_friday_letter(self):
        self.assertIn("· Opportunity · CloseDate", self.ok("report", friday(base())))











    # tasks



    def test_opportunity_fields_are_limited_by_branch(self):
        """Numbered blocks and options carry next steps and policy required fields; CloseDate, StageName, Amount are Friday letters."""
        data = base()
        data["blocks"][0]["changes"].append({"object": "Opportunity", "id": BIO, "field": "OwnerId", "current": "005A", "proposed": "005B"})
        self.fails("report", data, "Opportunity OwnerId is not a permitted change for any proposal here")
        data = base()
        data["blocks"][0]["changes"].append({"object": "Opportunity", "id": BIO, "field": "CloseDate", "current": "2026-09-30", "proposed": "2026-10-15"})
        self.fails("report", data, "Opportunity CloseDate is not a permitted change for a Friday letter")
        data = friday(base())
        data["friday"]["letters"][0]["change"]["field"] = "OwnerId"
        self.fails("report", data, "Opportunity OwnerId is not a permitted change")
        self.ok("report", friday(base()))



















    # writes
    def test_partial_write_receipt(self):
        data=base()
        data['blocks'][0]['status']='partial'
        data['blocks'][0]['changes'].append({'object':'Opportunity','id':BIO,'field':'LeadSource','current':None,'proposed':'Event'})
        data['writes']=[{'label':'1','object':'Opportunity','id':BIO,'field':'Deal_Type__c','outcome':'written'},
                        {'label':'1','object':'Opportunity','id':BIO,'field':'LeadSource','outcome':'rejected','detail':'Native validation rejected the value'}]
        output=self.ok('receipt',data,None)
        self.assertIn('partial',output)
        self.assertIn('1 of 2 changes written',output)
        self.assertIn('- Rejected · [Opportunity]',output)
        self.assertNotIn('· written\n',output)

    def test_fields_on_one_record_count_once(self):
        data = base()
        data["blocks"][1]["status"] = "written"
        complete = data["blocks"][1]["changes"][0]
        data["blocks"][1]["changes"] = [complete, dict(complete, field="LeadSource", proposed="Event")]
        data["writes"] = [{"label": "2", "object": "Opportunity", "id": ROYAL, "field": f, "outcome": "written"}
                          for f in ("Customer_Type__c", "LeadSource")]
        self.assertIn("1 record written · 0 rejected", self.ok("receipt", data, None))

    def test_repeated_successful_write_fails(self):
        data = base()
        data["blocks"][0]["status"] = "written"
        w = {"label": "1", "object": "Opportunity", "id": BIO, "field": "Deal_Type__c", "outcome": "written"}
        data["writes"] = [w, dict(w)]
        self.fails("receipt", data, "never repeat a successful write", None)

    def test_write_on_superseded_or_unapproved_label_fails(self):
        data = base()
        data["writes"] = [{"label": "1", "object": "Opportunity", "id": BIO, "field": "Deal_Type__c", "outcome": "written"}]
        self.fails("receipt", data, "only approved labels are written", None)

    def test_option_write_and_final_close(self):
        data=base()
        data['blocks'][0]['status']='written'
        data['blocks'][1]['status']='skipped'
        data['questions'][0]['status']='answered'
        data['questions'][0]['options'][0]['status']='written'
        data['writes']=[{'label':'1','object':'Opportunity','id':BIO,'field':'Deal_Type__c','outcome':'written'},
            {'label':'Q1-a','object':'Opportunity','id':ROUX,'field':'Deal_Type__c','outcome':'written'}]
        output=self.ok('receipt',data,None,'--final')
        self.assertIn('2 records written',output)
        self.assertIn('Skipped · 2',output)

    def test_approved_block_without_writes_is_named_in_final_receipt(self):
        """An approved block that was never attempted must appear, not vanish."""
        data = base()
        data["blocks"][0]["status"] = "approved"
        data["writes"] = []
        out = self.ok("receipt", data, None, "--final")
        self.assertIn("1 · [Acme Devices]", out)
        self.assertIn("· approved, not attempted\n", out)
        self.assertIn("- Not attempted · [Opportunity]", out)
        self.assertIn("- Not attempted · [Opportunity]", out)
        self.assertIn("0 records written · 0 rejected · 0 unverified · 1 not attempted", out)
        self.assertIn("Approved, not attempted · 1 · [Acme Devices]", out)
        # Without --final the receipt still reports only recorded writes.
        self.assertNotIn("Acme Devices", self.ok("receipt", data, None))

    # audit gaps
    def test_receipt_reconciles_against_approved_changes(self):
        data = base()
        data["blocks"][0]["status"] = "partial"
        data["blocks"][0]["changes"].append({"object": "Opportunity", "id": BIO, "field": "LeadSource", "current": None, "proposed": "Event"})
        data["writes"] = [{"label": "1", "object": "Opportunity", "id": BIO, "field": "Deal_Type__c", "outcome": "written"}]
        out = self.ok("receipt", data, None, "--labels", "1")
        self.assertIn("1 · [Acme Devices]", out)
        self.assertIn("· partial\n", out)
        self.assertIn("- Not attempted · [Opportunity]", out)
        self.assertIn("0 records written · 0 rejected · 0 unverified · 1 not attempted", out)
        data["writes"].append({"label": "1", "object": "Opportunity", "id": ROUX, "field": "Deal_Type__c", "outcome": "written"})
        self.fails("receipt", data, "is not an approved change of 1", None)

    def test_every_proposed_record_is_named(self):
        data = friday(base())
        del data["friday"]["letters"][0]["deal_name"]
        self.fails("report", data, "deal_name is required")
        data = base()
        data["blocks"][1]["changes"].append({"object": "Opportunity", "id": BIO, "field": "Deal_Type__c", "current": None,
                                              "proposed": "Annual Contract"})
        self.fails("report", data, "not the deal it is shown under")
        data = base()
        create = task_create()
        create["fields"]["Description"] = "Hidden text"
        data["blocks"][1]["changes"].append(create)
        self.fails("report", data, "cannot propose a Task change")

    def test_withheld_deal_has_nothing_approvable(self):
        data = base()
        data["withheld"] = [{"deal": ROYAL, "reason": "Calendar not read."}]
        self.fails("report", data, "is withheld", GAP)

    def test_duplicates_span_options_but_not_alternatives(self):
        data = base()
        data["questions"][0]["deal"] = BIO
        data["questions"][0]["options"][1]["changes"] = [copy.deepcopy(data["blocks"][0]["changes"][0])]
        self.fails("report", data, "is already proposed in block 1")
        self.ok("report", base())

    def test_written_label_frees_its_fields_for_a_later_fix(self):
        data = base()
        fix = {"label": "Q2", "deal": BIO, "status": "open", "context": "The written next step is out of date.",
               "question": "Correct it?", "next_step_current": None,
               "options": [{"label": "Q2-a", "text": "Move the Task", "status": "proposed",
                            "changes": [copy.deepcopy(data["blocks"][0]["changes"][0])]}],
               "evidence": [{"date": "9/28/26", "source": "Operator", "fact": "Operator moved the session."}]}
        data["questions"].append(fix)
        data["blocks"][0]["status"] = "partial"
        self.fails("question", data, "is already proposed in block 1", None, "--label", "Q2")
        data["blocks"][0]["status"] = "written"
        data["writes"] = [{"label": "1", "object": "Opportunity", "id": BIO, "field": "Deal_Type__c", "outcome": "written"}]
        self.ok("question", data, None, "--label", "Q2")

    def test_one_change_per_record_field_in_a_proposal(self):
        data = base()
        data["blocks"][0]["changes"].append(dict(data["blocks"][0]["changes"][0], proposed="2026-10-05"))
        self.fails("report", data, "appears twice")


    def test_partial_fields_count_the_same_in_receipt_and_close(self):
        data = base()
        data["blocks"][1]["status"] = "partial"
        complete = data["blocks"][1]["changes"][0]
        data["blocks"][1]["changes"] = [complete, dict(complete, field="LeadSource", proposed="Event")]
        data["writes"] = [{"label": "2", "object": "Opportunity", "id": ROYAL, "field": "Customer_Type__c", "outcome": "written"}]
        out = self.ok("receipt", data, None, "--final")
        self.assertIn("2 · [Corvid Foods]", out)
        self.assertIn("· partial\n", out)
        self.assertIn("- 1 of 2 changes written.", out)
        self.assertIn("0 records written · 0 rejected · 0 unverified · 1 not attempted", out)
        self.assertIn("· 0 records written · 0 skipped", out)


    def test_next_step_and_task_changes_are_rejected_in_every_proposal_path(self):
        next_change={'object':'Opportunity','id':BIO,'field':'Next_Steps__c','current':None,'proposed':'9/28/26 SR - Follow up by 10/2.'}
        for field in ('ActivityDate','Subject','Status','Description','create'):
            change={'object':'Task','id':T_BIO,'field':field,'current':None,'proposed':'changed','action':'create' if field=='create' else 'update'}
            for location in ('block','option','letter'):
                data=friday(base()) if location=='letter' else base()
                if location=='block': data['blocks'][0]['changes']=[change]
                elif location=='option': data['questions'][0]['options'][0]['changes']=[change]
                else: data['friday']['letters'][0]['change']=change
                self.fails('report',data,'cannot propose a Task change')
        for location in ('block','option','letter'):
            data=friday(base()) if location=='letter' else base()
            if location=='block': data['blocks'][0]['changes']=[next_change]
            elif location=='option': data['questions'][0]['options'][0]['changes']=[next_change]
            else: data['friday']['letters'][0]['change']=next_change
            self.fails('report',data,'cannot propose a next-step change')
        for key in ('proposed','proposed_full'):
            data=base()
            data['blocks'][0]['next_step'][key]='9/28/26 SR - Follow up by 10/2.'
            self.fails('report',data,'cannot propose a next-step change')

    def test_next_step_finding_is_readonly_and_covers_a_flag(self):
        data=base()
        data['blocks']=data['blocks'][1:]
        data['triage']=[{'deal':BIO,'name':'Acme Devices','reason':'Triage owns the next step','triage_next_step':True}]
        output=self.ok('report',data)
        self.assertIn('Triage owns the next step',output)
        self.assertNotIn('1. [Acme Devices]',output)

    def test_pilot_evidence_is_friday_only_in_requested_weekly_review(self):
        data = base()
        data['blocks'][0]['evidence'] = [{'source': 'Pilot report', 'date': '9/25/26',
                                         'fact': 'Synthetic pilot report states its reviewed window.'}]
        data['run']['date'] = '2026-09-25'
        self.ok('report', data)
        data['run']['date'] = '2026-09-29'
        self.fails('report', data, 'Pilot report input is Friday-only')

    def test_weekday_scope_is_retired_and_requested_day_uses_weekly_pass(self):
        data=base()
        data['run'].update(branch='weekday',coverage_scope='pipeline-daily')
        self.fails('report',data,'run.branch must be friday')
        data=base()
        data['run']['date']='2026-09-29'
        self.assertIn('## Rollup',self.ok('report',data))
        self.assertNotIn('Top 3',self.ok('report',data))

if __name__ == "__main__":
    unittest.main()
