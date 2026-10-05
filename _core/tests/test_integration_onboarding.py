"""Integration omissions, unsafe answers, deferred capabilities and real setting propagation."""
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '_core/scripts'))
import onboard


class IntegrationOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp' if Path('/private/tmp').exists() else None)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.destination = self.base / 'company'
        self.answers = json.loads((ROOT / '_core/tests/fixtures/onboarding/answers.fixture.json').read_text())
        self.answers.update(owner_email='rep@synthetic-seller.company', internal_domains=['synthetic-seller.company'],
                            owner_id='005123456789012ABC', crm_url='https://synthetic-seller.my.salesforce.com',
                            warehouse='SYNTHETIC_READONLY_WH', ops_channel='C1234567890',
                            ops_owners=['U1234567890'], deal_desk_channel='C1234567891',
                            artifact_dir=str(self.base / 'artifacts'))
        self.registry = onboard.read_integrations()

    def configure(self, name, settings=None, **changes):
        entry = {'choice': 'configure', 'transport': 'native', 'connection': 'Synthetic adapter',
                 'auth': 'runtime', 'settings': settings or {}}
        entry.update(changes)
        self.answers['integration_setup'][name] = entry
        return entry

    def create(self):
        return onboard.instantiate(self.answers, self.destination)

    def check(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = onboard.check(self.destination)
        return code, json.loads(output.getvalue())

    def test_inventory_resolves_every_source_and_workflow(self):
        names = {name for name, _, _ in onboard.routes(ROOT)}
        self.assertEqual(len(self.registry), 21)
        self.assertEqual(set().union(*(set(spec['workflows']) for spec in self.registry.values())), names)
        for key, spec in self.registry.items():
            with self.subTest(integration=key):
                self.assertLessEqual(set(spec['workflows']), names)
                self.assertTrue(all((ROOT / path).is_file() for path in spec['source']))
                for field in ('setup', 'authentication', 'verify', 'scope'):
                    self.assertTrue(spec[field].strip())

    def test_new_company_requires_an_explicit_choice_for_every_integration(self):
        for name in self.registry:
            answers = copy.deepcopy(self.answers)
            del answers['integration_setup'][name]
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'every system'):
                onboard.instantiate(answers, self.destination)
            self.assertFalse(self.destination.exists())

    def test_unknown_integration_rejected(self):
        self.answers['integration_setup']['invented'] = {'choice': 'defer', 'reason': 'Pending'}
        with self.assertRaisesRegex(ValueError, 'every system'):
            self.create()
        self.assertFalse(self.destination.exists())

    def test_bad_choice_or_unexplained_deferral_rejected(self):
        for entry in ({'choice': 'ready'}, {'choice': 'defer', 'reason': ''},
                      {'choice': 'not_used'}, {'choice': 'defer', 'reason': 'Pending', 'settings': {}}):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                onboard.validate_integrations({**self.answers['integration_setup'], 'audio': entry})

    def test_configure_does_not_mean_authenticated_or_verified(self):
        self.configure('web_research')
        status = self.create()
        self.assertFalse(status['external_ready'])
        self.assertFalse(status['integrations']['web_research']['live_verified'])
        self.assertEqual(set(status['pending']), set(self.registry))
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertIn('web_research', result['pending_live_verification'])
        self.assertNotIn('web_research', result['deferred_or_unused'])

    def test_deferral_preserves_specific_reason_and_affected_work(self):
        self.answers['integration_setup']['audio'] = {'choice': 'defer', 'reason': 'Use written briefs until speech is connected.'}
        status = self.create()
        policy = yaml.safe_load((self.destination / '_core/policy.yaml').read_text())
        self.assertEqual(policy['template']['integrations']['audio']['reason'], 'Use written briefs until speech is connected.')
        self.assertEqual(status['integrations']['audio']['workflows'], ['sales-call-prep'])
        self.assertIn('audio', self.check()[1]['deferred_or_unused'])

    def test_unused_surface_does_not_grant_readiness(self):
        self.answers['integration_setup']['event_invites'] = {'choice': 'not_used', 'reason': 'No event invite application.'}
        self.assertFalse(self.create()['external_ready'])
        self.assertIn('event_invites', self.check()[1]['deferred_or_unused'])

    def test_missing_or_unknown_connection_settings_rejected(self):
        entry = self.configure('audio')
        with self.assertRaisesRegex(ValueError, 'settings must match'):
            self.create()
        entry['settings'] = {'voice': 'configured-voice', 'unknown': 'extra'}
        with self.assertRaisesRegex(ValueError, 'settings must match'):
            self.create()
        self.assertFalse(self.destination.exists())

    def test_invalid_connection_or_auth_method_rejected(self):
        for changes in ({'transport': 'imagined'}, {'auth': 'authenticated'}, {'connection': ''}):
            self.configure('web_research', **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.create()
        self.assertFalse(self.destination.exists())

    def test_no_secret_values_in_answers_or_connection_metadata(self):
        for changes in ({'api_key': 'must-not-appear-in-errors'},
                        {'connection': 'https://user:must-not-appear-in-errors@api.company'},
                        {'connection': 'https://api.company?api_key=must-not-appear-in-errors'},
                        {'connection': 'Bearer must-not-appear-in-errors'},
                        {'connection': 'sk-' + 'x' * 25}):
            self.configure('web_research', **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError) as error:
                self.create()
            self.assertNotIn('must-not-appear-in-errors', str(error.exception))
        self.assertFalse(self.destination.exists())

    def test_private_key_in_nested_answers_rejected(self):
        self.configure('runtime', {'project': 'Synthetic project', 'deployment_root': 'Runtime root',
                                  'workspace_destinations': {name: '-----BEGIN RSA PRIVATE KEY-----'
                                                            for name in ('prospecting','pipeline','deal-coaching','forecasting','systems')}})
        with self.assertRaisesRegex(ValueError, 'secret store'):
            self.create()

    def test_configured_settings_replace_assistant_org_tool_voice_and_integration_users(self):
        self.configure('gmail', {'assistant_email': 'assistant@synthetic-seller.company'})
        self.configure('org_lookup', {'tool_name': 'company_org_lookup'})
        self.configure('audio', {'voice': 'company_voice'})
        self.configure('crm_sync', {'ignored_owner_ids': ['005123456789013ABC']})
        self.create()
        policy = yaml.safe_load((self.destination / '_core/policy.yaml').read_text())
        self.assertEqual(policy['email_voice']['computer_sender'], 'assistant@synthetic-seller.company')
        self.assertEqual(policy['tooling']['org_lookup_tool'], 'company_org_lookup')
        self.assertEqual(policy['call_prep']['audio']['voice'], 'company_voice')
        self.assertEqual(policy['prospecting']['scan']['warm_engagement']['ignored_owner_ids'], ['005123456789013ABC'])
        self.assertEqual(policy['template']['integrations']['org_lookup']['settings'], {})
        self.assertEqual(policy['template']['integrations']['audio']['settings'], {})
        self.assertEqual(self.check()[0], 0)

    def test_no_assumed_integration_user_when_sync_is_deferred(self):
        self.create()
        policy = yaml.safe_load((self.destination / '_core/policy.yaml').read_text())
        self.assertEqual(policy['prospecting']['scan']['warm_engagement']['ignored_owner_ids'], [])

    def test_invalid_assistant_domain_or_fictional_integration_id_rejected(self):
        self.configure('gmail', {'assistant_email': 'assistant@outside.company'})
        with self.assertRaisesRegex(ValueError, 'internal domain'):
            self.create()
        self.answers['integration_setup']['gmail'] = {'choice': 'defer', 'reason': 'Pending'}
        self.configure('crm_sync', {'ignored_owner_ids': ['005000000000002AAA']})
        with self.assertRaisesRegex(ValueError, 'actual 18-character'):
            self.create()

    def test_commercial_catalog_replaced_and_shape_checked(self):
        close = yaml.safe_load((ROOT / '_core/policy.yaml').read_text())['close']
        books = copy.deepcopy(close['price_books'])
        books['annual']['name'] = 'Synthetic Annual Catalog'
        books['annual']['annual_list'] = {'max': 2400, 'pro': 900}
        books['pilot']['name'] = 'Synthetic Pilot Catalog'
        credits = {**close['credits'], 'product': 'Synthetic Credits', 'bonus_product': 'Synthetic Bonus'}
        self.configure('billing', {'terms': close['terms_default'], 'price_books': books, 'credits': credits})
        self.create()
        policy = yaml.safe_load((self.destination / '_core/policy.yaml').read_text())
        self.assertEqual(policy['close']['price_books'], books)
        self.assertEqual(policy['close']['credits'], credits)
        self.assertEqual(self.check()[0], 0)

    def test_malformed_provisioning_payload_cannot_copy(self):
        close = yaml.safe_load((ROOT / '_core/policy.yaml').read_text())['close']['setup_trial']
        self.configure('provisioning', {'flow_name': 'Synthetic_Create_Org', 'tier': 'actual_tier',
                                       'payload': {'unrecognized': True}, 'success_fields': close['success_fields'],
                                       'restore_after': close['restore_after']})
        with self.assertRaisesRegex(ValueError, 'compatible policy key'):
            self.create()
        self.assertFalse(self.destination.exists())

    def test_warehouse_and_slack_answers_can_be_omitted_when_deferred(self):
        for key in ('warehouse', 'warehouse_timezone', 'ops_channel', 'ops_owners', 'deal_desk_channel'):
            del self.answers[key]
        self.create()
        self.assertEqual(self.check()[0], 0)
        self.assertIn('warehouse', self.check()[1]['deferred_or_unused'])

    def test_selected_warehouse_requires_company_values(self):
        self.configure('warehouse', {'schema_review': 'External schema review'})
        del self.answers['warehouse']
        with self.assertRaisesRegex(ValueError, 'warehouse is required'):
            self.create()
        self.assertFalse(self.destination.exists())

    def test_fictional_ids_or_warehouse_rejected_for_normal_setup(self):
        for key, value in [('owner_id','005000000000001AAA'), ('ops_channel','C0000000001'),
                           ('ops_owners',['U0000000001']), ('warehouse','EXAMPLE_READONLY_WH')]:
            answers = {**self.answers, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                onboard.instantiate(answers, self.destination)
        self.assertFalse(self.destination.exists())

    def test_amount_answer_alone_maps_revenue_consumers_and_conflicts_fail(self):
        self.answers['amount_field'] = 'Revenue__c'
        self.create()
        self.assertNotIn('ARR__c', (self.destination / '_core/scripts/coverage_check.py').read_text())
        self.assertEqual(self.check()[0], 0)
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            onboard.validate({**self.answers, 'crm_field_map': {'ARR__c': 'Different_Revenue__c'}})

    def test_operator_and_warehouse_timezones_remain_distinct(self):
        self.answers.update(timezone='Europe/London', warehouse_timezone='UTC')
        self.create()
        scripts = self.destination / 'workspaces/pipeline/workflows/pilot-usage/scripts'
        self.assertIn('ZoneInfo("Europe/London")', (scripts / 'resolve_pilot.py').read_text())
        self.assertIn('ZoneInfo("UTC")', (scripts / 'assemble_pilot_usage_input.py').read_text())

    def test_interview_explains_auth_and_verification_for_every_system(self):
        responses = [part for _ in self.registry for part in ('defer', 'Pending administrator setup.')]
        output = io.StringIO()
        with mock.patch('builtins.input', side_effect=responses) as prompt, redirect_stdout(output):
            selected = onboard.collect_integrations()
        self.assertEqual(set(selected), set(self.registry))
        self.assertEqual(prompt.call_count, len(self.registry) * 2)
        for spec in self.registry.values():
            self.assertIn(spec['authentication'], output.getvalue())
            self.assertIn(spec['verify'], output.getvalue())

    def test_terminal_configured_surface_collects_metadata_and_settings(self):
        responses = []
        for name in self.registry:
            if name == 'audio':
                responses.extend(['configure', 'api', 'Synthetic speech adapter', 'api_key', 'actual_voice'])
            else:
                responses.extend(['defer', 'Pending company setup.'])
        with mock.patch('builtins.input', side_effect=responses), redirect_stdout(io.StringIO()):
            selected = onboard.collect_integrations()
        onboard.validate_integrations(selected)
        self.assertEqual(selected['audio']['settings'], {'voice': 'actual_voice'})
        self.assertEqual(selected['audio']['auth'], 'api_key')

    def test_complete_company_selection_with_all_surfaces_still_needs_live_verification(self):
        policy = yaml.safe_load((ROOT / '_core/policy.yaml').read_text())
        for name, spec in self.registry.items():
            settings = {}
            for key, field in spec['settings'].items():
                if field.get('policy_shape'):
                    settings[key] = copy.deepcopy(onboard.nested_get(policy, field['target']))
                elif field['type'] == 'list' and field.get('target'):
                    settings[key] = copy.deepcopy(onboard.nested_get(policy, field['target']))
                elif field.get('keys'):
                    settings[key] = {workspace: 'Synthetic runtime thread ' + workspace for workspace in field['keys']}
                elif key == 'ignored_owner_ids':
                    settings[key] = []
                elif key == 'assistant_email':
                    settings[key] = 'assistant@synthetic-seller.company'
                elif field.get('format') == 'tool':
                    settings[key] = 'Synthetic_' + key
                else:
                    settings[key] = 'Synthetic company ' + key
            self.configure(name, settings)
        status = self.create()
        self.assertEqual(len(status['integrations']), 21)
        self.assertTrue(all(entry['choice'] == 'configure' and not entry['live_verified'] for entry in status['integrations'].values()))
        code, result = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(result['deferred_or_unused'], [])
        self.assertFalse(result['external_ready'])

    def test_pointer_lists_only_applicable_surfaces_and_live_gate(self):
        self.create()
        pointers = self.destination / '_core/onboarding/skill-pointers'
        research = (pointers / 'signal-scan.md').read_text()
        self.assertIn('web_research', research)
        dependencies = next(line for line in research.splitlines() if line.startswith('Integration choices under'))
        self.assertNotIn('warehouse', dependencies)
        self.assertIn('warehouse', (pointers / 'signal-user-scan.md').read_text())
        self.assertIn('current live verification', research)

    def test_missing_pointer_or_integration_and_false_readiness_are_detected(self):
        self.create()
        (self.destination / '_core/onboarding/skill-pointers/close.md').unlink()
        policy_path = self.destination / '_core/policy.yaml'
        policy = yaml.safe_load(policy_path.read_text())
        policy['template']['external_ready'] = True
        del policy['template']['integrations']['credentials']
        policy_path.write_text(yaml.safe_dump(policy))
        code, report = self.check()
        self.assertEqual(code, 1)
        self.assertTrue(any('external readiness' in error for error in report['errors']))
        self.assertTrue(any('skill pointer close' in error for error in report['errors']))
        self.assertTrue(any('every system' in error for error in report['errors']))

    def test_setup_from_existing_company_workspace_is_rejected(self):
        self.create()
        with self.assertRaisesRegex(ValueError, 'unconfigured template'):
            onboard.instantiate(self.answers, self.base / 'second', root=self.destination)
        self.assertFalse((self.base / 'second').exists())

    def test_cli_rejects_answers_inside_template_and_accepts_external_file(self):
        with redirect_stdout(io.StringIO()), mock.patch('sys.stderr', new=io.StringIO()) as errors:
            code = onboard.main(['setup', '--answers', str(ROOT / '_core/tests/fixtures/onboarding/answers.fixture.json'),
                                 '--destination', str(self.destination)])
        self.assertEqual(code, 1)
        self.assertIn('outside the template', errors.getvalue())
        self.assertFalse(self.destination.exists())
        answer_file = self.base / 'company-answers.json'
        answer_file.write_text(json.dumps(self.answers))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(onboard.main(['setup','--answers',str(answer_file),'--destination',str(self.destination)]), 0)

    def test_untracked_customer_file_and_runtime_state_are_not_copied(self):
        source = self.base / 'source'
        import shutil
        shutil.copytree(ROOT, source, ignore=lambda directory, names: [name for name in names if onboard.excluded_name(name)])
        subprocess.run(['git','init','-q',str(source)], check=True, capture_output=True)
        subprocess.run(['git','-C',str(source),'add','.'], check=True, capture_output=True)
        (source / 'private-customer.md').write_text('Synthetic private customer evidence')
        (source / '.perplexity').mkdir()
        (source / '.perplexity/result.json').write_text('{}')
        onboard.instantiate(self.answers, self.destination, root=source)
        self.assertFalse((self.destination / 'private-customer.md').exists())
        self.assertFalse((self.destination / '.perplexity').exists())


if __name__ == '__main__':
    unittest.main()
