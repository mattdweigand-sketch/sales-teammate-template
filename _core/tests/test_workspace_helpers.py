"""Relocated helpers still find canonical resources from a sandbox directory."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
POLICY = yaml.safe_load((ROOT / '_core' / 'policy.yaml').read_text())


class WorkspaceHelperResources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.sandbox = Path(self.temp.name)

    def run_helper(self, key, *args):
        return subprocess.run([sys.executable, str(ROOT / POLICY['tooling']['scripts'][key]), *args],
                              cwd=self.sandbox, text=True, capture_output=True)

    def test_prospecting_shared_loaders_work_without_workflow_folders(self):
        export = self.sandbox / 'export'
        (export / '_core').mkdir(parents=True)
        workspace = export / 'workspaces/prospecting'
        (workspace / 'scripts').mkdir(parents=True)
        shutil.copy(ROOT / '_core/policy.yaml', export / '_core/policy.yaml')
        shutil.copy(ROOT / POLICY['tooling']['scripts']['prospect_common'], workspace / 'scripts/prospect_common.py')
        shutil.copytree(ROOT / 'workspaces/prospecting/references', workspace / 'references')
        code = '''
import sys
sys.path.insert(0, sys.argv[1])
import prospect_common
assert prospect_common.load_policy()['identity']['sfdc_user_id']
assert prospect_common.load_taxonomy()['tiers']['tier1']
assert '## Target personas' in (prospect_common.REFERENCES / 'icp.md').read_text()
'''
        result = subprocess.run([sys.executable, '-c', code, str(workspace / 'scripts')],
                                cwd=self.sandbox, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_gmail_stats_loads_core_parser_and_default_policy_from_sandbox(self):
        path = self.sandbox / 'emails.json'
        path.write_text(json.dumps({'email_results': {'emails': []}}))
        result = self.run_helper('gmail_contact_stats', 'seller@example.com', str(path),
                                 '--as-of', '2026-10-04T10:00:00-07:00', '--only', 'buyer@example.com')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_outreach_uses_its_private_talk_track_from_sandbox(self):
        from test_prospect_outreach_gate import PACKET, NOW
        path = self.sandbox / 'packet.json'
        path.write_text(json.dumps(PACKET))
        result = self.run_helper('prospect_outreach_gate', '--packet', str(path), '--now', NOW.isoformat())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['verdict'], 'allow')

    def test_forecast_uses_root_policy_without_override(self):
        path = self.sandbox / 'input.json'
        path.write_text(json.dumps({'as_of': '2027-01-01', 'records': []}))
        result = self.run_helper('forecast_math', '--tracking', '--input', str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output['amount_field'], POLICY['forecast']['amount_field'])
        self.assertEqual(output['year']['target'], '1000000.00')

    def test_notification_runs_core_coverage_without_override(self):
        result = self.run_helper('forecast_notify', '--since', '2026-10-01T00:00:00-07:00',
                                 '--thread-url', 'https://example.test/run')
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output['title'], 'Weekly forecast incomplete')
        self.assertNotIn('No such file', output['body'])
        self.assertIn('https://example.test/run', output['body'])

    def test_closeout_imports_shared_saved_result_parser(self):
        path = self.sandbox / 'tasks.json'
        path.write_text(json.dumps({'result': {'records': [], 'done': True, 'totalSize': 0}}))
        result = self.run_helper('closeout_check', str(path), '--as-of', '2026-10-01T00:00:00-07:00')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PASS no open Tasks', result.stdout)

    def test_pipeline_render_loads_root_policy_and_preserves_output(self):
        from test_pipeline_render import base, READY, SAVED, SAVED_CAL, EXPECTED
        run, coverage = self.sandbox / 'run.json', self.sandbox / 'coverage.json'
        run.write_text(json.dumps(base()))
        coverage.write_text(json.dumps(READY))
        sources = self.sandbox / 'calls'
        sources.mkdir()
        (sources / 'output_mail.json').write_text(json.dumps(SAVED))
        (sources / 'output_cal.json').write_text(json.dumps(SAVED_CAL))
        result = self.run_helper('pipeline_render', 'report', '--run', str(run), '--coverage', str(coverage),
                                 '--sources', str(sources))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, EXPECTED.read_text())

    def test_pilot_default_policy_and_whole_repository_write_guard(self):
        pilot = ROOT / POLICY['tooling']['scripts']['pilot_usage_build']
        code = '''
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from pilot_usage_shared import PROJECT_FILES_ROOT, load_pilot_usage_policy, require_local_only_output_path
root = Path(sys.argv[2])
assert PROJECT_FILES_ROOT == root
policy = load_pilot_usage_policy()
for output in (root / 'out.pdf', root / '_core' / 'out.pdf', root / 'workspaces' / 'forecasting' / 'out.pdf'):
    try:
        require_local_only_output_path(output)
    except ValueError:
        pass
    else:
        raise AssertionError(output)
require_local_only_output_path(Path.cwd() / 'out.pdf')
print(json.dumps(policy))
'''
        result = subprocess.run([sys.executable, '-c', code, str(pilot.parent), str(ROOT)],
                                cwd=self.sandbox, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['top_users'], POLICY['pilot_usage']['top_users'])
