from pathlib import Path
import sys
import unittest
import yaml
from test_skill_contracts import SKILL_PATHS
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workspaces/prospecting/scripts"))
import prospect_common


class ProspectingMigration(unittest.TestCase):
    def test_four_explicit_routes_and_pipeline_ownership(self):
        routes = {name: path for name, path in SKILL_PATHS.items() if name.startswith("signal-")}
        self.assertEqual(len(routes), 4)
        for path in routes.values():
            text = (path / "CONTEXT.md").read_text()
            self.assertIn("Any open", text)
            self.assertIn("Pipeline", text)
            self.assertIn("rules#approval", text)
            self.assertIn("rules#write_protocol", text)

    def test_research_checks_current_named_account_before_either_branch_fetches(self):
        contract = (SKILL_PATHS["signal-scan"] / "CONTEXT.md").read_text()
        process = contract.split("## Process\n", 1)[1].split("## Checkpoints", 1)[0]
        ownership = process.index("2. Resolve one current Account owned by")
        self.assertLess(ownership, process.index("4. Buying signals fetches sources"))
        self.assertLess(ownership, process.index("6. Adoption"))
        self.assertIn("Missing or ambiguous identity stops", process)
        reference = (SKILL_PATHS["signal-scan"] / "references/buying-signals.md").read_text()
        self.assertIn("Only route scan continues", reference)
        self.assertIn("All other routes and unresolved identities stop before public research", reference)

    def test_approval_precedes_write_and_fresh_ownership_read(self):
        for name, path in SKILL_PATHS.items():
            if not name.startswith("signal-"):
                continue
            text = (path / "CONTEXT.md").read_text()
            metadata = yaml.safe_load(text.split("---\n", 2)[1])
            if metadata["writes"] == "nothing":
                continue
            process = text.split("## Process\n", 1)[1].split("## Checkpoints", 1)[0]
            checkpoints = text.split("## Checkpoints\n", 1)[1].split("## Audit", 1)[0]
            step = int([row for row in checkpoints.splitlines() if row.startswith("| ")][-1].split("|")[1].strip())
            self.assertIn(f"{step + 1}. After approval ", process)
            self.assertIn("Recheck owner, open Opportunities and duplicates", process)

    def test_nested_policy_matches_verbatim_live_fixture(self):
        live = yaml.safe_load((ROOT / "_core/tests/prospecting-fixtures/policy.yaml").read_text())
        current = prospect_common.load_policy()
        current.pop("event")
        self.assertEqual(current["approval"]["never"],
                         ["send email outside rules#event_sequence", "create Opportunity", "change deal stage or amount"])
        current["approval"]["never"] = live["approval"]["never"]
        self.assertEqual(current, live)

    def test_tools_registered_at_actual_paths(self):
        policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        tools = {name: path for name, path in policy["tooling"]["scripts"].items() if name.startswith("prospect_")}
        self.assertEqual(len(tools), 9)
        for path in tools.values():
            self.assertTrue((ROOT / path).is_file(), path)

    def test_routes_name_specific_outputs_and_review_boundaries(self):
        text = (ROOT / "workspaces/prospecting/CONTEXT.md").read_text()
        routing, pipeline = text.split("## Task routing\n", 1)[1].split("## Pipeline\n", 1)
        pipeline = pipeline.split("\n## ", 1)[0]
        routes = [row.split("|")[1:-1] for row in routing.splitlines() if row.startswith("| ")][1:]
        self.assertEqual(len(routes), 5)
        self.assertEqual(len({row[2].strip() for row in routes}), 5)
        self.assertEqual(len({row[3].strip() for row in routes}), 5)
        self.assertIn("| Stage | Trigger | Output | Human check | Contract route |", pipeline)
        stages = [row.split("|")[1:-1] for row in pipeline.splitlines() if row.startswith("| ")][1:]
        self.assertEqual(len(stages), 3)
        self.assertTrue(all(len(row) == 5 and all(cell.strip() for cell in row) for row in stages))
        signal_routes = [row for row in routes if row[1].strip() != "`workflows/event-sequence/CONTEXT.md`"]
        self.assertEqual({row[1].strip().split(",")[0] for row in signal_routes}, {row[4].strip() for row in stages})

    def test_inputs_are_specific_and_repo_contracts_have_no_draft_state(self):
        stock = ("Canonical content and rules", "Required executable checks or query", "Current run evidence",
                 "Execution details, report format and boundaries")
        for name, path in SKILL_PATHS.items():
            if not name.startswith("signal-"):
                continue
            text = (path / "CONTEXT.md").read_text()
            inputs = text.split("## Inputs\n", 1)[1].split("## Process\n", 1)[0]
            for phrase in stock:
                self.assertNotIn(phrase, inputs)
            self.assertNotIn("This package is a draft", text)
            self.assertNotIn("TODO", text)
        agents = (ROOT / "workspaces/prospecting/AGENTS.md").read_text()
        self.assertNotIn("TODO", agents)
        self.assertNotIn("Draft only", agents)
