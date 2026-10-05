"""Pilot usage pdf pipeline: assemble from saved results, fail-closed compute, render/print units, local-only outputs."""
import copy
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "workspaces" / "pipeline" / "workflows" / "pilot-usage" / "scripts"
POLICY = ROOT / "_core" / "policy.yaml"
sys.path.insert(0, str(PILOT))

import pilot_usage_shared  # noqa: E402
from assemble_pilot_usage_input import assemble_input, default_tool_calls_dir, load_marked_results
from build_pilot_usage_report import resolve_window  # noqa: E402
from compute_pilot_usage_report import (  # noqa: E402
    compute_pilot_usage_report,
    validate_computed_pilot_usage_report,
)
from pilot_usage_shared import ensure_font_assets, load_pilot_usage_policy, require_local_only_output_path  # noqa: E402
from render_pilot_usage_report import (  # noqa: E402
    PilotUsagePdfInspection,
    _format_date_range,
    _render_pilot_usage_report_html,
    _render_user_rows,
    _validate_inspection,
)

ORG = "11111111-2222-3333-4444-555555555555"
HANDLES = {"q1_roster": "h1", "q4_grants": "h4", "q5_tasks": "h5"}
START, THROUGH = "2026-08-12", "2026-09-20"
Q5_COLUMNS = ["CONTEXT_UUID", "USER_EMAIL", "FIRST_DATE", "AMOUNT_CENTS", "TASK_TITLE"]


def _statement(calls: Path, suffix: str, marker: str, handle: str) -> None:
    scope = f"organization_uuid = '{ORG}'"
    if marker == "q4_grants":
        scope += f" AND effective_at_pt::DATE <= '{THROUGH}'"
    else:
        scope += f" AND date_pt = '{THROUGH}'"
    if marker == "q5_tasks":
        scope += f" AND b.date_pt BETWEEN '{START}' AND '{THROUGH}' AND q.date_pt BETWEEN '{START}' AND '{THROUGH}'"
    statement = f"-- pilot_usage {marker}\nSELECT 1 WHERE {scope}"
    (calls / f"input_{suffix}.json").write_text(json.dumps(
        {"tool_name": "snowflake__execute_sql_readonly", "arguments": {"input": {"statement": statement}}}))
    (calls / f"output_{suffix}.json").write_text(json.dumps(
        {"tool": "snowflake__execute_sql_readonly", "result": {"statement_handle": handle, "data": None}}))


def _page(calls: Path, name: str, handle: str, columns, rows, **extra) -> None:
    result = {"statement_handle": handle, "data": rows, "row_count": len(rows),
              "result_set_meta_data": [{"name": c} for c in columns] if columns else None}
    result.update(extra)
    (calls / f"output_{name}.json").write_text(json.dumps({"tool": "snowflake__get_query_results", "result": result}))


def _saved(calls: Path, suffix: str, marker: str, handle: str, columns, rows) -> None:
    _statement(calls, suffix, marker, handle)
    _page(calls, f"{suffix}r0", handle, None, [])  # running placeholder, must be ignored
    _page(calls, f"{suffix}r1", handle, columns, rows)


def _user_row(index: int, tasks: int, credits: int) -> dict:
    return {"user_id": f"u{index}@x.test", "display_name": f"User {index:02d}", "task_count": tasks,
            "week_one_tasks": tasks, "week_two_tasks": 0, "credits": credits, "active_days": min(tasks, 1),
            "participation_note": ""}


class PilotUsagePdfTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.calls = Path(self.temp.name) / "calls"
        self.calls.mkdir()
        self.policy = load_pilot_usage_policy(POLICY)
        _saved(self.calls, "a", "q1_roster", "h1",
               ["USER_EMAIL", "FIRST_QUERY", "LAST_QUERY", "L7_QUERIES", "WINDOW_QUERIES", "WINDOW_COMPUTER_QUERIES"],
               [["a@x.test", "2026-08-13", "2026-08-20", "1", "5", "5"], ["b@x.test", None, None, "0", "0", "0"]])
        _saved(self.calls, "b", "q4_grants", "h4",
               ["USER_EMAIL", "BILLING_CREDIT_NAME", "BILLING_CREDIT_CATEGORY_ENRICHED", "EFFECTIVE_AT", "EXPIRES_AT", "VOIDED_AT", "AMOUNT_DOLLARS"],
               [["a@x.test", "n", "c", "2026-08-12 10:00:00.000", "2026-09-12 10:00:00.000", None, "150.000000"],
                ["a@x.test", "n", "c", "2026-08-12 10:00:01.000", "2026-09-12 10:00:00.000", "2026-08-13 00:00:00.000", "500.000000"],
                ["b@x.test", "n", "c", "2026-10-01 10:00:00.000", "2026-11-01 10:00:00.000", None, "150.000000"]])
        _saved(self.calls, "c", "q5_tasks", "h5", Q5_COLUMNS,
               [["ctx-1", "a@x.test", "2026-08-13", "100.5", "Draft a memo"],
                ["ctx-2", "a@x.test", "2026-08-20", "2.4999", None]])
        self.review = {
            "customer_name": "Test LLP", "organization_uuid": ORG, "prepared_by": "Sales Operator",
            "pilot_start": START, "pilot_end": "2026-09-24", "data_through": THROUGH, "approved": True,
            "display_names": {"a@x.test": "A Person"},
            "categories": [{"category_id": "drafting", "label": "Drafting", "description": "Memos."}],
            "task_categories": {"ctx-1": "drafting"},
            "narratives": {"scope_note": "s", "usage_highlights": [], "representative_work": [],
                           "work_interpretation": [], "business_value": [], "source_note": "src"},
        }

    def _load(self):
        return load_marked_results(self.calls, HANDLES, self.review["organization_uuid"],
                                   self.review["pilot_start"], self.review["data_through"])

    def test_default_pilot_directory_reads_live_session_and_refuses_ambiguity(self):
        home = Path(self.temp.name) / "home"
        live = home / ".perplexity" / "sessions" / "live" / "tool_calls" / "call_external_tool"
        live.parent.mkdir(parents=True)
        self.calls.rename(live)
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            self.assertEqual(default_tool_calls_dir(), live)
            results = load_marked_results(default_tool_calls_dir(), HANDLES, self.review["organization_uuid"],
                                          self.review["pilot_start"], self.review["data_through"])
            self.assertEqual(len(results["q5_tasks"]), 2)
            (home / ".perplexity" / "sessions" / "other" / "tool_calls" / "call_external_tool").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "Multiple saved tool-call session directories"):
                default_tool_calls_dir()
            review = Path(self.temp.name) / "review.json"
            review.write_text(json.dumps(self.review))
            result = subprocess.run([sys.executable, str(PILOT / "build_pilot_usage_report.py"), "window", "--review", str(review),
                                     "--grants-handle", "h4", "--tool-calls", str(live)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["pilot_start"], START)

    def _input(self):
        return assemble_input(self._load(), self.review, self.policy)

    def _report(self):
        return compute_pilot_usage_report(self._input(), self.policy)

    def _replace_q5(self, rows) -> None:
        _page(self.calls, "cr1", "h5", Q5_COLUMNS, rows)

    # --- assemble ---------------------------------------------------------------------------

    def test_assemble_uses_final_result_and_reconciles(self) -> None:
        normalized = self._input()
        self.assertEqual(normalized["report"]["pilot_start"], "2026-08-12")
        self.assertEqual(normalized["report"]["total_granted_credits"], 15000)  # voided and future rows dropped
        self.assertEqual([s["credits"] for s in normalized["sessions"]], [101, 2])  # half up per task
        self.assertEqual(normalized["sessions"][1]["category_id"], self.policy["uncategorized_category_id"])
        self.assertEqual(normalized["categories"][-1]["label"], self.policy["uncategorized_label"])
        self.assertEqual(normalized["report"]["confidentiality_label"], self.policy["confidentiality_label"])
        self.assertEqual(normalized["roster"][0]["display_name"], "A Person")
        self.assertEqual(normalized["roster"][1]["display_name"], "b")
        self.assertNotIn("supplemental_undated_sessions", normalized)
        report = compute_pilot_usage_report(normalized, self.policy)
        self.assertEqual(report["headline"]["credits_used"], 103)
        self.assertEqual(report["computed_highlights"]["top_user_count"], 1)  # min(policy top_users, active)
        self.assertNotIn("reconciliation", report)
        self.assertEqual(validate_computed_pilot_usage_report(normalized, self.policy, report), [])

    def test_grants_round_half_up(self) -> None:
        _page(self.calls, "br1", "h4",
              ["USER_EMAIL", "BILLING_CREDIT_NAME", "BILLING_CREDIT_CATEGORY_ENRICHED", "EFFECTIVE_AT", "EXPIRES_AT", "VOIDED_AT", "AMOUNT_DOLLARS"],
              [["a@x.test", "n", "c", "2026-08-12 10:00:00.000", "2026-09-12 10:00:00.000", None, "150.005000"]])
        self.assertEqual(self._input()["report"]["total_granted_credits"], 15001)

    def test_internal_domain_roster_and_tasks_are_filtered(self) -> None:
        _page(self.calls, "ar1", "h1", ["USER_EMAIL", "FIRST_QUERY"],
              [["a@x.test", "2026-08-13"], ["b@x.test", None], ["rep@seller.example", "2026-08-13"]])
        self._replace_q5([["ctx-1", "a@x.test", "2026-08-13", "100.5", "Draft a memo"],
                          ["ctx-9", "rep@seller.example", "2026-08-14", "40", "Internal test"]])
        normalized = self._input()
        self.assertEqual([r["user_id"] for r in normalized["roster"]], ["a@x.test", "b@x.test"])
        self.assertEqual([s["context_uuid"] for s in normalized["sessions"]], ["ctx-1"])

    def test_task_outside_window_is_filtered(self) -> None:
        self._replace_q5([["ctx-1", "a@x.test", "2026-08-13", "100.5", "Draft a memo"],
                          ["ctx-late", "a@x.test", "2026-09-21", "5", "after data_through"],
                          ["ctx-early", "a@x.test", "2026-08-11", "5", "before pilot_start"]])
        normalized = self._input()
        self.assertEqual([s["context_uuid"] for s in normalized["sessions"]], ["ctx-1"])
        self.assertEqual(validate_computed_pilot_usage_report(
            normalized, self.policy, compute_pilot_usage_report(normalized, self.policy)), [])

    def test_missing_pilot_end_raises(self) -> None:
        for value in (None, "", "  "):
            self.review["pilot_end"] = value
            with self.assertRaisesRegex(ValueError, "pilot_end missing"):
                self._input()
        self.review.pop("pilot_end")
        with self.assertRaisesRegex(ValueError, "pilot_end missing"):
            self._input()
        self.review["pilot_end"] = "soon"
        with self.assertRaisesRegex(ValueError, "ISO"):
            self._input()

    def test_unrelated_saved_calls_are_ignored(self) -> None:
        """A string or list result on an unrelated SQL call must not break the selected-handle scan."""
        (self.calls / "input_z.json").write_text(json.dumps(
            {"tool_name": "snowflake__execute_sql_readonly", "arguments": {"input": {"statement": "SELECT 1"}}}))
        (self.calls / "output_z.json").write_text(json.dumps({"result": "statement failed"}))
        (self.calls / "output_y.json").write_text(json.dumps([{"unrelated": True}]))
        self.assertEqual(len(self._load()["q5_tasks"]), 2)

    def test_missing_marker_is_an_error(self) -> None:
        for path in self.calls.glob("*_c*.json"):
            path.unlink()
        with self.assertRaises(RuntimeError):
            self._load()

    def test_failed_marked_result_is_rejected_even_with_rows(self) -> None:
        final = self.calls / "output_cr1.json"
        page = json.loads(final.read_text())
        page["result"]["status"] = "FAILED_WITH_ERROR"
        page["result"]["message"] = "SQL compilation error"
        final.write_text(json.dumps(page))
        with self.assertRaisesRegex(RuntimeError, "marked failed.*SQL compilation error"):
            self._load()

    def test_failed_page_with_null_data_reports_the_sql_error(self) -> None:
        submit = self.calls / "output_c.json"  # execute_sql page: data is null
        page = json.loads(submit.read_text())
        page["result"]["status"] = "FAILED_WITH_ERROR"
        page["result"]["message"] = "SQL compilation error: invalid identifier"
        submit.write_text(json.dumps(page))
        with self.assertRaisesRegex(RuntimeError, "marked failed.*invalid identifier"):
            self._load()

    def test_final_page_beats_running_placeholder_on_equal_mtime(self) -> None:
        stamp = (self.calls / "output_cr0.json").stat().st_mtime
        os.utime(self.calls / "output_cr1.json", (stamp, stamp))
        self.assertEqual(len(self._load()["q5_tasks"]), 2)

    def test_two_partition_result_merges_in_order(self) -> None:
        (self.calls / "output_cr1.json").unlink()
        _page(self.calls, "cp0", "h5", Q5_COLUMNS,
              [["ctx-1", "a@x.test", "2026-08-13", "100.5", "Draft a memo"],
               ["ctx-2", "a@x.test", "2026-08-20", "2.4999", None]],
              partition=0, total_partitions=2, total_row_count=3)
        _page(self.calls, "cp1", "h5", None, [["ctx-3", "b@x.test", "2026-08-21", "10", "Second page"]], partition=1)
        rows = self._load()["q5_tasks"]
        self.assertEqual([r["context_uuid"] for r in rows], ["ctx-1", "ctx-2", "ctx-3"])
        self.assertEqual(rows[2]["user_email"], "b@x.test")
        (self.calls / "output_cp1.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "pages incomplete"):
            self._load()

    # --- compute ----------------------------------------------------------------------------

    def test_unapproved_review_fails_closed(self) -> None:
        self.review["approved"] = False
        with self.assertRaises(ValueError):
            compute_pilot_usage_report(self._input(), self.policy)

    def test_credits_over_grant_fails_closed(self) -> None:
        normalized = self._input()
        normalized["report"]["total_granted_credits"] = 50
        with self.assertRaises(ValueError):
            compute_pilot_usage_report(normalized, self.policy)

    def test_tampered_report_fails_validation(self) -> None:
        normalized = self._input()
        report = compute_pilot_usage_report(normalized, self.policy)
        tampered = copy.deepcopy(report)
        tampered["headline"]["credits_used"] += 1
        self.assertTrue(validate_computed_pilot_usage_report(normalized, self.policy, tampered))

    def test_week_bucketing_when_data_through_is_inside_week_one(self) -> None:
        self.review["data_through"] = "2026-08-15"  # pilot_start 08-12, day 4 of week one
        for path in self.calls.glob("input_*.json"):
            path.write_text(path.read_text().replace(THROUGH, "2026-08-15"))
        report = self._report()
        periods = report["periods"]
        self.assertEqual(periods["week_one_end"], "2026-08-15")
        self.assertIsNone(periods["week_two_start"])
        user = report["users"][0]
        self.assertEqual((user["task_count"], user["week_one_tasks"], user["week_two_tasks"]), (1, 1, 0))
        html = _render_pilot_usage_report_html(report, self.policy)
        self.assertIn("After = none yet", html)
        self.assertNotIn("Aug 16–15", html)

    def test_week_bucketing_splits_after_week_one(self) -> None:
        report = self._report()  # tasks on 08-13 (week one) and 08-20 (after)
        self.assertEqual((report["periods"]["week_one_end"], report["periods"]["week_two_start"]),
                         ("2026-08-18", "2026-08-19"))
        user = report["users"][0]
        self.assertEqual((user["week_one_tasks"], user["week_two_tasks"]), (1, 1))

    def test_palette_overflow_raises(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["category_palette"] = ["#20808D"]  # drafting + uncategorized = 2 > 1
        with self.assertRaisesRegex(ValueError, "category_palette"):
            compute_pilot_usage_report(self._input(), policy)

    def test_top_users_comes_from_policy(self) -> None:
        normalized = self._input()
        normalized["roster"] = [{"user_id": f"u{i}@x.test", "display_name": f"U{i}", "participation_note": ""}
                                for i in range(8)]
        normalized["sessions"] = [
            {"context_uuid": f"c{i}", "user_id": f"u{i}@x.test", "date": "2026-08-13", "credits": 10,
             "category_id": "drafting", "task_title": "", "classification_reviewed": True}
            for i in range(8)
        ]
        report = compute_pilot_usage_report(normalized, self.policy)
        self.assertEqual(report["computed_highlights"]["top_user_count"], self.policy["top_users"])

    # --- render -----------------------------------------------------------------------------

    def test_user_table_folds_after_policy_max_rows(self) -> None:
        max_rows = self.policy["user_table_max_rows"]
        self.assertEqual(max_rows, 20)
        users = [_user_row(i, tasks=1 if i < 22 else 0, credits=100 - i) for i in range(24)]
        html = _render_user_rows(users, max_rows)
        self.assertEqual(html.count("<tr"), max_rows + 1)
        self.assertIn("User 19", html)
        self.assertNotIn("User 20", html)
        self.assertIn("Other (4 seats, 2 with no tasks)", html)
        self.assertIn(f"<td>{sum(u['credits'] for u in users[max_rows:]):,}</td>", html)
        self.assertEqual(_render_user_rows(users[:5], max_rows).count("<tr"), 5)

    def test_format_date_range(self) -> None:
        self.assertEqual(_format_date_range("2026-08-12", "2026-08-18"), "Aug 12–18, 2026")
        self.assertEqual(_format_date_range("2026-08-12", "2026-08-18", include_year=False), "Aug 12–18")
        self.assertEqual(_format_date_range("2026-08-28", "2026-09-03"), "Aug 28 – Sep 3, 2026")
        self.assertEqual(_format_date_range("2026-12-30", "2027-01-02"), "Dec 30, 2026 – Jan 2, 2027")

    def test_render_html_uses_policy_values(self) -> None:
        self.review["participation_notes"] = {"a@x.test": "Joined late."}
        report = self._report()
        html = _render_pilot_usage_report_html(report, self.policy)
        fonts = self.policy["fonts"]
        self.assertIn(f'font-family:"{fonts["sans"]["family"]}"', html)
        self.assertIn(f'font-family:"{fonts["mono"]["family"]}"', html)
        self.assertIn("@page{size:8.5in 11in", html)
        self.assertIn("A Person: Joined late.", html)
        self.assertIn(f"Prepared by Sales Operator, {self.policy['metadata_author']}", html)
        self.assertIn("1 context (2 credits, 1.9%) are uncategorized", html)
        self.assertNotIn("undated", html)

    # --- print ------------------------------------------------------------------------------

    def test_validate_inspection_on_hand_built_object(self) -> None:
        good = PilotUsagePdfInspection(
            page_count=2, media_boxes=((612.0, 792.0), (612.0, 792.0)),
            title=self.policy["metadata_title"], author=self.policy["metadata_author"],
            embedded_font_tokens=("DejaVuSans", "DejaVuSansMono"))
        _validate_inspection(good, self.policy)
        bad = PilotUsagePdfInspection(
            page_count=3, media_boxes=((612.0, 792.0), (595.0, 842.0), (612.0, 792.0)),
            title="x", author=self.policy["metadata_author"], embedded_font_tokens=("DejaVuSans",))
        with self.assertRaises(RuntimeError) as raised:
            _validate_inspection(bad, self.policy)
        message = str(raised.exception)
        self.assertIn("expected 2 pages, got 3", message)
        self.assertIn("Letter (612 × 792 points)", message)
        self.assertIn("title metadata", message)
        self.assertIn("DejaVu Sans and DejaVu Sans Mono fonts are not both embedded", message)

    # --- fonts ------------------------------------------------------------------------------

    def test_font_hash_mismatch_triggers_one_redownload(self) -> None:
        good = b"real font bytes"
        font_dir = Path(self.temp.name) / "fonts"
        font_dir.mkdir()
        (font_dir / "x.woff2").write_bytes(b"truncated")
        policy = {"fonts": {"sans": {
            "family": "X", "file_name": "x.woff2", "sha256": hashlib.sha256(good).hexdigest(),
            "pdf_name_token": "X", "url": "https://example.invalid/x.woff2"}}}
        with mock.patch.object(pilot_usage_shared.urllib.request, "urlopen", return_value=io.BytesIO(good)) as urlopen:
            ensure_font_assets(policy, font_dir)
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual((font_dir / "x.woff2").read_bytes(), good)
        # Print mode never downloads: a bad file is an error.
        (font_dir / "x.woff2").write_bytes(b"truncated")
        with mock.patch.object(pilot_usage_shared.urllib.request, "urlopen") as urlopen:
            with self.assertRaisesRegex(RuntimeError, "integrity verification"):
                ensure_font_assets(policy, font_dir, download=False)
        urlopen.assert_not_called()

    # --- storage and CLI --------------------------------------------------------------------

    def test_output_inside_project_files_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            require_local_only_output_path(ROOT / "out.pdf")
        self.assertTrue(require_local_only_output_path(Path(self.temp.name) / "out.pdf"))

    def test_selected_handles_reject_wrong_org_window_and_marker(self) -> None:
        path = self.calls / "input_c.json"
        original = path.read_text()
        for old, new, message in (
            (ORG, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "organization scope"),
            (START, "2026-08-01", "report window"),
            (THROUGH, "2026-09-21", "snapshot"),
            ("q5_tasks", "q1_roster", "SQL marker"),
        ):
            with self.subTest(message=message):
                path.write_text(original.replace(old, new))
                with self.assertRaisesRegex(RuntimeError, message):
                    self._load()
        path.write_text(original)
        wrong_review = copy.deepcopy(self.review)
        wrong_review["organization_uuid"] = "different-org"
        with self.assertRaisesRegex(RuntimeError, "organization scope"):
            load_marked_results(self.calls, HANDLES, wrong_review["organization_uuid"], START, THROUGH)

    def test_selected_failed_query_never_falls_back_to_older_success(self) -> None:
        _statement(self.calls, "new", "q5_tasks", "h5-new")
        (self.calls / "output_new.json").write_text(json.dumps({"result": {
            "statement_handle": "h5-new", "status": "failed", "data": None,
            "message": "selected query failed"}}))
        with self.assertRaisesRegex(RuntimeError, "selected query failed"):
            load_marked_results(self.calls, {**HANDLES, "q5_tasks": "h5-new"}, ORG, START, THROUGH)
        self.assertEqual(len(self._load()["q5_tasks"]), 2)  # Explicit old selection remains inspectable.

    def test_mismatched_result_handle_and_incomplete_terminal_evidence_stop(self) -> None:
        path = self.calls / "output_cr1.json"
        original = json.loads(path.read_text())
        for change in ({"statement_handle": "unrelated"}, {"status": "running"},
                       {"row_count": 99}, {"row_count": None}):
            with self.subTest(change=change):
                changed = copy.deepcopy(original)
                changed["result"].update(change)
                path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(RuntimeError, "no completed saved result"):
                    self._load()
        path.write_text(json.dumps(original))

    def test_repeated_terminal_read_accepts_same_rows_but_rejects_conflict(self) -> None:
        page = json.loads((self.calls / "output_cr1.json").read_text())
        page["result"].update(status="success", message="repeated terminal read")
        repeated = self.calls / "output_repeat.json"
        repeated.write_text(json.dumps(page))
        self.assertEqual(len(self._load()["q5_tasks"]), 2)
        page["result"]["data"][0][3] = "999"
        repeated.write_text(json.dumps(page))
        with self.assertRaisesRegex(RuntimeError, "conflicting saved terminal pages"):
            self._load()

    def test_boolean_review_flags_are_strict(self) -> None:
        for value in ("false", "true", 1, {"approved": True}):
            with self.subTest(value=value):
                self.review["approved"] = value
                with self.assertRaisesRegex(ValueError, "Boolean true"):
                    self._input()
        self.review["approved"] = True
        for path in (("organization_scopes", 0, "reviewed"),
                     ("reviewed_narratives", "reviewed"),
                     ("sessions", 0, "classification_reviewed")):
            normalized = self._input()
            target = normalized
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = "false"
            with self.assertRaisesRegex(ValueError, "reviewed"):
                compute_pilot_usage_report(normalized, self.policy)

    def test_category_cap_reserves_uncategorized_before_build(self) -> None:
        self.review["categories"] = [{"category_id": f"c{i}", "label": f"C{i}", "description": "D"}
                                     for i in range(len(self.policy["category_palette"]))]
        with self.assertRaisesRegex(ValueError, "cap includes.*Uncategorized"):
            self._input()

    def test_window_action_derives_start_and_clears_approval(self) -> None:
        draft = {k: v for k, v in self.review.items() if k != "pilot_start"}
        updated = resolve_window(draft, self._load()["q4_grants"])
        self.assertEqual(updated["pilot_start"], START)
        self.assertIs(updated["approved"], False)
        self.assertEqual(updated["data_through"], THROUGH)
        review_path = Path(self.temp.name) / "review.json"
        review_path.write_text(json.dumps(draft))
        result = subprocess.run([sys.executable, str(PILOT / "build_pilot_usage_report.py"),
                                 "window", "--review", str(review_path), "--tool-calls", str(self.calls),
                                 "--grants-handle", "h4"], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["pilot_start"], START)
        self.assertIs(json.loads(review_path.read_text())["approved"], False)

    def test_historical_templates_bind_end_before_aggregation(self) -> None:
        source = (ROOT / "workspaces/pipeline/references/pilot-usage-queries.md").read_text()
        self.assertNotIn("CURRENT_DATE", source)
        for alias in ("b", "q"):
            self.assertIn(f"{alias}.date_pt BETWEEN '<pilot_start>' AND '<data_through>'", source)

    def test_feature_mix_keeps_all_mode_rows_and_groups_research_as_other(self):
        source = (ROOT / "workspaces/pipeline/references/pilot-usage-queries.md").read_text()
        feature = source.split("## 2. Feature mix", 1)[1].split("## 3.", 1)[0]
        self.assertIn("GROUP BY GROUPING SETS ((product_mode), (display_model))", feature)
        self.assertIn("QUALIFY kind = 'mode' OR ROW_NUMBER() OVER (PARTITION BY kind ORDER BY queries DESC) <= 5", feature)
        self.assertNotIn("LIMIT", feature)
        self.assertIn("study_mode, research, research_mode, scheduled_tasks, pro, and NULL roll into Other", feature)

    def test_report_marks_both_window_boundary_weeks_partial(self):
        reference = (PILOT.parent / "references/report-format.md").read_text()
        self.assertIn("first and last week marked `partial, <d> days` when shorter than 7", reference)
        self.assertIn("count only days inside the resolved report window", reference)
        self.assertIn("A mid-week start makes the first week partial", reference)

    def test_pdf_approval_shows_counts_and_keeps_full_titles_in_sandbox(self):
        reference = (PILOT.parent / "references/pdf-format.md").read_text()
        approval = reference.split("## Approval", 1)[1].split("## Pipeline", 1)[0]
        self.assertIn("full task-title list, grouped by category, to a sandbox file", approval)
        self.assertIn("Never list every title in chat", approval)
        self.assertIn("categories, each with its task count", approval)
        self.assertNotIn("each with its task titles", approval)
        self.assertIn("Set `approved: true` only on approval", approval)

    def test_actual_substituted_markdown_queries_pass_scope_binding(self) -> None:
        source = (ROOT / "workspaces/pipeline/references/pilot-usage-queries.md").read_text()
        document = pilot_usage_shared.yaml.safe_load(POLICY.read_text())
        replacements = {
            "<org_uuid>": ORG, "<pilot_start>": START, "<data_through>": THROUGH,
            "<window_days>": str(document["pilot_usage"]["window_days"]),
            "<internal_domain_filter>": " AND ".join(
                f"user_email NOT ILIKE '%@{domain}'" for domain in self.policy["internal_domains"]),
        }
        found = re.findall(r"```sql\n(-- pilot_usage (q1_roster|q4_grants|q5_tasks)\n.*?)\n```", source, re.S)
        self.assertEqual({marker for _, marker in found}, set(HANDLES))
        for statement, marker in found:
            for old, new in replacements.items():
                statement = statement.replace(old, new)
            suffix = {"q1_roster": "a", "q4_grants": "b", "q5_tasks": "c"}[marker]
            path = self.calls / f"input_{suffix}.json"
            call = json.loads(path.read_text())
            call["arguments"]["input"]["statement"] = statement
            path.write_text(json.dumps(call))
        self.assertEqual(len(self._load()["q5_tasks"]), 2)

    def test_render_uses_only_evidence_supported_labels(self) -> None:
        rendered = _render_pilot_usage_report_html(self._report(), self.policy)
        for claim in ("tasks completed", "remain available", "Credit runway", "not returned", "onboarding"):
            self.assertNotIn(claim, rendered)
        self.assertIn("billed task contexts", rendered)
        self.assertIn("first billed within this window", rendered)
        self.assertIn("not a current available balance", rendered)


if __name__ == "__main__":
    unittest.main()
