"""Top 3 ranking moved from pipeline_render with its source and gap regressions."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from test_pipeline_render import ROOT, base, friday, gmail, READY, GAP, SAVED, BIO, ROUX, ROYAL, CARY

import test_pipeline_render as fixtures

SCRIPT = ROOT / 'workspaces/pipeline/scripts/top_actions.py'

class TopActions(unittest.TestCase):
    def setUp(self):
        fixtures.Render.setUp(self)

    def tearDown(self):
        fixtures.Render.tearDown(self)

    def call(self, data, coverage=READY, *extra):
        value = copy.deepcopy(data)
        value['coverage'] = coverage
        path = self.dir / 'actions.json'
        path.write_text(json.dumps(value))
        return subprocess.run([sys.executable,str(SCRIPT),'--input',str(path),'--sources',str(self.sources),*extra],text=True,capture_output=True)

    def ok(self, data, coverage=READY, *extra):
        result = self.call(data,coverage,*extra)
        self.assertEqual(result.returncode,0,result.stderr)
        return result.stdout

    def fails(self, data, needle, coverage=READY, *extra):
        result = self.call(data,coverage,*extra)
        self.assertEqual(result.returncode,1,result.stdout)
        self.assertIn(needle,result.stderr)

    def test_failed_delivery_top_action_does_not_claim_delivery(self):
        data = base()
        data["deals"] = [row for row in data["deals"] if row["id"] != BIO]
        data["blocks"] = [row for row in data["blocks"] if row["deal"] != BIO]
        data["routed"] = [{"kind": "deal_context", "deal": BIO, "name": "Acme Devices", "thread_url": "https://example.test/deal",
                           "reason": "Send rejected", "delivery": {"command": "session_send", "status": "failed"}}]
        data["today_actions"] = [{"deal": BIO, "name": "Acme Devices", "kind": "due", "date": "2026-09-28",
                                  "reason": "Review the overdue follow-up", "evidence": [
                                      {"source": "Salesforce", "date": "9/28/26", "who": "Operator",
                                       "title": "Open Task", "fact": "Follow-up is due today"}]}]
        out = self.ok(data)
        self.assertIn("routing failed, needs input · Review the overdue follow-up", out)
        self.assertNotIn("in deal thread · Review the overdue follow-up", out)


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
        out = self.ok(data)
        section = out.split("## Top 3 actions today\n", 1)[1]
        self.assertEqual(section.count("- Priority"), 3)
        self.assertIn("Priority 1 · [Acme Devices]", section)
        self.assertIn("Priority 2 · [Beacon Labs]", section)
        self.assertIn("Priority 3 · [Corvid Foods]", section)
        self.assertNotIn("Delta Holdings", section)
        self.assertEqual(section.count("Acme Devices"), 1)
        self.assertIn("Use the proposal labels below for approvals.", section)
        self.assertIn("Email, Calendar, and Slack evidence is the retrieved set", section)


    def test_top_actions_allow_unflagged_reviewed_deal_without_changing_counts(self):
        data = base()
        data["today_actions"] = [self.today_candidate(CARY, "Delta Holdings")]
        out = self.ok(data)
        self.assertIn("Priority 1 · [Delta Holdings]", out)
        self.assertNotIn("Priority 2", out)


    def test_top_actions_ties_are_stable_and_earlier_dates_rank_first(self):
        data = base()
        data["today_actions"] = [self.today_candidate(ROYAL, "Corvid Foods"), self.today_candidate(),
                                 self.today_candidate(ROUX, "Beacon Labs", when="2026-09-27")]
        first = self.ok(data)
        data["today_actions"].reverse()
        self.assertEqual(first, self.ok(data))
        self.assertIn("Priority 1 · [Beacon Labs]", first)
        self.assertIn("Priority 2 · [Acme Devices]", first)


    def test_top_actions_calendar_date_uses_run_timezone(self):
        data = base()
        (self.sources / "output_cal.json").write_text(json.dumps({"calendar_event_list": {"events": [
            {"event_id": "today", "start": "2026-09-29T01:00:00Z", "title": "Buyer sync"}]}}))
        candidate = self.today_candidate(kind="meeting", evidence=[{"source": "Calendar", "source_id": "today", "fact": "Prepare for the scheduled meeting."}])
        data["today_actions"] = [candidate]
        self.assertIn("Priority 1", self.ok(data))
        candidate["date"] = "2026-09-29"
        self.fails(data, "date must match the saved source")


    def test_top_actions_reject_unsupported_evidence_and_dates(self):
        cases = [(dict(evidence=[]), "needs at least one evidence"),
                 (dict(evidence=[{"source": "Operator", "date": "9/28/26", "fact": "Follow up."}]), "existing workflow sources"),
                 (dict(date="2026-09-29"), "future due date"),
                 (dict(kind="meeting", date="2026-09-30"), "today or tomorrow"),
                 (dict(reason="First line\nSecond line"), "one-line reason"),
                 (dict(date="20260928"), "date YYYY-MM-DD"),
                 (dict(kind="guess"), "supported action kind"),
                 (dict(name="Different deal"), "name must match")]
        for changes, error in cases:
            with self.subTest(changes=changes):
                data = base()
                data["today_actions"] = [self.today_candidate(**changes)]
                self.fails(data, error)


    def test_top_actions_require_reviewed_inbound_thread_and_real_source(self):
        data = base()
        candidate = self.buyer_candidate()
        data["today_actions"] = [candidate]
        candidate["reply_reviewed"] = False
        self.fails(data, "reply_reviewed true")
        candidate["reply_reviewed"] = True
        candidate["evidence"][0]["source_id"] = "missing"
        self.fails(data, "not in this run's saved Gmail results")
        candidate["evidence"][0]["source_id"] = "1a0d"
        saved = copy.deepcopy(SAVED)
        saved["email_results"]["emails"][0]["from_"] = "operator@seller.example"
        (self.sources / "output_mail.json").write_text(json.dumps(saved))
        self.fails(data, "external sender")


    def test_top_actions_exclude_coverage_gaps_and_incomplete_runs(self):
        data = base()
        data["today_actions"] = [self.today_candidate(), self.today_candidate(ROYAL, "Corvid Foods")]
        data["withheld"] = [{"deal": ROYAL, "reason": "Calendar coverage missing"}]
        data["blocks"] = data["blocks"][:1]
        out = self.ok(data, GAP)
        section = out.split("## Top 3 actions today", 1)[1]
        self.assertIn("Acme Devices", section)
        self.assertNotIn("Corvid Foods", section)
        data["run"].update(process_status="incomplete", process_gaps=["Task review unfinished"])
        self.assertIn("Ranking withheld because processing is incomplete.", self.ok(data, GAP))
        data["run"].update(process_status="complete", process_gaps=[])
        data["withheld"] = [{"deal": d["id"], "reason": "Unknown gap"} for d in data["deals"]]
        data.update(blocks=[], questions=[])
        self.assertIn("Ranking withheld because evidence coverage scope is unknown.", self.ok(data, dict(GAP, affected=None)))


    def test_reason_punctuation_warns_and_keeps_the_action_with_equal_ranking(self):
        """H1, H2. A colon, semicolon or em dash in a reason is a warning. Ranking is identical to the plain-prose reason."""
        plain = base()
        plain["today_actions"] = [self.today_candidate(ROYAL, "Corvid Foods", reason="Follow-up Task is due today"),
                                  self.today_candidate(reason="Buyer sync is tomorrow, confirm the agenda")]
        plain_out = self.ok(plain)
        for reason in ("Follow-up Task is due today; call Pat", "Follow-up Task: due today", "Follow-up Task — due today"):
            with self.subTest(reason=reason):
                data = copy.deepcopy(plain)
                data["today_actions"][0]["reason"] = reason
                result = self.call(data)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("reason should use plain prose", result.stderr)
                self.assertEqual(result.stdout.replace(reason, "Follow-up Task is due today"), plain_out)
                priorities = [line.split(" · ")[1] for line in result.stdout.splitlines() if line.startswith("- Priority")]
                self.assertEqual(priorities, [line.split(" · ")[1] for line in plain_out.splitlines() if line.startswith("- Priority")])

    def test_coverage_not_ready_with_empty_affected_withholds_ranking_as_unknown(self):
        """H3, W6-14. ready false with affected [] names no deal, so the scope is unknown and nothing is ranked."""
        data = base()
        data["today_actions"] = [self.today_candidate(), self.today_candidate(ROYAL, "Corvid Foods")]
        output = self.ok(data, dict(GAP, affected=[]))
        self.assertIn("Ranking withheld because evidence coverage scope is unknown.", output)
        self.assertNotIn("Priority 1", output)
        self.assertIn("Priority 1", self.ok(data, GAP))

    def test_complete_empty_ranking_is_not_withheld(self):
        data = base()
        data['today_actions'] = []
        output = self.ok(data)
        self.assertIn('No supported actions to prioritize today.', output)
        self.assertNotIn('Ranking withheld', output)

    def test_all_candidates_with_known_gaps_are_withheld(self):
        data = base()
        data['today_actions'] = [self.today_candidate(ROYAL, 'Corvid Foods')]
        output = self.ok(data, GAP)
        self.assertIn('Ranking withheld because all supported candidates have evidence gaps.', output)
        self.assertNotIn('No supported actions to prioritize today.', output)

    def test_top_actions_require_candidate_input(self):
        data = base()
        data.pop('today_actions',None)
        self.fails(data,'Top 3 needs today_actions')


    def test_size_uses_arr_only_zero_set_blanks_last_and_rejects_bad_values(self):
        data=base()
        data['today_actions']=[self.today_candidate(),self.today_candidate(ROUX,'Beacon Labs',ARR__c=0),
            self.today_candidate(ROYAL,'Corvid Foods',ARR__c=100,Amount=999999)]
        output=self.ok(data)
        self.assertIn('Priority 1 · [Corvid Foods]',output)
        self.assertIn('Priority 2 · [Beacon Labs]',output)
        self.assertIn('Priority 3 · [Acme Devices]',output)
        for value in (True,-1,'nan','not numeric'):
            data['today_actions'][0]['ARR__c']=value
            self.fails(data,'size must')

if __name__ == '__main__':
    unittest.main()
