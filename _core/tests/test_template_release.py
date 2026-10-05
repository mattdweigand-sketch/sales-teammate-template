"""Generalization boundaries and local connector failure cases for the reusable release."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'_core/scripts'))
sys.path.insert(0,str(ROOT/'workspaces/prospecting/scripts'))
from rehearse import LocalConnector


class TemplateReleaseTests(unittest.TestCase):
    def test_source_identity_and_collateral_are_absent(self):
        policy=yaml.safe_load((ROOT/'_core/policy.yaml').read_text())
        self.assertEqual(policy['salesforce']['instance_url'],'https://crm.example.invalid')
        self.assertEqual(policy['prospecting']['identity']['owner_email'],'rep@seller.example')
        self.assertTrue(policy['prospecting']['identity']['sfdc_user_id'].startswith('005000000000'))
        self.assertEqual(policy['close']['ops_channel'],'C0000000001')
        self.assertEqual(policy['close']['ops_owners'],['U0000000001','U0000000002'])
        self.assertEqual({p.name for p in (ROOT/'_core/collateral').iterdir()},{'approved-material.md'})

    def test_default_permission_and_quota_state_is_demo_only(self):
        policy=yaml.safe_load((ROOT/'_core/policy.yaml').read_text())
        self.assertEqual(policy['template']['mode'],'unconfigured')
        self.assertFalse(policy['template']['external_ready'])
        self.assertFalse(policy['template']['auto_date_move'])
        self.assertFalse(policy['prospecting']['approval']['unattended_writes'])
        self.assertEqual(policy['forecast']['targets'],{})
        self.assertEqual(policy['forecast']['target_default'],250000)

    def test_all_fonts_are_local_and_hash_verified(self):
        policy=yaml.safe_load((ROOT/'_core/policy.yaml').read_text())
        for font in policy['pilot_usage']['pdf']['fonts'].values():
            path=ROOT/font['source_path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),font['sha256'])
            self.assertTrue(font['url'].startswith('bundle:'))
        self.assertTrue((ROOT/'_core/assets/fonts/LICENSE.txt').is_file())

    def test_adapter_schema_covers_actual_sample_fields(self):
        import re
        schema=json.loads((ROOT/'_core/onboarding/adapter-schema.json').read_text())
        fields=set()
        for path in (ROOT/'workspaces').rglob('*'):
            if path.is_file() and path.suffix in ('.md','.py','.sql'):
                fields.update(re.findall(r'\b[A-Za-z][A-Za-z0-9_]*__c\b',path.read_text()))
        self.assertLessEqual(fields,set(schema['crm_field_map']))

    def test_no_approval_or_changed_approval_writes_nothing(self):
        bus=LocalConnector();proposal={'Subject':'Demo Task'}
        for approval in (None,{'Subject':'Different Task'}):
            with self.assertRaises(ValueError):bus.write('task',proposal,approved=approval)
        self.assertEqual(bus.records,{})

    def test_state_drift_blocks_write(self):
        bus=LocalConnector();bus.records['task']={'Status':'Completed'}
        with self.assertRaises(ValueError):bus.write('task',{'Status':'Not Started'},approved={'Status':'Not Started'},current={'Status':'Old'})
        self.assertEqual(bus.records['task'],{'Status':'Completed'})

    def test_readback_mismatch_cannot_be_reported_verified(self):
        bus=LocalConnector();proposal={'Subject':'Demo Task'}
        with self.assertRaises(ValueError):bus.write('task',proposal,approved=proposal,readback_override={'Subject':'Changed Task'})
        self.assertEqual(bus.writes,[])

    def test_exact_approval_readback_and_duplicate(self):
        bus=LocalConnector();proposal={'Subject':'Demo Task'}
        self.assertEqual(bus.write('task',proposal,approved=proposal),proposal)
        self.assertTrue(bus.writes[0]['verified'])
        with self.assertRaises(ValueError):bus.write('task',proposal,approved=proposal,current=proposal)
        self.assertEqual(len(bus.writes),1)


if __name__=='__main__':unittest.main()
