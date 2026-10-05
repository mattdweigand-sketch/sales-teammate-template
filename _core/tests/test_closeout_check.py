"""Regression checks for the task-triage closeout gate."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workspaces" / "pipeline" / "workflows" / "task-triage-speed-run" / "scripts"))
import closeout_check  # noqa: E402


AS_OF = "2026-09-25T12:00:00-07:00"


def task(id_, status="Not Started", due="2026-09-24", subject="Follow up"):
    return {"Id": id_, "Status": status, "ActivityDate": due, "Subject": subject}


class RecordsOfTests(unittest.TestCase):
    def test_accepts_list_records_object_and_saved_wrapper(self) -> None:
        rows = [task("a")]
        self.assertEqual(closeout_check.records_of(rows), rows)
        self.assertEqual(closeout_check.records_of({"records": rows}), rows)
        self.assertEqual(closeout_check.records_of({"results": [{"records": rows}]}), rows)
        with self.assertRaises(ValueError):
            closeout_check.records_of("junk")


class MainTests(unittest.TestCase):
    def run_main(self, doc):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(doc, handle)
        out = io.StringIO()
        with mock.patch.object(closeout_check.sys, "argv", ["closeout_check.py", handle.name, "--as-of", AS_OF]), \
                redirect_stdout(out):
            code = closeout_check.main()
        return code, out.getvalue()

    def test_passes_when_only_future_or_closed_tasks_remain(self) -> None:
        code, out = self.run_main([
            task("future", due="2026-09-26"),
            task("done", status="Completed", due="2026-09-01"),
            task("closed", status="closed", due=None),
        ])
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("PASS"))

    def test_fails_on_due_today_overdue_undated_and_bad_date(self) -> None:
        code, out = self.run_main({"records": [
            task("today", due="2026-09-25"),
            task("overdue", due="2026-09-01"),
            task("undated", due=None),
            task("garbage", due="not-a-date"),
            task("future", due="2026-10-01"),
        ]})
        self.assertEqual(code, 1)
        self.assertIn("FAIL 4 open Task(s)", out)
        for id_ in ("today", "overdue", "undated", "garbage"):
            self.assertIn(id_, out)
        self.assertNotIn("future", out)

    def test_rows_without_id_fail_closed(self) -> None:
        code, _ = self.run_main([{"Status": "Not Started", "ActivityDate": "2026-01-01"}, {"totalSize": 1}])
        self.assertEqual(code, 1)


    def test_saved_wrappers_preserve_overdue_rows(self):
        for doc in ({"result":{"records":[task("wrapped")]}}, {"result":json.dumps({"records":[task("string")]})}):
            self.assertEqual(self.run_main(doc)[0],1)

    def test_error_and_incomplete_empty_do_not_pass(self):
        for doc in ({"truncated":True,"result":{"records":[],"done":True,"totalSize":0}},{"hasMore":True,"result":{"records":[],"done":True}}, {"error":"query timeout"},{"records":[],"totalSize":1,"hasMore":True},{"records":[],"done":False},{"unexpected":[]}):
            self.assertEqual(self.run_main(doc)[0],1)
        self.assertEqual(self.run_main({"result":{"records":[],"totalSize":0,"done":True}})[0],0)

    def test_as_of_uses_caller_date_not_utc_or_sandbox(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
            json.dump({"records":[task("tomorrow", due="2026-09-26")]},f); f.flush()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(closeout_check.main([f.name,"--as-of","2026-09-25T23:30:00-07:00"]),0)
                self.assertEqual(closeout_check.main([f.name,"--as-of","2026-09-26T06:30:00+00:00"]),1)

if __name__ == "__main__":
    unittest.main()
