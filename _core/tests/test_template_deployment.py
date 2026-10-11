"""Template-specific deployed targets, setup propagation and factory policy holds.

Git fixtures prove local mechanics. They do not authenticate a production runtime.
"""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_core/scripts"))
import yaml

import onboard
from test_workflow_revision_check import WorkflowRevisionGitFixture, CHECK
from test_lost_path_stage_move import reviewed, renderer
from test_pipeline_render import base

ROOT = Path(__file__).resolve().parents[2]


class DeploymentTargetTests(WorkflowRevisionGitFixture):
    def local_policy(self, **target):
        path = self.checkout / '_core/policy.yaml'
        policy = yaml.safe_load(path.read_text())
        policy['tooling']['governing_revision'].update(target)
        path.write_text(yaml.safe_dump(policy, sort_keys=False))
        return path, policy

    def test_snapshot_format_and_target_are_bound(self):
        saved = self.baseline['snapshot']
        self.assertEqual(saved['format'], 2)
        self.assertEqual(saved['target'], {'repository': 'fixture:' + str(self.remote.resolve()),
                                           'remote': 'origin', 'branch': 'main'})
        self.assertIn('tooling.governing_revision',
                      [source.get('selector') for source in saved['scope']['sources']])

    def test_legacy_and_missing_target_never_reuse_approval(self):
        for field in ('legacy', 'missing', 'changed'):
            receipt = deepcopy(self.baseline)
            if field == 'legacy': receipt['snapshot']['format'] = 1
            elif field == 'missing': del receipt['snapshot']['target']
            else: receipt['snapshot']['target']['branch'] = 'other'
            self.assertEqual(self.check('prewrite', receipt)['status'], 'needs-input')

    def test_configured_identity_cannot_use_another_remote(self):
        self.local_policy(repository='fixture:' + str(self.sandbox / 'wrong.git'))
        result = self.check('snapshot')
        self.assertEqual(result['status'], 'needs-input')
        self.assertIn('identity', result['reasons'][0])

    def test_production_cannot_use_local_fixture_remote(self):
        path, policy = self.local_policy()
        policy['template']['mode'] = 'configured'
        path.write_text(yaml.safe_dump(policy))
        self.assertEqual(self.check('snapshot')['status'], 'needs-input')

    def test_unconfigured_files_do_not_supply_write_freshness(self):
        path, policy = self.local_policy()
        policy['template']['mode'] = 'unconfigured'
        path.write_text(yaml.safe_dump(policy))
        self.assertEqual(self.check('snapshot')['status'], 'needs-input')

    def test_missing_target_and_gitless_copy_hold(self):
        self.local_policy(repository=None)
        self.assertEqual(self.check('snapshot')['status'], 'needs-input')
        gitless = self.sandbox / 'gitless'
        gitless.mkdir()
        self.assertEqual(CHECK.check_workflow_revision(gitless, self.scope, phase='snapshot')['status'], 'needs-input')

    def test_nondefault_remote_and_branch_use_actual_configured_bytes(self):
        branch = 'deploy/configured'
        policy_path = self.upstream / '_core/policy.yaml'
        policy = yaml.safe_load(policy_path.read_text())
        policy['tooling']['governing_revision'].update(remote='company', branch=branch)
        policy_path.write_text(yaml.safe_dump(policy, sort_keys=False))
        self.git(self.upstream, 'checkout', '-b', branch)
        self.commit()
        self.git(self.upstream, 'push', 'origin', branch)
        self.git(self.checkout, 'remote', 'rename', 'origin', 'company')
        self.git(self.checkout, 'fetch', 'company', branch)
        self.git(self.checkout, 'checkout', '--detach', 'FETCH_HEAD')
        baseline = self.check('snapshot')
        self.assertEqual(baseline['status'], 'unchanged', baseline)
        self.assertEqual(baseline['snapshot']['target']['branch'], branch)
        self.assertEqual(self.check('prewrite', baseline)['status'], 'unchanged')
        self.assertEqual(self.check('prewrite', self.baseline)['status'], 'needs-input')
        # Unselected main may change without altering the deployed target.
        self.git(self.upstream, 'checkout', 'main')
        self.publish('README.md', 'Synthetic', 'Unselected main changed')
        self.assertEqual(self.check('prewrite', baseline)['status'], 'unchanged')

    def test_unsafe_ref_or_remote_options_hold_without_source_mutation(self):
        for target in ({'remote': '--upload-pack=bad'}, {'branch': '-bad'}, {'branch': '../bad'},
                       {'branch': 'main:other'}, {'branch': 'main\nother'}):
            self.local_policy(**target)
            before = self.git(self.checkout, 'status', '--porcelain')
            self.assertEqual(self.check('snapshot')['status'], 'needs-input')
            self.assertEqual(before, self.git(self.checkout, 'status', '--porcelain'))
            self.local_policy(remote='origin', branch='main')

    def test_github_https_ssh_identity_normalization(self):
        values = ('Owner/Repo', 'https://github.com/Owner/Repo.git',
                  'git@github.com:Owner/Repo.git', 'ssh://git@github.com/Owner/Repo.git')
        self.assertEqual({CHECK._repository_identity(value) for value in values}, {'github.com/owner/repo'})

    def test_repository_urls_reject_credentials_and_unsupported_shapes(self):
        for value in ('https://user:secret@github.com/o/r', 'https://github.com/o/r?token=secret',
                      'http://github.com/o/r', 'https://github.com/o/r/extra', '--upload-pack=bad',
                      'ssh://user@github.com/o/r', 'https://github.com/o/..',
                      'https://github.com:secret/o/r', 'https://[bad/o/r'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                CHECK._repository_identity(value)


class SetupPortTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.scratch = Path(self.temp.name).resolve()
        self.answers = json.loads((ROOT / '_core/tests/fixtures/onboarding/answers.fixture.json').read_text())
        self.answers.update(company_name='Synthetic Seller', owner_name='Avery Operator',
                            owner_email='avery@synthetic-seller.company', internal_domains=['synthetic-seller.company'],
                            owner_id='005123456789012ABC', crm_url='https://synthetic-seller.my.salesforce.com',
                            note_initials='AO', timezone='America/New_York', artifact_dir=str(self.scratch / 'artifacts'),
                            amount_field='Revenue__c', crm_field_map={'ARR__c': 'Revenue__c'},
                            warehouse_table_map={'analytics.analytics.fct_queries': 'company.metrics.query_events'},
                            quarter_targets={'2027-Q1': 90000}, quarter_target_default=120000,
                            operating_policy_review='https://synthetic-seller.company/reviews/sales-policy',
                            warehouse='SYNTHETIC_READONLY_WH', ops_channel='C1234567890',
                            ops_owners=['U1234567890'], deal_desk_channel='C1234567891')

    def configure(self, name, settings):
        self.answers['integration_setup'][name] = {'choice': 'configure', 'transport': 'api',
            'connection': 'Synthetic adapter', 'auth': 'oauth', 'settings': settings}

    def test_company_targets_maps_and_optional_slides_have_single_homes(self):
        self.configure('github', {'repository': 'synthetic-org/deployment', 'remote': 'company', 'branch': 'deploy/configured'})
        self.configure('google_slides', {'presentation_id': 'synthetic-presentation',
                                       'slide_title': 'Avery Operator | {quarter} Plan'})
        destination = self.scratch / 'company'
        status = onboard.instantiate(self.answers, destination)
        policy = yaml.safe_load((destination / '_core/policy.yaml').read_text())
        self.assertFalse((destination / '.git').exists())
        self.assertFalse(status['external_ready'])
        self.assertEqual(len(list((destination / '_core/onboarding/skill-pointers').glob('*.md'))), 19)
        self.assertEqual(len(status['integrations']), 22)
        self.assertEqual(policy['tooling']['governing_revision'],
                         {'repository': 'synthetic-org/deployment', 'remote': 'company', 'branch': 'deploy/configured'})
        for name in ('github', 'google_slides'):
            self.assertEqual(policy['template']['integrations'][name]['settings'], {})
        self.assertEqual(policy['forecast']['deck']['presentation_id'], 'synthetic-presentation')
        self.assertEqual(policy['forecast']['amount_field'], 'Revenue__c')
        self.assertEqual(policy['forecast']['target_default'], 120000)
        self.assertEqual(policy['pipeline']['worth_growing_min_employees'], None)
        text = (destination / 'workspaces/pipeline/references/pilot-usage-queries.md').read_text()
        self.assertIn('company.metrics.query_events', text)
        self.assertNotIn('ANALYTICS.ANALYTICS.FCT_QUERIES', text)
        self.assertEqual(policy['momentum']['display_tz'], 'America/New_York')
        with redirect_stdout(io.StringIO()): self.assertEqual(onboard.check(destination), 0)

    def test_size_floor_types_and_review_reference_are_required(self):
        for value in (None, 1, 1000):
            self.assertEqual(onboard.validate({**self.answers, 'lost_path_min_employees': value})['lost_path_min_employees'], value)
        for value in (False, True, 0, -1, '1000', 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                onboard.validate({**self.answers, 'lost_path_min_employees': value})
        for value in ('', None, False):
            with self.assertRaises(ValueError): onboard.validate({**self.answers, 'operating_policy_review': value})
        missing = deepcopy(self.answers)
        del missing['operating_policy_review']
        with self.assertRaises(ValueError): onboard.validate(missing)

    def test_deferred_slides_keeps_operator_title_and_legacy_auto_move_holds(self):
        destination = self.scratch / 'company'
        onboard.instantiate(self.answers, destination)
        path = destination / '_core/policy.yaml'
        policy = yaml.safe_load(path.read_text())
        self.assertIsNone(policy['forecast']['deck']['presentation_id'])
        self.assertIn('Avery Operator', policy['forecast']['deck']['slide_title'])
        policy['template']['auto_date_move'] = True
        path.write_text(yaml.safe_dump(policy))
        with redirect_stdout(io.StringIO()): self.assertEqual(onboard.check(destination), 1)

    def test_optional_deck_and_adopter_authority_are_explicit(self):
        deck = (ROOT / 'workspaces/forecasting/workflows/forecast-weekly/references/deck.md').read_text()
        self.assertIn('skip deck reads and planning', deck)
        self.assertIn('D is unavailable and continue the supported forecast and CRM letters', deck)
        self.assertNotIn('Dana', deck)
        conventions = (ROOT / '_core/CONVENTIONS.md').read_text()
        self.assertIn('The template grants no standing merge approval', conventions)
        adapters = (ROOT / '_core/onboarding/adapters.md').read_text()
        self.assertIn('native teammate mail capability once', adapters)
        self.assertNotIn('Try session send once', adapters)

    def test_null_floor_holds_size_path_without_removing_independent_policy(self):
        policy = yaml.safe_load((ROOT / '_core/policy.yaml').read_text())
        run = renderer.Run(base(), policy)
        self.assertIsNone(run.lost_path_destination(reviewed()))
        self.assertTrue(run.operator_statement_valid({'quote': 'Close this deal as lost.', 'date': '2026-09-27'}))
        for value in (0, False, -1):
            policy['pipeline']['worth_growing_min_employees'] = value
            self.assertIsNone(run.lost_path_destination(reviewed()))
