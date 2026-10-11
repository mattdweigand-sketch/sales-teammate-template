from pathlib import Path
import unittest
from test_skill_contracts import CONTRACT_PATHS, SKILL_BRANCHES, SIGNAL_WORKFLOW

ROOT = Path(__file__).resolve().parents[2]


class ProspectingBranches(unittest.TestCase):
    def test_research_aliases_have_one_contract_and_explicit_branch(self):
        research = CONTRACT_PATHS["signal-scan"]
        self.assertEqual(research, CONTRACT_PATHS["signal-user-scan"])
        self.assertEqual(SKILL_BRANCHES, {"signal-scan": "Buying signals", "signal-user-scan": "Adoption"})
        text = research.read_text()
        self.assertIn("Select the branch before loading branch-specific Inputs", text)
        for name, branch in SKILL_BRANCHES.items():
            self.assertIn(name, text)
            self.assertIn(branch, text)
        inputs = text.split("## Inputs\n", 1)[1].split("## Process\n", 1)[0]
        for row in inputs.splitlines():
            if ".sql`" in row or "Snowflake" in row:
                self.assertTrue(row.startswith("| Adoption"), row)
        self.assertIn("No warehouse in Buying signals", text)

    def test_aliases_do_not_create_duplicate_contracts(self):
        groups = {}
        for name, path in CONTRACT_PATHS.items():
            groups.setdefault(path, []).append(name)
        shared = [set(names) for names in groups.values() if len(names) > 1]
        self.assertEqual(shared, [{"signal-scan", "signal-user-scan"}])
        contexts = set((ROOT / "workspaces/prospecting/workflows").rglob("CONTEXT.md"))
        self.assertEqual(contexts, {SIGNAL_WORKFLOW / "CONTEXT.md", CONTRACT_PATHS["signal-scan"],
                                   CONTRACT_PATHS["signal-outreach"], CONTRACT_PATHS["signal-followup"],
                                   CONTRACT_PATHS["event-sequence"],
                                   *(CONTRACT_PATHS["event-sequence"].parent / stage / "CONTEXT.md"
                                     for stage in ("01-list-prep", "02-sequence-plan", "03-launch"))})
        self.assertEqual(len(list(CONTRACT_PATHS["event-sequence"].parent.glob("*/CONTEXT.md"))), 3)
        self.assertNotEqual(CONTRACT_PATHS["event-sequence"], CONTRACT_PATHS["signal-scan"])

    def test_buying_signals_batch_routes_by_named_sections(self):
        text = (CONTRACT_PATHS["signal-scan"].parent / "references/buying-signals.md").read_text()
        batch = text.split("## Batch mode\n", 1)[1].split("\n## Boundaries", 1)[0]
        for heading in ("Account and engagement", "Aliases", "Search", "Qualification", "Verdict"):
            self.assertIn(f'"{heading}"', batch)
            self.assertIn(f"## {heading}\n", text)
        self.assertNotRegex(batch, r"\bstep[s]? \d")
        self.assertIn("Do not load Adoption inputs", batch)
        self.assertIn("Never pool", batch)
        self.assertIn("policy.prospecting.scan.max_signals_per_account", batch)
