"""Stage contracts and their loaded references name only things that exist.

A saved Signal skill points directly to a numbered stage contract. Event Sequence enters its coordinator and selected stage. This test resolves what each execution
contract references: every `policy.<dotted>` key against policy.yaml, each explicit repo path against the
checkout, and every named script against the stage, workspace and core scripts/. A contract that
names a key or file that is not there fails here instead of at run time.
"""
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from test_skill_contracts import SKILL_PATHS, SIGNAL_WORKFLOW, EVENT_WORKFLOW, EVENT_STAGE_ORDER, EVENT_STAGE_PATHS, layout_entries, owning_workflow, reference_is_loaded

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
WORKFLOWS = ROOT / "workspaces/prospecting/workflows"
STAGES = SIGNAL_WORKFLOW
STAGE_ORDER = ("01-research", "02-outreach", "03-followup")
EXPECTED_STAGES = set(STAGE_ORDER) | set(EVENT_STAGE_ORDER)
EXPECTED_WORKFLOWS = {"signal-prospecting", "event-sequence"}
HEADINGS = ("## Inputs", "## Process", "## Checkpoints", "## Audit", "## Outputs")
ALLOWED_HEADINGS = set(HEADINGS) | {"## Checkpoints", "## Audit"}


def stage_contracts():
    """Stage contracts only; the blank starter in _core/templates is not a stage."""
    return sorted({path / "CONTEXT.md" for name, path in SKILL_PATHS.items()
                   if name.startswith("signal-")} | EVENT_STAGE_PATHS)


def stage_sources():
    return stage_contracts() + [EVENT_WORKFLOW / "CONTEXT.md"] + sorted(WORKFLOWS.rglob("references/*.md"))


def section(text, heading):
    return text.split(f"\n{heading}\n", 1)[1].split("\n## ", 1)[0]


POLICY_REF = re.compile(r"(?<![A-Za-z0-9_])policy\.((?!yaml\b)[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*)")
REPO_PATH = re.compile(r"(?<![A-Za-z0-9_./-])((?:_core|workspaces)/[A-Za-z0-9_./-]+)")
SCRIPT_NAME = re.compile(r"\b([a-z_]+\.(?:py|sql))\b")
SKILL_NAME = re.compile(r"`(signal-[a-z-]+|event-sequence)`")


def resolve(pol, dotted):
    node = pol
    for part in dotted.split("."):
        node = node.get(part) if isinstance(node, dict) else None
        if node is None:
            return False
    return True


class StageContractTests(unittest.TestCase):
    def setUp(self):
        self.pol = yaml.safe_load((CORE / "policy.yaml").read_text())
        self.files = stage_contracts()
        self.sources = stage_sources()
        self.assertEqual({f.parent.name for f in self.files}, EXPECTED_STAGES)
        self.assertEqual({p.name for p in layout_entries(WORKFLOWS)}, EXPECTED_WORKFLOWS)

    def test_signal_pipeline_order_is_declared_in_workflow_overview(self):
        text = (STAGES / "CONTEXT.md").read_text()
        pipeline = section(text, "## Pipeline")
        routes = re.findall(r"`([0-9]+-[a-z-]+)/CONTEXT.md`", pipeline)
        self.assertEqual(routes, list(STAGE_ORDER))

    def test_event_pipeline_order_and_conditional_coordinator_loading(self):
        text = (EVENT_WORKFLOW / "CONTEXT.md").read_text()
        routes = re.findall(r"`([0-9]+-[a-z-]+)/CONTEXT.md`", section(text, "## Pipeline"))
        self.assertEqual(routes, list(EVENT_STAGE_ORDER))
        self.assertIn("Only the selected stage when entered", section(text, "## Inputs"))
        self.assertIn("Never preload the union of stage Inputs", section(text, "## Inputs"))
        self.assertIn("Do not load Sequence Plan, Launch", section(text, "## Process"))
        close = section(text, "## Inputs")
        self.assertIn('"Handoff and close" only when closing early', close)
        self.assertNotIn('"Readback"', close)

    def test_launch_consumes_same_thread_exact_approval_and_narrows_before_all_apollo_calls(self):
        launch = (EVENT_WORKFLOW / "03-launch/CONTEXT.md").read_text()
        plan = (EVENT_WORKFLOW / "02-sequence-plan/CONTEXT.md").read_text()
        self.assertTrue(section(launch, "## Checkpoints").strip().startswith("None. "))
        self.assertIn("exact existing E approval in this same run thread", section(launch, "## Checkpoints"))
        self.assertIn("Exact E proposal and Operator's matching native approval in this same Prospecting run thread", section(launch, "## Inputs"))
        process = section(launch, "## Process")
        self.assertLess(process.index("Verify the exact proposal's same-thread native E approval"), process.index("Fresh-read ownership"))
        self.assertLess(process.index("Intersect the helper-eligible set with the approved snapshot"), process.index("skip every Apollo call"))
        self.assertLess(process.index("skip every Apollo call"), process.index("Otherwise create or reuse only approved contacts"))
        self.assertIn("Missing, cross-thread or invalid approval stops without writes", process)
        self.assertIn("require a revised exact proposal", process)
        self.assertIn("without re-approval or additions, replacements", process)
        self.assertIn("matching native approval message", section(plan, "## Process"))
        self.assertIn("A matching label from another thread, forwarded approval or past campaign does not qualify", plan)
        self.assertFalse((EVENT_WORKFLOW / "02-sequence-plan/references").exists())
        self.assertIn("Missing or invalid preparation stops and returns its gap to the coordinator", plan)

    def test_every_qualified_signal_has_a_fenced_bundle_for_matts_choice(self):
        buying = (STAGES / "01-research/references/buying-signals.md").read_text()
        intake = (STAGES / "02-outreach/references/execution.md").read_text()
        contract = (STAGES / "02-outreach/CONTEXT.md").read_text()
        self.assertIn("separate fenced json block for every qualified signal", buying)
        self.assertIn("not only the recommended signal", buying)
        self.assertIn("even when its item carries a fit objection", buying)
        self.assertIn("Label each bundle with its report signal number", buying)
        self.assertIn("fenced JSON bundle for the signal Operator chooses", intake)
        self.assertIn("If the choice is unclear, ask before drafting", intake)
        self.assertIn("same-thread fenced bundle for the signal Operator chooses", contract)
        self.assertIn("No bundle, no draft", intake)
        self.assertIn("policy.prospecting.outreach.bundle_checked_max_age_hours", intake)
        self.assertEqual(self.pol["prospecting"]["outreach"]["bundle_checked_max_age_hours"], 24)

    def test_stage_folder_supports_contract_references_and_tools(self):
        for f in self.files:
            entries = {p.name for p in layout_entries(f.parent)}
            self.assertIn("CONTEXT.md", entries, f.parent.name)
            if "references" in entries:
                self.assertTrue(list((f.parent / "references").glob("*.md")))
            else:
                self.assertTrue(f.parent.parent == EVENT_WORKFLOW)
            self.assertLessEqual(entries, {"CONTEXT.md", "scripts", "references"}, f"{f.parent.name}: {sorted(entries)}")

    def test_title_matches_stage_folder(self):
        for f in self.files:
            titles = {"01-research": "Research", "02-outreach": "Outreach", "03-followup": "Follow-up",
                      "01-list-prep": "List Prep", "02-sequence-plan": "Sequence Plan", "03-launch": "Launch"}
            title = f"# {titles[f.parent.name]}"
            self.assertEqual(f.read_text().split("---\n", 2)[2].strip().splitlines()[0], title, str(f))

    def test_contract_sections_present(self):
        for f in self.files:
            text = f.read_text()
            for heading in HEADINGS:
                self.assertIn(f"\n{heading}\n", text, f"{f.parent.name} lacks {heading}")
            self.assertLessEqual(set(re.findall(r"^## .+$", text, re.M)), ALLOWED_HEADINGS)
            self.assertIn("| Source | File/Location | Section/Scope | Why |", section(text, "## Inputs"))
            self.assertIn("| Artifact | Location | Format |", section(text, "## Outputs"))

    def test_contracts_load_their_stage_reference(self):
        for ref in WORKFLOWS.rglob("references/*.md"):
            consumers = [contract for contract in [*self.files, EVENT_WORKFLOW / "CONTEXT.md"]
                         if owning_workflow(contract.parent) == owning_workflow(ref.parent)]
            if ref.parent.parent.name in EXPECTED_STAGES:
                consumers = [ref.parent.parent / "CONTEXT.md"]
            self.assertTrue(any(reference_is_loaded(contract, ref) for contract in consumers), str(ref))

    def test_shared_reference_coverage_requires_inputs_exact_headings_and_same_workflow(self):
        with tempfile.TemporaryDirectory() as folder:
            workflow = Path(folder) / "workspaces/prospecting/workflows/group"
            stage = workflow / "01-stage"
            stage.mkdir(parents=True)
            (workflow / "references").mkdir()
            reference = workflow / "references/shared.md"
            reference.write_text("# Shared\n\n## One\nEvidence.\n\n## Two\nMore evidence.\n")
            contract = stage / "CONTEXT.md"
            contract.touch()
            route = "../references/shared.md"
            header = "## Inputs\n\n| Source | File/Location | Section/Scope | Why |\n|---|---|---|---|\n"
            valid = header + f'| Reference | `{route}` | "One", "Two" | Evidence |\n'
            self.assertTrue(reference_is_loaded(contract, reference, valid))
            for scope in ("Full file", "", '"Missing"', '"One", "Missing"'):
                text = header + f'| Reference | `{route}` | {scope} | Evidence |\n'
                self.assertFalse(reference_is_loaded(contract, reference, text))
            for section_name in ("Process", "Audit", "Outputs"):
                text = header + f'\n## {section_name}\n`{route}` "One"\n'
                self.assertFalse(reference_is_loaded(contract, reference, text))
            self.assertFalse(reference_is_loaded(contract, reference, header + f'<!-- `{route}` "One" -->'))
            absolute = valid.replace(route, str(reference))
            self.assertTrue(reference_is_loaded(contract, reference, absolute))
            with patch("test_skill_contracts.ROOT", Path(folder)):
                repo_relative = valid.replace(route, reference.relative_to(folder).as_posix())
                self.assertTrue(reference_is_loaded(contract, reference, repo_relative))
            self.assertFalse(reference_is_loaded(contract, workflow / "references/missing.md", valid))
            outside = Path(folder) / "workspaces/prospecting/workflows/other/CONTEXT.md"
            self.assertFalse(reference_is_loaded(outside, reference, absolute))

    def test_coordinator_shared_reference_needs_exact_headings_but_standalone_keeps_private_scopes(self):
        with tempfile.TemporaryDirectory() as folder:
            workflow = Path(folder) / "workspaces/prospecting/workflows/group"
            (workflow / "references").mkdir(parents=True)
            reference = workflow / "references/shared.md"
            reference.write_text("# Shared\n\n## One\nEvidence.\n")
            contract = workflow / "CONTEXT.md"
            header = "## Inputs\n\n| Source | File/Location | Section/Scope | Why |\n|---|---|---|---|\n"
            private = header + '| Reference | `references/shared.md` | Full file | Evidence |\n'
            self.assertTrue(reference_is_loaded(contract, reference, private))
            stage = workflow / "01-stage"
            stage.mkdir()
            (stage / "CONTEXT.md").touch()
            for scope in ("Full file", "", '"Missing"', '"One", "Missing"'):
                with self.subTest(scope=scope):
                    text = header + f'| Reference | `references/shared.md` | {scope} | Evidence |\n'
                    self.assertFalse(reference_is_loaded(contract, reference, text))
            valid = header + '| Reference | `references/shared.md` | "One" | Evidence |\n'
            self.assertTrue(reference_is_loaded(contract, reference, valid))
            self.assertTrue(reference_is_loaded(contract, reference, valid.replace("references/shared.md", str(reference))))
            with patch("test_skill_contracts.ROOT", Path(folder)):
                self.assertTrue(reference_is_loaded(contract, reference, valid.replace("references/shared.md", reference.relative_to(folder).as_posix())))

    def test_policy_keys_resolve(self):
        missing = []
        for f in self.sources:
            for dotted in sorted(set(POLICY_REF.findall(f.read_text()))):
                if not resolve(self.pol, dotted):
                    missing.append(f"{f.parent.name}: policy.{dotted}")
        self.assertEqual(missing, [], f"stage contract names policy keys absent from policy.yaml: {missing}")

    def test_explicit_repo_paths_exist(self):
        missing = []
        for f in self.sources:
            for p in sorted(set(REPO_PATH.findall(f.read_text()))):
                if not (ROOT / p).exists():
                    missing.append(f"{f.parent.name}: {p}")
        self.assertEqual(missing, [], f"stage contract names files that do not exist: {missing}")

    def test_named_scripts_exist(self):
        missing = []
        for f in self.sources:
            folders = (CORE / "scripts", ROOT / "workspaces/prospecting/scripts", owning_workflow(f.parent) / "scripts",
                       f.parent / "scripts" if f.name == "CONTEXT.md" else f.parent.parent / "scripts")
            present = {p.name for folder in folders for p in folder.glob("*") if p.is_file()}
            for s in sorted(set(SCRIPT_NAME.findall(f.read_text()))):
                if s not in present:
                    missing.append(f"{f.parent.name}: {s}")
        self.assertEqual(missing, [], f"stage contract names scripts absent from its workflow, workspace or core scripts/: {missing}")

    def test_agents_routes_to_every_stage_contract(self):
        agents = (ROOT / "AGENTS.md").read_text()
        for f in self.files:
            rel = f.relative_to(ROOT).as_posix()
            if f in EVENT_STAGE_PATHS:
                self.assertIn(f"`{f.parent.name}/CONTEXT.md`", (EVENT_WORKFLOW / "CONTEXT.md").read_text())
                rel = (EVENT_WORKFLOW / "CONTEXT.md").relative_to(ROOT).as_posix()
                skill = "event-sequence"
            else:
                skill = next(name for name, path in SKILL_PATHS.items() if path == f.parent)
            self.assertIn(f"`{rel}`", agents, f"AGENTS.md does not route to {rel}")
            self.assertIn(f"`{skill}`", agents)

    def test_named_skills_are_routed(self):
        """Every sibling skill a stage contract hands off to appears in the AGENTS.md route table."""
        agents = (ROOT / "AGENTS.md").read_text()
        unrouted = []
        for f in self.sources:
            for s in sorted(set(SKILL_NAME.findall(f.read_text()))):
                if f"`{s}`" not in agents:
                    unrouted.append(f"{f.parent.name}: {s}")
        self.assertEqual(unrouted, [], f"stage contract hands off to skills AGENTS.md does not route: {unrouted}")

    def test_handoffs_point_forward(self):
        """Signal handoffs follow the order declared in the workspace pipeline."""
        for f in self.files:
            workflow = owning_workflow(f.parent)
            order = STAGE_ORDER if workflow == SIGNAL_WORKFLOW else EVENT_STAGE_ORDER
            for target in re.findall(re.escape(workflow.name) + r"/([0-9]+-[a-z-]+)/", section(f.read_text(), "## Outputs")):
                self.assertGreater(order.index(target), order.index(f.parent.name),
                                   f"{f.parent.name} hands off backward to {target}")


    def test_context_and_reference_size_limits(self):
        for f in ROOT.rglob("CONTEXT.md"):
            self.assertLessEqual(len(f.read_text().splitlines()), 80, str(f))
        for f in [*WORKFLOWS.rglob("references/*.md"), *CORE.glob("*.md")]:
            self.assertLessEqual(len(f.read_text().splitlines()), 200, str(f))

    def test_checkpoints_reference_real_steps_and_outreach_has_audit(self):
        for f in self.files:
            text = f.read_text()
            steps = set(re.findall(r"^(\d+)\. ", section(text, "## Process"), re.M))
            if "## Checkpoints" in text:
                for n in re.findall(r"^\| (\d+) \|", section(text, "## Checkpoints"), re.M):
                    self.assertIn(n, steps, str(f))
            if f.parent.name == "02-outreach":
                self.assertIn("## Checkpoints", text)
                self.assertIn("| Check | Pass Condition |", section(text, "## Audit"))
                self.assertIn("Run the Audit", section(text, "## Process"))

    def test_markdown_fences_do_not_hide_sections(self):
        for f in [*self.sources, *CORE.glob("*.md")]:
            fence = None
            for n, line in enumerate(f.read_text().splitlines(), 1):
                opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
                if fence:
                    closing = re.fullmatch(r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line)
                    if closing:
                        fence = None
                elif opening:
                    fence = opening.group(1)
            self.assertIsNone(fence, f"{f}: unclosed code fence")


if __name__ == "__main__":
    unittest.main()
