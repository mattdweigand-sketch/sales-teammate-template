"""Real Git refresh and counted native-preflight flows without customer systems."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_task_reschedule_check import evaluate_task_reschedule, reschedule_request_fixture
import test_event_launch_check as launch_tests


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "_core/scripts/workflow_revision_check.py"
SPEC = importlib.util.spec_from_file_location("workflow_revision_check", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
CONTRACT = "workspaces/pipeline/workflows/task-triage-speed-run/CONTEXT.md"
REFERENCE = "workspaces/pipeline/workflows/task-triage-speed-run/references/writes.md"
HELPER = "workspaces/pipeline/scripts/task_reschedule_check.py"


def consumed_scope_fixture() -> CHECK.WorkflowRevisionScope:
    return {"contract": CONTRACT, "sources": [
        {"path": "_core/policy.yaml", "kind": "policy", "selector": "salesforce.note_prefix"},
        {"path": REFERENCE, "kind": "section", "selector": "Writes"},
        {"path": HELPER, "kind": "file"},
    ]}


class WorkflowRevisionGitFixture(unittest.TestCase):
    """Create an upstream, bare origin and independently used checkout per test."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.upstream = self.sandbox / "publisher"
        self.remote = self.sandbox / "origin.git"
        self.checkout = self.sandbox / "consumer"
        self.upstream.mkdir()
        self.git(self.upstream, "init", "-b", "main")
        self.git(self.upstream, "config", "user.name", "Synthetic publisher")
        self.git(self.upstream, "config", "user.email", "synthetic@example.invalid")
        self.write(self.upstream, CONTRACT, "# Triage\nUse the existing native preflight and approval.\n")
        self.write(self.upstream, REFERENCE, "# Writes reference\n\n## Writes\nVerify approved fields.\n\n## Close\nUnselected close text.\n")
        self.write(self.upstream, HELPER, "def synthetic_task_preflight():\n    return 'fixture only'\n")
        self.write(self.upstream, "_core/rules.md", '\n'.join(
            f'<a id="{anchor}"></a>\n{anchor} synthetic rule.\n'
            for anchor in ("write_protocol", "approval", "repo_currency", "unused")))
        self.write(self.upstream, "_core/policy.yaml", "template:\n  mode: demo\ntooling:\n  governing_revision:\n    repository: fixture:" + str(self.remote) + "\n    remote: origin\n    branch: main\n  scripts:\n    workflow_revision_check: _core/scripts/workflow_revision_check.py\nsalesforce:\n  note_prefix: 'M/D/YY SR - '\n  unrelated: old\n")
        self.write(self.upstream, "_core/scripts/interfaces.md", "# Interfaces\n\n| workflow_revision_check | fixture |\n\n## Workflow revisions\nRead consumed sources.\n\n## Unused\nUnselected interface.\n")
        self.write(self.upstream, "_core/scripts/workflow_revision_check.py", SCRIPT.read_text())
        self.write(self.upstream, "README.md", "Synthetic repository.\n")
        self.commit()
        self.git(self.sandbox, "clone", "--bare", str(self.upstream), str(self.remote))
        self.git(self.upstream, "remote", "add", "origin", str(self.remote))
        self.git(self.sandbox, "clone", str(self.remote), str(self.checkout))
        self.scope = consumed_scope_fixture()
        self.baseline = self.check("snapshot")
        self.assertEqual(self.baseline["status"], "unchanged", self.baseline)

    def git(self, repo: Path, *arguments: str) -> bytes:
        result = subprocess.run(["git", "-C", str(repo), *arguments], capture_output=True, check=True)
        return result.stdout

    def write(self, repo: Path, path: str, text: str) -> None:
        destination = repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)

    def commit(self) -> None:
        self.git(self.upstream, "add", ".")
        self.git(self.upstream, "commit", "-m", "Synthetic instruction revision")

    def publish(self, path: str, old: str, new: str) -> None:
        destination = self.upstream / path
        self.assertIn(old, destination.read_text())
        destination.write_text(destination.read_text().replace(old, new))
        self.commit()
        self.git(self.upstream, "push", "origin", "main")

    def check(self, phase: str, baseline=None, scope=None) -> CHECK.WorkflowRevisionResult:
        return CHECK.check_workflow_revision(self.checkout, scope or self.scope, phase=phase,
                                             baseline=self.baseline if baseline is None and phase == "prewrite" else baseline)

    def cli(self, phase: str, baseline=None, scope=None) -> CHECK.WorkflowRevisionResult:
        scope_path = self.sandbox / "scope.json"
        scope_path.write_text(json.dumps(self.scope if scope is None else scope))
        command = [sys.executable, str(SCRIPT), "--repo", str(self.checkout), "--scope", str(scope_path), "--phase", phase]
        if baseline is not None:
            baseline_path = self.sandbox / "proposal-baseline.json"
            baseline_path.write_text(json.dumps(baseline))
            command.extend(["--baseline", str(baseline_path)])
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        output = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0 if output["status"] == "unchanged" else 1)
        return output

    def approved_task_write(self, baseline, approved=True, task_changed=False, writer="triage") -> dict:
        freshness = self.cli("prewrite", baseline)
        writes, readbacks = [], []
        request = reschedule_request_fixture()
        request["writer"] = writer
        proposal = evaluate_task_reschedule(request)
        self.assertEqual(proposal["status"], "ready")
        request["baseline"] = proposal["baseline"]
        request["baseline_links"] = proposal["baseline_links"]
        request["displayed_payload"] = proposal["payload"]
        if task_changed:
            request["task"]["Description"] += "Another writer changed the native Task.\n"
        native = evaluate_task_reschedule(request, "prewrite")
        if not task_changed:
            self.assertEqual(native["status"], "ready", native)
        if freshness["status"] == "unchanged" and approved and native["status"] == "ready":
            saved_record = deepcopy(request["task"])
            saved_record.update(native["payload"])
            writes.append(deepcopy(native["payload"]))
            readbacks.append({field: saved_record[field] for field in native["payload"]})
        return {"freshness": freshness, "writes": writes, "readbacks": readbacks, "native": native}


class WorkflowRevisionBehaviorTests(WorkflowRevisionGitFixture):
    def test_unchanged_scopes_have_historical_git_evidence_not_authority(self):
        result = self.check("prewrite")
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(result["revision"], self.baseline["snapshot"]["revision"])
        self.assertNotIn("authorized", result)
        self.assertNotIn("payload", result)
        self.assertNotIn("snapshot", result)

    def test_each_governing_source_change_is_identified(self):
        for path, old, new in (
            ("_core/rules.md", "repo_currency synthetic", "repo_currency revised"),
            ("_core/policy.yaml", "M/D/YY SR", "M/D/YY NEW"),
            (CONTRACT, "existing native", "revised native"),
            (HELPER, "fixture only", "changed helper"),
            (REFERENCE, "Verify approved fields", "Verify revised fields"),
        ):
            with self.subTest(path=path):
                self.publish(path, old, new)
                result = self.check("prewrite")
                self.assertEqual(result["status"], "changed")
                self.assertIn(path, [change["source"]["path"] for change in result["changes"]])

    def test_unconsumed_commits_policy_keys_sections_and_rules_pass(self):
        for path, old, new in (
            ("README.md", "Synthetic", "Updated"),
            ("_core/policy.yaml", "unrelated: old", "unrelated: new"),
            (REFERENCE, "Unselected close", "Updated close"),
            ("_core/rules.md", "unused synthetic", "unused revised"),
            ("_core/scripts/interfaces.md", "Unselected interface", "Updated interface"),
        ):
            self.publish(path, old, new)
        result = self.check("prewrite")
        self.assertEqual(result["status"], "unchanged", result)
        self.assertNotEqual(result["revision"], self.baseline["snapshot"]["revision"])

    def test_local_governing_modification_holds_without_mutating_sources(self):
        destination = self.checkout / REFERENCE
        destination.write_text(destination.read_text().replace("Verify approved", "Locally changed"))
        before = destination.read_bytes()
        result = self.check("prewrite")
        self.assertEqual(result["status"], "changed")
        self.assertEqual(destination.read_bytes(), before)
        self.assertIn("worktree", result["changes"][0]["reason"])

    def test_relevant_index_change_holds_even_if_worktree_is_current(self):
        destination = self.checkout / HELPER
        original = destination.read_bytes()
        destination.write_text("staged relevant change\n")
        self.git(self.checkout, "add", HELPER)
        destination.write_bytes(original)
        index_before = self.git(self.checkout, "show", ":" + HELPER)
        result = self.check("prewrite")
        self.assertEqual(result["status"], "changed")
        self.assertTrue(any("index" in change["reason"] for change in result["changes"]))
        self.assertEqual(index_before, self.git(self.checkout, "show", ":" + HELPER))

    def test_unrelated_staged_and_unstaged_work_is_preserved(self):
        destination = self.checkout / "README.md"
        destination.write_text("User staged README.\n")
        self.git(self.checkout, "add", "README.md")
        destination.write_text("User unstaged README.\n")
        policy = self.checkout / "_core/policy.yaml"
        policy.write_text(policy.read_text().replace("unrelated: old", "unrelated: local"))
        self.git(self.checkout, "add", "_core/policy.yaml")
        before_status = self.git(self.checkout, "status", "--porcelain")
        before_index = (self.checkout / ".git/index").read_bytes()
        self.publish("README.md", "Synthetic", "Remote updated")
        self.assertEqual(self.check("prewrite")["status"], "unchanged")
        self.assertEqual(before_status, self.git(self.checkout, "status", "--porcelain"))
        self.assertEqual(before_index, (self.checkout / ".git/index").read_bytes())
        self.assertEqual(destination.read_text(), "User unstaged README.\n")

    def test_missing_legacy_baseline_holds(self):
        result = CHECK.check_workflow_revision(self.checkout, self.scope, phase="prewrite")
        self.assertEqual(result["status"], "needs-input")
        self.assertIn("historical snapshot", result["reasons"][0])

    def test_missing_inconsistent_or_forged_evidence_holds(self):
        for mutation in ("fingerprints", "scope", "revision", "status", "format", "top_revision", "top_changes", "top_reasons"):
            with self.subTest(mutation=mutation):
                saved = deepcopy(self.baseline)
                if mutation == "status":
                    saved["status"] = "changed"
                elif mutation.startswith("top_"):
                    saved[mutation.removeprefix("top_")] = "contradictory snapshot receipt"
                elif mutation == "format":
                    saved["snapshot"]["format"] = True
                elif mutation == "fingerprints":
                    saved["snapshot"][mutation][0]["sha256"] = "0" * 64
                else:
                    del saved["snapshot"][mutation]
                self.assertEqual(self.check("prewrite", saved)["status"], "needs-input")

    def test_prewrite_cannot_replace_or_widen_the_saved_scope(self):
        for replacement in ([], [{"path": REFERENCE, "kind": "file"}]):
            with self.subTest(replacement=replacement):
                scope = deepcopy(self.scope)
                scope["sources"] = replacement
                self.assertEqual(self.check("prewrite", scope=scope)["status"], "needs-input")
        entry_scope = {"deal_thread_entry": "workspaces/pipeline/AGENTS.md", "sources": self.scope["sources"]}
        result = self.check("prewrite", scope=entry_scope)
        self.assertEqual(result["status"], "needs-input")
        self.assertIn("cannot be substituted", result["reasons"][0])

    def test_deleted_remote_and_local_sources_hold(self):
        (self.upstream / HELPER).unlink()
        self.commit()
        self.git(self.upstream, "push", "origin", "main")
        self.assertEqual(self.check("prewrite")["status"], "needs-input")
        (self.checkout / HELPER).unlink()
        self.assertEqual(self.check("snapshot")["status"], "needs-input")

    def test_invalid_selectors_paths_shapes_and_escape_links_hold(self):
        for source in (
            {"path": ".", "kind": "file"},
            {"path": "../outside", "kind": "file"},
            {"path": "/_core/rules.md", "kind": "file"},
            {"path": REFERENCE, "kind": "section", "selector": "Absent"},
            {"path": "_core/policy.yaml", "kind": "policy", "selector": "salesforce.absent"},
            {"path": "_core/rules.md", "kind": "rule", "selector": "absent"},
            {"path": "_core/policy.yaml", "kind": "file"},
            {"path": "_core/rules.md", "kind": "section", "selector": "Rules"},
            {"path": HELPER, "kind": "file", "current_hash": "trusted"},
        ):
            with self.subTest(source=source):
                scope = deepcopy(self.scope)
                scope["sources"].append(source)
                self.assertEqual(self.check("snapshot", scope=scope)["status"], "needs-input")
        destination = self.checkout / HELPER
        destination.unlink()
        destination.symlink_to(SCRIPT)
        self.assertEqual(self.check("snapshot")["status"], "needs-input")

    def test_failed_fetch_never_uses_cached_main_as_fresh_proof(self):
        shutil.rmtree(self.remote)
        result = self.check("prewrite")
        self.assertEqual(result["status"], "needs-input")
        self.assertIn("fetch", result["reasons"][0])

    def test_synthetic_fetch_errors_classify_without_leaking_credentials(self):
        failed_upload = self.sandbox / "failed-upload"
        self.git(self.checkout, "config", "remote.origin.uploadpack", str(failed_upload))
        secret = "synthetic-secret-token"
        for diagnostic, category in (
            ("Authentication failed", "authentication or access denied"),
            ("couldn't find remote ref refs/heads/main", "requested deployment ref is missing"),
            ("cannot lock ref refs/remotes/origin/main", "local tracking ref conflict"),
            ("Could not resolve host", "transport connection failed"),
            ("unrecognized private upstream failure", "unclassified Git failure"),
        ):
            with self.subTest(category=category):
                failed_upload.write_text("#!/bin/sh\ncat >&2 <<'ERROR'\n" + diagnostic +
                    " https://private-user:" + secret + "@synthetic.invalid/private?token=" + secret +
                    "\nERROR\nexit 128\n")
                failed_upload.chmod(0o700)
                result = self.check("prewrite")
                self.assertEqual(result["status"], "needs-input", result)
                self.assertIn(category, result["reasons"][0])
                self.assertLess(len(result["reasons"][0]), 180)
                self.assertNotIn(secret, json.dumps(result))
                self.assertNotIn("private-user", json.dumps(result))
                self.assertNotIn("https://", json.dumps(result))

    def test_native_missing_main_reports_specific_refresh_gap(self):
        self.git(self.remote, "update-ref", "-d", "refs/heads/main")
        result = self.check("prewrite")
        self.assertEqual(result["status"], "needs-input")
        self.assertIn("requested deployment ref is missing", result["reasons"][0])

    def test_ambiguous_sections_and_rule_anchors_hold(self):
        for path, extra in ((REFERENCE, "\n## Writes\nAmbiguous.\n"),
                            ("_core/rules.md", '\n<a id="repo_currency"></a>\nAmbiguous.\n')):
            with self.subTest(path=path):
                destination = self.checkout / path
                destination.write_text(destination.read_text() + extra)
                self.assertEqual(self.check("snapshot")["status"], "needs-input")

    def fenced_source_baseline(self, path: str, text: str, name: str) -> CHECK.WorkflowRevisionResult:
        self.write(self.upstream, path, text)
        self.commit()
        self.git(self.upstream, "push", "origin", "main")
        self.checkout = self.sandbox / name
        self.git(self.sandbox, "clone", str(self.remote), str(self.checkout))
        return self.check("snapshot")

    def test_changes_after_fenced_heading_lines_in_selected_section_are_changed(self):
        for index, fence in enumerate(("```", "~~~", "````")):
            with self.subTest(fence=fence):
                text = "## Writes\nBefore.\n" + fence + "markdown\n# example\nInside example.\n" + fence + "\nGoverning after fence.\n\n## Close\nUnused.\n"
                baseline = self.fenced_source_baseline(REFERENCE, text, "fenced-section-" + str(index))
                self.assertEqual(baseline["status"], "unchanged", baseline)
                self.publish(REFERENCE, "Governing after fence", "Revised governing after fence")
                result = self.check("prewrite", baseline)
                self.assertEqual(result["status"], "changed", result)
                self.assertIn({"source": {"path": REFERENCE, "kind": "section", "selector": "Writes"},
                               "reason": "deployed branch scope changed"}, result["changes"])

    def test_fenced_duplicate_heading_and_anchor_are_not_ambiguous(self):
        for index, fence in enumerate(("```", "~~~")):
            with self.subTest(fence=fence):
                text = "## Writes\n" + fence + "markdown\n## Writes\n" + fence + "\nActual instructions.\n\n## Close\nUnused.\n"
                baseline = self.fenced_source_baseline(REFERENCE, text, "duplicate-section-" + str(index))
                self.assertEqual(baseline["status"], "unchanged", baseline)
                rules = self.upstream / "_core/rules.md"
                text = rules.read_text().replace("repo_currency synthetic rule.",
                    "repo_currency synthetic rule.\n" + fence + 'html\n<a id="repo_currency"></a>\n' + fence + "\nActual instructions.")
                baseline = self.fenced_source_baseline("_core/rules.md", text, "duplicate-anchor-" + str(index))
                self.assertEqual(baseline["status"], "unchanged", baseline)
                self.assertEqual(self.check("prewrite", baseline)["status"], "unchanged")

    def test_rule_boundaries_ignore_fenced_headings_and_anchors_but_hash_body(self):
        for index, fence in enumerate(("```", "~~~")):
            with self.subTest(fence=fence):
                rules = self.upstream / "_core/rules.md"
                text = rules.read_text().replace("approval synthetic rule.",
                    "approval synthetic rule.\n" + fence + 'markdown\n# example\n<a id="fake_boundary"></a>\nExample body.\n' + fence + "\nApproval after fence.")
                baseline = self.fenced_source_baseline("_core/rules.md", text, "fenced-rule-" + str(index))
                self.assertEqual(baseline["status"], "unchanged", baseline)
                self.publish("_core/rules.md", "Approval after fence", "Revised approval after fence")
                result = self.check("prewrite", baseline)
                self.assertEqual(result["status"], "changed", result)
                self.assertIn({"source": {"path": "_core/rules.md", "kind": "rule", "selector": "approval"},
                               "reason": "deployed branch scope changed"}, result["changes"])

    def test_short_or_other_fence_does_not_close_fenced_boundary_mask(self):
        for fence, shorter in (("````", "```"), ("~~~~", "~~~")):
            with self.subTest(fence=fence):
                text = "## Writes\n" + fence + "\n" + shorter + "\n## Writes\nFenced payload.\n" + ("~~~" if fence[0] == "`" else "```") + "\n" + fence + "\nFinal body.\n\n## Close\nUnused.\n"
                source = {"path": REFERENCE, "kind": "section", "selector": "Writes"}
                selected = CHECK._selected_bytes(text.encode(), source)
                self.assertIn(b"Final body.", selected)
                self.assertNotIn(b"Unused.", selected)
                self.assertIn(b"Fenced payload.", selected)
                self.assertNotEqual(selected, CHECK._selected_bytes(text.replace("Fenced payload.", "Changed payload.").encode(), source))
                self.assertNotEqual(selected, CHECK._selected_bytes(text.replace("Final body.", "Changed body.").encode(), source))

    def test_selected_stage_does_not_require_sibling_contracts_or_sections(self):
        sibling = "workspaces/pipeline/workflows/other-stage/CONTEXT.md"
        self.write(self.upstream, sibling, "Sibling must not be consumed.\n")
        self.commit()
        self.git(self.upstream, "push", "origin", "main")
        self.assertFalse((self.checkout / sibling).exists())
        self.assertEqual(self.check("prewrite")["status"], "unchanged")
        self.assertFalse(any(item["source"]["path"] == sibling for item in self.baseline["snapshot"]["fingerprints"]))


class WorkflowRevisionEndToEndTests(WorkflowRevisionGitFixture):
    """Execute both freshness CLI phases and the existing native Task validator."""

    def test_unchanged_snapshot_fetch_prewrite_native_write_and_readback(self):
        baseline = self.cli("snapshot")
        result = self.approved_task_write(baseline)
        self.assertEqual(len(result["writes"]), 1)
        self.assertEqual(result["readbacks"], result["writes"])
        self.assertEqual(result["writes"][0]["ActivityDate"], "2026-10-09")

    def test_each_relevant_intervening_commit_causes_zero_native_writes(self):
        for path, old, new in (
            ("_core/rules.md", "approval synthetic", "approval revised"),
            ("_core/policy.yaml", "M/D/YY SR", "M/D/YY NEW"),
            (CONTRACT, "existing native", "revised native"),
            (HELPER, "fixture only", "changed helper"),
        ):
            with self.subTest(path=path):
                baseline = self.cli("snapshot")
                self.publish(path, old, new)
                result = self.approved_task_write(baseline)
                self.assertEqual(result["freshness"]["status"], "changed")
                self.assertEqual(result["writes"], [])
                self.assertEqual(result["readbacks"], [])
                fresh_checkout = self.sandbox / ("fresh-" + str(len(list(self.sandbox.glob("fresh-*")))))
                self.git(self.sandbox, "clone", str(self.remote), str(fresh_checkout))
                self.checkout = fresh_checkout

    def test_unrelated_commit_still_allows_existing_approval_and_readback(self):
        baseline = self.cli("snapshot")
        self.publish("_core/policy.yaml", "unrelated: old", "unrelated: new")
        self.publish(REFERENCE, "Unselected close", "Changed close")
        self.publish("README.md", "Synthetic", "Changed")
        result = self.approved_task_write(baseline)
        self.assertEqual(len(result["writes"]), 1)
        self.assertEqual(result["readbacks"], result["writes"])

    def test_missing_history_and_failed_refresh_produce_zero_writes(self):
        result = self.approved_task_write(None)
        self.assertEqual(result["writes"], [])
        shutil.rmtree(self.remote)
        self.assertEqual(self.approved_task_write(self.baseline)["writes"], [])

    def test_freshness_does_not_replace_approval_or_native_stale_gates(self):
        self.assertEqual(self.approved_task_write(self.baseline, approved=False)["writes"], [])
        result = self.approved_task_write(self.baseline, task_changed=True)
        self.assertEqual(result["freshness"]["status"], "unchanged")
        self.assertEqual(result["writes"], [])
        self.assertNotEqual(result["native"]["status"], "ready")

    def test_clean_checkout_reread_requires_new_snapshot_and_fresh_approval(self):
        old_baseline = self.cli("snapshot")
        self.publish(CONTRACT, "existing native", "revised native")
        fresh_checkout = self.sandbox / "fresh-consumer"
        self.git(self.sandbox, "clone", str(self.remote), str(fresh_checkout))
        old_checkout = self.checkout
        self.checkout = fresh_checkout
        self.assertEqual(self.approved_task_write(old_baseline)["writes"], [])
        new_baseline = self.cli("snapshot")
        self.assertEqual(new_baseline["status"], "unchanged")
        self.assertEqual(self.approved_task_write(new_baseline, approved=False)["writes"], [])
        self.assertEqual(len(self.approved_task_write(new_baseline)["writes"]), 1)
        self.assertIn("existing native", (old_checkout / CONTRACT).read_text())

    def test_forecast_letter_cannot_reuse_old_approval_after_recalculation(self):
        contract = "workspaces/forecasting/workflows/forecast-weekly/CONTEXT.md"
        self.write(self.upstream, contract, "# Forecast\nLettered ForecastCategoryName changes only.\n")
        policy = self.upstream / "_core/policy.yaml"
        policy.write_text(policy.read_text() + "forecast:\n  forecast_category_map:\n    commit: Commit\n")
        self.commit()
        self.git(self.upstream, "push", "origin", "main")
        first_checkout = self.sandbox / "forecast-display"
        self.git(self.sandbox, "clone", str(self.remote), str(first_checkout))
        self.checkout = first_checkout
        self.scope = {"contract": contract, "sources": [
            {"path": "_core/policy.yaml", "kind": "policy", "selector": "forecast.forecast_category_map"}]}
        old_baseline = self.cli("snapshot")
        old_proposal = {"letter": "A", "payload": {"ForecastCategoryName": "Commit"}, "baseline": old_baseline}
        self.publish("_core/policy.yaml", "commit: Commit", "commit: BestCase")
        old_check = self.cli("prewrite", old_proposal["baseline"])
        writes = []
        if old_check["status"] == "unchanged":
            writes.append(old_proposal["payload"])
        self.assertEqual(writes, [])
        fresh_checkout = self.sandbox / "forecast-recalculation"
        self.git(self.sandbox, "clone", str(self.remote), str(fresh_checkout))
        self.checkout = fresh_checkout
        new_proposal = {"letter": "B", "payload": {"ForecastCategoryName": "BestCase"}, "baseline": self.cli("snapshot")}
        self.assertEqual(self.cli("prewrite", new_proposal["baseline"])["status"], "unchanged")
        for native_reply, expected_count in (("A", 0), ("B", 1)):
            with self.subTest(native_reply=native_reply):
                writes = []
                if native_reply == new_proposal["letter"] and self.cli("prewrite", new_proposal["baseline"])["status"] == "unchanged":
                    writes.append(deepcopy(new_proposal["payload"]))
                self.assertEqual(len(writes), expected_count)
                self.assertEqual(deepcopy(writes), writes)


class WorkflowRevisionDealThreadTests(WorkflowRevisionGitFixture):
    """A direct Pipeline deal action needs no invented workflow or sibling files."""

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.upstream / "workspaces/pipeline/workflows")
        self.entry = "workspaces/pipeline/AGENTS.md"
        self.write(self.upstream, self.entry, "# Pipeline\nDeal threads use shared approval and native Task gates.\n")
        rules = self.upstream / "_core/rules.md"
        rules.write_text(rules.read_text() + '\n<a id="task_date_coordination"></a>\nShared native Task coordination.\n')
        self.commit()
        self.git(self.upstream, "push", "origin", "main")
        self.checkout = self.sandbox / "deal-thread"
        self.git(self.sandbox, "clone", str(self.remote), str(self.checkout))
        self.scope = {"deal_thread_entry": self.entry, "sources": [
            {"path": "_core/rules.md", "kind": "rule", "selector": "task_date_coordination"},
            {"path": "_core/policy.yaml", "kind": "policy", "selector": "salesforce.note_prefix"},
            {"path": HELPER, "kind": "file"}]}
        self.baseline = self.cli("snapshot")
        self.assertEqual(self.baseline["status"], "unchanged", self.baseline)

    def test_actual_deal_entry_without_any_workflow_folder_allows_approved_write(self):
        self.assertFalse((self.checkout / "workspaces/pipeline/workflows").exists())
        self.assertFalse((self.upstream / "workspaces/pipeline/workflows").exists())
        saved_scope = self.baseline["snapshot"]["scope"]
        self.assertEqual(saved_scope["deal_thread_entry"], self.entry)
        self.assertNotIn("contract", saved_scope)
        self.assertFalse(any("/workflows/" in source["path"] for source in saved_scope["sources"]))
        result = self.approved_task_write(self.baseline, writer="deal_thread")
        self.assertEqual(len(result["writes"]), 1)
        self.assertEqual(result["readbacks"], result["writes"])

    def test_changed_deal_entry_holds_old_approval_with_zero_writes(self):
        self.publish(self.entry, "shared approval", "revised shared approval")
        result = self.approved_task_write(self.baseline, writer="deal_thread")
        self.assertEqual(result["freshness"]["status"], "changed")
        self.assertEqual(result["writes"], [])
        self.assertIn(self.entry, [change["source"]["path"] for change in result["freshness"]["changes"]])

    def test_invalid_workspace_entries_and_dual_entry_claims_hold(self):
        for entry in ("AGENTS.md", "workspaces/prospecting/AGENTS.md", "workspaces/pipeline/CONTEXT.md", CONTRACT, "../AGENTS.md"):
            with self.subTest(entry=entry):
                scope = deepcopy(self.scope)
                scope["deal_thread_entry"] = entry
                self.assertEqual(self.cli("snapshot", scope=scope)["status"], "needs-input")
        scope = deepcopy(self.scope)
        scope["contract"] = CONTRACT
        self.assertEqual(self.cli("snapshot", scope=scope)["status"], "needs-input")

    def test_deal_entry_cannot_substitute_workflow_scope_or_add_sources_at_prewrite(self):
        for replacement in (consumed_scope_fixture(), {**self.scope, "sources": [*self.scope["sources"],
                {"path": "_core/rules.md", "kind": "rule", "selector": "unused"}]}):
            with self.subTest(scope=replacement):
                result = self.cli("prewrite", self.baseline, replacement)
                self.assertEqual(result["status"], "needs-input")
                self.assertIn("cannot be substituted", result["reasons"][0])
                self.assertNotIn("snapshot", result)


class WorkflowRevisionStagedEndToEndTests(WorkflowRevisionGitFixture):
    """Keep an E proposal's Plan scope and separately establish Launch entry."""

    def setUp(self):
        super().setUp()
        self.plan = "workspaces/prospecting/workflows/event-sequence/02-sequence-plan/CONTEXT.md"
        self.launch = "workspaces/prospecting/workflows/event-sequence/03-launch/CONTEXT.md"
        self.sequence = "workspaces/prospecting/workflows/event-sequence/references/sequence.md"
        self.write(self.upstream, self.plan, "# Plan\nDisplay the exact E proposal. No writes.\n")
        self.write(self.upstream, self.launch, "# Launch\nUse the same exact E approval and native payload gates.\n")
        self.write(self.upstream, self.sequence, "## Approval\nExact E in this run.\n\n## Enrollment\nNative payload checks.\n\n## Unselected\nNo preload.\n")
        self.commit()
        self.git(self.upstream, "push", "origin", "main")
        self.refresh_checkout("entry")
        self.plan_scope = {"contract": self.plan, "sources": [
            {"path": self.sequence, "kind": "section", "selector": "Approval"}]}
        self.launch_scope = {"contract": self.launch, "sources": [
            {"path": self.sequence, "kind": "section", "selector": "Enrollment"}]}
        self.plan_baseline = self.cli("snapshot", scope=self.plan_scope)
        self.assertEqual(self.plan_baseline["status"], "unchanged")

    def refresh_checkout(self, name: str) -> None:
        self.checkout = self.sandbox / name
        self.git(self.sandbox, "clone", str(self.remote), str(self.checkout))

    def enter_launch(self) -> CHECK.WorkflowRevisionResult:
        plan = self.cli("prewrite", self.plan_baseline, self.plan_scope)
        if plan["status"] != "unchanged":
            return plan
        return self.cli("snapshot", scope=self.launch_scope)

    def launch_write(self, launch_baseline, native_approval=True, native_payload_valid=True) -> dict:
        checks = [self.cli("prewrite", self.plan_baseline, self.plan_scope),
                  self.cli("prewrite", launch_baseline, self.launch_scope)]
        writes = []
        fixture = launch_tests.EventLaunchCheck()
        fixture.setUp()
        if not native_payload_valid:
            fixture.bundle["payload"]["send_email_from_email_account_id"] = "unapproved-mailbox"
        payload_check = launch_tests.launch.check(fixture.bundle)
        self.assertEqual(payload_check["status"], "PASS" if native_payload_valid else "FAIL")
        if all(result["status"] == "unchanged" for result in checks) and native_approval and payload_check["status"] == "PASS":
            writes.append(deepcopy(payload_check["payload"]))
        return {"checks": checks, "writes": writes, "readbacks": deepcopy(writes), "payload_check": payload_check}

    def test_plan_change_stops_launch_entry_with_no_writes(self):
        self.publish(self.plan, "exact E proposal", "revised exact E proposal")
        entry = self.enter_launch()
        self.assertEqual(entry["status"], "changed")
        self.assertNotIn("snapshot", entry)
        self.assertEqual(self.launch_write(entry)["writes"], [])

    def test_unchanged_plan_allows_legitimately_refreshed_launch_entry(self):
        self.publish(self.launch, "native payload gates", "revised native payload gates")
        self.refresh_checkout("refreshed-launch")
        entry = self.enter_launch()
        self.assertEqual(entry["status"], "unchanged", entry)
        self.assertNotEqual(entry["snapshot"]["revision"], self.plan_baseline["snapshot"]["revision"])
        self.assertFalse(any(item["source"]["path"] == self.launch for item in self.plan_baseline["snapshot"]["fingerprints"]))
        self.assertFalse(any(item["source"]["path"] == self.plan for item in entry["snapshot"]["fingerprints"]))
        result = self.launch_write(entry)
        self.assertEqual(len(result["writes"]), 1)
        self.assertEqual(result["readbacks"], result["writes"])

    def test_launch_change_after_entry_stops_every_subsequent_write(self):
        entry = self.enter_launch()
        saved_entry = deepcopy(entry)
        completed = self.launch_write(entry)["writes"]
        self.assertEqual(len(completed), 1)
        self.publish(self.launch, "native payload gates", "revised native payload gates")
        for write_boundary in ("create_contact", "update_sequence", "enroll", "activate"):
            with self.subTest(write_boundary=write_boundary):
                result = self.launch_write(entry)
                self.assertEqual(result["checks"][0]["status"], "unchanged")
                self.assertEqual(result["checks"][1]["status"], "changed")
                self.assertEqual(result["writes"], [])
                self.assertEqual(result["readbacks"], [])
                self.assertEqual(len(completed), 1)
                self.assertEqual(entry, saved_entry)

    def test_current_native_approval_and_payload_remain_required(self):
        entry = self.enter_launch()
        for approval, payload in ((False, True), (True, False)):
            with self.subTest(approval=approval, payload=payload):
                result = self.launch_write(entry, approval, payload)
                self.assertTrue(all(check["status"] == "unchanged" for check in result["checks"]))
                self.assertEqual(result["writes"], [])


class WorkflowRevisionContractTests(unittest.TestCase):
    def test_freshness_inputs_only_cover_writers_and_the_e_proposal_stage(self):
        expected = {
            "pipeline/workflows/interaction-sync", "pipeline/workflows/close", "pipeline/workflows/customer-review",
            "pipeline/workflows/pipeline-review", "pipeline/workflows/task-triage-speed-run",
            "forecasting/workflows/forecast-weekly", "prospecting/workflows/signal-prospecting/02-outreach",
            "prospecting/workflows/signal-prospecting/03-followup", "prospecting/workflows/event-sequence/01-list-prep",
            "prospecting/workflows/event-sequence/02-sequence-plan", "prospecting/workflows/event-sequence/03-launch",
        }
        actual = {str(path.parent.relative_to(ROOT / "workspaces"))
                  for path in (ROOT / "workspaces").glob("*/workflows/**/CONTEXT.md")
                  if "| Core freshness |" in path.read_text()}
        self.assertEqual(actual, expected)
        forecast = (ROOT / "workspaces/forecasting/workflows/forecast-weekly/CONTEXT.md").read_text()
        self.assertIn('| Forecast only, `rules#repo_currency`, `workflow_revision_check`, "Workflow revisions" |', forecast)

    def test_deployment_has_one_canonical_receipt_not_thread_broadcasts(self):
        conventions = (ROOT / "_core/CONVENTIONS.md").read_text()
        section = conventions.split("## Deployment communication\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("one deployment receipt in Systems", section)
        self.assertIn("Never enumerate or wake every deal thread", section)
        self.assertIn("Do not retry obsolete undelivered guidance notices", section)
        for workflow in ("repo-maintenance", "agent-configuration"):
            text = (ROOT / "workspaces/systems/workflows" / workflow / "CONTEXT.md").read_text()
            self.assertIn('"Deployment communication"', text)
            self.assertIn("necessary", text)

    def test_staged_inputs_keep_existing_e_grammar_and_boundaries(self):
        directory = ROOT / "workspaces/prospecting/workflows/event-sequence"
        plan = (directory / "02-sequence-plan/CONTEXT.md").read_text()
        launch = (directory / "03-launch/CONTEXT.md").read_text()
        coordinator = (directory / "CONTEXT.md").read_text()
        self.assertIn("E proposal scope only, no Launch preload or writes", plan)
        self.assertIn("No separate list-only or copy-only approval is added", plan)
        self.assertIn("Original Plan and separate Launch-entry scope checks", launch)
        self.assertIn("separate from E and native receipts", launch)
        self.assertIn("No extra Launch approval is added", launch)
        self.assertIn("Report completed calls without replay, implied rollback", launch)
        self.assertNotIn("| Core freshness |", coordinator)

    def test_forecast_letters_hold_and_pipeline_handoffs_transfer_no_approval(self):
        directory = ROOT / "workspaces/forecasting/workflows/forecast-weekly"
        contract = (directory / "CONTEXT.md").read_text()
        report = (directory / "references/report-format.md").read_text()
        self.assertIn("snapshot each write letter's scope", contract)
        self.assertIn("Pipeline makes its own source fingerprint, proposal and approval", contract)
        self.assertIn("Relevant changes hold that old letter for a new proposal and approval", report)
        self.assertIn("Never silently reuse approval after recalculation", report)


if __name__ == "__main__":
    unittest.main()
