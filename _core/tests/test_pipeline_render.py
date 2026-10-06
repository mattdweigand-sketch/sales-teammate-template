"""pipeline_render.py: presentation is fixed, counts reconcile, labels stay unique, and status comes from inputs."""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "workspaces" / "pipeline" / "workflows" / "pipeline-review" / "scripts" / "pipeline_render.py"
EXPECTED = Path(__file__).resolve().parent / "fixtures" / "pipeline_render_weekday.txt"
URL = "https://example.test/run"

BIO, ROUX, ROYAL, CARY = "006AAA000000001AAA", "006AAA000000002AAA", "006AAA000000003AAA", "006AAA000000004AAA"
T_BIO, T_DUP, T_ROYAL = "00TAAA000000001AAA", "00TAAA000000002AAA", "00TAAA000000003AAA"
C_JIM, C_STEVE = "003AAA000000001AAA", "003AAA000000002AAA"
READY = {"ready": True, "process_status": "complete",
         "lines": ["Coverage (pipeline-daily) · 18 in scope. Inbox complete.", "Salesforce Events matched 6/6 eligible."]}
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
    return {
        "run": {"id": "fixture", "date": "2026-09-28", "branch": "weekday", "coverage_scope": "pipeline-daily",
                "process_status": "complete", "thread_url": URL, "schedule": "Mon-Thu · 7am"},
        "counts": {"open": 43, "reviewed": 18, "not_checked": 0},
        "today_actions": [],
        "deals": [{"id": BIO, "name": "Acme Devices", "flags": ["next_passed"]},
                  {"id": ROUX, "name": "Beacon Labs", "flags": ["blank_field"]},
                  {"id": ROYAL, "name": "Corvid Foods", "flags": ["blank_field"]}],
        "blocks": [
            {"label": "1", "deal": BIO, "status": "proposed",
             "next_step": {"current": "Next: Pat&#39;s presentation outcome · Operator · 9/26/26",
                           "proposed": "9/28/26 SR - Follow up with Pat by 10/2 if he has not replied."},
             "changes": [{"object": "Task", "id": T_BIO, "name": "Follow-up: Pat&#39;s presentation outcome",
                          "field": "ActivityDate", "current": "2026-09-28", "proposed": "2026-10-02",
                          "task_kind": "reschedule", "same_action": True}],
             "evidence": [gmail("Asked whether the plan is moving or should pause until Q1.")]},
            {"label": "2", "deal": ROYAL, "status": "proposed",
             "next_step": {"current": "<p>9/25/26 SR - Hold the 10/1 session.<br>Sam confirmed.</p>",
                           "proposed": None},
             "changes": [{"object": "Task", "id": T_ROYAL, "name": "Send Corvid rollout plan and pricing",
                          "field": "Status", "current": "Not Started", "proposed": "Completed", "task_kind": "complete",
                          "same_action": True, "completion_evidence": "Operator sent the order form 9/24."},
                         {"object": "Task", "action": "create", "who_name": "Sam Rivera",
                          "linkage_verified": True, "candidates_refreshed": True,
                          "fields": {"Subject": "Confirm rollout and order form next steps", "ActivityDate": "2026-10-01",
                                     "Status": "Not Started", "WhoId": C_STEVE, "WhatId": ROYAL}}],
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
        "writes": []}


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


class Render(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.sources = self.dir / "calls"
        self.sources.mkdir()
        (self.sources / "output_mail.json").write_text(json.dumps(SAVED))
        (self.sources / "output_cal.json").write_text(json.dumps(SAVED_CAL))

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, mode, data, coverage=READY, *extra):
        run = self.dir / "run.json"
        run.write_text(json.dumps(data))
        args = [sys.executable, str(SCRIPT), mode, "--run", str(run), "--sources", str(self.sources)]
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
        explicit = subprocess.run(arguments + ["--sources", str(self.sources)], cwd=self.dir, env=environment,
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
    def test_weekday_report_matches_expected_output(self):
        self.assertEqual(self.ok("report", base()), EXPECTED.read_text())

    def test_routed_section_counts_separately_and_marks_top_priority(self):
        data = base()
        data["deals"] = [row for row in data["deals"] if row["id"] != BIO]
        data["blocks"] = [row for row in data["blocks"] if row["deal"] != BIO]
        data["routed"] = [{"deal": BIO, "name": "Acme Devices", "thread_url": "https://example.test/deal",
                           "reason": "Current action belongs to the deal thread"}]
        data["today_actions"] = [{"deal": BIO, "name": "Acme Devices", "kind": "due", "date": "2026-09-28",
                                  "reason": "Review the overdue follow-up", "evidence": [
                                      {"source": "Salesforce", "date": "9/28/26", "who": "Operator",
                                       "title": "Open Task", "fact": "Follow-up is due today"}]}]
        out = self.ok("report", data)
        self.assertIn("18 reviewed · 2 flagged · 1 clear recommendation", out)
        self.assertIn("## Routed to deal threads\n\n1 routed · counted separately", out)
        self.assertIn("[Acme Devices](https://example.test/deal) · Current action belongs to the deal thread", out)
        self.assertIn("in deal thread · Review the overdue follow-up", out)
        self.assertIn("15 reviewed deals had no trigger", out)
        self.assertNotIn("1. [Acme Devices]", out)

    def test_routed_records_reject_local_proposals_and_double_counts(self):
        data = base()
        data["routed"] = [{"deal": BIO, "name": "Acme Devices", "thread_url": "https://example.test/deal",
                           "reason": "Owned elsewhere"}]
        self.fails("report", data, "routed deals must be counted separately")
        data["deals"] = [row for row in data["deals"] if row["id"] != BIO]
        self.fails("report", data, "routed deal is owned elsewhere; propose nothing here")

    def test_routed_rows_require_unique_ids_links_and_complete_counts(self):
        data = base()
        row = {"deal": CARY, "name": "Delta Labs", "thread_url": "https://example.test/deal", "reason": "Owned elsewhere"}
        data["routed"] = [row, copy.deepcopy(row)]
        self.fails("report", data, "routed: each deal appears once")
        data["routed"] = [row]
        row["thread_url"] = ""
        self.fails("report", data, "routed needs an https deal-thread link")
        row["thread_url"] = "https://example.test/deal"
        data["counts"]["reviewed"] = 3
        self.fails("report", data, "plus routed 1")

    def test_malformed_routed_rows_reject_without_output(self):
        for routed in (None, {}, [None], [{"deal": []}], [{"deal": "bad"}], [{"deal": "006invalid!00001AAA", "name": "Account", "reason": "Owner", "thread_url": "https://example.test/deal"}]):
            with self.subTest(routed=routed):
                data = base()
                data["routed"] = routed
                result = self.call("report", data)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("Traceback", result.stderr)
        for link in ("https://", "https://bad link", "https://user:secret@example.test", "https://["):
            with self.subTest(link=link):
                data = base()
                data["routed"] = [{"deal": CARY, "name": "Account", "reason": "Owned elsewhere", "thread_url": link}]
                self.fails("report", data, "routed needs an https deal-thread link")

    def test_routed_friday_records_reject_letters(self):
        data = friday(base())
        data["routed"] = [{"deal": data["friday"]["letters"][0]["deal"], "name": "Acme Devices",
                           "thread_url": "https://example.test/deal", "reason": "Owned elsewhere"}]
        result = self.call("report", data)
        self.assertEqual(result.returncode, 1)
        self.assertIn("routed deal is owned elsewhere; propose nothing here", result.stderr)

    def test_html_entities_decode_for_display_and_writes_stay_exact(self):
        out = self.ok("report", base())
        self.assertIn("Next: Pat's presentation outcome", out)
        self.assertNotIn("&#39;", out)
        self.assertIn("9/25/26 SR - Hold the 10/1 session.\nSam confirmed.\n", out)
        self.assertNotIn("<p>", out)
        self.assertIn("9/28/26 SR - Follow up with Pat by 10/2 if he has not replied.", out)

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
        self.assertEqual(note["send"], False)
        self.assertEqual(note["status"], "clean")

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
        data = base()
        data["today_actions"] = [self.buyer_candidate()]
        data["today_actions"][0]["evidence"] = [slack]
        self.fails("report", data, "evidence must support its action kind using existing workflow sources")

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
        self.assertIn("ActivityDate", clear)
        self.assertIn("2. [Corvid Foods]", clear)
        self.assertNotIn(limitation, clear)
        self.assertIn("Q2 · [Acme Devices]", needs)
        self.assertIn(limitation, needs)
        self.assertNotIn("Withheld", out)
        self.assertNotIn("Incomplete", out)
        question = self.ok("question", data, READY, "--label", "Q2")
        self.assertIn(limitation, question)
        self.assertNotIn("Q2-a", question)
        self.assertEqual(json.loads(self.ok("notification", data))["status"], "action")

    def test_fresh_slack_fact_supports_proposal_despite_other_missing_user(self):
        data = base()
        data["blocks"][0]["next_step"] = {
            "current": "9/25/26 SR - Wait for legal approval.",
            "proposed": "9/28/26 SR - Legal approval complete. Operator to confirm the rollout plan by 10/2."}
        data["blocks"][0]["evidence"] = [
            {"source": "Slack", "date": "9/28/26", "who": "Pat Lee", "title": "Legal complete",
             "link": "https://example.slack.com/archives/CEXAMPLE/p1790611200000000",
             "fact": "Buyer confirmed legal approval is complete and asked for the rollout plan."}]
        data["run"]["slack_coverage_notes"] = [
            {"deal": BIO, "name": "Acme Devices", "contacts": ["Alex Smith"], "reason": "No Slack user"}]
        out = self.ok("report", data)
        self.assertIn("Legal approval complete. Operator to confirm the rollout plan by 10/2.", out)
        self.assertIn("9/28/26 · Slack · Pat Lee · [Legal complete]", out)
        self.assertIn("Buyer confirmed legal approval is complete", out)
        self.assertNotIn("Incomplete", out)
        self.assertNotIn("Withheld", out)

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
        self.assertTrue(note["body"].startswith("Incomplete · 1 withheld · Corvid Foods · 43 open deals"))

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
        data["run"]["coverage_scope"] = "pipeline"
        self.fails("report", data, "coverage_scope must be pipeline-daily")

    def test_weekday_notification_with_actions(self):
        note = json.loads(self.ok("notification", base()))
        self.assertEqual(note["send"], True)
        self.assertEqual(note["title"], "Pipeline review · 9/28/26")
        self.assertEqual(note["body"], "43 open deals · 18 reviewed · 3 flagged · 2 clear recommendations · 1 question · "
                                       "0 records written · " + URL)
        self.assertEqual(note["schedule_description"], "Mon-Thu · 7am")

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

    def test_next_step_change_carries_its_task(self):
        """rules#followup_task: a next-step change without a Task create, reschedule, or kept Task fails."""
        data = base()
        data["blocks"][0]["changes"] = []
        self.fails("report", data, "rules#followup_task")
        data["blocks"][0]["followup_task"] = T_BIO
        self.assertIn(f"- Task kept · [Task {T_BIO}]", self.ok("report", data))
        data = base()
        data["questions"][0]["options"][0]["changes"].append(
            {"object": "Opportunity", "id": ROUX, "field": "Next_Steps__c", "mode": "prepend",
             "proposed": "9/28/26 SR - Send the order form by 10/2."})
        self.fails("report", data, "rules#followup_task")
        data = friday(base())
        data["friday"]["letters"][0].update(deal=ROYAL, deal_name="Corvid Foods")
        data["friday"]["letters"][0]["change"] = {"object": "Opportunity", "id": ROYAL, "field": "Next_Steps__c",
                                                  "mode": "prepend", "proposed": "9/28/26 SR - Send the order form by 10/2."}
        self.fails("report", data, "rules#followup_task")
        data["friday"]["letters"][0]["followup_task"] = T_ROYAL
        self.ok("report", data)

    # tasks
    def test_task_create_needs_linkage_and_fresh_candidates(self):
        data = base()
        create = data["blocks"][1]["changes"][1]
        create["candidates_refreshed"] = False
        self.fails("report", data, "candidates_refreshed true")
        data = base()
        data["blocks"][1]["changes"][1]["fields"]["WhoId"] = "0035"
        self.fails("report", data, "Contact id")

    def test_task_reuse_needs_same_action_and_completion_evidence(self):
        data = base()
        data["blocks"][0]["changes"][0]["same_action"] = False
        self.fails("report", data, "same_action true")
        data = base()
        del data["blocks"][1]["changes"][0]["completion_evidence"]
        self.fails("report", data, "completion_evidence")

    def test_task_kind_must_match_field_and_value(self):
        """Relabeling Status = Completed as update cannot skip completion evidence."""
        data = base()
        complete = data["blocks"][1]["changes"][0]
        complete["task_kind"] = "update"
        del complete["completion_evidence"]
        self.fails("report", data, "task_kind update does not match Status → Completed")
        data = base()
        data["blocks"][0]["changes"][0]["task_kind"] = "rename"
        self.fails("report", data, "does not match ActivityDate")
        data = base()
        data["blocks"][0]["changes"][0].update(field="WhoId", current=C_JIM, proposed=C_STEVE, task_kind="update")
        self.fails("report", data, "Task WhoId is not a permitted change")

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

    def test_option_next_step_is_a_new_first_entry(self):
        data = base()
        change = {"object": "Opportunity", "id": ROUX, "field": "Next_Steps__c", "current": None,
                  "proposed": "9/28/26 SR - Confirm the deal type with Dana by 10/2."}
        data["questions"][0]["options"][1].update(changes=[change], followup_task=T_BIO)
        self.fails("question", data, "mode prepend", None, "--label", "Q1")
        change["mode"] = "prepend"
        out = self.ok("question", data, None, "--label", "Q1")
        self.assertIn("  - Opportunity · Next_Steps__c · new first entry · 9/28/26 SR - Confirm the deal type", out)

    def test_duplicate_task_closure_is_a_question_only(self):
        close = {"object": "Task", "id": T_DUP, "name": "Pat's presentation outcome", "field": "Status",
                 "current": "Not Started", "proposed": "Completed", "task_kind": "close_duplicate",
                 "same_action": True, "duplicate_of": T_BIO}
        data = base()
        data["blocks"][0]["changes"].append(dict(close))
        self.fails("report", data, "never a clear recommendation")
        data = base()
        data["questions"][0]["options"][1]["changes"] = [dict(close)]
        out = self.ok("question", data, None, "--label", "Q1")
        self.assertIn("Status · Not Started → Completed · duplicate of [Task 00TAAA000000001AAA]", out)

    def test_task_create_renders_linkage(self):
        out = self.ok("report", base())
        self.assertIn("- New Task · Confirm rollout and order form next steps · ActivityDate 2026-10-01 · Status Not Started · "
                      "Contact [Sam Rivera]", out)

    def milestone(self, **changes):
        return {"task_id": T_DUP, "event_id": "00UAAA000000001AAA", "due_date": "2026-10-07",
                "reason": "Readout action and scheduled Event linkage reviewed.", "action_verified": True, **changes}

    def test_interim_task_create_keeps_reviewed_later_milestone_visible(self):
        data = base()
        data["blocks"][1]["retained_milestones"] = [self.milestone()]
        out = self.ok("report", data)
        self.assertIn("New Task · Confirm rollout", out)
        self.assertIn("Later milestone Task kept · [Task " + T_DUP, out)
        self.assertIn("due 2026-10-07", out)
        self.assertIn("00UAAA000000001AAA", out)
        self.assertIn("Readout action and scheduled Event linkage reviewed.", out)

    def test_retained_milestone_does_not_replace_current_followup(self):
        data = base()
        data["blocks"][1].update(changes=[], retained_milestones=[self.milestone()])
        data["blocks"][1]["next_step"]["proposed"] = "9/28/26 SR - Reply to the buyer by 10/1."
        self.fails("report", data, "a next-step change needs a Task create or reschedule")

    def test_retained_milestone_validation(self):
        cases = [(dict(action_verified=False), "action_verified true"), (dict(reason=""), "needs reason"),
                 (dict(task_id=[]), "not a valid Task Id"),
                 (dict(event_id=T_DUP), "not a valid Event Id"), (dict(due_date="tomorrow"), "due_date YYYY-MM-DD"),
                 (dict(due_date="2026-10-01"), "later than the current follow-up"),
                 (dict(due_date="2026-09-01"), "must be in the future")]
        for changes, error in cases:
            with self.subTest(changes=changes):
                data = base()
                data["blocks"][1]["retained_milestones"] = [self.milestone(**changes)]
                self.fails("report", data, error)
        data = base()
        data["blocks"][0]["retained_milestones"] = [self.milestone(task_id=T_BIO)]
        self.fails("report", data, "cannot also be changed")
        data = base()
        data["blocks"][1]["retained_milestones"] = [self.milestone(), self.milestone()]
        self.fails("report", data, "must be a distinct Task")

    def test_kept_milestone_is_visible_in_question_and_friday_letter(self):
        data = base()
        data["questions"][0]["options"][0]["retained_milestones"] = [self.milestone()]
        self.assertIn("Later milestone Task kept", self.ok("question", data, None, "--label", "Q1"))
        data = friday(base())
        data["friday"]["letters"][0]["retained_milestones"] = [self.milestone()]
        self.assertIn("Later milestone Task kept", self.ok("report", data))

    def today_candidate(self, deal=BIO, name="Acme Devices", kind="due", when="2026-09-28", **extra):
        fact = {"meeting": f"Event scheduled on {when}.", "due": f"Open Task due {when}.",
                "date_at_risk": f"Hygiene flags CloseDate {when} at risk."}.get(kind, "Reviewed source fact.")
        return {"deal": deal, "name": name, "kind": kind, "date": when,
                "reason": "Follow-up Task is due today",
                "evidence": [{"source": "Salesforce", "date": "9/28/26", "fact": fact}], **extra}

    def buyer_candidate(self):
        saved = copy.deepcopy(SAVED)
        saved["email_results"]["emails"][0]["from_"] = "buyer@example.test"
        (self.sources / "output_mail.json").write_text(json.dumps(saved))
        return self.today_candidate(kind="buyer_reply", when="2026-09-25", reply_reviewed=True,
                                    reason="Buyer request needs a reply in the retrieved thread",
                                    evidence=[gmail("Buyer asked whether the plan is moving.", who="Buyer to Operator")])

    def test_top_three_ranks_deduplicates_and_keeps_approval_labels_separate(self):
        data = base()
        data["today_actions"] = [
            self.today_candidate(CARY, "Delta Holdings", "date_at_risk", "2026-09-30", reason="Close date is at risk"),
            self.today_candidate(), self.today_candidate(ROYAL, "Corvid Foods"),
            self.today_candidate(ROUX, "Beacon Labs", "meeting", "2026-09-29", reason="Prepare for tomorrow's meeting"),
            self.buyer_candidate()]
        out = self.ok("report", data)
        section = out.split("## Top 3 actions today\n", 1)[1].split("## Clear recommendations", 1)[0]
        self.assertEqual(section.count("- Priority"), 3)
        self.assertIn("Priority 1 · [Acme Devices]", section)
        self.assertIn("Priority 2 · [Beacon Labs]", section)
        self.assertIn("Priority 3 · [Corvid Foods]", section)
        self.assertNotIn("Delta Holdings", section)
        self.assertEqual(section.count("Acme Devices"), 1)
        self.assertIn("Use the proposal labels below for approvals.", section)
        self.assertIn("1. [Acme Devices]", out)
        self.assertIn("Email, Calendar, and Slack evidence is the retrieved set", section)

    def test_top_actions_allow_unflagged_reviewed_deal_without_changing_counts(self):
        data = base()
        data["today_actions"] = [self.today_candidate(CARY, "Delta Holdings")]
        out = self.ok("report", data)
        self.assertIn("Priority 1 · [Delta Holdings]", out)
        self.assertNotIn("Priority 2", out)
        self.assertIn("3 flagged · 2 clear recommendations · 1 question", out)

    def test_top_actions_ties_are_stable_and_earlier_dates_rank_first(self):
        data = base()
        data["today_actions"] = [self.today_candidate(ROYAL, "Corvid Foods"), self.today_candidate(),
                                 self.today_candidate(ROUX, "Beacon Labs", when="2026-09-27")]
        first = self.ok("report", data)
        data["today_actions"].reverse()
        self.assertEqual(first, self.ok("report", data))
        self.assertIn("Priority 1 · [Beacon Labs]", first)
        self.assertIn("Priority 2 · [Acme Devices]", first)

    def test_top_actions_calendar_date_uses_run_timezone(self):
        data = base()
        (self.sources / "output_cal.json").write_text(json.dumps({"calendar_event_list": {"events": [
            {"event_id": "today", "start": "2026-09-29T01:00:00Z", "title": "Buyer sync"}]}}))
        candidate = self.today_candidate(kind="meeting", evidence=[{"source": "Calendar", "source_id": "today", "fact": "Prepare for the scheduled meeting."}])
        data["today_actions"] = [candidate]
        self.assertIn("Priority 1", self.ok("report", data))
        candidate["date"] = "2026-09-29"
        self.fails("report", data, "date must match the saved source")

    def test_top_actions_reject_unsupported_evidence_and_dates(self):
        cases = [(dict(evidence=[]), "needs at least one evidence"),
                 (dict(evidence=[{"source": "Operator", "date": "9/28/26", "fact": "Follow up."}]), "existing workflow sources"),
                 (dict(date="2026-09-29"), "future due date"),
                 (dict(kind="meeting", date="2026-09-30"), "today or tomorrow"),
                 (dict(reason="First line\nSecond line"), "one-line reason"),
                 (dict(reason="Due today; follow up"), "plain prose"),
                 (dict(date="20260928"), "date YYYY-MM-DD"),
                 (dict(kind="guess"), "supported action kind"),
                 (dict(name="Different deal"), "name must match")]
        for changes, error in cases:
            with self.subTest(changes=changes):
                data = base()
                data["today_actions"] = [self.today_candidate(**changes)]
                self.fails("report", data, error)

    def test_top_actions_require_reviewed_inbound_thread_and_real_source(self):
        data = base()
        candidate = self.buyer_candidate()
        data["today_actions"] = [candidate]
        candidate["reply_reviewed"] = False
        self.fails("report", data, "reply_reviewed true")
        candidate["reply_reviewed"] = True
        candidate["evidence"][0]["source_id"] = "missing"
        self.fails("report", data, "not in this run's saved Gmail results")
        candidate["evidence"][0]["source_id"] = "1a0d"
        saved = copy.deepcopy(SAVED)
        saved["email_results"]["emails"][0]["from_"] = "rep@seller.example"
        (self.sources / "output_mail.json").write_text(json.dumps(saved))
        self.fails("report", data, "external sender")

    def test_top_actions_exclude_coverage_gaps_and_incomplete_runs(self):
        data = base()
        data["today_actions"] = [self.today_candidate(), self.today_candidate(ROYAL, "Corvid Foods")]
        data["withheld"] = [{"deal": ROYAL, "reason": "Calendar coverage missing"}]
        data["blocks"] = data["blocks"][:1]
        out = self.ok("report", data, GAP)
        section = out.split("## Top 3 actions today", 1)[1].split("## Clear recommendations", 1)[0]
        self.assertIn("Acme Devices", section)
        self.assertNotIn("Corvid Foods", section)
        data["run"].update(process_status="incomplete", process_gaps=["Task review unfinished"])
        self.assertIn("No supported actions to prioritize today.", self.ok("report", data, GAP))
        data["run"].update(process_status="complete", process_gaps=[])
        data["withheld"] = [{"deal": d["id"], "reason": "Unknown gap"} for d in data["deals"]]
        data.update(blocks=[], questions=[])
        self.assertIn("No supported actions to prioritize today.", self.ok("report", data, dict(GAP, affected=None)))

    def test_top_actions_require_weekday_input_and_leave_friday_unchanged(self):
        data = base()
        del data["today_actions"]
        self.fails("report", data, "weekday report needs today_actions")
        self.assertNotIn("Top 3 actions today", self.ok("report", friday(data)))

    # writes
    def test_partial_write_receipt(self):
        data = base()
        data["blocks"][0]["status"] = "partial"
        data["writes"] = [
            {"label": "1", "object": "Opportunity", "id": BIO, "field": "Next_Steps__c", "outcome": "written"},
            {"label": "1", "object": "Task", "id": T_BIO, "field": "ActivityDate", "outcome": "rejected",
             "detail": "FIELD_INTEGRITY_EXCEPTION"}]
        out = self.ok("receipt", data, None, "--labels", "1")
        self.assertIn("1 · [Acme Devices]", out)
        self.assertIn("· partial\n", out)
        self.assertIn("- Rejected · [Task]", out)
        self.assertIn("- 1 of 2 changes written. Written changes are kept and not repeated.", out)
        self.assertIn("1 record written · 1 rejected · 0 unverified · 0 not attempted · 43 open deals at run start", out)
        self.assertNotIn("· written\n", out)

    def test_fields_on_one_record_count_once(self):
        data = base()
        data["blocks"][1]["status"] = "written"
        complete = data["blocks"][1]["changes"][0]
        data["blocks"][1]["changes"] = [complete, dict(complete, field="Description", task_kind="update", mode="prepend",
                                                       proposed="9/28/26 SR - Order form sent 9/24.")]
        data["writes"] = [{"label": "2", "object": "Task", "id": T_ROYAL, "field": f, "outcome": "written"}
                          for f in ("Status", "Description")]
        self.assertIn("1 record written · 0 rejected", self.ok("receipt", data, None))

    def test_repeated_successful_write_fails(self):
        data = base()
        data["blocks"][0]["status"] = "written"
        w = {"label": "1", "object": "Opportunity", "id": BIO, "field": "Next_Steps__c", "outcome": "written"}
        data["writes"] = [w, dict(w)]
        self.fails("receipt", data, "never repeat a successful write", None)

    def test_write_on_superseded_or_unapproved_label_fails(self):
        data = base()
        data["writes"] = [{"label": "1", "object": "Opportunity", "id": BIO, "field": "Next_Steps__c", "outcome": "written"}]
        self.fails("receipt", data, "only approved labels are written", None)

    def test_option_write_and_final_close(self):
        data = base()
        data["blocks"][0]["status"] = "written"
        data["blocks"][1]["status"] = "skipped"
        data["questions"][0]["status"] = "answered"
        data["questions"][0]["options"][0]["status"] = "written"
        data["writes"] = [
            {"label": "1", "object": "Opportunity", "id": BIO, "field": "Next_Steps__c", "outcome": "written"},
            {"label": "1", "object": "Task", "id": T_BIO, "field": "ActivityDate", "outcome": "written"},
            {"label": "Q1-a", "object": "Opportunity", "id": ROUX, "field": "Deal_Type__c", "outcome": "written"}]
        out = self.ok("receipt", data, None, "--final")
        self.assertIn("Q1-a · [Beacon Labs]", out)
        self.assertIn("**Close**\n\n43 open deals · 18 reviewed · 3 flagged · 2 proposed · 3 records written · 1 skipped · "
                      "0 not checked  \nSkipped · 2 · [Corvid Foods]", out)

    def test_approved_block_without_writes_is_named_in_final_receipt(self):
        """An approved block that was never attempted must appear, not vanish."""
        data = base()
        data["blocks"][0]["status"] = "approved"
        data["writes"] = []
        out = self.ok("receipt", data, None, "--final")
        self.assertIn("1 · [Acme Devices]", out)
        self.assertIn("· approved, not attempted\n", out)
        self.assertIn("- Not attempted · [Opportunity]", out)
        self.assertIn("- Not attempted · [Task]", out)
        self.assertIn("0 records written · 0 rejected · 0 unverified · 2 not attempted", out)
        self.assertIn("Approved, not attempted · 1 · [Acme Devices]", out)
        # Without --final the receipt still reports only recorded writes.
        self.assertNotIn("Acme Devices", self.ok("receipt", data, None))

    # audit gaps
    def test_receipt_reconciles_against_approved_changes(self):
        data = base()
        data["blocks"][0]["status"] = "partial"
        data["writes"] = [{"label": "1", "object": "Opportunity", "id": BIO, "field": "Next_Steps__c", "outcome": "written"}]
        out = self.ok("receipt", data, None, "--labels", "1")
        self.assertIn("1 · [Acme Devices]", out)
        self.assertIn("· partial\n", out)
        self.assertIn("- Not attempted · [Task]", out)
        self.assertIn("1 record written · 0 rejected · 0 unverified · 1 not attempted", out)
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
        data["blocks"][1]["changes"][1]["fields"]["Description"] = "Hidden text"
        self.fails("report", data, "are not displayed")

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
        data["writes"] = [{"label": "1", "object": "Opportunity", "id": BIO, "field": "Next_Steps__c", "outcome": "written"},
                          {"label": "1", "object": "Task", "id": T_BIO, "field": "ActivityDate", "outcome": "written"}]
        self.ok("question", data, None, "--label", "Q2")

    def test_one_change_per_record_field_in_a_proposal(self):
        data = base()
        data["blocks"][0]["changes"].append(dict(data["blocks"][0]["changes"][0], proposed="2026-10-05"))
        self.fails("report", data, "appears twice")

    def test_one_task_create_per_label(self):
        data = base()
        create = data["blocks"][1]["changes"][1]
        second = copy.deepcopy(create)
        second["fields"]["Subject"] = "Send order form reminder"
        data["blocks"][1]["changes"].append(second)
        self.fails("report", data, "one Task create per approval label")

    def test_partial_fields_count_the_same_in_receipt_and_close(self):
        data = base()
        data["blocks"][1]["status"] = "partial"
        complete = data["blocks"][1]["changes"][0]
        data["blocks"][1]["changes"] = [complete, dict(complete, field="Description", task_kind="update", mode="prepend",
                                                       proposed="9/28/26 SR - Order form sent 9/24.")]
        data["writes"] = [{"label": "2", "object": "Task", "id": T_ROYAL, "field": "Status", "outcome": "written"}]
        out = self.ok("receipt", data, None, "--final")
        self.assertIn("2 · [Corvid Foods]", out)
        self.assertIn("· partial\n", out)
        self.assertIn("- 1 of 2 changes written.", out)
        self.assertIn("0 records written · 0 rejected · 0 unverified · 1 not attempted", out)
        self.assertIn("· 0 records written · 0 skipped", out)


if __name__ == "__main__":
    unittest.main()
