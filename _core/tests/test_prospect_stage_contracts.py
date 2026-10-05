"""Stage contracts and their loaded references name only things that exist.

A saved signal skill points to `workspaces/prospecting/workflows/<name>/CONTEXT.md`. This test resolves what each stage
contract references: every `policy.<dotted>` key against policy.yaml, each explicit repo path against the
checkout, and every named script against the stage, workspace and core scripts/. A contract that
names a key or file that is not there fails here instead of at run time.
"""
import re
import unittest
from pathlib import Path

import yaml
from test_skill_contracts import SKILL_PATHS, layout_entries

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
WORKFLOWS = ROOT / "workspaces/prospecting/workflows"
STAGES = WORKFLOWS
STAGE_ORDER = ("research", "outreach", "followup")
EXPECTED_STAGES = set(STAGE_ORDER)
EXPECTED_WORKFLOWS = EXPECTED_STAGES | {"event-sequence"}
HEADINGS = ("## Inputs", "## Process", "## Checkpoints", "## Audit", "## Outputs")
ALLOWED_HEADINGS = set(HEADINGS) | {"## Checkpoints", "## Audit"}


def stage_contracts():
    """Stage contracts only; the blank starter in _core/templates is not a stage."""
    return sorted(WORKFLOWS.rglob("CONTEXT.md"))


def stage_sources():
    return stage_contracts() + sorted(WORKFLOWS.rglob("references/*.md"))


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
        self.assertEqual({f.parent.name for f in self.files}, EXPECTED_WORKFLOWS)
        self.assertEqual({p.name for p in layout_entries(WORKFLOWS)}, EXPECTED_WORKFLOWS)

    def test_signal_pipeline_order_is_declared_in_workspace_context(self):
        text = (ROOT / "workspaces/prospecting/CONTEXT.md").read_text()
        pipeline = section(text, "## Pipeline")
        routes = re.findall(r"workflows/([a-z-]+)/CONTEXT.md", pipeline)
        self.assertEqual(routes, list(STAGE_ORDER))

    def test_every_qualified_signal_has_a_fenced_bundle_for_operators_choice(self):
        buying = (WORKFLOWS / "research/references/buying-signals.md").read_text()
        intake = (WORKFLOWS / "outreach/references/execution.md").read_text()
        contract = (WORKFLOWS / "outreach/CONTEXT.md").read_text()
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
            self.assertIn("references", entries, f.parent.name)
            self.assertTrue(list((f.parent / "references").glob("*.md")))
            self.assertLessEqual(entries, {"CONTEXT.md", "scripts", "references"}, f"{f.parent.name}: {sorted(entries)}")

    def test_title_matches_stage_folder(self):
        for f in self.files:
            titles = {"research": "Research", "outreach": "Outreach", "followup": "Follow-up", "event-sequence": "Event Sequence"}
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
        for f in self.files:
            for ref in (f.parent / "references").glob("*.md"):
                scope = f.parent if f.parent.name == "event-sequence" else ROOT
                self.assertIn(f"`{ref.relative_to(scope).as_posix()}`", section(f.read_text(), "## Inputs"))

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
            folders = (CORE / "scripts", ROOT / "workspaces/prospecting/scripts",
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
            self.assertIn(f"`{rel}`", agents, f"AGENTS.md does not route to {rel}")
            skill = next(name for name, path in SKILL_PATHS.items() if path == f.parent)
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
            if f.parent.name not in EXPECTED_STAGES:
                continue
            for target in re.findall(r"workflows/([a-z-]+)/", section(f.read_text(), "## Outputs")):
                self.assertGreater(STAGE_ORDER.index(target), STAGE_ORDER.index(f.parent.name),
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
            if f.parent.name == "outreach":
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
