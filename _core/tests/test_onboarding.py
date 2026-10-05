"""Onboarding portability, invalid-input and no-overwrite checks with disposable copies."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import yaml

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'_core/scripts'))
import onboard


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/private/tmp' if Path('/private/tmp').exists() else None)
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.answers=json.loads((ROOT/'_core/tests/fixtures/onboarding/answers.fixture.json').read_text())
        self.answers['artifact_dir']=str(self.base/'artifacts')
        self.destination=self.base/'configured'

    def validate_fixture(self, answers):
        return onboard.validate(answers,simulation=True)

    def instantiate_fixture(self, answers, destination, root=ROOT):
        return onboard.instantiate(answers,destination,root=root,simulation=True)

    def company_answers(self):
        # Syntactically valid company settings for local tests, with no provider calls.
        return {**self.answers,'owner_email':'rep@synthetic-seller.company',
                'internal_domains':['synthetic-seller.company'],
                'crm_url':'https://synthetic-seller.my.salesforce.com',
                'owner_id':'005123456789012ABC','warehouse':'SYNTHETIC_READONLY_WH',
                'ops_channel':'C1234567890','ops_owners':['U1234567890'],
                'deal_desk_channel':'C1234567891'}

    def test_fixture_is_complete_and_typed(self):
        self.assertEqual(set(self.answers),set(onboard.read_schema()))
        self.assertEqual(self.validate_fixture(self.answers)['mode'],'demo')

    def test_missing_and_unknown_answers(self):
        for change in ('missing','unknown'):
            answers=copy.deepcopy(self.answers)
            if change=='missing':del answers['owner_email']
            else:answers['unexpected']=True
            with self.assertRaises(ValueError):self.instantiate_fixture(answers,self.destination)
            self.assertFalse(self.destination.exists())

    def test_invalid_answer_types(self):
        for key,value in [('internal_domains','example.test'),('quarter_target_default',True),('quarter_target_default',float('nan')),
                          ('quarter_targets',[]),('crm_field_map',[]),('owner_name','')]:
            with self.subTest(key=key):
                answers={**self.answers,key:value}
                with self.assertRaises(ValueError):self.validate_fixture(answers)

    def test_invalid_identity_timezone_and_origin(self):
        for key,value in [('owner_id','001000000000001AAA'),('owner_email','buyer@different.test'),('timezone','Mars/Base'),
                          ('crm_url','http://crm.test'),('crm_url','https://user:secret@crm.test'),('crm_url','https://crm.test/path'),
                          ('note_initials','bad'),('warehouse_timezone','Mars/Base'),('amount_field','DROP TABLE'),
                          ('owner_name','name\nnew line'),('product_review_date','2026-02-30')]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.validate_fixture({**self.answers,key:value})

    def test_invalid_targets_and_mapping(self):
        for key,value in [('quarter_targets',{'2026-Q9':3}),('quarter_targets',{'2026-Q1':True}),('crm_field_map',{'ARR__c':'DROP TABLE'}),
                          ('crm_field_map',{'unknown':'Revenue__c'}),('warehouse_table_map',{'analytics.analytics.dim_organizations':'x; DELETE'})]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate_fixture({**self.answers,key:value})

    def test_duplicate_mapping_rejects_unmapped_collision(self):
        with self.assertRaises(ValueError):self.validate_fixture({**self.answers,'crm_field_map':{'ARR__c':'Next_Steps__c'}})

    def test_source_unchanged_and_routes_present(self):
        source=ROOT/'_core/policy.yaml';before=hashlib.sha256(source.read_bytes()).hexdigest()
        status=self.instantiate_fixture(self.answers,self.destination)
        self.assertFalse(status['external_ready'])
        self.assertEqual(len(list((self.destination/'_core/onboarding/skill-pointers').glob('*.md'))),18)
        self.assertFalse((self.destination/'.git').exists())
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
        self.assertEqual(onboard.check(self.destination),0)

    def test_different_company_timezone_targets_and_fields(self):
        answers={**self.answers,'company_name':'Demo West','owner_name':'Alex Demo','owner_email':'alex@demo-west.test',
                 'internal_domains':['demo-west.test'],'timezone':'Europe/London','warehouse_timezone':'UTC',
                 'note_initials':'AD','product_name':'Demo Service','product_value':'Demo Service coordinates review work.',
                 'quarter_targets':{'2026-Q4':12345},'quarter_target_default':43210,'amount_field':'Revenue__c',
                 'crm_field_map':{'ARR__c':'Revenue__c','Next_Steps__c':'Next_Action__c'}}
        self.instantiate_fixture(answers,self.destination)
        policy=yaml.safe_load((self.destination/'_core/policy.yaml').read_text())
        self.assertEqual(policy['forecast']['amount_field'],'Revenue__c')
        self.assertEqual(policy['forecast']['targets'],{'2026-Q4':12345})
        self.assertEqual(policy['momentum']['attendee_email'],'alex@demo-west.test')
        self.assertEqual(policy['coach']['schedule']['deal_review']['tz'],'Europe/London')
        self.assertEqual(policy['salesforce']['note_prefix'],'M/D/YY AD - ')
        text=(self.destination/'workspaces/prospecting/workflows/outreach/references/talk-track.md').read_text()
        self.assertEqual(policy['template']['product_value'],'Demo Service coordinates review work.')
        self.assertNotIn('Example Product',text)
        self.assertNotIn('Next_Steps__c',(self.destination/'_core/scripts/hygiene_check.py').read_text())

    def test_repeat_refuses_without_changing_destination(self):
        self.instantiate_fixture(self.answers,self.destination)
        policy=self.destination/'_core/policy.yaml';before=policy.read_bytes()
        with self.assertRaises(ValueError):self.instantiate_fixture(self.answers,self.destination)
        self.assertEqual(policy.read_bytes(),before)

    def test_overlap_and_artifact_paths_rejected(self):
        for destination in [ROOT,ROOT/'generated',ROOT.parent]:
            with self.subTest(destination=destination),self.assertRaises(ValueError):self.instantiate_fixture(self.answers,destination)
        for artifact_dir in [str(self.destination),str(self.destination/'outputs'),str(ROOT/'outputs'),'relative/path']:
            with self.subTest(artifact_dir=artifact_dir),self.assertRaises(ValueError):
                self.instantiate_fixture({**self.answers,'artifact_dir':artifact_dir},self.destination)
        self.assertFalse(self.destination.exists())

    def test_symlink_destination_rejected(self):
        link=self.base/'alias';link.symlink_to(self.base,target_is_directory=True)
        with self.assertRaises(ValueError):self.instantiate_fixture(self.answers,link/'copy')

    def test_normal_setup_rejects_fictional_fixture_without_partial_copy(self):
        with self.assertRaisesRegex(ValueError,'your company email and Salesforce origin'):
            onboard.instantiate(self.answers,self.destination)
        self.assertFalse(self.destination.exists())

    def test_mode_is_not_an_onboarding_answer(self):
        for mode in ('demo','configured'):
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'unknown answers'):
                onboard.validate({**self.company_answers(),'mode':mode})

    def test_normal_company_setup_rejects_reserved_email_or_crm_separately(self):
        for domain in ('seller.test','seller.example','seller.invalid','example.com','sub.example.org'):
            for surface in ('email','crm'):
                answers=self.company_answers()
                if surface=='email':
                    answers.update(owner_email='rep@'+domain,internal_domains=[domain])
                else:
                    answers['crm_url']='https://'+domain
                with self.subTest(domain=domain,surface=surface),self.assertRaisesRegex(ValueError,'reserved example domains'):
                    onboard.instantiate(answers,self.destination)
                self.assertFalse(self.destination.exists())

    def test_normal_setup_uses_company_settings_and_keeps_live_checks_pending(self):
        answers=self.company_answers()
        status=onboard.instantiate(answers,self.destination)
        policy=yaml.safe_load((self.destination/'_core/policy.yaml').read_text())
        self.assertEqual(status['mode'],'configured')
        self.assertFalse(status['external_ready'])
        self.assertTrue(status['pending'])
        self.assertEqual(policy['prospecting']['identity']['owner_email'],answers['owner_email'])
        self.assertEqual(policy['salesforce']['instance_url'],answers['crm_url'])
        self.assertEqual(onboard.check(self.destination),0)
        self.assertEqual(len(list((self.destination/'_core/onboarding/skill-pointers').glob('*.md'))),18)

    def test_environment_and_answer_files_are_not_copied(self):
        import shutil
        source=self.base/'source'
        shutil.copytree(ROOT,source,ignore=lambda directory,names:[name for name in names if name in onboard.EXCLUDED])
        for name in ('.env','.env.production','answers.json','secret.local.json'):
            (source/name).write_text('private setup example')
        self.instantiate_fixture(self.answers,self.destination,root=source)
        self.assertFalse(any((self.destination/name).exists() for name in ('.env','.env.production','answers.json','secret.local.json')))

    def test_interactive_company_questionnaire_has_no_mode_choice(self):
        expected=self.company_answers()
        responses=[expected[key] if spec['type']=='string' else json.dumps(expected[key])
                   for key,spec in onboard.read_schema().items()]
        responses = responses[:-1]
        with mock.patch('builtins.input',side_effect=responses) as prompt, \
                mock.patch.object(onboard,'collect_integrations',return_value=expected['integration_setup']):
            answers=onboard.collect_questionnaire()
        self.assertEqual(prompt.call_count,len(onboard.read_schema())-1)
        self.assertNotIn('mode',answers)
        self.assertEqual(onboard.validate(answers)['mode'],'configured')
        self.assertEqual(answers,expected)
        self.assertFalse(any('demo' in call.args[0].lower() for call in prompt.call_args_list))

    def test_blank_interview_cannot_accept_fictional_defaults(self):
        with mock.patch('builtins.input',return_value='') as prompt, \
                mock.patch.object(onboard,'collect_integrations',return_value=self.answers['integration_setup']):
            answers=onboard.collect_questionnaire()
        self.assertEqual(prompt.call_count,len(onboard.read_schema())-1)
        self.assertNotIn('owner_email',answers)
        with self.assertRaisesRegex(ValueError,'missing answers'):
            onboard.instantiate(answers,self.destination)
        self.assertFalse(self.destination.exists())

    def test_unconfigured_check_requires_setup(self):
        self.assertEqual(onboard.check(ROOT),1)
        self.assertEqual(onboard.check(ROOT,allow_template=True),0)


if __name__=='__main__':unittest.main()
