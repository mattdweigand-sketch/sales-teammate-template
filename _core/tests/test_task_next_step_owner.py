from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / 'workspaces/pipeline'
TRIAGE = PIPELINE / 'workflows/task-triage-speed-run'
REVIEW = PIPELINE / 'workflows/pipeline-review'


def read(path):
    return path.read_text()


class NextStepOwnership(unittest.TestCase):
    def test_ownership_rules_have_their_canonical_sections(self):
        text = read(ROOT / '_core/rules.md')
        coordination = text.split('<a id="task_date_coordination">', 1)[1].split('<a id=', 1)[0]
        followup = text.split('<a id="followup_task">', 1)[1].split('<a id=', 1)[0]
        self.assertIn('Pipeline-review leaves Task and next-step issues to triage', coordination)
        self.assertIn("Only triage, interaction-sync, Close and a deal thread on Operator's typed command write", followup)
        self.assertIn('one approval', followup)

    def test_weekly_schedule_and_shared_helper_registry(self):
        policy = yaml.safe_load(read(ROOT / '_core/policy.yaml'))
        self.assertNotIn('daily', policy['pipeline']['schedule'])
        self.assertEqual(policy['tooling']['scripts']['top_actions'], 'workspaces/pipeline/scripts/top_actions.py')
        self.assertIn('friday', policy['pipeline']['schedule'])
        self.assertIn('task_triage', policy['pipeline']['schedule'])

    def test_shared_native_reads_have_one_home(self):
        shared = read(PIPELINE / 'references/deal-activity-reads.md')
        self.assertIn('FROM Opportunity WHERE OwnerId', shared)
        self.assertIn('FROM Task', shared)
        self.assertIn('FROM Event', shared)
        self.assertIn('IsClosed = false OR ActivityDate = LAST_N_DAYS:', shared)
        self.assertIn('Never relabel Gmail or Calendar', shared)
        for workflow in (TRIAGE, REVIEW):
            collect = read(workflow / 'references/collect.md')
            self.assertIn('deal-activity-reads.md', collect)
            self.assertNotIn('SELECT Id, Subject, ActivityDate, StartDateTime', collect)
            self.assertIn('hygiene_check', read(workflow / 'CONTEXT.md'))

    def test_drafting_and_trigger_contracts_moved_not_copied(self):
        drafts = read(TRIAGE / 'references/next-steps.md')
        self.assertIn('newest message in either direction plus the next scheduled Event', drafts)
        self.assertIn('wait and a re-follow-up date', drafts)
        self.assertIn('Every clause traces', drafts)
        self.assertIn('Call needs logging', drafts)
        self.assertIn('Propose no next step for that deal until logging is verified', drafts)
        self.assertNotIn('Build each next-step proposal', read(REVIEW / 'references/proposals.md'))
        self.assertFalse((REVIEW / 'references/triggers.md').exists())
        self.assertTrue((PIPELINE / 'references/triggers.md').exists())

    def test_call_logging_blocker_only_applies_after_newest_next_step_entry(self):
        text = read(TRIAGE / 'references/next-steps.md')
        recent_call = ('For a held meeting dated after the newest next-step entry with no verified call Task or source marker, '
                       'show `Call needs logging` and route to interaction-sync.\n'
                       'Propose no next step for that deal until logging is verified.')
        older_call = 'An older unlogged held call is a separate `Call needs logging` finding, not a blocker.'
        self.assertIn(recent_call + '\n' + older_call, text)
        self.assertNotIn('For a held meeting with no verified call Task or source marker', text)

    def test_pair_approval_write_order_and_partial_failure(self):
        walk = read(TRIAGE / 'references/walk.md')
        writes = read(TRIAGE / 'references/writes.md')
        self.assertIn('One approval covers the pair', walk)
        self.assertIn('next step first', writes)
        self.assertIn('Then complete the old Task', writes)
        self.assertIn('partial with the actual state of both sides and one corrective proposal', writes)
        self.assertIn('Contact-only, meeting-prep and later milestone rows have no Opportunity next-step write', writes)
        self.assertIn('fresh-read Next_Steps__c and stop for a changed baseline', writes)
        rules = read(ROOT / '_core/rules.md')
        history_condition = 'new inbound buyer evidence arrived after the newest note'
        self.assertIn(history_condition, read(TRIAGE / 'references/next-steps.md'))
        self.assertNotIn(history_condition, rules)
        self.assertIn('\n\n<a id="next_steps">', rules)
        self.assertIn("Only triage, interaction-sync, Close and a deal thread on Operator's typed command write", rules)
        self.assertNotIn('Deal threads keep Next_Steps__c', rules)

    def test_one_deal_mode_is_bounded_and_command_is_not_approval(self):
        text = read(TRIAGE / 'references/next-steps.md')
        for phrase in ('typed in any project thread', 'exactly one open Opportunity', 'With no date, ask once and propose nothing',
                       'all related open Tasks', 'Keep writer=triage and use manual_one_deal', 'new action replaces it', 'A done row names its replacement action and date', 'No typed command is itself write approval'):
            self.assertIn(phrase, text)
        rules = read(ROOT / '_core/rules.md')
        self.assertIn("In one-deal mode or a deal thread, Operator's typed command is the quoted source", rules)
        self.assertIn('Scheduled runs keep the evidence rules above', rules)

    def test_pairing_excludes_prep_contacts_and_milestones(self):
        text = read(TRIAGE / 'references/next-steps.md')
        self.assertIn("Only the deal's current-action Task pairs", text)
        self.assertIn('Contact-only, meeting-prep and retained later milestone Tasks never pair', text)
        self.assertIn('Never touch non-current Tasks or retained milestones', text)
        self.assertIn('Name an existing exact-action Task instead of creating a duplicate', text)
        self.assertIn('All three propose the exact next-step and current-action Task pair', text)

    def test_daily_slack_covers_every_deal_and_preserves_limits(self):
        collect = read(TRIAGE / 'references/collect.md')
        self.assertIn('every in-scope deal, plus run Task contacts', collect)
        self.assertIn('policy.tooling.slack_lookback_days', collect)
        self.assertIn('Page all identity and message cursors', collect)
        self.assertIn('Slack watches never replace these reads', collect)
        self.assertIn('shared Search contract also excludes bots', collect)
        self.assertIn('Every in-scope deal has paged named-buyer reads', read(TRIAGE / 'CONTEXT.md'))
        self.assertIn("Required-field and CloseDate checks remain weekly on Friday by Operator's decision", read(TRIAGE / 'references/next-steps.md'))

    def test_receipts_never_request_a_second_proposal(self):
        text = read(TRIAGE / 'references/writes.md')
        self.assertIn('written next step and Task links', text)
        self.assertIn('never a request for another field or Task proposal', text)
        interaction = read(PIPELINE / 'workflows/interaction-sync/references/proposals.md')
        self.assertIn('matched deal thread differs from this run thread', interaction)
        self.assertIn('Post the run result first', interaction)
        self.assertIn('pplx tm mail send', interaction)

    def test_early_stage_next_steps_have_friday_triage_receiver(self):
        shared = read(PIPELINE / 'references/deal-activity-reads.md')
        collect = read(TRIAGE / 'references/collect.md')
        drafting = read(TRIAGE / 'references/next-steps.md')
        self.assertIn('policy.pipeline.early_stages` on local Friday only', shared)
        self.assertIn('Monday through Thursday leave early stages alone except already-due Tasks', shared)
        self.assertIn('Automatic Task gaps remain limited to `policy.pipeline.stages`', shared)
        self.assertIn('## Friday early stages', collect)
        self.assertIn('policy.pipeline.stages` or `policy.pipeline.early_stages`', drafting)
        self.assertIn('Friday early stages', read(TRIAGE / 'CONTEXT.md'))
        self.assertIn('early-stage next steps only on local Friday or in explicit one-deal mode',
                      read(PIPELINE / 'references/triggers.md'))

    def test_account_domain_gmail_has_shared_bounded_reads(self):
        shared = read(PIPELINE / 'references/deal-activity-reads.md')
        self.assertIn('after:<previous scheduled run date>', shared)
        self.assertIn('Monday starts last Friday', shared)
        self.assertIn('sender domain exactly matches an in-scope Account domain', shared)
        self.assertIn('new sender at a verified Account domain', shared)
        self.assertIn('(from:@<verified Account domain> OR to:@<verified Account domain>)', shared)
        self.assertIn('reviewed Gmail `new_activity`', shared)
        self.assertIn('Follow every returned cursor', shared)
        for workflow in (TRIAGE, REVIEW):
            self.assertIn('Account-domain Gmail', read(workflow / 'references/collect.md'))
            self.assertNotIn('(from:@', read(workflow / 'references/collect.md'))

    def test_requested_weekly_review_loads_qualification_not_weekday_pilot(self):
        context = read(REVIEW / 'CONTEXT.md')
        report = read(REVIEW / 'references/report-format.md')
        self.assertIn('for every weekly or requested run', context)
        self.assertIn('policy.pipeline.early_stages` on every weekly or requested run', report)
        self.assertIn('Friday only, when supplied', context)
        self.assertIn('Friday only, when Operator supplies', read(REVIEW / 'references/collect.md'))

    def test_ranking_retired_from_weekly_review(self):
        renderer = read(REVIEW / 'scripts/pipeline_render.py')
        self.assertNotIn('TODAY_ACTION_ORDER', renderer)
        self.assertNotIn('def today_action_lines', renderer)
        self.assertNotIn('def check_today_actions', renderer)
        helper = read(PIPELINE / 'scripts/top_actions.py')
        self.assertIn('def today_action_lines', helper)
        self.assertIn('len(selected) == 3', helper)
        self.assertIn('output unchanged first', read(TRIAGE / 'references/walk.md'))


if __name__ == '__main__':
    unittest.main()
