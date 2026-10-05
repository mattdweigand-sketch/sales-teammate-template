"""Onboarding portability, invalid-input and no-overwrite checks with disposable copies."""
import copy
import hashlib
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
        self.answers=json.loads((ROOT/'_core/onboarding/answers.example.json').read_text())
        self.answers['artifact_dir']=str(self.base/'artifacts')
        self.destination=self.base/'configured'

    def test_example_is_complete_and_typed(self):
        self.assertEqual(set(self.answers),set(onboard.read_schema()))
        self.assertEqual(onboard.validate(self.answers)['mode'],'demo')

    def test_missing_and_unknown_answers(self):
        for change in ('missing','unknown'):
            answers=copy.deepcopy(self.answers)
            if change=='missing':del answers['owner_email']
            else:answers['unexpected']=True
            with self.assertRaises(ValueError):onboard.instantiate(answers,self.destination)
            self.assertFalse(self.destination.exists())

    def test_invalid_answer_types(self):
        for key,value in [('internal_domains','example.test'),('quarter_target_default',True),('quarter_target_default',float('nan')),
                          ('quarter_targets',[]),('crm_field_map',[]),('owner_name','')]:
            with self.subTest(key=key):
                answers={**self.answers,key:value}
                with self.assertRaises(ValueError):onboard.validate(answers)

    def test_invalid_identity_timezone_and_origin(self):
        for key,value in [('owner_id','001000000000001AAA'),('owner_email','buyer@different.test'),('timezone','Mars/Base'),
                          ('crm_url','http://crm.test'),('crm_url','https://user:secret@crm.test'),('crm_url','https://crm.test/path'),
                          ('note_initials','bad'),('warehouse_timezone','Mars/Base'),('amount_field','DROP TABLE'),
                          ('owner_name','name\nnew line'),('product_review_date','2026-02-30')]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):onboard.validate({**self.answers,key:value})

    def test_invalid_targets_and_mapping(self):
        for key,value in [('quarter_targets',{'2026-Q9':3}),('quarter_targets',{'2026-Q1':True}),('crm_field_map',{'ARR__c':'DROP TABLE'}),
                          ('crm_field_map',{'unknown':'Revenue__c'}),('warehouse_table_map',{'analytics.analytics.dim_organizations':'x; DELETE'})]:
            with self.subTest(key=key),self.assertRaises(ValueError):onboard.validate({**self.answers,key:value})

    def test_duplicate_mapping_rejects_unmapped_collision(self):
        with self.assertRaises(ValueError):onboard.validate({**self.answers,'crm_field_map':{'ARR__c':'Next_Steps__c'}})

    def test_source_unchanged_and_routes_present(self):
        source=ROOT/'_core/policy.yaml';before=hashlib.sha256(source.read_bytes()).hexdigest()
        status=onboard.instantiate(self.answers,self.destination)
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
        onboard.instantiate(answers,self.destination)
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
        onboard.instantiate(self.answers,self.destination)
        policy=self.destination/'_core/policy.yaml';before=policy.read_bytes()
        with self.assertRaises(ValueError):onboard.instantiate(self.answers,self.destination)
        self.assertEqual(policy.read_bytes(),before)

    def test_overlap_and_artifact_paths_rejected(self):
        for destination in [ROOT,ROOT/'generated',ROOT.parent]:
            with self.subTest(destination=destination),self.assertRaises(ValueError):onboard.instantiate(self.answers,destination)
        for artifact_dir in [str(self.destination),str(self.destination/'outputs'),str(ROOT/'outputs'),'relative/path']:
            with self.subTest(artifact_dir=artifact_dir),self.assertRaises(ValueError):
                onboard.instantiate({**self.answers,'artifact_dir':artifact_dir},self.destination)
        self.assertFalse(self.destination.exists())

    def test_symlink_destination_rejected(self):
        link=self.base/'alias';link.symlink_to(self.base,target_is_directory=True)
        with self.assertRaises(ValueError):onboard.instantiate(self.answers,link/'copy')

    def test_configured_mode_rejects_fictional_identity(self):
        with self.assertRaises(ValueError):onboard.validate({**self.answers,'mode':'configured'})

    def test_environment_and_answer_files_are_not_copied(self):
        import shutil
        source=self.base/'source'
        shutil.copytree(ROOT,source,ignore=lambda directory,names:[name for name in names if name in onboard.EXCLUDED])
        for name in ('.env','.env.production','answers.json','secret.local.json'):
            (source/name).write_text('private setup example')
        onboard.instantiate(self.answers,self.destination,root=source)
        self.assertFalse(any((self.destination/name).exists() for name in ('.env','.env.production','answers.json','secret.local.json')))

    def test_interactive_one_pass_defaults(self):
        with mock.patch('builtins.input',return_value='') as prompt:
            answers=onboard.collect_questionnaire()
        self.assertEqual(prompt.call_count,25)
        self.assertEqual(onboard.validate(answers)['mode'],'demo')

    def test_unconfigured_check_requires_setup(self):
        self.assertEqual(onboard.check(ROOT),1)
        self.assertEqual(onboard.check(ROOT,allow_template=True),0)


if __name__=='__main__':unittest.main()
