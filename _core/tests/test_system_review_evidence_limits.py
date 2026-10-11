"""Guard review evidence against export-local counters and incomplete task pages."""
import unittest

from test_icm_contracts import sections
from test_skill_contracts import CONTRACT_PATHS, ROOT, inputs_rows, loaded_contract_text


class SystemReviewEvidenceLimits(unittest.TestCase):
    def test_timestamped_history_window_requires_coverage_or_new_session(self):
        loaded = loaded_contract_text(CONTRACT_PATHS["system-review"].parent)
        for expected in (
            "Call `load_sessions` in Code Mode with the verified session context UUID, not the URL task ID.",
            "`first_entry_at`, `last_entry_at` and each entry's UTC timestamp",
            "Window thread entries by their timestamps, never by turn numbers.",
            "`first_entry_at` is at or before the window start",
            "`session_get` confirms the session was created after the window start",
            "Otherwise report the uncovered span as not checked and do not advance that thread's baseline.",
            "If `load_sessions` is unavailable or fails, fall back to `session_download_content`",
            "An undated fallback cannot prove a timed window complete.",
        ):
            self.assertIn(expected, loaded)
        lookup = "\n".join(sections((ROOT / "_core/thread-locators.md").read_text())["Teammate thread lookup"])
        self.assertIn("Prefer `load_sessions` in Code Mode with that context UUID, never a URL task ID.", lookup)
        self.assertIn("If it is unavailable or fails, fall back to `session_download_content`", lookup)

    def test_shifted_export_turns_cannot_advance_a_review_baseline(self):
        loaded = loaded_contract_text(CONTRACT_PATHS["system-review"].parent)
        self.assertIn("Turn numbers are export-local positions, not durable entry identities.", loaded)
        self.assertIn("Never select new entries by comparing turn numbers across exports.", loaded)
        self.assertIn("Native entry IDs are not required when timestamp coverage is verified.", loaded)
        self.assertIn("Do not advance its baseline or count unread outcomes when required coverage is incomplete.", loaded)
        self.assertNotIn("read only turns later than its last-read turn number", loaded)
        self.assertNotIn("The next review reads only later turns.", loaded)

    def test_capped_task_pages_do_not_prove_dedupe_complete(self):
        loaded = loaded_contract_text(CONTRACT_PATHS["system-review"].parent)
        self.assertIn("A returned `next_cursor` means the task inventory is incomplete.", loaded)
        self.assertIn("If the installed CLI cannot consume it, report dedupe not checked and create no tasks.", loaded)
        self.assertIn("Never invent a cursor option or treat a full 100-task page as complete.", loaded)
        self.assertIn("Unreadable or incomplete dedupe evidence blocks new task creation", loaded)

    def test_sweep_checks_current_release_gate_without_a_historical_pr_state(self):
        sweep = ROOT / "workspaces/pipeline/workflows/interaction-sync/references/sweep.md"
        text = sweep.read_text()
        self.assertNotIn("held policy PR", text)
        self.assertIn("Read the deployed `rules#momentum` before enumeration.", text)
        self.assertIn("This contract grants no new shared-rule authority.", text)
        self.assertIn("Missing settings stop enumeration as not checked.", text)

    def test_history_consumers_load_verified_runtime_thread_lookup(self):
        for skill in ("deal-coach", "forecast-weekly", "system-review"):
            with self.subTest(skill=skill):
                rows = inputs_rows(CONTRACT_PATHS[skill].read_text())
                routes = [row for row in rows if row[1] == "`_core/thread-locators.md`"
                          and '"Teammate thread lookup"' in row[2]]
                self.assertEqual(len(routes), 1)
        interface = sections((ROOT / "_core/thread-locators.md").read_text())
        lookup = "\n".join(interface["Teammate thread lookup"])
        self.assertIn("Use the unique approved role entry's `agent_id` as the owning session context UUID.", lookup)
        self.assertIn("The roster is not a complete deal-thread inventory.", lookup)
        self.assertIn("Use `session_get` to verify the destination's project", lookup)
        self.assertIn("Metadata previews never replace a transcript.", lookup)
        self.assertIn("Missing history is not proof of a first report or no change.", lookup)
