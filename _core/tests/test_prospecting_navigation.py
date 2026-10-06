"""Selective local navigation and rejected reference-consumer fixtures."""
from pathlib import Path
import sys
import tempfile
import unittest

from test_skill_contracts import reference_consumers

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '_core/scripts'))
from rehearse import contract_trace

EVENT = 'workspaces/prospecting/workflows/event-sequence'
SIGNAL = 'workspaces/prospecting/workflows/signal-prospecting'


class ReferenceConsumerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.workflows = Path(temp.name) / 'workspaces/prospecting/workflows'
        self.flow = self.workflows / 'sample'
        self.stage = self.flow / '01-first/CONTEXT.md'
        self.stage.parent.mkdir(parents=True)
        self.reference = self.flow / 'references/run.md'
        self.reference.parent.mkdir()
        self.reference.write_text('# Run\n\n## Readback\n\nVerify.\n\n## Handoff and close\n\nClose.\n')

    def contract(self, path, rows='', rest=''):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# Stage\n\n## Inputs\n\n| Source | File/Location | Section/Scope | Why |\n'
                        '|---|---|---|---|\n' + rows + '\n## Process\n\n' + rest)

    def test_mentions_outside_inputs_do_not_count(self):
        for heading in ('Process', 'Audit', 'Outputs'):
            self.contract(self.stage, rest=f'## {heading}\n\nRead `../references/run.md` "Readback".\n')
            with self.subTest(heading=heading):
                self.assertEqual(reference_consumers(self.reference, [self.stage]), [])

    def test_shared_inputs_require_exact_quoted_headings(self):
        for scope in ('Full file', 'Readback', '"readback"', '"Missing"',
                      '"Readback", "Missing"', 'Full file including "Readback"'):
            self.contract(self.stage, f'| Reference | `../references/run.md` | {scope} | Test |\n')
            with self.subTest(scope=scope):
                self.assertEqual(reference_consumers(self.reference, [self.stage]), [])
        self.contract(self.stage, '| Reference | `../references/run.md` | "Readback", "Handoff and close" | Test |\n')
        self.assertEqual(reference_consumers(self.reference, [self.stage]), [self.stage])

    def test_shared_coordinator_also_requires_sections(self):
        self.contract(self.stage)
        parent = self.flow / 'CONTEXT.md'
        self.contract(parent, '| Reference | `references/run.md` | Full file | Test |\n')
        self.assertEqual(reference_consumers(self.reference, [parent]), [])
        self.contract(parent, '| Reference | `references/run.md` | "Handoff and close" | Test |\n')
        self.assertEqual(reference_consumers(self.reference, [parent]), [parent])

    def test_another_workflow_cannot_claim_a_shared_reference(self):
        self.contract(self.stage)
        other = self.workflows / 'other/01-first/CONTEXT.md'
        self.contract(other, '| Reference | `../../sample/references/run.md` | "Readback" | Test |\n')
        self.assertEqual(reference_consumers(self.reference, [self.stage, other]), [])

    def test_private_reference_requires_its_own_stage_inputs(self):
        private = self.stage.parent / 'references/private.md'
        private.parent.mkdir()
        private.write_text('# Private\n\n## Run\n\nRun.\n')
        sibling = self.flow / '02-second/CONTEXT.md'
        self.contract(self.stage)
        self.contract(sibling, '| Reference | `../01-first/references/private.md` | "Run" | Test |\n')
        self.assertEqual(reference_consumers(private, [self.stage, sibling]), [])
        self.contract(self.stage, '| Reference | `references/private.md` | Full file | Test |\n')
        self.assertEqual(reference_consumers(private, [self.stage, sibling]), [self.stage])


class ProspectingNavigationTests(unittest.TestCase):
    def test_event_coordinator_loads_only_entered_stage(self):
        stages = {'list-prep': '01-list-prep', 'sequence-plan': '02-sequence-plan',
                  'launch': '03-launch', 'zero-recipients': '03-launch'}
        all_stages = {f'{EVENT}/{stage}/CONTEXT.md' for stage in stages.values()}
        for branch, stage in stages.items():
            with self.subTest(branch=branch):
                trace = contract_trace('event-sequence', f'{EVENT}/CONTEXT.md', ROOT, branch)
                self.assertEqual(trace['actual_local_reads'][0], 'AGENTS.md')
                self.assertIn('review_contract', trace)
                self.assertTrue(trace['downstream_handoff'])
                self.assertEqual(set(trace['actual_local_reads']) & all_stages, {f'{EVENT}/{stage}/CONTEXT.md'})
                self.assertNotIn(f'{EVENT}/references/readback.md', trace['actual_local_reads'])
                self.assertEqual([row['source'] for row in trace['input_scopes']].count('Stage'), 1)

    def test_event_early_close_skips_all_stages_and_execution_inputs(self):
        trace = contract_trace('event-sequence', f'{EVENT}/CONTEXT.md', ROOT, 'early-close')
        self.assertEqual([path for path in trace['actual_local_reads'] if path.startswith(EVENT)],
                         [f'{EVENT}/CONTEXT.md', f'{EVENT}/references/readback.md'])
        self.assertEqual([row['scope'] for row in trace['input_scopes'] if row['source'] == 'Reference'],
                         ['"Handoff and close" only for early no-recipient close'])

    def test_unknown_event_entry_is_rejected(self):
        with self.assertRaises(ValueError):
            contract_trace('event-sequence', f'{EVENT}/CONTEXT.md', ROOT, 'all-stages')

    def test_research_aliases_load_only_their_branch_reference(self):
        contract = f'{SIGNAL}/01-research/CONTEXT.md'
        for skill, selected, excluded in (('signal-scan', 'buying-signals', 'adoption'),
                                          ('signal-user-scan', 'adoption', 'buying-signals')):
            with self.subTest(skill=skill):
                trace = contract_trace(skill, contract, ROOT)
                self.assertIn(f'{SIGNAL}/01-research/references/{selected}.md', trace['actual_local_reads'])
                self.assertNotIn(f'{SIGNAL}/01-research/references/{excluded}.md', trace['actual_local_reads'])
                self.assertNotIn(f'{SIGNAL}/CONTEXT.md', trace['actual_local_reads'])
                self.assertFalse(any('/02-outreach/' in path or '/03-followup/' in path for path in trace['actual_local_reads']))


if __name__ == '__main__':
    unittest.main()
