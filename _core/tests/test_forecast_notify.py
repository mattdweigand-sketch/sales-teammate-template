"""forecast_notify.py: the title follows coverage_check's exit code, not the caller."""
import json
import subprocess
import sys
from pathlib import Path

from test_coverage_check import CoverageFixture

SCRIPTS = Path(__file__).resolve().parents[2] / "workspaces" / "forecasting" / "workflows" / "forecast-weekly" / "scripts"
sys.path.insert(0, str(SCRIPTS))
URL = "https://example.test/run"


class ForecastNotifyTests(CoverageFixture):
    def setUp(self) -> None:
        super().setUp()
        self.inbox = "from:@example.com after:2026-06-30"
        self.calendar_start = "2026-08-21T00:00:00-07:00"
        self.opp["CloseDate"] = "2026-09-30"

    def notify(self, *extra: str) -> subprocess.CompletedProcess:
        args = [sys.executable, str(SCRIPTS / "forecast_notify.py"), "--since", self.since, "--thread-url", URL,
                "--policy", str(self.policy), "--summary", "Booked $1. Call $1.", *extra]
        return subprocess.run(args, cwd=self.root, env=self.env, text=True, capture_output=True)

    def test_notify_uses_live_session_coverage_without_a_legacy_directory(self):
        self.ready()
        live = self.home / ".perplexity" / "sessions" / "live" / "tool_calls" / "call_external_tool"
        live.parent.mkdir(parents=True)
        self.calls.rename(live)
        result = self.notify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["title"], "Weekly forecast ready")

    def test_notify_passes_explicit_calls_directory_through_ambiguity(self):
        self.ready()
        for name in ("older", "newer"):
            (self.home / ".perplexity" / "sessions" / name / "tool_calls" / "call_external_tool").mkdir(parents=True)
        result = self.notify()
        self.assertEqual(json.loads(result.stdout)["title"], "Weekly forecast incomplete")
        self.assertIn("Multiple saved tool-call session directories", result.stdout)
        explicit = self.notify("--calls-dir", str(self.calls))
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        self.assertEqual(json.loads(explicit.stdout)["title"], "Weekly forecast ready")

    def test_ready_only_when_coverage_passes(self) -> None:
        self.ready()
        result = self.notify("--schedule", "Fridays · 10am")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["title"], "Weekly forecast ready")
        self.assertEqual(payload["channels"], ["in_app"])
        self.assertEqual(payload["schedule_description"], "Fridays · 10am")
        self.assertIn("Booked $1. Call $1.", payload["body"])
        self.assertIn("Gmail 1/1. Calendar 1/1.", payload["body"])
        self.assertTrue(payload["body"].endswith(URL))

    def test_incomplete_when_a_source_is_missing(self) -> None:
        self.salesforce(); self.mail()
        result = self.notify()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["title"], "Weekly forecast incomplete")
        self.assertIn("Calendar missing: Example Buyer", payload["body"])
        self.assertTrue(payload["body"].endswith(URL))

    def test_incomplete_when_contacts_were_never_queried(self) -> None:
        self.salesforce()
        (self.calls / "input_Contact.json").unlink()
        (self.calls / "output_Contact.json").unlink()
        self.mail(); self.calendar()
        payload = json.loads(self.notify().stdout)
        self.assertEqual(payload["title"], "Weekly forecast incomplete")
        self.assertIn("Run the Contact query", payload["body"])

    def test_no_snapshot_is_incomplete_not_a_crash(self) -> None:
        result = self.notify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["title"], "Weekly forecast incomplete")


class PayloadReadinessTests(__import__('unittest').TestCase):
    def test_false_ready_or_process_status_cannot_announce_ready(self):
        from forecast_notify import build_payload
        for result in ({"ready":False,"process_status":"complete","lines":["looked fine"]},
                       {"ready":True,"process_status":"incomplete","lines":["partial"]}):
            self.assertEqual(build_payload(0,json.dumps(result),"",URL,None)["title"],"Weekly forecast incomplete")
        good=json.dumps({"ready":True,"process_status":"complete","lines":["Coverage ready"]})
        self.assertEqual(build_payload(0,good,"",URL,None,"review-needed")["title"],"Weekly forecast incomplete")
        self.assertEqual(build_payload(1,good,"",URL,None)["title"],"Weekly forecast incomplete")
