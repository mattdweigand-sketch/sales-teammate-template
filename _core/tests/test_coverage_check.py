"""CLI regressions for weekday pipeline source coverage."""
import datetime as dt
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2] / "_core" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from _saved_json import resolve_calls_dir


class SavedCallsDirectory(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.environment = patch.dict(os.environ, {"HOME": str(self.home)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.directory = patch("os.getcwd", return_value=str(self.root))
        self.directory.start()
        self.addCleanup(self.directory.stop)

    def session(self, name):
        directory = self.home / ".perplexity" / "sessions" / name / "tool_calls" / "call_external_tool"
        directory.mkdir(parents=True)
        return directory

    def test_exactly_one_session_directory_is_selected(self):
        live = self.session("live")
        (self.home / ".perplexity" / "sessions" / "without-calls").mkdir()
        self.assertEqual(resolve_calls_dir(), live)

    def test_no_session_directory_falls_back_to_legacy_cwd(self):
        expected = self.root / "current_session_context" / "tool_calls" / "call_external_tool"
        self.assertEqual(resolve_calls_dir(), expected)
        expected.mkdir(parents=True)
        self.assertEqual(resolve_calls_dir(), expected)

    def test_several_session_directories_fail_without_guessing(self):
        self.session("older")
        self.session("newer")
        with self.assertRaisesRegex(ValueError, "Multiple saved tool-call session directories.*explicit"):
            resolve_calls_dir()

    def test_explicit_override_wins_even_when_multiple_sessions_or_path_missing(self):
        self.session("older")
        self.session("newer")
        explicit = self.root / "explicit"
        self.assertEqual(resolve_calls_dir(explicit), explicit)
        self.assertEqual(resolve_calls_dir("~/explicit"), self.home / "explicit")

    def test_stale_legacy_directory_is_ignored_when_live_session_exists(self):
        stale = self.root / "current_session_context" / "tool_calls" / "call_external_tool"
        stale.mkdir(parents=True)
        (stale / "output_old.json").write_text('{"records": []}')
        os.utime(stale / "output_old.json", (0, 0))
        live = self.session("live")
        (live / "output_new.json").write_text('{"records": [{"Id": "synthetic"}]}')
        self.assertEqual(resolve_calls_dir(), live)


class CoverageFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = {**os.environ, "HOME": str(self.home)}
        self.calls = self.root / "current_session_context/tool_calls/call_external_tool"
        self.calls.mkdir(parents=True)
        self.sequence = 0
        self.since = "2026-09-21T07:00:31-07:00"
        self.timestamp = dt.datetime.fromisoformat(self.since).timestamp()
        # Minimal policy so edits to the live _core/policy.yaml cannot break these tests.
        self.policy = self.root / "policy.yaml"
        self.policy.write_text(json.dumps({
            "tooling": {"internal_domains": ["seller.example", "seller-tools.example"], "calendar_lookahead_days": 30, "calendar_lookback_days":30},
            "pipeline": {"stages": ["S2", "S3", "S4", "S5"], "activity_query_days":30},
            "forecast": {"quarters": "calendar", "amount_field": "ARR__c", "open_min_stage": "S2"},
        }))
        self.opp = {
            "attributes": {"type": "Opportunity"}, "Id": "o1", "AccountId": "a1",
            "Account": {"Name": "Example Buyer"}, "StageName": "S2 - Solutioning",
        }
        self.contact = {"attributes": {"type": "Contact"}, "Id":"c1", "Email": "buyer@example.com", "AccountId": "a1"}
        self.calendar_start = "2026-08-22T00:00:00-07:00"
        self.inbox = "(from:@example.com OR to:@example.com) after:2026-08-22"

    def pair(self, name: str, tool: str, args: dict, result: dict) -> None:
        self.sequence += 1
        for prefix, data in (
            ("input", {"tool_name": tool, "arguments": args}),
            ("output", {"result": result}),
        ):
            path = self.calls / f"{prefix}_{name}.json"
            path.write_text(json.dumps(data))
            os.utime(path, (self.timestamp + self.sequence, self.timestamp + self.sequence))

    TASK_FIELDS = "Id, Subject, ActivityDate, Status, IsClosed, OwnerId, Description, LastModifiedDate, WhatId, AccountId, WhoId, Who.Name"
    EVENT_FIELDS = "Id, Subject, ActivityDate, StartDateTime, EndDateTime, WhatId, AccountId, WhoId, OwnerId"
    ACTIVITY_SCOPE = "(WhatId IN ('o1') OR AccountId IN ('a1'))"

    def task_query(self, scope: str = ACTIVITY_SCOPE, window: str = "(IsClosed = false OR ActivityDate = LAST_N_DAYS:30)",
                   fields: str = TASK_FIELDS, extra: str = "") -> str:
        return f"SELECT {fields} FROM Task WHERE {scope} AND {window}{extra}"

    def event_query(self, scope: str = ACTIVITY_SCOPE, window: str = "(ActivityDate = LAST_N_DAYS:30 OR ActivityDate >= TODAY)",
                    fields: str = EVENT_FIELDS, extra: str = "") -> str:
        return f"SELECT {fields} FROM Event WHERE {scope} AND {window}{extra}"

    def salesforce(self, event_fields: str = "StartDateTime, EndDateTime") -> None:
        """The documented Opportunity, Contact, Task and Event reads for the fixture deal."""
        event_select = self.EVENT_FIELDS.replace("StartDateTime, EndDateTime", event_fields).replace(", ,", ",")
        queries = {"Opportunity": "SELECT Id FROM Opportunity WHERE OwnerId = 'owner' AND IsClosed = false",
                   "Contact": "SELECT Id FROM Contact", "Task": self.task_query(),
                   "Event": self.event_query(fields=event_select)}
        for kind, records in (("Opportunity", [self.opp]), ("Contact", [self.contact]), ("Task", []), ("Event", [])):
            self.pair(kind, "query", {"query": queries[kind]}, {"records": records, "hasMore": False, "totalSize": len(records)})
        for name, where, rows in (("current", "IsClosed = false AND CloseDate = THIS_QUARTER", [self.opp]),
                                  ("next", "IsClosed = false AND CloseDate = NEXT_QUARTER", []),
                                  ("booked", "StageName = 'Closed Won' AND CloseDate = THIS_QUARTER", [])):
            self.pair(name,"query",{"query":f"SELECT Id FROM Opportunity WHERE OwnerId = 'owner' AND {where}"},
                      {"records":rows,"done":True,"totalSize":len(rows)})

    def mail(self, name: str = "mail", cursor: str | None = None, next_cursor: str | None = None, emails: list | None = None) -> None:
        args = {"queries": [self.inbox]}
        if cursor:
            args["cursor"] = cursor
        self.pair(name, "search_email", args, {
            "authenticated": True, "email_results": {"emails": emails or [], "next_cursor": next_cursor},
        })

    def calendar(self, query: str = "Example Buyer", end: str = "2026-10-21T23:59:59-07:00") -> None:
        self.pair("calendar", "search_calendar", {
            "queries": [query], "start_date": self.calendar_start, "end_date": end,
        }, {"status": "success", "calendar_event_list": {"events": []}})

    def run_check(self, scope: str = "pipeline", *extra: str) -> subprocess.CompletedProcess:
        args = [sys.executable, str(SCRIPTS / "coverage_check.py"), "--scope", scope, "--since", self.since,
                "--policy", str(self.policy), *extra]
        return subprocess.run(args, cwd=self.root, env=self.env, text=True, capture_output=True)

    def ready(self) -> None:
        self.salesforce()
        self.mail()
        self.calendar()


class SavedCallsCoverageTests(CoverageFixture):
    def test_cli_uses_live_results_instead_of_stale_legacy_snapshots(self):
        self.ready()
        live = self.home / ".perplexity" / "sessions" / "live" / "tool_calls" / "call_external_tool"
        shutil.copytree(self.calls, live)
        for path in self.calls.glob("*.json"):
            os.utime(path, (self.timestamp - 1000, self.timestamp - 1000))
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Coverage ready", result.stdout)

    def test_cli_multiple_sessions_are_incomplete_until_explicit_override(self):
        self.ready()
        for name in ("older", "newer"):
            (self.home / ".perplexity" / "sessions" / name / "tool_calls" / "call_external_tool").mkdir(parents=True)
        result = self.run_check("pipeline", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)["ready"])
        self.assertIn("Multiple saved tool-call session directories", result.stdout)
        explicit = self.run_check("pipeline", "--calls-dir", str(self.calls))
        self.assertEqual(explicit.returncode, 0, explicit.stdout + explicit.stderr)


class PipelineDailyCoverageTests(CoverageFixture):
    def test_pipeline_default_checks_missing_early_stage_evidence(self) -> None:
        for stage in ("S0 - Prospect", "S1 - Discovery"):
            with self.subTest(stage=stage):
                self.opp["StageName"] = stage
                self.salesforce()
                result = self.run_check("pipeline", "--json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data["affected"], ["o1"])
                self.assertIn("Gmail missing: Example Buyer", result.stdout)
                self.assertIn("Calendar missing: Example Buyer", result.stdout)

    def test_pipeline_default_accepts_checked_early_stage_evidence(self) -> None:
        self.opp["StageName"] = "S1 - Discovery"
        self.ready()
        result = self.run_check("pipeline")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 deals in scope", result.stdout)

    def test_complete_daily_coverage_passes(self) -> None:
        self.ready()
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Coverage ready.", result.stdout)

    def test_missing_calendar_account_blocks_readiness(self) -> None:
        self.salesforce(); self.mail(); self.calendar("Unrelated")
        result = self.run_check()
        self.assertIn("Calendar missing: Example Buyer", result.stdout)
        self.assertEqual(result.returncode, 1)

    def test_missing_contact_domain_blocks_full_coverage(self) -> None:
        self.contact["Email"] = "internal@seller.example"
        self.ready()
        self.assertIn("No Contact domain in evidence: Example Buyer", self.run_check().stdout)

    def test_missing_output_is_not_a_successful_check(self) -> None:
        self.ready()
        (self.calls / "output_calendar.json").unlink()
        self.assertEqual(self.run_check().returncode, 1)

    def test_incomplete_email_pagination_blocks(self) -> None:
        self.salesforce(); self.calendar(); self.mail(next_cursor="returned")
        self.assertIn("Email pagination incomplete", self.run_check().stdout)

    def test_returned_email_cursor_completes_pagination(self) -> None:
        self.salesforce(); self.calendar(); self.mail(next_cursor="returned")
        self.mail("mail2", cursor="returned")
        self.assertEqual(self.run_check().returncode, 0)

    def test_invented_cursor_blocks_readiness(self) -> None:
        self.ready()
        self.mail("mail2", cursor="invented")
        self.assertIn("cursor was not returned", self.run_check().stdout)

    def test_event_query_requires_timestamps(self) -> None:
        self.salesforce(event_fields=""); self.mail(); self.calendar()
        self.assertIn("Event query missing start/end timestamps", self.run_check().stdout)

    def test_short_calendar_window_blocks(self) -> None:
        self.salesforce(); self.mail(); self.calendar(end="2026-09-22T00:00:00-07:00")
        self.assertEqual(self.run_check().returncode, 1)

    def test_matching_emails_have_recorded_domain_receipts(self) -> None:
        self.salesforce(); self.calendar()
        self.mail(emails=[
            {"from_": "Buyer <buyer@example.com>", "email_id": "matched"},
            {"from_": "Someone <user@unrelated.com>", "email_id": "unmatched"},
        ])
        result = self.run_check()
        self.assertEqual(result.returncode, 0)
        self.assertIn("Gmail 1/1", result.stdout)
        self.assertNotIn("Domain-matched inbox receipts", result.stdout)

    def test_weekly_account_query_needs_no_broad_weekday_inbox(self) -> None:
        self.ready()
        self.assertEqual(self.run_check().returncode, 0)
        result = self.run_check("pipeline-daily")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)

    def test_corrected_salesforce_retry_does_not_block(self) -> None:
        self.pair("failed", "query", {"query": "SELECT Id, Id FROM Opportunity WHERE OwnerId = 'owner' AND IsClosed = false"}, {"error": "duplicate field"})
        self.ready()
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Recovered Salesforce call error", result.stdout)

    def test_sparse_rows_do_not_crash_daily_mode(self) -> None:
        self.opp["attributes"] = None
        self.opp["StageName"] = None
        self.contact["Email"] = None
        self.ready()
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("No opportunity snapshot found", result.stdout)

    def test_naive_since_is_rejected(self) -> None:
        self.since = "2026-09-21T07:00:31"
        self.ready()
        result = self.run_check()
        self.assertEqual(result.returncode, 2)
        self.assertIn("timezone offset", result.stderr)


class WeeklyCoverageTests(CoverageFixture):
    """Friday --scope pipeline and --scope forecast."""

    def setUp(self) -> None:
        super().setUp()
        self.inbox = "(from:@example.com OR to:@example.com) after:2026-08-21"
        self.calendar_start = "2026-08-21T00:00:00-07:00"

    def test_existing_friday_mode_remains_compatible(self) -> None:
        self.ready()
        result = self.run_check("pipeline")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 deals in scope (open S0+). Gmail 1/1. Calendar 1/1.", result.stdout)

    def test_zero_deals_exits_one(self) -> None:
        self.mail(); self.calendar()
        result = self.run_check("pipeline")
        self.assertEqual(result.returncode, 1)
        self.assertIn("No opportunity snapshot found", result.stdout)

    def test_failed_search_outputs_do_not_count(self) -> None:
        self.salesforce()
        self.pair("mail", "search_email", {"queries": [self.inbox]}, {"error": "quota exceeded"})
        self.pair("calendar", "search_calendar", {"queries": ["Example Buyer"]}, {"error": "quota exceeded"})
        result = self.run_check("pipeline")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Gmail 0/1. Calendar 0/1.", result.stdout)
        self.assertIn("Gmail missing: Example Buyer", result.stdout)
        self.assertIn("Calendar missing: Example Buyer", result.stdout)

    def test_no_contact_records_names_the_missing_query(self) -> None:
        self.pair("Opportunity", "query", {"query": "SELECT Id FROM Opportunity WHERE OwnerId = 'owner' AND IsClosed = false"}, {"records": [self.opp], "hasMore": False, "totalSize": 1})
        self.mail(); self.calendar()
        result = self.run_check("pipeline")
        self.assertEqual(result.returncode, 1)
        self.assertIn("No Contact records saved since 2026-09-21T07:00-07:00. Run the Contact query, then rerun.", result.stdout)
        self.assertNotIn("No Contact domain in evidence", result.stdout)

    def test_zero_row_contact_query_is_not_a_missing_query(self) -> None:
        self.pair("Opportunity", "query", {"query": "SELECT Id FROM Opportunity WHERE OwnerId = 'owner' AND IsClosed = false"}, {"records": [self.opp], "hasMore": False, "totalSize": 1})
        self.pair("Contact", "query", {"query": "SELECT Id, Email FROM Contact"}, {"records": [], "hasMore": False, "totalSize": 0})
        self.mail(); self.calendar()
        result = self.run_check("pipeline")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Run the Contact query", result.stdout)
        self.assertIn("No Contact domain in evidence: Example Buyer", result.stdout)

    def test_failed_contact_query_counts_as_missing(self) -> None:
        self.pair("Opportunity", "query", {"query": "SELECT Id FROM Opportunity WHERE OwnerId = 'owner' AND IsClosed = false"}, {"records": [self.opp], "hasMore": False, "totalSize": 1})
        self.pair("Contact", "query", {"query": "SELECT Id, Email FROM Contact"}, {"error": "timeout"})
        self.mail(); self.calendar()
        result = self.run_check("pipeline")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Run the Contact query, then rerun.", result.stdout)

    def test_internal_domain_contact_is_not_a_buyer_domain(self) -> None:
        self.contact["Email"] = "internal@seller.example"
        self.inbox = "from:@seller.example after:2026-08-21"
        self.ready()
        result = self.run_check("pipeline")
        self.assertEqual(result.returncode, 1)
        self.assertIn("No Contact domain in evidence: Example Buyer", result.stdout)
        self.assertIn("Gmail missing: Example Buyer", result.stdout)

    def test_stage_min_and_list_are_honoured(self) -> None:
        self.ready()
        result = self.run_check("pipeline", "--stage-min", "3", "--list")
        self.assertIn("0 deals in scope (open S3+)", result.stdout)
        result = self.run_check("pipeline", "--list")
        self.assertIn("  Example Buyer\n", result.stdout)

    def test_forecast_floor_is_policy_forecast_open_min_stage_and_pipeline_floor_is_unchanged(self) -> None:
        """V5. One forecast floor. Mutating it moves forecast scope and leaves Pipeline's every-open-stage floor alone."""
        self.inbox = "from:@example.com after:2026-07-01"
        self.opp["CloseDate"] = "2026-09-30"
        self.ready()
        self.assertIn("1 deals in scope (S2+ CloseDate this quarter", self.run_check("forecast").stdout)
        policy = json.loads(self.policy.read_text())
        policy["forecast"]["open_min_stage"] = "S3"
        policy["pipeline"]["stages"] = ["S0", "S1", "S2", "S3", "S4", "S5"]
        self.policy.write_text(json.dumps(policy))
        forecast = self.run_check("forecast")
        self.assertIn("0 deals in scope (S3+ CloseDate this quarter", forecast.stdout)
        self.assertIn("1 deals in scope (open S0+)", self.run_check("pipeline").stdout)
        del policy["forecast"]["open_min_stage"]
        self.policy.write_text(json.dumps(policy))
        missing = self.run_check("forecast")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("policy.forecast.open_min_stage", missing.stderr + missing.stdout)
        self.assertIn("1 deals in scope (open S0+)", self.run_check("pipeline").stdout)

    def test_forecast_quarter_boundary_comes_from_since(self) -> None:
        self.inbox = "from:@example.com after:2026-07-01"
        self.opp["CloseDate"] = "2026-09-30"
        self.ready()
        result = self.run_check("forecast")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("1 deals in scope", result.stdout)
        # Same calls, run start on Oct 1: Q3 deals are out of scope.
        self.since = "2026-10-01T07:00:31-07:00"
        self.timestamp = dt.datetime.fromisoformat(self.since).timestamp()
        self.ready()
        result = self.run_check("forecast")
        self.assertIn("0 deals in scope", result.stdout)

    def test_forecast_next_quarter_needs_policy_amount_not_standard_amount(self) -> None:
        self.opp["CloseDate"] = "2026-11-15"
        self.ready()
        self.assertIn("0 deals in scope", self.run_check("forecast").stdout)
        self.opp["Amount"] = 5000
        self.ready()
        self.assertIn("0 deals in scope", self.run_check("forecast").stdout)
        self.opp["ARR__c"] = 500
        self.opp["Amount"] = None
        self.ready()
        self.assertIn("1 deals in scope", self.run_check("forecast").stdout)

    def test_forecast_next_quarter_zero_formula_amount_is_unset(self) -> None:
        # Salesforce's ARR formula returns numeric zero when its source Amount is blank.
        for amount in (None, "", 0):
            with self.subTest(policy_amount=amount):
                self.opp.update(CloseDate="2026-11-15", ARR__c=amount, Amount=None)
                self.ready()
                self.assertIn("0 deals in scope", self.run_check("forecast").stdout)

    def test_forecast_scope_names_policy_amount_field(self) -> None:
        self.opp.update(CloseDate="2026-09-30", ARR__c=500)
        self.ready()
        self.assertIn("next quarter with ARR__c", self.run_check("forecast").stdout)

    def test_null_close_date_is_skipped_in_forecast(self) -> None:
        self.opp["CloseDate"] = None
        self.ready()
        result = self.run_check("forecast")
        self.assertEqual(result.stderr, "")
        self.assertIn("0 deals in scope", result.stdout)


class CompletenessRegressions(CoverageFixture):
    def test_truncated_and_cursorless_more_results_fail(self):
        self.ready()
        for payload in ({"truncated":True,"email_results":{"emails":[]}},
                        {"email_results":{"emails":[],"has_more":True}},
                        {"email_results":{"emails":[],"hasMore":True}}):
            self.pair("mail","search_email",{"queries":[self.inbox]},payload)
            self.assertEqual(self.run_check().returncode,1)

    def test_monday_requires_friday_not_sunday(self):
        self.ready()
        self.assertEqual(self.run_check().returncode,0)
        self.inbox="after:2026-09-20 -from:seller.example -from:seller-tools.example"
        self.mail()
        self.assertEqual(self.run_check().returncode,1)

    def test_consumed_calendar_cursor_passes(self):
        self.salesforce();self.mail()
        args={"queries":["Example Buyer"],"start_date":self.calendar_start,"end_date":"2026-10-21T23:59:59-07:00"}
        self.pair("cal1","search_calendar",args,{"status":"success","calendar_event_list":{"events":[],"next_cursor":"page2"}})
        self.assertEqual(self.run_check().returncode,1)
        self.pair("cal2","search_calendar",{**args,"cursor":"page2"},{"status":"success","calendar_event_list":{"events":[]}})
        self.assertEqual(self.run_check().returncode,0)

    def test_consumed_salesforce_cursor_passes_and_partial_fails(self):
        self.ready()
        self.pair("Opportunity","query",{"query":"SELECT Id FROM Opportunity WHERE OwnerId = 'owner' AND IsClosed = false"},{"records":[self.opp],"totalSize":2,"done":False,"nextRecordsUrl":"page2"})
        self.assertEqual(self.run_check().returncode,1)
        second={**self.opp,"Id":"o2"}
        self.pair("Opportunity2","query_more",{"nextRecordsUrl":"page2"},{"records":[second],"totalSize":2,"done":True})
        self.assertEqual(self.run_check().returncode,0)

    def test_limited_salesforce_query_fails(self):
        self.ready()
        self.pair("Opportunity","query",{"query":"SELECT Id FROM Opportunity LIMIT 1"},{"records":[self.opp],"totalSize":1,"done":True})
        self.assertIn("LIMIT/OFFSET",self.run_check().stdout)
        self.assertEqual(self.run_check().returncode,1)

    def test_daily_thread_requires_or_and_exact_domain(self):
        self.ready()
        hygiene=self.root/"hygiene.json"
        hygiene.write_text(json.dumps([{"Id":"o1","Account":"Example Buyer","triggers":["stale"]}]))
        for q in ("from:@example.com to:@example.com after:2026-08-22", "(from:@example.com.evil.test OR to:@example.com.evil.test) after:2026-08-22"):
            self.pair("mail","search_email",{"queries":[q]},{"email_results":{"emails":[]}})
            self.assertEqual(self.run_check("pipeline").returncode,1)
        self.pair("thread","search_email",{"queries":["(from:@example.com OR to:@example.com) after:2026-08-22"]},{"email_results":{"emails":[]}})
        self.assertEqual(self.run_check("pipeline").returncode,0)

    def test_calendar_unrelated_short_name_cannot_cover_account(self):
        self.salesforce();self.mail();self.calendar("Buyer")
        self.assertEqual(self.run_check().returncode,1)

    def test_explicit_empty_opportunity_collection_can_pass(self):
        self.ready()
        self.pair("Opportunity","query",{"query":"SELECT Id FROM Opportunity WHERE OwnerId = 'owner' AND IsClosed = false"},{"records":[],"totalSize":0,"done":True})
        self.pair("current","query",{"query":"SELECT Id FROM Opportunity WHERE OwnerId = 'owner' AND IsClosed = false AND CloseDate = THIS_QUARTER"},{"records":[],"done":True,"totalSize":0})
        self.assertEqual(self.run_check().returncode,0)

    def test_json_false_readiness_on_incomplete_collection(self):
        self.ready(); self.mail(next_cursor="not-fetched")
        response=self.run_check("pipeline","--json")
        self.assertEqual(response.returncode,1)
        self.assertFalse(json.loads(response.stdout)["ready"])

    def test_json_affected_names_deals_to_withhold(self):
        self.ready()
        self.pair("mail", "search_email", {"queries": ["from:@wrong.test after:2026-08-22"]}, {"email_results": {"emails": []}})
        response = json.loads(self.run_check("pipeline", "--json").stdout)
        self.assertEqual((response["ready"], response["affected"]), (False, ["o1"]))
        self.mail()
        response = json.loads(self.run_check("pipeline", "--json").stdout)
        self.assertEqual((response["ready"], response["affected"]), (True, []))
        self.assertFalse(any(line.startswith("Affected deals") for line in response["lines"]))

    def test_json_affected_is_whole_scope_for_unattributed_gap(self):
        self.ready()
        self.pair("tasks","query",{"query":self.task_query(scope="WhatId IN ('o1')")},{"records":[{"Id":"t1"}],"totalSize":2,"done":False})
        response=json.loads(self.run_check("pipeline","--json").stdout)
        self.assertEqual((response["ready"],response["affected"]),(False,["o1"]))


class WeeklyCompletenessRegressions(CoverageFixture):
    def setUp(self):
        super().setUp()
        self.calendar_start="2026-08-21T00:00:00-07:00"
        self.opp.update(CloseDate="2026-09-30",Amount=100)
        self.inbox="from:@example.com after:2026-07-01"

    def test_weekly_unconsumed_mail_fails(self):
        self.ready();self.mail(next_cursor="not-fetched")
        self.assertEqual(self.run_check("forecast").returncode,1)

    def test_weekly_wrong_domain_fails(self):
        self.inbox="from:@example.com.evil.test after:2026-07-01";self.ready()
        self.assertEqual(self.run_check("forecast").returncode,1)

    def test_forecast_shorter_retry_only_after_one_timeout(self):
        self.salesforce();self.calendar()
        self.inbox="from:@example.com after:2026-09-07";self.mail()
        self.assertEqual(self.run_check("forecast").returncode,1)
        self.pair("earlier","search_email",{"queries":["from:@example.com after:2026-07-01"]},{"error":"timeout"})
        self.assertEqual(self.run_check("forecast").returncode,1)
        self.mail()
        result=self.run_check("forecast")
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertIn("earlier window 2026-07-01 to 2026-09-07 unread",result.stdout)
        self.pair("second-timeout","search_email",{"queries":["from:@example.com after:2026-07-01"]},{"error":"timeout"})
        self.assertEqual(self.run_check("forecast").returncode,1)


class CollectionScopeRegressions(CoverageFixture):
    def test_missing_snapshot_preserves_salesforce_error(self):
        self.pair("failed","query",{"query":"SELECT Id FROM Opportunity WHERE OwnerId = 'owner' AND IsClosed = false"},{"error":"specific provider timeout"})
        result=self.run_check()
        self.assertEqual(result.returncode,1)
        self.assertIn("specific provider timeout",result.stdout)
        self.assertIn("No opportunity snapshot found",result.stdout)

    def test_forecast_requires_each_documented_collection_even_when_booked_empty(self):
        self.ready()
        for prefix in ("input", "output"):
            (self.calls/f"{prefix}_current.json").unlink()
            (self.calls/f"{prefix}_next.json").unlink()
        result=self.run_check("forecast")
        self.assertEqual(result.returncode,1)
        self.assertIn("Missing complete Opportunity collections: current_open, next_open",result.stdout)

    def test_wrong_account_query_cannot_replace_broad_pipeline_collection(self):
        self.ready()
        self.pair("Opportunity","query",{"query":"SELECT Id FROM Opportunity WHERE AccountId = 'a1'"},{"records":[self.opp],"done":True,"totalSize":1})
        self.assertEqual(self.run_check().returncode,1)
        self.assertIn("Missing complete Opportunity collections: open",self.run_check().stdout)

    def test_incidental_lookup_does_not_poison_complete_collection(self):
        self.ready()
        self.pair("lookup","query",{"query":"SELECT Id FROM Opportunity WHERE Id = 'o1' LIMIT 1"},{"records":[self.opp],"done":True,"totalSize":1})
        self.assertEqual(self.run_check().returncode,0)

    def test_task_and_event_queries_must_cover_in_scope_accounts(self):
        """A complete Task or Event query scoped to other Ids is not coverage for the reviewed deal."""
        self.ready()
        self.pair("Task","query",{"query":self.task_query(scope="AccountId IN ('unrelated')")},{"records":[],"hasMore":False,"totalSize":0})
        self.pair("Event","query",{"query":self.event_query(scope="WhatId IN ('unrelated')")},{"records":[],"hasMore":False,"totalSize":0})
        result=self.run_check()
        self.assertEqual(result.returncode,1)
        self.assertIn("Task query scope missing: Example Buyer",result.stdout)
        self.assertIn("Event query scope missing: Example Buyer",result.stdout)
        self.pair("Task2","query",{"query":self.task_query()},{"records":[],"hasMore":False,"totalSize":0})
        self.pair("Event2","query",{"query":self.event_query(scope="AccountId IN ('a1')")},{"records":[],"hasMore":False,"totalSize":0})
        self.assertEqual(self.run_check().returncode,0)

    def test_narrowed_task_or_event_queries_cannot_certify_coverage(self):
        """A complete query that names the required Ids but narrows by Subject or a shorter window is not coverage."""
        self.ready()
        (self.calls / "input_Task.json").unlink(); (self.calls / "output_Task.json").unlink()
        (self.calls / "input_Event.json").unlink(); (self.calls / "output_Event.json").unlink()
        cases = {"Subject": (self.task_query(extra=" AND Subject LIKE 'Email:%'"), self.event_query(extra=" AND Subject = 'Kickoff'")),
                 "LAST_N_DAYS:7": (self.task_query(window="(IsClosed = false OR ActivityDate = LAST_N_DAYS:7)"),
                                   self.event_query(window="(ActivityDate = LAST_N_DAYS:7 OR ActivityDate >= TODAY)")),
                 "SELECT Id": (self.task_query(fields="Id"), self.event_query(fields="Id, StartDateTime, EndDateTime")),
                 "window missing": (self.task_query(window="IsClosed = false"), self.event_query(window="ActivityDate >= TODAY"))}
        for label, (task, event) in cases.items():
            with self.subTest(label=label):
                self.pair("Task", "query", {"query": task}, {"records": [], "hasMore": False, "totalSize": 0})
                self.pair("Event", "query", {"query": event}, {"records": [], "hasMore": False, "totalSize": 0})
                response = json.loads(self.run_check("pipeline", "--json").stdout)
                self.assertEqual((response["ready"], response["affected"]), (False, ["o1"]))
                self.assertIn("Task query scope missing: Example Buyer", response["lines"])
                self.assertIn("Event query scope missing: Example Buyer", response["lines"])
                self.assertTrue(any(line.startswith("input_Task.json: ignored narrowed Task query, ") for line in response["lines"]), response["lines"])
                self.assertTrue(any(line.startswith("input_Event.json: ignored narrowed Event query, ") for line in response["lines"]), response["lines"])

    def test_forecast_scope_accepts_its_documented_task_form_and_rejects_a_shorter_window(self):
        self.inbox = "from:@example.com after:2026-07-01"
        self.opp["CloseDate"] = "2026-09-30"
        self.ready()
        forecast_fields = "Id, Subject, ActivityDate, Status, IsClosed, WhatId, AccountId, Who.Name"
        documented = self.task_query(fields=forecast_fields, extra=" AND ActivityDate != null",
                                     window="(IsClosed = false OR ActivityDate = LAST_N_DAYS:14)")
        self.pair("Task", "query", {"query": documented}, {"records": [], "hasMore": False, "totalSize": 0})
        result = self.run_check("forecast")
        self.assertEqual(result.returncode, 0, result.stdout)
        shorter = documented.replace("LAST_N_DAYS:14", "LAST_N_DAYS:7")
        self.pair("Task", "query", {"query": shorter}, {"records": [], "hasMore": False, "totalSize": 0})
        result = self.run_check("forecast")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("shorter than the required 14 days", result.stdout)
        self.assertIn("Task query scope missing: Example Buyer", result.stdout)

    def test_equivalent_formatting_of_documented_activity_queries_passes(self):
        self.ready()
        (self.calls / "input_Task.json").unlink(); (self.calls / "output_Task.json").unlink()
        (self.calls / "input_Event.json").unlink(); (self.calls / "output_Event.json").unlink()
        task = ("select id,subject,activitydate,status,isclosed,ownerid,description,lastmodifieddate,whatid,accountid,whoid,who.name\n"
                "FROM Task\nWHERE (WhatId IN ('o1')   OR AccountId IN ('a1'))\n  AND (IsClosed=false OR ActivityDate=LAST_N_DAYS:45) ORDER BY ActivityDate DESC")
        event = ("SELECT Id, Subject, ActivityDate, StartDateTime, EndDateTime, WhatId, AccountId, WhoId, OwnerId FROM Event "
                 "WHERE (ActivityDate >= TODAY OR ActivityDate = LAST_N_DAYS:30) AND (AccountId IN ('a1') OR WhatId IN ('o1'))")
        self.pair("Task", "query", {"query": task}, {"records": [], "hasMore": False, "totalSize": 0})
        self.pair("Event", "query", {"query": event}, {"records": [], "hasMore": False, "totalSize": 0})
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("ignored narrowed", result.stdout)



class CalendarRetrievalTests(CoverageFixture):
    """Cap detection, event de-duplication, generic-domain exclusion, Salesforce Event corroboration."""

    def event(self, event_id: str, start: str, attendee: str = "buyer@example.com", title: str = "Sync") -> dict:
        return {"event_id": event_id, "title": title, "start": start, "end": start, "attendees": [{"email": attendee}]}

    def calendar_with(self, events: list, name: str = "calendar", query: str = "Example Buyer") -> None:
        self.pair(name, "search_calendar", {"queries": [query], "start_date": self.calendar_start, "end_date": "2026-10-21T23:59:59-07:00"},
                  {"status": "success", "calendar_event_list": {"events": events}})

    def salesforce_events(self, rows: list, scope: str = CoverageFixture.ACTIVITY_SCOPE) -> None:
        self.pair("Event", "query", {"query": self.event_query(scope=scope)},
                  {"records": rows, "hasMore": False, "totalSize": len(rows)})

    def test_other_owner_event_is_not_eligible_for_calendar_corroboration(self) -> None:
        self.ready()
        self.salesforce_events([{"attributes": {"type": "Event"}, "Id": "ev1", "Subject": "Kickoff",
                                "StartDateTime": "2026-09-22T17:00:00Z", "WhatId": "o1", "AccountId": "a1",
                                "OwnerId": "other-owner"}])
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Salesforce Events matched 0/0 eligible.", result.stdout)
        self.assertIn("Coverage ready.", result.stdout)

    def test_same_or_missing_owner_event_still_requires_calendar_corroboration(self) -> None:
        self.ready()
        for owner in ("owner", None, ""):
            with self.subTest(owner=owner):
                self.salesforce_events([{"attributes": {"type": "Event"}, "Id": "ev1", "Subject": "Kickoff",
                                        "StartDateTime": "2026-09-22T17:00:00Z", "WhatId": "o1", "AccountId": "a1",
                                        "OwnerId": owner}])
                result = self.run_check()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("Salesforce Events matched 0/1 eligible", result.stdout)
                self.assertIn("Calendar 0/1", result.stdout)

    def test_event_owner_matches_fifteen_and_eighteen_character_ids(self) -> None:
        self.ready()
        owner = "005AAA000000001"
        for path in self.calls.glob("input_*.json"):
            call = json.loads(path.read_text())
            if "query" in call["arguments"]:
                call["arguments"]["query"] = call["arguments"]["query"].replace("'owner'", f"'{owner}AAA'")
                path.write_text(json.dumps(call))
        for event_owner in (owner, owner + "AAA"):
            with self.subTest(event_owner=event_owner):
                self.salesforce_events([{"attributes": {"type": "Event"}, "Id": "ev1", "Subject": "Kickoff",
                                        "StartDateTime": "2026-09-22T17:00:00Z", "WhatId": "o1", "AccountId": "a1",
                                        "OwnerId": event_owner}])
                result = self.run_check()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("Salesforce Events matched 0/1 eligible", result.stdout)

    def test_page_at_cap_is_incomplete(self) -> None:
        self.salesforce(); self.mail()
        self.calendar_with([self.event(f"e{i}", "2026-09-22T10:00:00-07:00") for i in range(50)])
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Calendar result cap reached (50 events)", result.stdout)
        self.assertIn("Calendar: result cap reached; retrieval incomplete.", result.stdout)
        self.assertIn("Calendar missing: Example Buyer", result.stdout)

    def test_page_below_cap_reports_no_cap_not_completeness(self) -> None:
        self.ready()
        result = self.run_check()
        self.assertIn("Calendar: defined searches completed, no cap detected.", result.stdout)
        self.assertNotIn("Calendar complete", result.stdout)

    def test_cap_value_comes_from_policy(self) -> None:
        policy = json.loads(self.policy.read_text()); policy["tooling"]["calendar_result_cap"] = 2; self.policy.write_text(json.dumps(policy))
        self.salesforce(); self.mail()
        self.calendar_with([self.event("e1", "2026-09-22T10:00:00-07:00"), self.event("e2", "2026-09-23T10:00:00-07:00")])
        self.assertIn("Calendar result cap reached (2 events)", self.run_check().stdout)

    def test_duplicate_events_across_queries_count_once(self) -> None:
        self.salesforce(); self.mail()
        e = self.event("e1", "2026-09-22T10:00:00-07:00")
        self.calendar_with([e]); self.calendar_with([e], name="cal2", query="buyer@example.com")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Calendar 1/1", result.stdout)

    def test_generic_email_domain_is_not_an_account_domain(self) -> None:
        policy = json.loads(self.policy.read_text()); policy["tooling"]["generic_email_domains"] = ["linkedin.com"]; self.policy.write_text(json.dumps(policy))
        self.contact["Email"] = "notify@linkedin.com"
        self.ready()
        result = self.run_check()
        self.assertIn("No Contact domain in evidence: Example Buyer", result.stdout)

    def test_salesforce_event_matched_by_start_and_attendee_domain(self) -> None:
        self.salesforce(); self.mail()
        self.salesforce_events([{"attributes": {"type": "Event"}, "Id": "ev1", "Subject": "Kickoff", "StartDateTime": "2026-09-22T17:00:00.000+0000", "EndDateTime": "2026-09-22T17:30:00.000+0000", "WhatId": "o1", "AccountId": "a1"}])
        self.calendar_with([self.event("e1", "2026-09-22T10:00:30-07:00")])
        result = self.run_check()
        self.assertIn("Salesforce Events matched 1/1 eligible.", result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_salesforce_event_same_start_without_domain_attendee_is_uncertain(self) -> None:
        self.salesforce(); self.mail()
        self.salesforce_events([{"attributes": {"type": "Event"}, "Id": "ev1", "Subject": "Kickoff", "StartDateTime": "2026-09-22T17:00:00.000+0000", "EndDateTime": "2026-09-22T17:30:00.000+0000", "WhatId": "o1", "AccountId": "a1"}])
        self.calendar_with([self.event("e1", "2026-09-22T10:00:00-07:00", attendee="someone@other.org")])
        result = self.run_check()
        self.assertIn("Salesforce Events matched 0/1 eligible; uncertain (attendee domain unverified): Example Buyer · Kickoff · 2026-09-22.", result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Calendar 0/1", result.stdout)

    def test_empty_account_title_search_with_salesforce_event_fails_readiness(self) -> None:
        self.salesforce(); self.mail()
        self.salesforce_events([{"attributes": {"type": "Event"}, "Id": "ev1", "Subject": "Kickoff", "StartDateTime": "2026-09-22T17:00:00.000+0000", "EndDateTime": "2026-09-22T17:30:00.000+0000", "WhatId": "o1", "AccountId": "a1"}])
        self.calendar_with([])
        result = self.run_check()
        self.assertIn("unmatched (reconcile before proposing on these Accounts): Example Buyer · Kickoff · 2026-09-22.", result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Calendar 0/1", result.stdout)
        self.assertNotIn("Coverage ready.", result.stdout)
        payload = json.loads(self.run_check("pipeline", "--json").stdout)
        self.assertFalse(payload["ready"])
        self.assertEqual(payload["affected"], ["o1"])

    def test_subject_search_recovers_empty_account_title_search(self) -> None:
        self.ready()
        self.salesforce_events([{"attributes": {"type": "Event"}, "Id": "ev1", "Subject": "Buyer sync",
                                "StartDateTime": "2026-09-22T17:00:00Z", "WhatId": "o1", "AccountId": "a1"}])
        self.calendar_with([self.event("e1", "2026-09-22T10:00:00-07:00", title="Buyer sync")],
                           name="subject", query="Buyer sync")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Calendar 1/1", result.stdout)

    def test_nonempty_title_search_missing_the_salesforce_event_still_fails(self) -> None:
        self.ready()
        self.salesforce_events([{"attributes": {"type": "Event"}, "Id": "ev1", "Subject": "Buyer sync",
                                "StartDateTime": "2026-09-22T17:00:00Z", "WhatId": "o1", "AccountId": "a1"}])
        self.calendar_with([self.event("other", "2026-09-23T10:00:00-07:00")])
        self.assertEqual(self.run_check().returncode, 1)

    def test_calendar_gap_affects_only_the_linked_deal(self) -> None:
        self.ready()
        second = dict(self.opp, Id="o2", AccountId="a2", Account={"Name": "Example Two"})
        self.pair("Opportunity", "query", {"query": "SELECT Id FROM Opportunity WHERE OwnerId = 'owner' AND IsClosed = false"},
                  {"records": [self.opp, second], "done": True})
        self.pair("Contact", "query", {"query": "SELECT Id, Email FROM Contact"},
                  {"records": [self.contact, dict(self.contact, Id="c2", AccountId="a2")], "done": True})
        self.calendar_with([], name="second", query="Example Two")
        both = "(WhatId IN ('o1', 'o2') OR AccountId IN ('a1', 'a2'))"
        self.pair("Task", "query", {"query": self.task_query(scope=both)}, {"records": [], "hasMore": False, "totalSize": 0})
        self.salesforce_events([{"attributes": {"type": "Event"}, "Id": "ev1", "Subject": "Buyer sync",
                                "StartDateTime": "2026-09-22T17:00:00Z", "WhatId": "o1", "AccountId": "a1"}], scope=both)
        payload = json.loads(self.run_check("pipeline", "--json").stdout)
        self.assertEqual(payload["affected"], ["o1"])
        self.assertTrue(any("Calendar 1/2" in line for line in payload["lines"]))

    def test_salesforce_event_outside_window_is_not_eligible(self) -> None:
        self.salesforce(); self.mail()
        self.salesforce_events([{"attributes": {"type": "Event"}, "Id": "ev1", "Subject": "Old", "StartDateTime": "2026-06-01T17:00:00.000+0000", "EndDateTime": "2026-06-01T17:30:00.000+0000", "WhatId": "o1", "AccountId": "a1"}])
        self.calendar_with([])
        self.assertIn("Salesforce Events matched 0/0 eligible.", self.run_check().stdout)


class CalendarSplitWindowTests(CoverageFixture):
    """rules#calendar_search recovery: a capped window is superseded by complete split windows that cover the full range."""

    event = CalendarRetrievalTests.event
    calendar_with = CalendarRetrievalTests.calendar_with

    def split(self, name: str, start: str, end: str, events: list | None = None, query: str = "Example Buyer") -> None:
        self.pair(name, "search_calendar", {"queries": [query], "start_date": start, "end_date": end},
                  {"status": "success", "calendar_event_list": {"events": events or []}})

    def test_capped_window_recovered_by_covering_splits(self) -> None:
        self.salesforce(); self.mail()
        self.calendar_with([self.event(f"e{i}", "2026-09-22T10:00:00-07:00") for i in range(50)])
        self.split("cal_a", "2026-08-22T00:00:00-07:00", "2026-10-04T23:59:59-07:00", [self.event("e1", "2026-09-22T10:00:00-07:00")])
        self.split("cal_b", "2026-10-04T23:59:59-07:00", "2026-10-21T23:59:59-07:00", [self.event("e2", "2026-10-10T10:00:00-07:00")])
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Superseded Calendar call for ['Example Buyer']", result.stdout)
        self.assertIn("Calendar: result cap reached, recovered by split windows", result.stdout)
        self.assertNotIn("Calendar result cap reached (50 events)", result.stdout)
        self.assertNotIn("Calendar pagination incomplete", result.stdout)
        self.assertIn("Calendar 1/1", result.stdout)

    def test_splits_with_a_gap_do_not_recover(self) -> None:
        self.salesforce(); self.mail()
        self.calendar_with([self.event(f"e{i}", "2026-09-22T10:00:00-07:00") for i in range(50)])
        self.split("cal_a", "2026-08-22T00:00:00-07:00", "2026-10-01T00:00:00-07:00")
        self.split("cal_b", "2026-10-05T00:00:00-07:00", "2026-10-21T23:59:59-07:00")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("uncovered from 2026-10-01T00:00-07:00", result.stdout)
        self.assertIn("Calendar result cap reached (50 events)", result.stdout)
        self.assertIn("Calendar: result cap reached; retrieval incomplete.", result.stdout)
        self.assertIn("Calendar missing: Example Buyer", result.stdout)

    def test_splits_alone_cover_without_a_capped_call(self) -> None:
        self.salesforce(); self.mail()
        self.split("cal_a", "2026-08-22T00:00:00-07:00", "2026-10-04T23:59:59-07:00")
        self.split("cal_b", "2026-10-04T23:59:59-07:00", "2026-10-21T23:59:59-07:00")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Calendar: defined searches completed, no cap detected.", result.stdout)

    def test_supplemental_day_sweep_corroborates_without_full_window(self) -> None:
        self.salesforce(); self.mail(); self.calendar()
        event = self.event("buyer-sync", "2026-09-22T10:00:00-07:00")
        self.pair("Event", "query", {"query": self.event_query()},
                  {"records": [{"Id": "sf-event", "attributes": {"type": "Event"},
                                "WhatId": "o1", "StartDateTime": event["start"]}], "done": True})
        self.pair("day_sweep", "search_calendar",
                  {"start_date": "2026-09-22T00:00:00-07:00", "end_date": "2026-09-23T00:00:00-07:00"},
                  {"calendar_event_list": {"events": [event]}})
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Salesforce Events matched 1/1 eligible", result.stdout)

    def test_supplemental_subject_search_does_not_require_full_window(self) -> None:
        self.ready()
        self.split("subject", "2026-09-22T00:00:00-07:00", "2026-09-23T00:00:00-07:00",
                   query="Buyer sync")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_supplemental_sweep_never_replaces_defined_search(self) -> None:
        self.salesforce(); self.mail()
        self.pair("day_sweep", "search_calendar",
                  {"start_date": "2026-09-22T00:00:00-07:00", "end_date": "2026-09-23T00:00:00-07:00"},
                  {"calendar_event_list": {"events": []}})
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Calendar missing: Example Buyer", result.stdout)

    def test_capped_supplemental_search_requires_its_own_full_range(self) -> None:
        self.ready()
        self.split("supplemental", "2026-09-22T00:00:00-07:00", "2026-09-23T00:00:00-07:00",
                   [self.event(f"s{i}", "2026-09-22T10:00:00-07:00") for i in range(50)], query="Buyer sync")
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.split("supplemental_a", "2026-09-22T00:00:00-07:00", "2026-09-22T12:00:00-07:00", query="Buyer sync")
        self.split("supplemental_b", "2026-09-22T12:00:00-07:00", "2026-09-23T00:00:00-07:00", query="Buyer sync")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_one_second_gap_is_not_silently_covered(self) -> None:
        self.salesforce(); self.mail()
        self.split("cal_a", "2026-08-22T00:00:00-07:00", "2026-10-04T23:59:59-07:00")
        self.split("cal_b", "2026-10-05T00:00:00-07:00", "2026-10-21T23:59:59-07:00")
        self.assertEqual(self.run_check().returncode, 1)

if __name__ == "__main__":
    unittest.main()
