"""Workflow contracts follow the ICM stage-contract shape and stay routers.

- every CONTEXT.md is at most 80 lines and every reference at most 200
- in every markdown file, prose lines are at most 200 characters and table rows at most 300; code fences are exempt
- every workflow contract has Inputs, Process, Checkpoints, Audit, and Outputs in that order
- the Inputs, Checkpoints, Audit, and Outputs tables use the builder's exact columns
- Process is numbered from 1 with no gaps, and each checkpoint names a real step
- every `references/...` path a contract names exists, and every reference file is named by its contract
- every quoted section after a reference path names a real heading in that file
- frontmatter `reads` and `writes` agree with the Inputs and Outputs tables
- workspace task routes cover every contract and authoring guidance has one home
- approval checkpoints and conditional record or criteria handoffs stay explicit
- the template has the same sections and columns
- the active/cold definition and the pilot handoff each have one anchor in _core/rules.md, cited by the workflows that depend on them
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from test_skill_contracts import SKILLS, CONTRACT_PATHS, OVERVIEW_PATHS, SIGNAL_WORKFLOW, EVENT_WORKFLOW, EVENT_STAGE_ORDER, COORDINATOR_PATHS, skill_dirs, owning_workflow, reference_is_loaded

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
WORKSPACES = ROOT / "workspaces"
TEMPLATE = CORE / "templates" / "workflow-context-template.md"

CONTEXT_MAX_LINES = 80
REFERENCE_MAX_LINES = 200
PROSE_MAX_CHARS = 200
TABLE_MAX_CHARS = 300
SECTION_ORDER = ["Inputs", "Process", "Checkpoints", "Audit", "Outputs"]
REQUIRED_SECTIONS = set(SECTION_ORDER)
TABLE_HEADERS = {
    "Inputs": "| Source | File/Location | Section/Scope | Why |",
    "Checkpoints": "| After Step | Agent Presents | Human Decides |",
    "Audit": "| Check | Pass Condition |",
    "Outputs": "| Artifact | Location | Format |",
}
# `path` "Heading" or `path` "Heading one", "Heading two"
SCOPED_REF = re.compile(r"`((?:workspaces/[^`]+/)?references/[a-z0-9-]+\.md|_core/scripts/interfaces\.md|_core/slack-evidence\.md|_core/CONVENTIONS\.md)`((?:[^`\n|]*?\"[^\"]+\")*)")
QUOTED = re.compile(r"\"([^\"]+)\"")


def workflow_dirs():
    return skill_dirs()


def workflow_path(name):
    return CONTRACT_PATHS[name].parent


def context_files():
    files = [ROOT / "CONTEXT.md", CORE / "CONTEXT.md", CORE / "scripts" / "CONTEXT.md"]
    return files + sorted(WORKSPACES.glob("*/CONTEXT.md")) + sorted(OVERVIEW_PATHS) + [d / "CONTEXT.md" for d in workflow_dirs()]


def reference_files():
    files = sorted(WORKSPACES.rglob("references/*.md"))
    files += [CORE / "CONVENTIONS.md", CORE / "rules.md", CORE / "slack-evidence.md", CORE / "scripts" / "interfaces.md", TEMPLATE]
    return files


def body(text):
    return text.split("---\n", 2)[2] if text.startswith("---\n") else text


def sections(text):
    """Map each `## ` heading to its body lines, in order."""
    out, name = {}, None
    for line in body(text).splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            out[name] = []
        elif name:
            out[name].append(line)
    return out


def table_rows(lines):
    rows = [l for l in lines if l.startswith("|")]
    return rows[0] if rows else None, [[c.strip() for c in r.strip("|").split("|")] for r in rows[2:]]


def headings(path):
    return {l.lstrip("#").strip() for l in path.read_text().splitlines() if l.startswith("#")}


def resolve_ref(contract_dir, ref):
    return ROOT / ref if ref.startswith(("workspaces/", "_core/")) else contract_dir / ref


class ContractShape(unittest.TestCase):
    def test_line_limits(self):
        over = [f"{f.relative_to(ROOT)}: {n}" for f in context_files()
                if (n := len(f.read_text().splitlines())) > CONTEXT_MAX_LINES]
        over += [f"{f.relative_to(ROOT)}: {n}" for f in reference_files()
                 if (n := len(f.read_text().splitlines())) > REFERENCE_MAX_LINES]
        self.assertEqual(over, [])

    def test_markdown_lines_are_readable(self):
        """Prose lines at most PROSE_MAX_CHARS, table rows at most TABLE_MAX_CHARS, code fences exempt."""
        files = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CONTEXT.md"] + sorted(CORE.rglob("*.md")) + sorted(WORKSPACES.rglob("*.md"))
        long = []
        for f in files:
            fence = False
            for i, line in enumerate(f.read_text().splitlines(), 1):
                if line.lstrip().startswith("```"):
                    fence = not fence
                    continue
                limit = TABLE_MAX_CHARS if line.lstrip().startswith("|") else PROSE_MAX_CHARS
                if not fence and len(line) > limit:
                    long.append(f"{f.relative_to(ROOT)}:{i} ({len(line)})")
        self.assertEqual(long, [])

    def check_sections(self, path):
        secs = sections(path.read_text())
        names = list(secs)
        order = ["Pipeline", *SECTION_ORDER] if path in COORDINATOR_PATHS else SECTION_ORDER
        self.assertEqual(names, [s for s in order if s in secs], f"{path.relative_to(ROOT)}: {names}")
        if path in COORDINATOR_PATHS:
            self.assertEqual(table_rows(secs["Pipeline"])[0], "| Stage | Trigger | Output | Human check | Contract route |")
        self.assertTrue(REQUIRED_SECTIONS <= set(names), f"{path.relative_to(ROOT)}: {names}")
        for name, header in TABLE_HEADERS.items():
            if name in secs:
                if name == "Checkpoints" and "\n".join(secs[name]).strip().startswith("None."):
                    self.assertRegex("\n".join(secs[name]).strip(), r"\ANone\. \S[^\n]*\Z",
                                     f"{path.relative_to(ROOT)} Checkpoints needs None. plus a reason")
                    continue
                got, rows = table_rows(secs[name])
                self.assertEqual(got, header, f"{path.relative_to(ROOT)} {name}")
                self.assertTrue(rows, f"{path.relative_to(ROOT)} {name} has no rows")
                self.assertTrue(all(len(r) == header.count("|") - 1 and all(r) for r in rows),
                                f"{path.relative_to(ROOT)} {name} has an empty or malformed row")
        return secs

    def test_workflow_contract_sections(self):
        for d in workflow_dirs():
            self.check_sections(d / "CONTEXT.md")

    def test_none_with_reason_is_valid_for_any_contract_shape(self):
        for directory in workflow_dirs():
            path = directory / "CONTEXT.md"
            text = re.sub(r"## Checkpoints\n.*?(?=## Audit)",
                          "## Checkpoints\n\nNone. This workflow runs without an approval pause.\n\n",
                          path.read_text(), flags=re.S)
            with self.subTest(workflow=directory.name), patch.object(Path, "read_text", return_value=text):
                self.check_sections(path)

    def test_none_without_reason_or_mixed_with_table_is_invalid(self):
        path = workflow_path("sales-call-prep") / "CONTEXT.md"
        original = path.read_text()
        for body in ("None.", "None.   ", "None.\nNo approval pause.",
                     "None. No approval pause.\n| After Step | Agent Presents | Human Decides |"):
            text = re.sub(r"## Checkpoints\n.*?(?=## Audit)", f"## Checkpoints\n\n{body}\n\n",
                          original, flags=re.S)
            with self.subTest(body=body), patch.object(Path, "read_text", return_value=text):
                with self.assertRaises(AssertionError):
                    self.check_sections(path)

    def test_missing_checkpoints_section_is_invalid(self):
        path = workflow_path("sales-call-prep") / "CONTEXT.md"
        text = re.sub(r"## Checkpoints\n.*?(?=## Audit)", "", path.read_text(), flags=re.S)
        with patch.object(Path, "read_text", return_value=text), self.assertRaises(AssertionError):
            self.check_sections(path)

    def test_template_matches_contract_shape(self):
        secs = self.check_sections(TEMPLATE)
        self.assertIn("Checkpoints", secs)

    def test_process_numbering_and_checkpoint_steps(self):
        for d in workflow_dirs():
            secs = sections((d / "CONTEXT.md").read_text())
            steps = [int(m.group(1)) for l in secs["Process"] if (m := re.match(r"^(\d+)\. ", l))]
            self.assertEqual(steps, list(range(1, len(steps) + 1)), d.name)
            if "Checkpoints" in secs:
                _, rows = table_rows(secs["Checkpoints"])
                for r in rows:
                    self.assertIn(int(r[0]), steps, f"{d.name} checkpoint after step {r[0]}")

    def test_frontmatter_agrees_with_tables(self):
        for d in workflow_dirs():
            text = (d / "CONTEXT.md").read_text()
            fm = yaml.safe_load(text.split("---\n", 2)[1])
            secs = sections(text)
            _, inputs = table_rows(secs["Inputs"])
            _, outputs = table_rows(secs["Outputs"])
            has_refs = any(r[0] == "Reference" for r in inputs)
            self.assertEqual("references/" in fm["reads"], has_refs, d.name)
            approved = [r for r in outputs if "after approval" in r[1]]
            if d.name == "system-review":
                self.assertEqual(fm["writes"], "Teammate improvement tasks and evidence comments only")
                self.assertEqual(approved, [], d.name)
                records = [row for row in outputs if row[0] == "Improvement records"]
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0][1], "Teammate project tasks")
                self.assertIn("Open, unassigned tasks labeled improvement", records[0][2])
                self.assertIn("Existing matches get new evidence comments only", records[0][2])
            elif str(fm["writes"]).startswith("nothing"):
                self.assertEqual(approved, [], d.name)
            else:
                self.assertTrue(approved, f"{d.name}: writes on approval but no approved output row")


class ScopedReferences(unittest.TestCase):
    def test_process_section_reads_are_declared_in_inputs(self):
        missing = []
        for directory in workflow_dirs():
            scoped = sections((directory / "CONTEXT.md").read_text())
            _, inputs = table_rows(scoped["Inputs"])
            declared = {}
            for row in inputs:
                for ref in re.findall(r"`([^`]+\.md)`", row[1]):
                    declared.setdefault(ref, []).append(row[2])
                    steps = re.fullmatch(r"The section named in each of steps (\d+) to (\d+)", row[2])
                    if steps:
                        # A bounded step route names its scope through those Process lines.
                        first, last = map(int, steps.groups())
                        for line in scoped["Process"]:
                            number = re.match(r"^(\d+)\. ", line)
                            if number and first <= int(number.group(1)) <= last:
                                for cited_ref, tail in SCOPED_REF.findall(line):
                                    if cited_ref == ref:
                                        declared[ref].append(tail)
            for ref, tail in SCOPED_REF.findall("\n".join(scoped["Process"])):
                scope = " ".join(declared.get(ref, []))
                if "full file" in scope.lower():
                    continue
                for heading in QUOTED.findall(tail):
                    if heading not in QUOTED.findall(scope):
                        missing.append(f'{directory.name}: {ref} "{heading}"')
        self.assertEqual(missing, [])

    def test_contract_reference_paths_and_sections_resolve(self):
        missing = []
        for d in workflow_dirs():
            text = (d / "CONTEXT.md").read_text()
            for ref in set(re.findall(r"`(references/[^`]+)`", text)):
                if not (d / ref).is_file():
                    missing.append(f"{d.name}: {ref}")
            _, inputs = table_rows(sections(text)["Inputs"])
            for r in inputs:
                refs = re.findall(r"`(references/[^`]+\.md)`", r[1])
                for ref in refs:
                    target = d / ref
                    if not target.is_file():
                        continue
                    for q in QUOTED.findall(r[2]):
                        if q not in headings(target):
                            missing.append(f"{d.name}: {ref} \"{q}\"")
        self.assertEqual(missing, [])

    def test_scoped_citations_name_real_headings(self):
        """`path` "Heading" anywhere in a contract or reference names a heading in that file."""
        missing = []
        files = context_files() + reference_files() + [ROOT / "AGENTS.md"] + sorted(WORKSPACES.glob("*/AGENTS.md"))
        for f in files:
            base = f.parent.parent if f.parent.name == "references" else f.parent
            for ref, tail in SCOPED_REF.findall(f.read_text()):
                target = resolve_ref(base, ref)
                if not target.is_file():
                    missing.append(f"{f.relative_to(ROOT)}: {ref}")
                    continue
                first = QUOTED.search(tail)
                if first and tail[:first.start()].strip(" ,;") == "" and first.group(1) not in headings(target):
                    missing.append(f"{f.relative_to(ROOT)}: {ref} \"{first.group(1)}\"")
        self.assertEqual(missing, [])

    def test_every_reference_is_routed_by_its_contract(self):
        orphans = []
        for ref in sorted(WORKSPACES.glob("*/workflows/**/references/*.md")):
            owner = owning_workflow(ref.parent)
            consumers = [directory / "CONTEXT.md" for directory in workflow_dirs() if owning_workflow(directory) == owner]
            if ref.parent.parent != owner:
                consumers = [ref.parent.parent / "CONTEXT.md"]
            if not any(reference_is_loaded(contract, ref) for contract in consumers):
                orphans.append(str(ref.relative_to(ROOT)))
        self.assertEqual(orphans, [])


class WorkspaceNavigation(unittest.TestCase):
    def test_call_prep_is_owned_by_pipeline_without_stale_paths(self):
        workflow = WORKSPACES / "pipeline" / "workflows" / "sales-call-prep"
        old_workflow = WORKSPACES / "deal-coaching" / "workflows" / "sales-call-prep"
        self.assertEqual(SKILLS["sales-call-prep"], "pipeline")
        self.assertTrue((workflow / "CONTEXT.md").is_file())
        self.assertEqual({str(path.relative_to(workflow)) for path in workflow.rglob("*") if path.is_file()},
                         {"CONTEXT.md", "references/brief-formats.md", "references/collect.md", "references/daily.md"})
        self.assertFalse(old_workflow.exists())
        route = f'| `sales-call-prep` | `{(workflow / "CONTEXT.md").relative_to(ROOT)}` |'
        self.assertIn(route, (ROOT / "AGENTS.md").read_text())
        pipeline_routes = "\n".join(sections((WORKSPACES / "pipeline" / "CONTEXT.md").read_text())["Task routing"])
        self.assertIn("Named external call or call window | `workflows/sales-call-prep/CONTEXT.md`", pipeline_routes)
        coaching_routes = "\n".join(sections((WORKSPACES / "deal-coaching" / "CONTEXT.md").read_text())["Task routing"])
        self.assertNotIn("sales-call-prep", coaching_routes)
        contract = (workflow / "CONTEXT.md").read_text()
        self.assertEqual(yaml.safe_load(contract.split("---\n", 2)[1])["writes"], "nothing")
        old_path = str(old_workflow.relative_to(ROOT))
        files = [ROOT / "AGENTS.md", ROOT / "CONTEXT.md"]
        for directory in (CORE, WORKSPACES):
            files.extend(sorted(directory.rglob("*.md")))
            files.extend(sorted(directory.rglob("*.py")))
        for path in files:
            self.assertNotIn(old_path, path.read_text(), str(path.relative_to(ROOT)))

    def test_task_routes_cover_each_contract(self):
        header, rows = table_rows(sections((ROOT / "CONTEXT.md").read_text())["Task routing"])
        self.assertEqual(header, "| Task or event | Workspace | Output and handoff |")
        self.assertTrue(all(len(row) == 3 and all(row) for row in rows))
        routes = [row[1].strip("`") for row in rows]
        self.assertEqual(sorted(routes), [str(p.relative_to(ROOT)) for p in sorted(WORKSPACES.glob("*/CONTEXT.md"))])
        contracts = []
        for route in routes:
            workspace = (ROOT / route).parent
            header, rows = table_rows(sections((ROOT / route).read_text())["Task routing"])
            self.assertEqual(header, "| Task or event | Contract | Output and handoff | Human check |")
            self.assertTrue(all(len(row) == 4 and all(row) for row in rows))
            owned = [workspace / row[1].strip("`") for row in rows]
            self.assertEqual(sorted(set(owned)), sorted(workspace.glob("workflows/*/CONTEXT.md")))
            if workspace.name == "prospecting":
                _, pipeline = table_rows(sections((SIGNAL_WORKFLOW / "CONTEXT.md").read_text())["Pipeline"])
                stages = [SIGNAL_WORKFLOW / row[4].strip("`") for row in pipeline]
                self.assertEqual(sorted(stages), sorted(SIGNAL_WORKFLOW.glob("*/CONTEXT.md")))
                owned = [contract for contract in owned if contract not in OVERVIEW_PATHS] + stages
                _, event_pipeline = table_rows(sections((EVENT_WORKFLOW / "CONTEXT.md").read_text())["Pipeline"])
                event_stages = [EVENT_WORKFLOW / row[4].strip("`") for row in event_pipeline]
                self.assertEqual(sorted(event_stages), sorted(EVENT_WORKFLOW.glob("*/CONTEXT.md")))
                owned.extend(event_stages)
            contracts.extend(owned)
        self.assertEqual(sorted(set(contracts)), sorted(d / "CONTEXT.md" for d in workflow_dirs()))

    def test_workspace_instructions_are_explicitly_reachable(self):
        agents = (ROOT / "AGENTS.md").read_text()
        for owner in set(SKILLS.values()):
            for entry in ("AGENTS.md", "CONTEXT.md"):
                self.assertIn(f"workspaces/{owner}/{entry}", agents)
            context = (WORKSPACES / owner / "CONTEXT.md").read_text()
            self.assertIn(f"workspaces/{owner}/AGENTS.md", context)
            workspace_agents = (WORKSPACES / owner / "AGENTS.md").read_text()
            self.assertIn(f"workspaces/{owner}/CONTEXT.md", workspace_agents)
            self.assertIn("_core/CONVENTIONS.md", workspace_agents)

    def test_authoring_guidance_has_one_home(self):
        conventions = CORE / "CONVENTIONS.md"
        authoring = {"Terms", "Folder ownership", "Adding a workflow", "Tests and maintenance", "Repo write boundaries"}
        self.assertTrue(authoring <= headings(conventions))
        for entry in (ROOT / "AGENTS.md", ROOT / "CONTEXT.md"):
            self.assertTrue(authoring.isdisjoint(headings(entry)), entry.name)
            self.assertIn("`_core/CONVENTIONS.md`", entry.read_text())
        self.assertIn("`CONVENTIONS.md`", (CORE / "CONTEXT.md").read_text())

    def test_side_effects_keep_human_checkpoints(self):
        for d in workflow_dirs():
            text = (d / "CONTEXT.md").read_text()
            fm = yaml.safe_load(text.split("---\n", 2)[1])
            if d.name == "system-review":
                self.assertEqual(fm["writes"], "Teammate improvement tasks and evidence comments only")
                checkpoints = "\n".join(sections(text)["Checkpoints"])
                self.assertIn("Improvement task recording needs no approval pause", checkpoints)
                self.assertIn("Repairs and policy decisions follow their owning workflow's approval rules", checkpoints)
                continue
            needs_checkpoint = not fm["writes"].startswith("nothing") or d.name in {"pilot-usage", "deal-coach"}
            if needs_checkpoint:
                if d == EVENT_WORKFLOW / "03-launch":
                    self.assertIn("None. Launch consumes Sequence Plan's exact existing E approval in this same run thread", text)
                    self.assertIn("Operator's matching native approval in this same Prospecting run thread", text)
                    self.assertIn("Missing, cross-thread or invalid approval stops without writes", text)
                    continue
                _, rows = table_rows(sections(text).get("Checkpoints", []))
                self.assertTrue(rows, f"{d.name} must expose its existing human review boundary")

    def test_record_and_criteria_handoffs_agree(self):
        def contract(name):
            text = (workflow_path(name) / "CONTEXT.md").read_text()
            return yaml.safe_load(text.split("---\n", 2)[1]), sections(text)

        pipeline, pipeline_sections = contract("pipeline-review")
        self.assertIn("forecast-weekly", pipeline["next"])
        self.assertIn("forecast-weekly", "\n".join(pipeline_sections["Outputs"]).lower())
        _, forecast_sections = contract("forecast-weekly")
        self.assertIn("pipeline-review", "\n".join(forecast_sections["Inputs"]))
        coach, coach_sections = contract("deal-coach")
        self.assertEqual(coach["writes"], "nothing")
        for term in ("criteria-refresh", "Operator approves", "Systems repo-maintenance", "PR"):
            self.assertIn(term, coach["next"])
        outputs = "\n".join(coach_sections["Outputs"])
        for term in ("Coach thread", "Systems repo-maintenance", "approval link", "canonical references"):
            self.assertIn(term, outputs)
        learning = (workflow_path("deal-coach") / "references" / "learning.md").read_text()
        for term in ("Operator approves", "Systems repo-maintenance", "PR", "canonical criteria"):
            self.assertIn(term, learning)

    def test_systems_writes_are_scoped_and_review_defers_repairs(self):
        for name in ("repo-maintenance", "agent-configuration"):
            text = (workflow_path(name) / "CONTEXT.md").read_text()
            fm = yaml.safe_load(text.split("---\n", 2)[1])
            self.assertIn("after approval", fm["writes"])
            self.assertNotIn("Salesforce", fm["writes"])
            _, checkpoints = table_rows(sections(text)["Checkpoints"])
            self.assertTrue(checkpoints)
            self.assertIn("Review boundaries", text)
        review = (workflow_path("system-review") / "CONTEXT.md").read_text()
        fm = yaml.safe_load(review.split("---\n", 2)[1])
        self.assertEqual(fm["writes"], "Teammate improvement tasks and evidence comments only")
        self.assertEqual(fm["cadence"], "Friday")
        for route in ("repo-maintenance", "agent-configuration"):
            self.assertIn(route, fm["next"])
        review_policy = yaml.safe_load((CORE / "policy.yaml").read_text())["system_review"]
        self.assertEqual(set(review_policy), {"schedule", "preapproval"})

    def test_domain_learning_routes_to_systems_without_changing_authority(self):
        for name in ("deal-coach", "forecast-weekly"):
            learning = (workflow_path(name) / "references" / "learning.md").read_text()
            self.assertIn("Operator approves", learning)
            self.assertIn("Systems repo-maintenance", learning)
            self.assertIn("workspaces/systems/workflows/repo-maintenance/CONTEXT.md", learning)
            self.assertIn("approval link", learning)
        conventions = (CORE / "CONVENTIONS.md").read_text()
        self.assertIn("Explicit task-specific holds override that standing rule", conventions)
        self.assertIn("wording changes in `_core/rules.md` and `_core/policy.yaml` first", conventions)

    def test_system_review_distinguishes_delivered_runs_from_failures(self):
        workflow = workflow_path("system-review")
        reference = sections((workflow / "references" / "review.md").read_text())
        drift = "\n".join(reference["Drift and failures"])
        for expected in ("still in progress at review time that started before the review day",
                         "check its output location", "For an existing thread, check the entry or turns after the run's start",
                         "For a new thread, check that session", "When matching output exists",
                         "classify the run as `delivered, receipt open`",
                         "Count these separately as a platform receipt issue, not a failure",
                         "When no output exists, classify the run as a failed run only when a native failure status or retrieved stopped-progress evidence establishes it",
                         "Otherwise it stays pending or unknown.", "Crossing midnight alone is not failure.",
                         "Unreadable output is not checked, and `delivered, receipt open` stays its own count."):
            self.assertIn(expected, drift)
        self.assertNotIn("classify the run as a failed run. Unreadable", drift)
        contract = sections((workflow / "CONTEXT.md").read_text())
        self.assertIn('"Drift and failures"', "\n".join(contract["Inputs"]))
        self.assertIn('"Drift and failures"', "\n".join(contract["Process"]))

    def test_system_review_counts_replies_and_checks_live_profiles(self):
        reference = sections((workflow_path("system-review") / "references" / "review.md").read_text())
        evidence = "\n".join(reference["Evidence and scorecard"])
        self.assertIn("Operator's replies per weekday by workflow and deal thread", evidence)
        self.assertIn("Approvals versus rejections, keeping skipped or edited proposals distinguishable", evidence)
        self.assertEqual(len([line for line in reference["Evidence and scorecard"] if line.startswith("- ")]), 7)
        drift = "\n".join(reference["Drift and failures"])
        for expected in ("Run `pplx tm orchestrator list` to read the five live Teammate profiles",
                         "Compare workflow paths, ownership, and write limits with the repo",
                         "Unreadable profiles are not checked"):
            self.assertIn(expected, drift)
        self.assertIn("Post a scorecard of seven lines or fewer", "\n".join(reference["Report and routing"]))

    def test_system_review_census_runs_only_on_typed_eval(self):
        workflow = workflow_path("system-review")
        review = sections((workflow / "references" / "review.md").read_text())
        outcomes = "\n".join(review["Proposal outcomes"])
        self.assertIn("The census and kind table below run only on a typed `eval` request.", outcomes)
        self.assertIn("Friday Review keeps failures, drift, repeated corrections, capture and backlog, and collects no census.", outcomes)
        self.assertIn("over the typed `eval` run's own complete four-week window ending at its run start", outcomes)
        self.assertIn("Prior Friday reviews are history links for dedupe, not the source of counts.", outcomes)
        self.assertIn("If verified coverage does not reach four weeks back, or proposal or reply reads are incomplete, label the observed window and counts partial.", outcomes)
        drift = "\n".join(review["Drift and failures"])
        self.assertIn("Propose it only from linked complete eligible evidence in a typed `eval` census. Otherwise label preapproval not checked.", drift)
        report = "\n".join(review["Report and routing"])
        self.assertIn("Use the five teammate lines and the health line above.", report)
        self.assertIn("The approvals line is optional and appears only when a typed `eval` census covers the window.", report)
        self.assertNotIn("Use exactly the seven", report)
        evaluation = sections((workflow / "references" / "eval.md").read_text())
        invocation = "\n".join(evaluation["Invocation"])
        self.assertIn("A typed `eval` request also collects the proposal census and four-week kind table", invocation)
        self.assertIn("That census uses its own complete four-week window ending at the run start and labels partial coverage. Friday Review collects no census.", invocation)
        self.assertIn("Friday Review keeps failures, drift, repeated corrections, capture and backlog.", invocation)
        evidence = "\n".join(evaluation["Window and evidence"])
        self.assertIn("A typed `eval` additionally reads proposal-bearing run outputs", evidence)
        self.assertNotIn("Friday Review additionally reads proposal-bearing run outputs", evidence)
        contract = sections((workflow / "CONTEXT.md").read_text())
        self.assertIn("A typed `eval` adds its own four-week census window.", "\n".join(contract["Process"]))
        inputs = "\n".join(contract["Inputs"])
        self.assertIn("On a typed `eval` only, numbered proposals, kinds, outcomes and replies over its own four-week window", inputs)
        self.assertIn("from linked complete typed `eval` evidence, otherwise not checked", inputs)
        self.assertNotIn("prior three Friday reviews", inputs)
        audit = next(line for line in contract["Audit"] if line.startswith("| Measurement, before output |"))
        self.assertIn("The approvals line and kind rates come only from a typed `eval` census over its own four-week window, or are not checked", audit)
        output = next(line for line in contract["Outputs"] if line.startswith("| Health report |"))
        self.assertIn("adds the census and kind table", output)

    def test_system_review_inventory_covers_owned_sales_duties_without_personal_reads(self):
        evidence = "\n".join(sections((workflow_path("system-review") / "references" / "eval.md").read_text())["Window and evidence"])
        for expected in ("List every automation for a relevant Sales duty Operator owns with `pplx automation list`, following its pages, whether its collection is project-bound or null.",
                         "Record each one's owner, source, approval or exception, and actual expiry evidence.",
                         "Unrelated personal automations are not read.",
                         "Listing an exception transfers no ownership and changes no settings."):
            self.assertIn(expected, evidence)


class FridayMeasurementContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = workflow_path("system-review")
        cls.review = sections((cls.workflow / "references/review.md").read_text())
        cls.contract = sections((cls.workflow / "CONTEXT.md").read_text())
        cls.coach = sections((workflow_path("deal-coach") / "references/report-format.md").read_text())

    def test_platform_limits_name_all_nine_observed_constraints(self):
        conventions = (CORE / "CONVENTIONS.md").read_text()
        limits = sections(conventions)["Platform limits"]
        names = ("Automation edit scope", "Automation delivery", "Dedicated threads", "Worker messaging",
                 "Teammate instructions", "Credential injection", "Slack watch coverage", "Session tools",
                 "Retire a replaced Teammate by rewriting its Description to read-only before archiving")
        numbered = [line for line in limits if re.match(r"^\d+\. ", line)]
        self.assertEqual(len(numbered), 9)
        self.assertIn("supported included adapter uses native session tools for reads", "\n".join(limits))
        for number, name in enumerate(names, 1):
            self.assertTrue(numbered[number - 1].startswith(f"{number}. {name}."))
        text = "\n".join(limits)
        for expected in ("direct Operator turns", "Agent Mail turns and automation wakes",
                         "RUN_AUTOMATION_SCOPE_VIOLATION", "automation screen", "cannot change delivery",
                         "Recreate the automation", "dedicated automation thread needs a schedule",
                         "Connector events use new threads", "Workers cannot message other sessions",
                         "`pplx tm new --description` did not save", "Description field holds standing instructions",
                         "Role is the short title", "Readback can lag seconds", "literal top-level `pplx` commands",
                         "not sourced scripts or loops", "miss app and bot messages", "Operator's DMs never fire"):
            self.assertIn(expected, text)
        self.assertIn('"Platform limits"', "\n".join(self.contract["Inputs"]))

    def test_every_numbered_proposal_has_a_kind_and_evidenced_outcome(self):
        outcomes = "\n".join(self.review["Proposal outcomes"])
        for expected in ("Record every numbered proposal by workflow and kind", "originating entry link",
                         "proposal number", "exact proposed change", "Operator's outcome evidence",
                         "approved unchanged", "approved with edits", "rejected", "no reply",
                         "Do not pool unlike kinds or workflows", "Later replies update that proposal's outcome",
                         "never add another proposal", "numbered Systems improvement proposals published in the window",
                         "No reply requires a complete read", "Unread replies are not checked",
                         "stay in the Systems thread, never in Git", "Measurement grants no pre-approval"):
            self.assertIn(expected, outcomes)
        self.assertIn('"Proposal outcomes"', "\n".join(self.contract["Inputs"]))
        evaluation = (self.workflow / "references/eval.md").read_text()
        self.assertIn("A typed `eval` additionally reads proposal-bearing run outputs", evaluation)
        self.assertIn("not permission to open every normal run thread", evaluation)

    def test_four_week_rates_use_current_and_prior_three_reviews_without_a_threshold(self):
        outcomes = "\n".join(self.review["Proposal outcomes"])
        for expected in ("typed `eval` run's own complete four-week window", "covering four weeks",
                         "original proposal in its originating review window", "without counting a proposal twice",
                         "total proposals, each outcome count", "count divided by the total proposals for that kind",
                         "includes edited approvals, rejections, and no replies in its denominator",
                         "zero denominator has no rate", "never a zero-percent claim",
                         "does not reach four weeks back, or proposal or reply reads are incomplete",
                         "label the observed window and counts partial", "four-week rate is not checked",
                         "introduces no threshold or target"):
            self.assertIn(expected, outcomes)
        for pending_key in ("min_proposals", "min_unchanged", "max_rejections", "policy.system_review"):
            self.assertNotIn(pending_key, outcomes)

    def test_scorecard_has_exactly_five_teammates_health_and_approvals(self):
        evidence = self.review["Evidence and scorecard"]
        rows = [line for line in evidence if line.startswith("- ")]
        names = [row.split(". ", 1)[0].removeprefix("- ") for row in rows]
        self.assertEqual(names, ["Prospecting", "Pipeline", "Forecasting", "Coach", "Systems", "Health", "Approvals"])
        for expected in ("accounts researched", "drafts approved", "proven sends", "event contacts enrolled", "replies",
                         "meetings", "Pipeline handoffs"):
            self.assertIn(expected.lower(), rows[0].lower())
        for expected in ("ARR created since the previous review", "`policy.forecast.amount_field`",
                         "Opportunities created in that interval", "field history"):
            self.assertIn(expected, rows[1])
        self.assertIn("last week's reported call", rows[2])
        self.assertIn("quarter-end accuracy from Forecasting's existing check", rows[2])
        self.assertIn("Copy only Coach's count line, never rescore deals", rows[3])
        self.assertIn("Operator's approval replies per day", rows[4])
        self.assertIn("receipt-open counts separate from failures", rows[5])
        self.assertIn("four-week approved-unchanged rate", rows[6])
        report = "\n".join(self.review["Report and routing"])
        self.assertIn("Use the five teammate lines and the health line above", report)
        self.assertIn("Approvals. Optional.", rows[6])
        self.assertIn("proposal-kind tables and per-thread delay or stall evidence outside the scorecard and after the backlog", report)

    def test_scorecard_preserves_source_windows_unknowns_and_domain_ownership(self):
        evidence = "\n".join(self.review["Evidence and scorecard"])
        for expected in ("A draft is not a proven send", "Missing reads are not checked, never zero",
                         "Opportunity creation dates (`CreatedDate`)", "not CloseDate",
                         "dated old and new values from field history", "Missing ARR amounts remain unknown",
                         "without recomputing forecasts or setting targets", "daily totals"):
            self.assertIn(expected, evidence)

    def test_coach_view_assesses_ten_questions_internally_and_displays_the_short_view(self):
        approved = ("Assess all ten questions internally. Mark unsupported answers unknown. "
                    "Display material supported facts, major gaps, supported risk patterns, and one next move per deal with the person to involve.\n"
                    "Show all answers on request. Score table, scoring, stakeholder coverage and count evidence unchanged.")
        strategy = (workflow_path("deal-coach") / "references/strategy.md").read_text()
        questions = sections(strategy)["Strategy questions"]
        self.assertEqual("\n".join(questions).count(approved), 1)
        self.assertEqual(len([line for line in questions if re.match(r"^\d+\. ", line)]), 10)
        self.assertNotIn("Answer each question in one or two sentences", strategy)
        review = "\n".join(self.coach["Deal review"])
        self.assertEqual(review.count(approved), 1)
        self.assertNotIn("Answer every strategy question briefly", review)
        self.assertIn("Present the score table first, strategy answers second, and one next best move last.", review)

    def test_coach_gap_count_uses_prior_gaps_and_all_current_quarter_deals(self):
        report = "\n".join(self.coach["Deal review"])
        for expected in ("Add one count line to the weekly deal review", "Gaps closed since last deal review <n>",
                         "Open gaps on deals closing this quarter <n>", "previous deal review in the Coach thread",
                         "Opportunity Id and gap label", "dated evidence resolves the previously reported gap",
                         "Unknown or unread evidence never proves closure", "all owned open Opportunities with CloseDate",
                         "including deals outside the selected review set", "affected count unknown with its limit, never zero",
                         "Systems copies only the count line"):
            self.assertIn(expected, report)
        contract = sections((workflow_path("deal-coach") / "CONTEXT.md").read_text())
        self.assertIn("previous gap records and all owned open Opportunities closing this quarter", "\n".join(contract["Inputs"]))

    def test_coach_gap_definition_bounds_the_scan_and_requires_a_matching_baseline(self):
        report = "\n".join(self.coach["Deal review"])
        for expected in ("A gap is a MEDDICC element scored below its `policy.coach.stage_gate_minimums` value",
                         "for the deal's current stage", "Label it by element, for example EB or PP",
                         "For open gaps, apply this definition to all owned open Opportunities",
                         "including deals outside the selected review set",
                         "The closed count is unknown when the prior review has no baseline in this format"):
            self.assertIn(expected, report)

    def test_thread_latency_reports_actual_occurrences_and_verified_stalls(self):
        drift = "\n".join(self.review["Drift and failures"])
        for expected in ("For each teammate thread", "started more than 30 minutes late or stalled",
                         "expected scheduled occurrence with the actual run start", "schedule's timezone",
                         "run link, both timestamps, delay, state, and output evidence",
                         "Unread schedules, starts, or output locations are not checked",
                         "retrieved evidence of stopped progress, not merely an in-progress label",
                         "Do not count a delivered receipt-open issue as a stall"):
            self.assertIn(expected, drift)

    def test_thread_moves_need_two_consecutive_reviews_and_matt_approval(self):
        drift = "\n".join(self.review["Drift and failures"])
        for expected in ("only when the same thread shows a delay in two consecutive Friday reviews",
                         "links to both reviews and their run evidence", "recreate that thread's runs in their own threads",
                         "results-only summaries", "Recreating needs Operator's approval, never an automatic move",
                         '"Platform limits"', "Connector events use new threads",
                         "Do not invent a schedule to bypass a limit"):
            self.assertIn(expected, drift)


class AuditFindingContracts(unittest.TestCase):
    def test_close_verification_keeps_prior_pending_downstream_items_in_scope(self):
        reference = (workflow_path("close") / "references/paths.md").read_text()
        self.assertIn("Keep unresolved downstream items from the prior handoff in scope", reference)
        self.assertIn("even when current org status selects a different path", reference)
        self.assertIn("Never repeat a verified conversion or completed handoff", reference)

    def test_close_loads_all_fields_before_reading_every_field(self):
        contract = sections((workflow_path("close") / "CONTEXT.md").read_text())
        _, inputs = table_rows(contract["Inputs"])
        fields = [row for row in inputs if row[1] == "`references/fields.md`"]
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0][2], "Full file at step 2")
        self.assertIn("Read every field in `references/fields.md`", "\n".join(contract["Process"]))

    def test_triage_next_and_output_match_deal_receipts_and_field_ownership(self):
        text=(workflow_path('task-triage-speed-run')/'CONTEXT.md').read_text()
        frontmatter=yaml.safe_load(text.split('---\n',2)[1])
        self.assertIn('deal-thread receipts',frontmatter['next'])
        self.assertIn('Next_Steps__c',frontmatter['writes'])
        self.assertIn('verified written next step',text)
        self.assertNotIn('for its field owner',text)

    def test_root_systems_summary_includes_improvement_tasks(self):
        _, routes = table_rows(sections((ROOT / "CONTEXT.md").read_text())["Task routing"])
        systems = [row for row in routes if row[1] == "`workspaces/systems/CONTEXT.md`"]
        self.assertEqual(len(systems), 1)
        self.assertIn("improvement tasks and findings routed for repair", systems[0][2])

    def test_preview_input_output_and_report_use_helper_values(self):
        directory = workflow_path("forecast-weekly") / "references"
        compute = (directory / "compute.md").read_text()
        for expected in ("`policy.forecast.next_quarter_preview_days`", "every next-quarter row",
                         "explicit null when missing", "may overlap pull_ins, but never booked or deals",
                         "Omit preview outside that window", "`quarter`, `count`, `sum`, `missing_amount_count`, `top_three`, and `target`",
                         "Missing amounts are counted, never treated as zero", "`policy.forecast.target_default`"):
            self.assertIn(expected, compute)
        report = (directory / "report-format.md").read_text()
        for expected in ("returned preview.quarter", "preview.count", "preview.sum", "preview.top_three", "preview.target",
                         "only when returned `preview.missing_amount_count` is greater than zero",
                         "Never sum or rank next-quarter rows in prose"):
            self.assertIn(expected, report)


class CoachCoverageAndPatterns(unittest.TestCase):
    def test_meddicc_zero_cells_require_absence_not_unknown_sources(self):
        text = (workflow_path("deal-coach") / "references/meddicc.md").read_text()
        for element in ("Economic Buyer", "Decision Criteria", "Decision Process", "Paper Process", "Competition"):
            with self.subTest(element=element):
                self.assertIn(f"| {element} | Absent in reviewed evidence |", text)
        self.assertNotIn("Unknown in reviewed evidence", text)
        self.assertIn("Unread or missing sources leave the element unknown rather than proving a zero.", text)
        self.assertIn("Use zero when the reviewed evidence establishes that the element is absent.", text)
        self.assertIn("Unknown elements make the gate unverified, never passed.", text)

    def setUp(self):
        self.directory = workflow_path("deal-coach")
        self.text = (self.directory / "CONTEXT.md").read_text()
        self.contract = sections(self.text)
        self.report = sections((self.directory / "references" / "report-format.md").read_text())
        self.learning = sections((self.directory / "references" / "learning.md").read_text())

    def test_stakeholder_inputs_cover_all_open_late_stage_deals_not_only_selected_reviews(self):
        _, inputs = table_rows(self.contract["Inputs"])
        coverage = [row for row in inputs if row[1] == "Salesforce Contact Roles, Gmail, and Momentum"]
        self.assertEqual(len(coverage), 1)
        for expected in ("every owned open S3 to S5 Opportunity", "outside the deal_review_count selection"):
            self.assertIn(expected, coverage[0][2])
        self.assertEqual(coverage[0][3], "Stakeholder roles and active contacts")
        scope = "\n".join(self.report["Scope and evidence"])
        self.assertIn("every owned open S3 to S5 deal's stakeholder coverage, including unselected deals", scope)
        self.assertIn("all open S3 to S5 coverage", "\n".join(self.contract["Inputs"]))

    def test_stakeholder_section_follows_reviews_and_names_each_role_with_evidence_or_missing(self):
        review = "\n".join(self.report["Deal review"])
        self.assertLess(review.index("For each deal"), review.index("After the per-deal reviews"))
        for expected in ("Stakeholder coverage section", "one line for every owned open S3 to S5 Opportunity",
                         "including deals outside `policy.coach.deal_review_count`", "economic buyer or signer",
                         "security or IT reviewer", "legal or procurement contact",
                         "Contact Roles, Gmail, or Momentum evidence, or marked missing"):
            self.assertIn(expected, review)
        self.assertIn("Every owned open S3 to S5 deal has one coverage line, including unselected deals",
                      "\n".join(self.contract["Audit"]))

    def test_single_threading_uses_distinct_active_contacts_and_never_turns_unread_into_absence(self):
        review = "\n".join(self.report["Deal review"])
        for expected in ("dated buyer participation in Gmail or Momentum within the supported review window",
                         "Contact Roles alone do not prove a contact is active", "single-threaded",
                         "only one distinct active contact is evidenced", "even when that person holds multiple roles",
                         "Unread evidence is not checked, not proof of missing roles or inactivity"):
            self.assertIn(expected, review)

    def test_contact_suggestions_require_named_evidence_and_existing_pipeline_approval_route(self):
        review = "\n".join(self.report["Deal review"])
        self.assertIn("Suggest a Contact or Contact Role only when a named person has evidence", review)
        self.assertIn('one-line note to the Pipeline thread per "Output rules", never a write', review)
        output_rules = "\n".join(self.report["Output rules"])
        self.assertIn("for Operator to approve there", output_rules)
        self.assertIn("without performing it", output_rules)
        frontmatter = yaml.safe_load(self.text.split("---\n", 2)[1])
        self.assertEqual(frontmatter["writes"], "nothing")
        _, checkpoints = table_rows(self.contract["Checkpoints"])
        self.assertEqual(len(checkpoints), 1)
        self.assertIn("Operator approves specific edits", checkpoints[0][2])

    def test_monthly_inputs_load_transcript_policy_rules_and_owned_prior_month_evidence(self):
        _, inputs = table_rows(self.contract["Inputs"])
        self.assertTrue(any(row[1] == "`_core/policy.yaml`" and
                            row[2] == "All branches load `momentum`, `tooling`" for row in inputs))
        self.assertTrue(any(row[1] == "`_core/rules.md`" and
                            row[2] == "All branches load `rules#momentum`, `rules#handoff_delivery`" for row in inputs))
        month = [row for row in inputs if row[1] ==
                 "Owned Opportunity call Tasks and Next_Steps__c, Momentum transcripts, and linked deal evidence"]
        self.assertEqual(len(month), 1)
        self.assertIn("Criteria-refresh uses the previous calendar month, within supported source limits", month[0][2])
        self.assertIn("since the last refresh", "\n".join(self.contract["Inputs"]))

    def test_monthly_patterns_have_recurrence_cap_accounts_dated_evidence_and_named_owner_choices(self):
        monthly = "\n".join(self.learning["Monthly refresh"])
        report = "\n".join(self.report["Criteria refresh"])
        for text in (monthly, report):
            for expected in ("Patterns section", "previous calendar month", "objections, blockers, and product gaps",
                             "two or more distinct deals", "at most 10 patterns", "the accounts",
                             "one dated piece of evidence per deal", "a suggested owner",
                             "product, security, deal desk, or enablement"):
                self.assertIn(expected, text)
        self.assertIn("not merely repeated calls on one deal", monthly)
        self.assertIn("State the month's dates in the refresh schedule's timezone", monthly)
        self.assertIn("separate from the since-last-refresh window for criteria edits", monthly)

    def test_pattern_only_scheduled_output_and_no_pattern_no_edit_quiet_case(self):
        monthly = "\n".join(self.learning["Monthly refresh"])
        report = "\n".join(self.report["Criteria refresh"])
        for text in (monthly, report):
            self.assertIn("even when no criteria edit is supported", text)
            self.assertIn("nothing only when there are neither patterns nor supported edits", text)
        self.assertIn("only when criteria edits are proposed", report)
        self.assertIn("For a typed request with neither patterns nor supported edits", report)
        self.assertNotIn("A scheduled refresh with no supported change posts nothing", report)
        _, outputs = table_rows(self.contract["Outputs"])
        patterns = [row for row in outputs if row[0] == "Monthly patterns"]
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0][1], "Coach thread")
        self.assertIn("even without supported criteria edits", patterns[0][2])

    def test_capped_momentum_windows_mark_the_account_not_checked_and_split_on_refresh(self):
        review = "\n".join(self.report["Deal review"])
        self.assertIn("An Account-filtered window that returns `policy.momentum.sweep.page_size` meetings is capped.", review)
        self.assertIn("mark that Account not checked for coverage, never fully covered", review)
        monthly = "\n".join(self.learning["Monthly refresh"])
        anchor = "Respect supported retrieval windows and limits. "
        approved = ("A Momentum window that returns `policy.momentum.sweep.page_size` meetings is incomplete. "
                    "Split it in half and rerun until every window returns fewer.")
        self.assertEqual(monthly.count(anchor + approved), 1)
        policy = yaml.safe_load((CORE / "policy.yaml").read_text())
        self.assertIsInstance(policy["momentum"]["sweep"]["page_size"], int)

    def test_agent_configuration_recovers_from_connector_and_platform_failures(self):
        process = "\n".join(sections((workflow_path("agent-configuration") / "CONTEXT.md").read_text())["Process"])
        for expected in ("Recovery from a connector or platform failure.", "quote the exact error with the command or tool that raised it",
                         "Nothing after that step is assumed applied.", "Verify which tools, permissions and settings are still readable",
                         "read back actual settings", "Retry only under the original authorization",
                         "proposed `_core/CONVENTIONS.md` \"Platform limits\" line through repo-maintenance, never a workaround"):
            self.assertIn(expected, process)

    def test_pattern_evidence_limits_privacy_and_existing_criteria_delivery_gates_remain_explicit(self):
        monthly = "\n".join(self.learning["Monthly refresh"])
        for expected in ("Respect supported retrieval windows and limits", "unread or out-of-lookback evidence as not checked",
                         "never as an absence of patterns", "not criteria changes or approval to execute work",
                         "Account names and buyer quotes stay in the Coach thread, never the repo"):
            self.assertIn(expected, monthly)
        self.assertIn("Pattern account names and buyer quotes stay in the Coach thread, never the repo",
                      "\n".join(self.report["Criteria refresh"]))
        delivery = "\n".join(self.learning["Approval and delivery"])
        self.assertIn("Operator approves specific proposal numbers", delivery)
        self.assertIn("The coach never edits or merges repository files", delivery)
        self.assertIn("Systems repo-maintenance", delivery)


class SystemReviewEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = workflow_path("system-review")
        cls.contract_text = (cls.workflow / "CONTEXT.md").read_text()
        cls.contract = sections(cls.contract_text)
        cls.frontmatter = yaml.safe_load(cls.contract_text.split("---\n", 2)[1])
        cls.evaluation = sections((cls.workflow / "references" / "eval.md").read_text())
        cls.review = sections((cls.workflow / "references" / "review.md").read_text())

    def test_eval_is_in_friday_review_or_on_demand_without_a_new_schedule(self):
        self.assertEqual(self.frontmatter["cadence"], "Friday")
        self.assertEqual(self.frontmatter["writes"], "Teammate improvement tasks and evidence comments only")
        invocation = "\n".join(self.evaluation["Invocation"])
        for expected in ("Eval is part of the existing Friday Review", "typed `eval` request runs the same evaluation on demand",
                         "Cadence remains Friday", "no daily Eval branch, separate eval automation, or weekday schedule",
                         "On-demand Eval uses the previous-review window and does not reset the review baseline"):
            self.assertIn(expected, invocation)
        drift = "\n".join(self.review["Drift and failures"])
        self.assertIn("policy.system_review.schedule", drift)
        self.assertIn("Eval introduces no daily or weekday schedule", drift)

    def test_evidence_window_and_automation_reads_are_complete_and_selective(self):
        evidence = "\n".join(self.evaluation["Window and evidence"])
        for expected in ("time since the previous review in the Systems thread, or 24 hours on the first run",
                         "An unread baseline is not checked, not proof of a first run",
                         "with `pplx automation list`, following its pages",
                         "Read every automation run in the window with `pplx automation runs <id>`",
                         "Follow returned cursors until the window is covered", "Do not use `--responses`",
                         "Open a run thread only for failures, stuck receipts, or Operator's edits, rejections, or silence",
                         "Unread or incomplete threads are not checked, not evidence of silence",
                         "Read Pipeline, Forecasting, Coach and deal thread entries within their verified timestamp windows",
                         "Read PRs merged in the window",
                         "open improvement tasks", "keeping delivered receipts separate from failures"):
            self.assertIn(expected, evidence)

    def test_friday_thread_windows_require_verified_boundaries_not_export_positions(self):
        evidence = "\n".join(self.evaluation["Window and evidence"])
        for expected in ("Call `load_sessions` in Code Mode with the verified session context UUID", "`conversation.jsonl`",
                         "mark that thread context not checked", "Never infer its contents",
                         "Window thread entries by their timestamps, never by turn numbers", "Never infer thread-entry dates",
                         "timestamped window boundary", "previous Friday review's Systems output",
                         "first Friday review sets each thread's baseline", "without claiming historical turns",
                         "newly encountered thread also gets a baseline", "not permission to reset or advance",
                         "On-demand Eval uses those baselines without advancing them",
                         "Run threads keep their run's `created_at` window, not a turn baseline",
                         "Keep counts and baseline history out of Git"):
            self.assertIn(expected, evidence)
        review = sections((workflow_path("system-review") / "references/review.md").read_text())
        scorecard = "\n".join(review["Evidence and scorecard"])
        for expected in ("links its retained source snapshots, context UUIDs and coverage timestamps",
                         "in its Systems thread output", "The first review sets the baseline",
                         "The next review needs complete timestamp coverage after that boundary", "never in Git",
                         "An unread thread is not checked and its baseline does not advance"):
            self.assertIn(expected, scorecard)

    def test_improvement_signals_cover_all_approved_cases(self):
        signals = "\n".join(self.evaluation["Signals"])
        self.assertEqual(len([line for line in self.evaluation["Signals"] if line.startswith("- ")]), 7)
        for expected in ("A recurring failure or stuck run", "The same edit or rejection twice",
                         "Manual work Operator repeats that a workflow could prepare", "A no-op or duplicate run",
                         "A missed handoff", "Drift from the profile, pointer, or schedule checks",
                         "A system gap against the reviewed targets in `policy.forecast.targets` or `policy.forecast.target_default`, framed as a system change"):
            self.assertIn(expected, signals)

    def test_repeated_corrections_ask_once_with_links_and_record_answer_evidence(self):
        signals = "\n".join(self.evaluation["Signals"])
        approved = (
            "For each same-edit or same-rejection pattern, ask Operator one question, with both links, asking what was wrong. Ask once per pattern, never per proposal.\n"
            "Skip a pattern whose reason Operator already gave. Without his answer the cause stays a labeled hypothesis. Never infer his reason from the edit.\n"
            "Record his answer as an evidence comment on the matching improvement task, with the reply link. It replaces the hypothesis as the cause evidence for that fix."
        )
        self.assertEqual(signals.count(approved), 1)
        self.assertGreater(signals.index(approved), signals.rindex("- "))

    def test_repeated_correction_questions_follow_proposals_without_pausing_review(self):
        routing = "\n".join(self.review["Report and routing"])
        approved = 'Then list each repeated-correction question per `references/eval.md` "Signals", one line with both links. Questions are not proposals and wait for no reply.'
        preceding = 'Follow with at most 3 new ranked proposals per `references/eval.md` "Proposals and task recording". Use compact lines and evidence links rather than copying run output.'
        self.assertIn(preceding + "\n" + approved, routing)
        self.assertEqual(routing.count(approved), 1)
        self.assertIn("None.", "\n".join(self.contract["Checkpoints"]))
        self.assertEqual(self.frontmatter["writes"], "Teammate improvement tasks and evidence comments only")

    def test_repeated_correction_questions_are_audited_and_reported_separately(self):
        audit = next(line for line in self.contract["Audit"] if line.startswith("| Report, before output |"))
        self.assertTrue(audit.endswith("Repeated-correction questions follow the proposals, one per pattern. |"))
        output = next(line for line in self.contract["Outputs"] if line.startswith("| Health report |"))
        self.assertIn("Friday scorecard, Improvement backlog, at most 3 new ranked proposals, and repeated-correction questions. On-demand Eval uses the same evaluation", output)

    def test_proposals_are_capped_ranked_and_do_not_set_forecasts_or_policy(self):
        proposals = "\n".join(self.evaluation["Proposals and task recording"])
        for expected in ("at most 3 new numbered proposals, ranked by impact", "evidence links, an owner, the exact fix",
                         "effort `S`, `M`, or `L`, and verification",
                         "repo-maintenance, agent-configuration, or the domain teammate and Operator for policy",
                         "a proposed execution owner, not a task assignment",
                         "Forecasting's latest reported numbers only for impact ranking",
                         "Unsupported impact remains unknown, never a recomputed forecast or a new policy"):
            self.assertIn(expected, proposals)
        evidence = "\n".join(self.evaluation["Window and evidence"])
        self.assertIn("Never recompute forecasts or set sales policy", evidence)

    def test_dedupe_and_only_unassigned_improvement_task_writes_are_allowed(self):
        proposals = "\n".join(self.evaluation["Proposals and task recording"])
        for expected in ("Dedupe against open or declined improvement tasks", "underlying issue, workflow, and intended fix",
                         "Add only new evidence to an existing task as a comment",
                         "Do not repeat evidence already recorded", "declined match does not authorize a duplicate task",
                         "one open, unassigned Teammate task labeled `improvement`",
                         "`pplx tm tasks create <title> --description <proposal> --label improvement`",
                         "Keep its owner in the description. Do not call `tasks assign`",
                         "Never close, cancel, or reopen tasks", "Read back each task or evidence comment",
                         "Verify status open, no execution assignment, label improvement",
                         "Report a failed or unverified recording as such", "Do not claim it was recorded or retry blindly",
                         "Task creation and evidence comments are the only durable writes"):
            self.assertIn(expected, proposals)
        evidence = "\n".join(self.evaluation["Window and evidence"])
        self.assertIn("Read prior decline evidence", evidence)
        self.assertIn("Unreadable or incomplete dedupe evidence blocks new task creation", evidence)

    def test_no_new_eval_is_quiet_without_discarding_friday_report_or_gaps(self):
        proposals = "\n".join(self.evaluation["Proposals and task recording"])
        for expected in ("If nothing is new after complete evidence reads and dedupe, post one line",
                         "Comment-only additions do not need a new proposal notification",
                         "Friday still keeps its scorecard and backlog", "Friday collects no census.",
                         "A no-new typed Eval posts the one line plus the requested census and four-week kind table, or their partial and not-checked limits",
                         "Zero new improvements never drops the census",
                         "For a scheduled run, call `pplx automation suppress-run-notification` for that run only",
                         "A typed Eval has no automation notification to suppress",
                         "Do not hide missing evidence or recording failures as a no-new result"):
            self.assertIn(expected, proposals)
        self.assertIn("Friday keeps its scorecard and backlog", "\n".join(self.contract["Outputs"]))
        outputs = "\n".join(self.contract["Outputs"])
        self.assertIn("| Quiet receipt | Systems thread | One Eval line when nothing is new. A typed `eval` adds its census and kind table or their limits.", outputs)
        process = "\n".join(self.contract["Process"])
        self.assertIn("A no-new typed `eval` still returns its census and kind table, or their partial and not-checked limits, with the one line.", process)
        audit = next(line for line in self.contract["Audit"] if line.startswith("| Report, before output |"))
        self.assertIn("No-new Eval is one line, typed adds census and kind table.", audit)

    def test_friday_backlog_has_age_top_five_and_proposed_not_applied_closures(self):
        backlog = "\n".join(self.evaluation["Friday backlog"])
        for expected in ("Immediately after the Friday scorecard, add an Improvement backlog section",
                         "top 5 open improvement tasks by impact, each with its link and age",
                         "from task creation to this review's run-start time, not from its last evidence comment",
                         "Check all open improvement tasks for resolution, not only the five displayed",
                         "Propose closing any that new evidence resolved", "Never close the tasks here",
                         "scorecard remains seven lines or fewer", "backlog is a separate section"):
            self.assertIn(expected, backlog)
        report = "\n".join(self.review["Report and routing"])
        self.assertIn("Add Improvement backlog immediately after it", report)
        self.assertIn("at most 3 new ranked proposals", report)

    def test_eval_inputs_audits_outputs_and_systems_route_keep_approval_boundaries(self):
        inputs = "\n".join(self.contract["Inputs"])
        self.assertIn("`references/eval.md`", inputs)
        for heading in self.evaluation:
            self.assertIn(f'"{heading}"', inputs)
        audit = "\n".join(self.contract["Audit"])
        for expected in ("Open and declined improvement tasks were checked", "one open, unassigned task labeled improvement",
                         "Only improvement tasks and evidence comments are writes", "Never assign or close tasks",
                         "recompute forecasts, set policy, or write customer systems"):
            self.assertIn(expected, audit)
        outputs = "\n".join(self.contract["Outputs"])
        self.assertIn("Improvement records | Teammate project tasks", outputs)
        self.assertIn("policy goes to the domain teammate and Operator", outputs)
        routes = sections((WORKSPACES / "systems" / "CONTEXT.md").read_text())
        self.assertIn("Friday Review or typed health or eval request", "\n".join(routes["Task routing"]))


class CanonicalHomes(unittest.TestCase):
    """Shared definitions have one anchor, and the workflows that depend on them cite it."""

    def cites(self, name, anchor):
        text = "\n".join(p.read_text() for p in workflow_path(name).rglob("*.md"))
        return f"rules#{anchor}" in text

    def test_interaction_sync_b_requires_its_matching_task(self):
        workflow = workflow_path("interaction-sync")
        proposals = (workflow / "references" / "proposals.md").read_text()
        letters = "\n".join(sections(proposals)["Letters"])
        proposal_b = letters.split("- **B. Opportunity update.**", 1)[1].split("- **C.", 1)[0]
        for expected in ("include its matching follow-up Task change in B", "full Task payload and current-to-new values",
                         "One `approved B` covers both sides", "Never propose or apply a B change",
                         "Reuse one, or propose its reschedule by exact ID",
                         "A new action completes the old Task and creates one", "reviewed later milestone stays open",
                         "The Task's ActivityDate is the action's due date, not the date the next-step entry is written"):
            self.assertIn(expected, proposal_b)
        self.assertIn("matching Task changes, which stay together under B", proposals)
        proposal_c = letters.split("- **C.", 1)[1].split("- **D.", 1)[0]
        self.assertIn("reuse or reschedule by exact ID before creating another", proposal_c)
        self.assertIn("When none fits, propose a Not Started Task", proposal_c)
        self.assertIn("Use C only for Task changes not tied to a next-step change", proposal_c)
        self.assertIn("Never split B's matching Task into C", proposal_c)
        self.assertNotIn("Required with B", proposal_c)
        self.assertIn("a Task completion already included in B", letters)
        apply = "\n".join(sections(proposals)["Apply"])
        for expected in ("item 4 review before a new Task in B or C",
                         "write the next step first, then its matching Task changes, then read both back",
                         "If a Task write fails, report B as partial with the actual state of both sides",
                         "one corrective proposal for the remaining Task change", "Do not claim both applied"):
            self.assertIn(expected, apply)
        audit = "\n".join(sections((workflow / "CONTEXT.md").read_text())["Audit"])
        self.assertIn("B includes its matching Task for any next-step change", audit)
        self.assertIn("writes next step then Task, and reads both back", audit)
        self.assertIn("A failed Task write is partial with one corrective proposal", audit)

    def test_next_step_writers_load_content_and_format_rules_in_inputs(self):
        for name in ("interaction-sync", "close"):
            contract = sections((workflow_path(name) / "CONTEXT.md").read_text())
            inputs = "\n".join(contract["Inputs"])
            rule_refs = set(re.findall(r"`(rules#[a-z_]+)`", inputs))
            self.assertTrue({"rules#next_steps", "rules#next_steps_format"} <= rule_refs, name)

    def test_interaction_sync_checks_transcript_identity_before_extract(self):
        workflow = workflow_path("interaction-sync")
        reference = (workflow / "references" / "reconcile.md").read_text()
        find = " ".join(sections(reference)["Find the interaction"])
        for expected in ("For a Momentum transcript, before Extract", "Compare the meeting start instant",
                         "every external Calendar attendee email", "read source verifies that it belongs to the same person",
                         "do not infer a Contact identity from a name",
                         "conflicting start time or unexplained missing Calendar attendee makes the run needs-input",
                         "date cues that contradict that date",
                         "scheduling that same date as a future meeting", "first meeting when an earlier one is logged",
                         "identity check that cannot be completed makes the run needs-input",
                         "State the reason and propose nothing derived from that transcript"):
            self.assertIn(expected, find)
        contract = sections((workflow / "CONTEXT.md").read_text())
        find_step = next(line for line in contract["Process"] if line.startswith("2. "))
        self.assertIn('"Find the interaction"', find_step)
        extract_step = next(line for line in contract["Process"] if line.startswith("3. "))
        self.assertIn('"Extract"', extract_step)
        audit = "\n".join(contract["Audit"])
        for expected in ("Identity, before step 3", '`references/reconcile.md` "Find the interaction"',
                         "no contradictory transcript date cues", "needs-input", "states the reason",
                         "proposes nothing derived from that transcript"):
            self.assertIn(expected, audit)

    def test_active_cold_has_one_home(self):
        self.assertIn('<a id="contact_status"></a>', (CORE / "rules.md").read_text())
        for name in ("interaction-sync", "task-triage-speed-run"):
            self.assertTrue(self.cites(name, "contact_status"), name)

    def test_email_body_security_reread_uses_approved_wording(self):
        rules = (CORE / "rules.md").read_text()
        anchor = '<a id="email_body"></a>**email_body**'
        self.assertEqual(rules.count(anchor), 1)
        block = rules.split(anchor, 1)[1].split('<a id="', 1)[0]
        approved = (
            "- Re-read linked security threads before drafting customer security answers, "
            "rather than relying on notifications."
        )
        self.assertEqual(rules.count(approved), 1)
        self.assertEqual(block.strip().splitlines()[-2:], [
            "- No phrase in `policy.email_voice.banned`.",
            approved,
        ])
        for name in ("interaction-sync", "task-triage-speed-run"):
            self.assertTrue(self.cites(name, "email_body"), name)

    def test_pilot_handoff_has_one_home(self):
        self.assertIn('<a id="pilot_handoff"></a>', (CORE / "rules.md").read_text())
        for name in ("interaction-sync", "pipeline-review", "pilot-usage"):
            self.assertTrue(self.cites(name, "pilot_handoff"), name)
        self.assertFalse(self.cites("forecast-weekly", "pilot_handoff"))

    def test_triage_current_action_ownership_and_unthreaded_opportunities_are_separate(self):
        workflow=workflow_path('task-triage-speed-run')
        group=(workflow/'references/grouping.md').read_text()
        self.assertIn('rules#task_date_coordination',group)
        self.assertIn('rules#followup_task',group)
        self.assertIn('references/next-steps.md',group)
        self.assertNotIn('Triage never writes',group)
        self.assertIn('Deal Task follow-up drafts follow these same recipient',group)

    def test_triage_owned_tasks_share_the_message_but_never_get_date_moves(self):
        workflow = workflow_path("task-triage-speed-run")
        walk = (workflow / "references/walk.md").read_text()
        drafts = (workflow / "references/drafts.md").read_text()
        self.assertIn("including deal Tasks and the unthreaded Opportunity branch", walk)
        self.assertIn("Deal Tasks and unthreaded Opportunity Tasks stay in this same message", walk)
        self.assertIn("Deal Task follow-up drafts follow these same recipient, prior-email, hold, approval and readback gates", (workflow / "references/grouping.md").read_text())
        self.assertIn("Deal Task follow-up drafts use this same path", drafts)

    def test_triage_rechecks_state_before_pairs_and_reports_partial_results(self):
        writes = (workflow_path("task-triage-speed-run") / "references/writes.md").read_text()
        for expected in ("Recheck action evidence and ownership", "all related open Tasks", "changed Status, ActivityDate, LastModifiedDate, Subject or Description",
                         "create or readback leaves the old Task open and due", "completion failure after a verified create is partial", "receipt of at most 3 lines", "does not undo verified writes"):
            self.assertIn(expected, writes)

    def test_triage_no_reply_has_no_write_exception(self):
        rules = (CORE / "rules.md").read_text()
        scheduled = rules.split('<a id="scheduled_runs">', 1)[1].split("## Evidence and tooling", 1)[0]
        self.assertIn("No reply writes nothing", scheduled)
        self.assertNotIn("Except", scheduled)
        contract = (workflow_path("task-triage-speed-run") / "CONTEXT.md").read_text()
        self.assertEqual(yaml.safe_load(contract.split("---\n", 2)[1])["writes"],
                         "Salesforce Next_Steps__c, Task and Contact fields, Contact creates, unsent Gmail drafts, after approval only")

    def test_triage_positive_action_evidence_replaces_absence_based_moves(self):
        collect = (workflow_path("task-triage-speed-run") / "references/collect.md").read_text()
        for expected in ("exact sent email, held-call source or reply", "Quote and link it", "not proof Operator completed an action", "scheduled meetings do not prove attendance", "flag `Draft not sent`", "no helper flag authorizes a write"):
            self.assertIn(expected, collect)

    def test_triage_write_order_preserves_due_task_when_action_or_create_fails(self):
        writes = (workflow_path("task-triage-speed-run") / "references/writes.md").read_text()
        self.assertLess(writes.index("Write and read the approved next step first"), writes.index("complete the old Task"))
        for expected in ("No write is automatic", "failed or unverified draft gets no next-step, completion or next-Task write", "with its quoted source per `rules#task_date_coordination`"):
            self.assertIn(expected, writes)


class TriageSinglePassApproval(unittest.TestCase):
    def setUp(self):
        self.workflow = workflow_path("task-triage-speed-run")
        self.contract = (self.workflow / "CONTEXT.md").read_text()
        self.walk = (self.workflow / "references" / "walk.md").read_text()
        self.drafts = (self.workflow / "references" / "drafts.md").read_text()
        self.writes = (self.workflow / "references" / "writes.md").read_text()

    def test_readout_has_one_main_question_not_group_stage_questions(self):
        readout = self.walk.split("## Readout\n", 1)[1].split("## Section walk\n", 1)[0]
        self.assertEqual(readout.count("?"), 1)
        self.assertEqual(self.walk.count("?"), 1)
        self.assertIn("End with exactly one main-pass question", readout)
        self.assertIn("Approve all eligible numbered rows, select numbers", readout)
        self.assertIn("add approved with a Recycle number, or skip?", readout)
        self.assertNotIn("Walk the sections?", self.walk)

    def test_full_proposal_covers_every_group_row_and_exact_change(self):
        for expected in ("exactly once, numbered as proposed or blocked", "action evidence", "new Task's Subject, date, OwnerId, WhatId, WhoId and Description", "complete draft", "unchanged current date", "quote its permitted source per `rules#task_date_coordination`"):
            self.assertIn(expected, self.walk)
        _, checkpoints = table_rows(sections(self.contract)["Checkpoints"])
        self.assertEqual([row[0] for row in checkpoints], ["5", "8"])
        self.assertIn("One full proposal", checkpoints[0][1])
        self.assertIn("One CRM correction after the main pass", checkpoints[1][1])

    def test_all_scope_recycle_and_crm_approvals_stay_narrow(self):
        for expected in ("`all` covers every numbered proposed row in the displayed pass except Recycle and CRM corrections", "Blockers and ambiguous ownership never gain authority", "Recycle needs `approved` with its number", "no Push option", "Neither `all` nor numbered main-pass selections approve a CRM correction"):
            self.assertIn(expected, self.walk)
        self.assertIn("No email is sent", self.writes)

    def test_approved_draft_rows_cover_pair_but_require_verified_creation_first(self):
        self.assertIn("contingent completion and next Task", self.drafts)
        self.assertIn("Create and verify the draft, then read back any displayed next step, then verify or create/read back the matching Task before completing the old one", self.drafts)
        self.assertIn("Do not create it until its displayed row is approved", self.drafts)
        self.assertIn("confirm To, CC, Subject, and full body match the approved row", self.drafts)
        self.assertIn("failed or unverified draft gets no next-step, completion or next-Task write", self.drafts)
        self.assertIn("flag `Draft not sent`, never a new follow-up", self.drafts)

    def test_receipts_and_remaining_batch_do_not_rewalk_or_repeat_verified_writes(self):
        for expected in ("Post one combined receipt for the approved pass", "one remaining batch with their original numbers", "Accept a follow-up approval on that batch without re-walking the groups", "Do not reopen verified rows or repeat successful writes", "never retry it automatically", "`skip` declines the displayed batch", "Do not ask for the same approval again"):
            self.assertIn(expected, self.walk)
        self.assertIn("Never repeat verified draft creation or a verified record write", self.writes)
        self.assertIn("Read every changed record back, including `Description`", self.writes)


class EventSequenceContract(unittest.TestCase):
    def test_default_mailbox_selection_filters_to_runtime_apollo_user_first(self):
        intake = "\n".join(sections(self.prep)["Intake"])
        self.assertLess(intake.index("resolve Operator's Apollo user"), intake.index("Filter the complete mailbox list"))
        for requirement in ("before counting `default: true`", "exactly one default for that user",
                            "multiple owned defaults is needs-input", "never hardcoded in Git",
                            "Other users' defaults do not block Operator's selection"):
            self.assertIn(requirement, intake)
        timing = "\n".join(sections(self.sequence)["Copy and timing"])
        self.assertIn("filtering to Operator's resolved Apollo user", timing)
        self.assertIn("Keep user and mailbox IDs in run-time evidence, not Git", timing)

    def test_event_sequence_history_checks_all_statuses_before_enrichment(self):
        checks = "\n".join(sections(self.prep)["Salesforce and reply checks"])
        for requirement in ("event_sequence_ids", "apollo_sequence_enrollments",
                            "including finished, paused and removed, not only active",
                            "any prior enrollment in this event's sequences, regardless of status",
                            "another active sequence", "Missing target or history evidence stays needs-input"):
            self.assertIn(requirement, checks)
        self.assertIn("prior same-event enrollment in every status", self.sequence)

    def test_copy_timing_uses_approved_interval_mode_and_expected_local_windows(self):
        timing = "\n".join(sections(self.sequence)["Copy and timing"])
        approved = (
            "Build the sequence in Apollo interval mode on a named sending schedule, not exact datetimes. "
            "Email 1 waits 0 days from enrollment and later steps wait the configured gap.\n"
            "Show each step's expected local send date and window with timezone, not just relative offsets. "
            "The exact schedule is chosen and approved by Operator, never inferred from the sandbox timezone."
        )
        self.assertEqual(timing.count(approved), 1)
        self.assertNotIn("Show every absolute local date and time with timezone, not just relative offsets.", self.sequence)

    def setUp(self):
        self.workflow = workflow_path("event-sequence")
        self.contract = (self.workflow / "CONTEXT.md").read_text()
        self.list_prep = (self.workflow / "01-list-prep/CONTEXT.md").read_text()
        self.plan = (self.workflow / "02-sequence-plan/CONTEXT.md").read_text()
        self.launch = (self.workflow / "03-launch/CONTEXT.md").read_text()
        self.prep = (self.workflow / "references" / "prep.md").read_text()
        self.sequence = (self.workflow / "references" / "sequence.md").read_text()
        self.readback = (self.workflow / "references" / "readback.md").read_text()

    def test_live_sequence_mutation_needs_a_new_exact_approval(self):
        process = "\n".join(sections(self.contract)["Process"])
        for expected in ("A change to a live sequence after Launch is a mutation.",
                         "adding or removing contacts, editing copy, schedule or mailbox, and pausing or resuming",
                         "A mutation needs a new exact proposal in this Prospecting run thread and Operator's native approval of that proposal",
                         "`rules#approval` and `rules#write_protocol`", "The original E approval never covers a mutation.",
                         "Read the native sequence back after the approved change.", "An unavailable readback is not checked, never assumed applied."):
            self.assertIn(expected, process)

    def test_pipeline_receives_the_open_opportunity_contact_handoff_as_evidence_only(self):
        handoffs = sections((WORKSPACES / "pipeline" / "CONTEXT.md").read_text())["Handoffs"]
        header, rows = table_rows(handoffs)
        self.assertEqual(header, "| Inbound source | Receiving contract | Existing approval scope |")
        matches = [r for r in rows if "open-Opportunity contacts" in r[0] or "open-Opportunity contact handoff" in r[0]]
        self.assertEqual(len(matches), 1, "exactly one receiving row for the Prospecting open-Opportunity contact handoff")
        row = matches[0]
        self.assertIn("deal thread", row[1])
        self.assertTrue(row[2].startswith("Evidence only."))
        self.assertIn("No prospecting write", row[2])
        close = (self.workflow / "references/readback.md").read_text()
        self.assertIn("without implying that enrollment authorizes Pipeline writes", close)

    def test_catalog_rows_name_all_pipeline_helpers_both_owner_flags_and_skill_branches(self):
        shared = "\n".join(sections((WORKSPACES / "pipeline" / "CONTEXT.md").read_text())["Shared resources"])
        for helper in sorted(path.stem for path in (WORKSPACES / "pipeline" / "scripts").glob("*.py")):
            self.assertIn(helper, shared)
        row = next(line for line in (CORE / "scripts/interfaces.md").read_text().splitlines() if line.startswith("| `event_list_prep` |"))
        self.assertIn("--outreach-owner-column <col> --outreach-owner-value <v>", row)
        self.assertIn("Owner flags together or neither", row)
        agents = (ROOT / "AGENTS.md").read_text()
        self.assertIn("| `deal-coach` | `workspaces/deal-coaching/workflows/deal-coach/CONTEXT.md` | Call review, pre-meeting, deal review or criteria refresh |", agents)
        self.assertIn("| `forecast-weekly` | `workspaces/forecasting/workflows/forecast-weekly/CONTEXT.md` | Forecast, tracking or manager update |", agents)

    def test_nineteen_routes_and_two_prospecting_workflows(self):
        self.assertEqual(len(SKILLS), 19)
        self.assertIn("| `event-sequence` | `workspaces/prospecting/workflows/event-sequence/CONTEXT.md` | None |",
                      (ROOT / "AGENTS.md").read_text())
        routes = (WORKSPACES / "prospecting" / "CONTEXT.md").read_text()
        self.assertIn("| Named-account event contacts or `event-sequence` | `workflows/event-sequence/CONTEXT.md`", routes)
        self.assertEqual(self.workflow.parent, SIGNAL_WORKFLOW.parent)
        self.assertEqual(workflow_path("signal-scan").parent, SIGNAL_WORKFLOW)
        self.assertEqual(self.workflow_folders(self.workflow.parent), {"signal-prospecting", "event-sequence"})
        self.assertIn("coordinated Event Sequence", (CORE / "CONVENTIONS.md").read_text())

    @staticmethod
    def workflow_folders(directory):
        return {path.name for path in directory.iterdir() if path.is_dir() and not path.name.startswith(".")}

    def test_prospecting_folder_set_ignores_dotfiles_and_nondirectories(self):
        with tempfile.TemporaryDirectory() as folder:
            copied = Path(folder) / "workflows"
            shutil.copytree(self.workflow.parent, copied)
            (copied / ".DS_Store").touch()
            (copied / "extra.txt").touch()
            (copied / ".metadata").mkdir()
            self.assertEqual(self.workflow_folders(copied), {"signal-prospecting", "event-sequence"})

    def test_exact_rule_words_and_proposed_policy_values(self):
        rule = (CORE / "rules.md").read_text().split('<a id="event_sequence"></a>**event_sequence**\n', 1)[1].split('\n\n', 1)[0]
        self.assertEqual(rule.replace("\n  ", " "),
                         "- An event campaign may enroll contacts in an Apollo sequence only after Operator approves the exact contact list, "
                         "sequence copy, sending mailbox, and schedule in the thread. That approval is the only exception to never sending email.\n"
                         "- A pre-enrollment reply recheck may drop or hold approved contacts without re-approval. It never adds contacts.\n"
                         "- Apollo's CRM sync may create or update Salesforce Contacts from approved enrichment or enrollment. "
                         "Each C and E proposal states this. The workflow itself makes no Salesforce writes.\n"
                         "- Apollo sends. A reply stops that contact's sequence and Operator takes over.")
        policy = yaml.safe_load((CORE / "policy.yaml").read_text())
        event = policy["prospecting"]["event"]
        self.assertEqual(event, {
            "exclude": ["open_opportunity", "outside_named_accounts", "recent_reply", "unverified_email", "catch_all_email",
                        "active_sequence", "event_app_invite"],
            "recent_reply_days": 14, "enrich": "missing_or_unverified",
            "enrich_order": ["apollo_match", "apollo_waterfall"], "stop_on_reply": True,
            "steps": ["email", "email", "linkedin_task"], "step_gap_days": 3, "last_touch_before_event_days": 2,
            "outreach_owner_scope": {"house_owner_ids": [],
                                     "include_missing_account": False}})
        self.assertEqual(policy["prospecting"]["approval"]["never"],
                         ["send email outside rules#event_sequence", "create Opportunity", "change deal stage or amount"])
        for key, filename in (("event_list_prep", "event_list_prep.py"), ("event_scrub_leads", "scrub_leads.py"),
                              ("event_make_batches", "make_batches.py")):
            directory = self.workflow if key == "event_list_prep" else self.workflow / "01-list-prep"
            self.assertEqual(policy["tooling"]["scripts"][key],
                             (directory / "scripts" / filename).relative_to(ROOT).as_posix())

    def test_credit_spends_and_waterfall_are_separate_from_enrollment(self):
        for name in ("apollo_people_bulk_match", "run_waterfall_email=true"):
            self.assertIn(name, self.prep)
        self.assertIn("Before every credit spend", self.prep)
        self.assertIn("propose a separate waterfall search and spend", self.prep)
        self.assertIn("the final enrollment approval never authorizes enrichment", self.prep)
        self.assertIn("Verified means Apollo `verified` on a non-catch-all domain, with `catchall_domain` false", self.prep)
        self.assertIn("Unknown catch-all evidence, any error, empty result, or out-of-credits response is unverified", self.prep)
        self.assertIn("Both reports must say PASS", self.prep)
        self.assertIn("--clean-column-profile full", self.prep)
        self.assertIn("domain_mismatch.csv", self.prep)

    def test_outreach_owner_policy_insert_and_scope_rule_are_exact(self):
        policy_text = (CORE / "policy.yaml").read_text()
        policy = yaml.safe_load(policy_text)
        self.assertEqual(policy['prospecting']['event']['outreach_owner_scope'],
                         {'house_owner_ids': [], 'include_missing_account': False})
        agents = (WORKSPACES / "prospecting/AGENTS.md").read_text()
        rule = "For an event list Operator names, rows marked with Operator as outreach owner are in scope when the Salesforce Account is unassigned or missing. Other sellers' Accounts stay out."
        self.assertEqual(agents.count(rule), 1)
        self.assertIn("Event Sequence uses the same named-account scope.\n" + rule, agents)
        for phrase in ("prospecting.event.outreach_owner_scope.house_owner_ids", "completed lookup found no Account",
                       "prospecting.event.outreach_owner_scope.include_missing_account", "Other list overrides cannot expand it."):
            self.assertIn(phrase, agents)

    def test_outreach_owner_contracts_keep_fresh_scope_marker_and_sync_disclosure(self):
        self.assertIn("`prospecting.event.outreach_owner_scope`", self.contract)
        for phrase in ("outreach-owner column and Operator's value", "missing or ambiguous column is needs-input",
                       "--outreach-owner-column", "--outreach-owner-value", "on every helper run, including launch rechecks",
                       "Other sellers' Accounts, including inactive other owners", "scope: outreach_owner",
                       "No other list override can expand it."):
            self.assertIn(phrase, self.prep)
        self.assertIn("except approved outreach-owner rows", (self.workflow / "01-list-prep/CONTEXT.md").read_text())
        launch = (self.workflow / "03-launch/CONTEXT.md").read_text()
        self.assertIn("still house-owned or a completed lookup still finds no Account", launch)
        self.assertIn("Anything else outside named accounts stops", launch)
        self.assertIn("Named-account scope, including the outreach-owner rule, cannot be overridden", self.sequence)
        self.assertIn("Count outreach-owner rows with no Account", self.sequence)
        self.assertIn("Apollo's CRM sync may create Salesforce Contacts for them", self.sequence)
        self.assertIn("Repeat the completed missing-Account lookup", self.sequence)

    def test_event_enrichment_is_apollo_only_and_waterfall_requires_no_verified_email_after_match(self):
        policy_text = (CORE / "policy.yaml").read_text()
        self.assertEqual(yaml.safe_load(policy_text)['prospecting']['event']['enrich_order'],
                         ['apollo_match', 'apollo_waterfall'])
        enrichment = "\n".join(sections(self.prep)["Enrichment"])
        operations = [line for line in enrichment.splitlines() if re.match(r"^\d+\. ", line)]
        self.assertEqual(len(operations), 2)
        self.assertTrue(operations[1].startswith("2. For candidates with no verified email after step 1,"))
        self.assertIn("Only after approval", operations[1])
        self.assertIn("run_waterfall_email=true", operations[1])
        self.assertLess(enrichment.index(operations[0]), enrichment.index(operations[1]))
        self.assertIn("Native Apollo verification status and explicit domain flag.", self.prep)
        frontmatter = yaml.safe_load(self.list_prep.split("---\n", 2)[1])
        self.assertTrue(frontmatter["reads"].endswith("Salesforce, Gmail, Apollo"))

    def test_crm_sync_disclosure_is_in_every_credit_and_enrollment_proposal_and_readback(self):
        enrichment = "\n".join(sections(self.prep)["Enrichment"])
        approval = "\n".join(sections(self.sequence)["Approval"])
        self.assertIn("Every C proposal states that Apollo's CRM sync may create or update Salesforce Contacts", enrichment)
        self.assertIn("Include this in E1 and every revised E proposal", approval)
        self.assertIn("Apollo's CRM sync may create or update Salesforce Contacts from approved enrollment", approval)
        self.assertIn("no direct Salesforce writes", self.contract)
        self.assertIn("Apollo CRM sync disclosed in every C and E proposal", self.contract)
        self.assertIn("native CRM push status from enrichment and enrollment", self.readback)
        self.assertIn("If unavailable, say not checked", self.readback)
        self.assertIn("Never infer a successful Salesforce sync from enrollment counts", self.readback)
        close = "\n".join(sections(self.readback)["Handoff and close"])
        self.assertIn("native CRM push status from any approved enrichment already run", close)
        self.assertIn("even with zero enrollment", close)

    def test_enrichment_selection_and_same_run_domain_fallback_preserve_holds(self):
        enrichment = "\n".join(sections(self.prep)["Enrichment"])
        for requirement in ("whose only exclusion is unverified_email", "Never select enrichment by the needs_input label",
                            "never enrich outside_named_accounts or contacts with other exclusions",
                            "same-run Apollo match flag for the same exact email domain", "Preserve immutable run_start",
                            "Record the inherited flag source", "unknown and held", "not a guessed non-catch-all value or another spend"):
            self.assertIn(requirement, enrichment)
        for name in ("run_start", "apollo_match_run_start", "apollo_match_catchall_domain", "catchall_source", "enrichment_candidates"):
            self.assertIn(name, self.prep)

    def test_exact_domain_matching_and_apollo_invite_checks_precede_e1(self):
        checks = "\n".join(sections(self.prep)["Salesforce and reply checks"])
        for requirement in ("as supersets only", "A wildcard hit never counts as a match",
                            "removing scheme, www, and path", "then compare exact hosts",
                            "Do not collapse subdomains", "Review any subdomain alias explicitly",
                            "Before E1 run `apollo_contacts_search` by each exact email", "following all cursors",
                            "different or personal email", "CRM link owned by another seller", "Show each hold reason in E1",
                            "Unknown active_sequence stays needs-input", "If no export is supplied, E1 says none was checked",
                            "active_sequence and event_app_invite are named, overridable per-list exclusions"):
            self.assertIn(requirement, checks)
        self.assertIn("A returned identity mismatch stops enrollment for a revised proposal", self.sequence)
        self.assertIn("Apollo existing-contact identity holds and reasons", self.sequence)
        self.assertIn("outside_named_accounts", checks)

    def test_permission_error_read_tools_preserve_complete_checks_without_copy_fallback(self):
        readback = "\n".join(sections(self.readback)["Readback"])
        self.assertLess(readback.index("apollo_emailer_campaigns_show"), readback.index("On a permission error only"))
        for requirement in ("use available Apollo campaign and message search tools with complete pages",
                            "counts, active state, stop on reply, and first send",
                            "Missing or mismatched fields stay partial",
                            "Other errors never enable the permission-error search path",
                            "The permission-error search path changes the read tools, never the copy gate"):
            self.assertIn(requirement, readback)
        self.assertNotIn("counts-only", self.readback)
        self.assertNotIn("counts-only", self.contract)

    def test_native_sequence_response_copy_is_saved_and_compared_without_inference(self):
        for requirement in ("Save the full create or update response in the sandbox",
                            "native steps, touches, and templates with subject and body",
                            "Never substitute the approved proposal for returned native copy evidence"):
            self.assertIn(requirement, self.sequence)
        for requirement in ("full saved `apollo_sequences_create` or `apollo_sequences_update` response",
                            "stored steps, touches, and templates with subject and body",
                            "normalizing only the HTML Apollo sanitizes", "Preserve text and links",
                            "Merge variables must match exactly", "Unexplained differences stay partial",
                            "Never infer native copy from the approved proposal alone"):
            self.assertIn(requirement, self.readback)

    def test_scheduled_subjects_require_complete_pages_and_touch_mapping(self):
        for requirement in ("in list mode, paging all returned cursors",
                            "Before the first send, check every scheduled message's `variant.subject`",
                            "approved subject for its `touch_id`", "Complete pages and exact touch mapping",
                            "missing variants, unknown touches, or subject mismatches stay partial"):
            self.assertIn(requirement, self.readback)

    def test_sent_content_check_is_conditional_and_native_verification_is_complete(self):
        for requirement in ("If any step has already sent at readback",
                            "`apollo_emailer_messages_get_content` for each sent email",
                            "same HTML normalization and exact merge-variable checks",
                            'Otherwise state "first send pending, sent-content check not yet run"',
                            "Never use get_content as evidence for unsent messages",
                            "missing sent content stays partial",
                            "create or update response copy, scheduled subjects, counts, active state, stop on reply, and first send all match approval"):
            self.assertIn(requirement, self.readback)
        audit = "\n".join(sections(self.launch)["Audit"])
        for requirement in ("Pre-enrollment copy result, scheduled subjects", "sent-content checks when sent"):
            self.assertIn(requirement, audit)

    def test_no_email_checks_are_deferred_only_for_enrichment_and_completed_before_e1(self):
        enrichment = "\n".join(sections(self.prep)["Enrichment"])
        for requirement in ("For a row with no usable email", "only the exact-email Apollo existing-contact/active-sequence",
                            "supplied invite-export matching and reply checks may wait for the returned address",
                            "Account identity and owner, open-deal, name, duplicate and any existing-Apollo-contact conflict checks must pass first",
                            "row stays needs_input", "On the address enrichment returns", "Do not reuse checks from a missing or different address",
                            "Rerun the helper before E1", "Incomplete results stay needs-input and cannot enroll",
                            "Known-email enrichment still requires all checks complete"):
            self.assertIn(requirement, enrichment)
        self.assertIn("With no usable email, defer only exact-email checks", self.list_prep)

    def test_native_copy_comparison_and_missing_templates_stop_before_real_send_boundary(self):
        enrollment = "\n".join(sections(self.sequence)["Enrollment"])
        save = enrollment.index("Save the full create or update response")
        compare = enrollment.index("Before step 3, compare the saved response with the approved snapshot")
        stop_missing = enrollment.index("If the response has no templates, stop before step 3 and ask Operator")
        stop_mismatch = enrollment.index("Any mismatch or unexplained difference stops before step 3 with one fix proposal")
        send = enrollment.index("3. `apollo_emailer_campaigns_add_contact_ids`")
        activate = enrollment.index("4. `apollo_emailer_campaigns_approve`")
        self.assertLess(save, compare)
        for check in (compare, stop_missing, stop_mismatch):
            self.assertLess(check, send)
        self.assertLess(send, activate)
        for requirement in ('using `references/readback.md` "Readback" copy rules',
                            "Compare steps, touches, subject and body templates, merge variables, schedule and stop on reply",
                            "Normalize only the HTML Apollo sanitizes and require exact merge variables",
                            "Never enroll copy that has not been compared", "Never call add_contact_ids or approve on unmatched copy"):
            self.assertIn(requirement, enrollment)
        self.assertIn("Report the pre-enrollment comparison result", self.readback)
        self.assertIn("Missing templates stop before enrollment and require Operator's input", self.readback)
        self.assertIn("Copy, before enrollment call", "\n".join(sections(self.launch)["Audit"]))

    def test_blocked_campaign_readback_names_schedule_and_mailbox_sources(self):
        for requirement in ("When campaigns_show is blocked on this run, take steps and exact send times from the stored create or update response",
                            "saved `apollo_emailer_campaigns_add_contact_ids` response",
                            "each contact's sending account", "After the first send, also check the sender on get_content results",
                            "If neither shows the mailbox", "accepted enrollment request's `send_email_from_email_account_id`",
                            'labeled "mailbox from accepted enrollment request"',
                            "verified only when the enrollment call succeeded with no errors and the ID matches the approved mailbox",
                            "Missing sources or any mismatch stay partial"):
            self.assertIn(requirement, self.readback)

    def test_bounded_reply_check_is_explicit_and_limited_to_proposals(self):
        for requirement in ("verified Contact address", "through run start, inclusive",
                            "targeted inbound search", "separate sent search", "exact email addresses",
                            "every returned cursor", "every message in each returned Gmail thread",
                            "both searches and all returned thread reads", "false or unknown",
                            "Neither an override nor a null timestamp completes the check",
                            "no substantive reply retrieved", "does not establish complete Gmail history"):
            self.assertIn(requirement, self.prep)
        rules = (CORE / "rules.md").read_text()
        absence = rules.split('<a id="absence_conclusions"></a>', 1)[1].split('<a id=', 1)[0]
        self.assertIn("for the E1 enrollment proposal and its pre-enrollment recheck only", " ".join(absence.split()))
        self.assertIn("It does not establish complete history or authorize enrichment or enrollment. Its stated retrieval limit must appear in the enrollment proposal.", absence)
        self.assertIn("does not establish complete history or authorize enrichment or enrollment", absence)
        approval = self.sequence.split("## Approval\n", 1)[1].split("\n## Enrollment", 1)[0]
        self.assertIn("bounded reply-check summary", approval)
        self.assertIn("window, query shapes, contacts checked, replies found, holds, and the retrieval limit", approval)
        self.assertIn("Attach the saved receipt file to the E1 thread message", approval)

    def test_reply_queries_use_sender_only_inbound_and_never_group_contacts(self):
        self.assertIn("exact Contact sender address over the window in Operator's mailbox, without a recipient restriction", self.prep)
        self.assertIn("inbound `from:<Contact address>`", self.prep)
        self.assertIn("sent `from:<Operator address> to:<Contact address>`", self.prep)
        self.assertIn("Run each Contact separately, never grouped searches", self.prep)
        self.assertNotIn("from that Contact to Operator", self.prep)
        self.assertIn("the E1 enrollment proposal and its pre-enrollment recheck only", self.prep)

    def test_run_start_exceptions_are_only_the_three_named_checks(self):
        rules = (CORE / "rules.md").read_text()
        run_start = rules.split('<a id="run_start"></a>**run_start**\n', 1)[1].split('\n\n', 1)[0]
        self.assertEqual(run_start,
                         '- Read the `_core/policy.yaml` blocks and `_core/rules.md` anchors the contract cites.\n'
                         "- Record one run-start ISO datetime with the user's local offset. "
                         "Every helper's `--since` or `--as-of` takes it, except three checks that record and take a fresh local-offset time.\n"
                         "  The event_list_prep pre-enrollment reply recheck and the triage pre-write reply recheck also end their reply search at that time.\n"
                         "  The pipeline-review post-write `hygiene_check` uses it on re-queried records. "
                         "A fresh time never changes scope, lookback, pagination, approvals or readback, and never authorizes a write.\n"
                         '- Take userId and owner email from `salesforce_rest_api-get-current-user`.')
        enrollment = self.sequence.split("## Enrollment\n", 1)[1]
        self.assertIn("`--as-of` set to that recheck time, never the old run start", enrollment)

    def test_pre_enrollment_reply_recheck_only_narrows_the_approved_snapshot(self):
        enrollment = self.sequence.split("## Enrollment\n", 1)[1]
        for requirement in ("from the saved window end through the recheck time, inclusive",
                            "sender-only inbound searches, separate sent searches, full thread reads",
                            "same saved reviewed rows in their original order",
                            "Update `replies_checked` from the recheck, never reuse the earlier true marker",
                            "`--as-of` set to that recheck time, never the old run start",
                            "do not carry a prior recent_reply override forward",
                            "Drop approved Contacts newly labeled `recent_reply`",
                            "hold Contacts whose reply recheck is incomplete",
                            "without re-approval", "never add or replace a Contact",
                            "copy, mailbox, or schedule differs, stop and present a revised exact proposal",
                            "If no recipients remain, skip every Apollo call"):
            self.assertIn(requirement, enrollment)
        self.assertLess(enrollment.index("Re-run the bounded reply check"), enrollment.index("apollo_contacts_bulk_create"))
        process = "\n".join(sections(self.launch)["Process"])
        self.assertIn("fresh `--as-of`", process)
        self.assertIn("without re-approval or additions", process)
        freshness = next(row for row in sections(self.launch)["Audit"] if row.startswith("| Freshness,"))
        self.assertIn("only drops or holds approved contacts", freshness)
        self.assertIn("schedule changes require revision", freshness)

    def test_e1_and_recheck_receipts_attach_evidence_and_reconcile_drops(self):
        for requirement in ("window endpoints", "exact query shapes", "contacts checked", "substantive replies found",
                            "holds and reasons", "Attach that saved receipt file to the E1 thread message"):
            self.assertIn(requirement, self.prep)
        self.assertNotIn("with links to its saved receipts", self.sequence)
        self.assertIn("Attach the saved receipt file to the E1 thread message, not a sandbox-path link", self.sequence)
        self.assertIn("Save and attach the recheck receipt", self.sequence)
        for requirement in ("remaining approved Contacts plus reported drops and holds", "remaining approved recipients",
                            "Reply recheck", "exact dropped and held lists with reasons",
                            "Attach its saved receipt file to the thread message"):
            self.assertIn(requirement, self.readback)

    def test_early_no_enrollment_close_does_not_require_or_run_a_reply_recheck(self):
        process = "\n".join(sections(self.contract)["Process"])
        self.assertIn('close directly through shared "Handoff and close"', process)
        audit = "\n".join(sections(self.contract)["Audit"])
        self.assertIn("With no recipients and no remaining enrichment", audit)
        self.assertIn("without nonexistent-file audits, E approval, Launch entry or an unneeded recheck", audit)
        close = "\n".join(sections(self.readback)["Handoff and close"])
        for requirement in ("If a reply recheck ran", "Attach its saved receipt file to the thread message",
                            "Otherwise close with the original exclusions, holds, and handoff evidence",
                            "pre-enrollment recheck was not reached", "Never run a recheck just to fill the receipt",
                            "skip Apollo calls", "report zero enrolled with no sends"):
            self.assertIn(requirement, close)
        _, receipt_rows = table_rows(sections(self.readback)["Readback"])
        reply_row = next(row for row in receipt_rows if row[0] == "Reply recheck")
        self.assertTrue(reply_row[1].startswith("When run,"))

    def test_approval_and_fresh_guards_precede_real_send_boundary(self):
        process = "\n".join(sections(self.contract)["Process"])
        self.assertLess(process.index("enter Sequence Plan with a viable prepared list"), process.index("Enter Launch only with Operator's exact native E approval"))
        for name in ("apollo_contacts_bulk_create", "apollo_sequences_create", "apollo_sequences_update",
                     "apollo_emailer_campaigns_add_contact_ids", "apollo_emailer_campaigns_approve"):
            self.assertIn(name, self.sequence)
        self.assertLess(self.sequence.index("apollo_contacts_bulk_create"), self.sequence.index("apollo_sequences_create"))
        self.assertLess(self.sequence.index("apollo_sequences_create"), self.sequence.index("apollo_emailer_campaigns_add_contact_ids"))
        self.assertLess(self.sequence.index("apollo_emailer_campaigns_add_contact_ids"), self.sequence.index("apollo_emailer_campaigns_approve"))
        self.assertIn("exact contact list, sequence copy, sending mailbox, and schedule", self.sequence)
        self.assertIn("cannot be undone once sent", self.sequence)
        self.assertIn("stop and present a revised exact proposal", self.sequence)
        self.assertIn("Never blindly reenroll", self.sequence)

    def test_native_readback_and_pipeline_handoff_end_without_salesforce_writes(self):
        for name in ("apollo_emailer_campaigns_show", "apollo_emailer_messages_search", "list mode",
                     "actual enrolled Contact IDs and email addresses", "first-send date and time", "stop-on-reply setting",
                     "partial", "one exact fix proposal", "Pipeline thread", "Operator takes over"):
            self.assertIn(name, self.readback)
        self.assertIn("no direct Salesforce writes", self.contract)
        self.assertIn("Event-sequence writes no Salesforce records", (WORKSPACES / "prospecting" / "AGENTS.md").read_text())
        self.assertIn("No direct Salesforce writes", "\n".join(sections(self.contract)["Audit"]))
        self.assertIn("Workers do not directly message other sessions", self.readback)
        self.assertIn("The workflow ends here", self.readback)
        self.assertIn("never Git", self.readback)

    def test_no_enrollment_routes_to_handoff_without_an_empty_file_audit(self):
        self.assertIn('shared prep "No enrollment"', self.list_prep)
        self.assertIn('close directly through shared "Handoff and close"', self.contract)
        self.assertIn("For a nonempty candidate list, scrub and standalone audit both PASS", self.list_prep)
        no_enrollment = self.prep.split("## No enrollment\n", 1)[1].split("\n## Helper evidence", 1)[0]
        self.assertIn("no enrichment remains to propose or perform", no_enrollment)
        self.assertIn("audit of nonexistent clean files", no_enrollment)
        self.assertIn("preserve the open-Opportunity handoff list", no_enrollment)
        self.assertIn("skip Apollo calls and report zero enrolled with no sends", self.readback)

    def test_campaign_and_each_spend_define_exact_approval_responses(self):
        self.assertIn("Label it E1", self.sequence)
        self.assertIn("Label each spend C1, C2", self.prep)
        for reference in (self.sequence, self.prep):
            self.assertIn("Accept only its displayed label or `approved <label>` under `rules#approval`", reference)
        self.assertIn("next unused E label", self.sequence)

    def test_root_event_route_and_migrated_scrubber_authoring_paths(self):
        self.assertIn("prepare named-account event lists", (ROOT / "CONTEXT.md").read_text())
        scrubber = (self.workflow / "01-list-prep/references/scrubber.md").read_text()
        self.assertIn("adjacent `scripts/email_rules.json`", scrubber)
        self.assertIn("-m unittest _core.tests.test_event_scrub_leads", scrubber)
        self.assertNotIn("<skill-folder>", scrubber)

    def test_scrubber_is_full_column_hygiene_not_external_verification(self):
        scrubber = (self.workflow / "01-list-prep/references/scrubber.md").read_text()
        for requirement in ("deterministic CSV hygiene after Apollo email verification",
                            "does not prove email verification, authorize credit spending or approve enrollment",
                            "policy.tooling.scripts.event_scrub_leads", "--clean-column-profile full",
                            "policy.tooling.scripts.event_make_batches", "including Website for batch domain checks",
                            "default `--clean-column-profile upload`", "reduced clean-column profile",
                            "Removed rows retain source and diagnostic columns",
                            "Keep removed and quarantined rows out of enrollment",
                            "separately audit", "output_manifest.json"):
            self.assertIn(requirement, scrubber)
        for obsolete in ("email validator", "email verifier", "external email validation", "Python 3.9+"):
            self.assertNotIn(obsolete, scrubber)


class ICMRefactorContracts(unittest.TestCase):
    def test_runtime_setup_and_registry_notation_have_one_existing_home(self):
        interfaces = (CORE / "scripts" / "interfaces.md").read_text()
        running = "\n".join(sections(interfaces)["Running"])
        for requirement in ("Python 3.12 or later", "PyYAML and pypdf", "outside the repository", "python3.12 -m venv /tmp/",
                            "--version", "import yaml, pypdf", "packages it actually imports",
                            "policy.tooling.scripts.<key> <args>", "resolved in the checkout",
                            "working directory this section names for that helper",
                            "prerequisite gap, not a repository defect"):
            self.assertIn(requirement, running)
        conventions = "\n".join(sections((CORE / "CONVENTIONS.md").read_text())["Tests and maintenance"])
        self.assertIn('`_core/scripts/interfaces.md` "Running"', conventions)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s _core/tests", conventions)
        self.assertIn("in that active environment", conventions)
        for duplicate in ("Python 3.12", "PyYAML", "pypdf", "/tmp/sales-maintenance-venv", "prerequisite gap"):
            self.assertNotIn(duplicate, conventions)
        for workflow in skill_dirs():
            self.assertNotIn("| Runtime |", (workflow / "CONTEXT.md").read_text())

    def test_helper_working_directories_and_research_semantics_are_preserved(self):
        running = "\n".join(sections((CORE / "scripts" / "interfaces.md").read_text())["Running"])
        self.assertIn("Coverage and forecast notification run from the sandbox root. Pilot commands run from the checkout with explicit sandbox input/output paths, as the pilot-usage contract shows.", running)
        self.assertIn("Pipeline rendering with its default `--sources` also runs from the sandbox root.", running)
        research = (workflow_path("signal-scan") / "CONTEXT.md").read_text()
        for requirement in ("Keep nonqualifying evidence and fit objections in the report.",
                            "Batch mode never pools evidence across accounts.",
                            "Adoption resolves ambiguous identity before lookup"):
            self.assertIn(requirement, research)

    def test_pdf_prerequisites_are_local_to_pdf_mode(self):
        workflow = WORKSPACES / "pipeline" / "workflows" / "pilot-usage"
        pdf = (workflow / "references" / "pdf-format.md").read_text()
        for requirement in ("Python 3.12 or later", "PyYAML and pypdf", "Report any unavailable prerequisite before building",
                            "`chromium`, `google-chrome`, then `chromium-browser`",
                            "~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome",
                            "policy.pilot_usage.pdf.fonts", "policy SHA256", "without downloading",
                            "pdftoppm", "PyMuPDF", "image viewer", "do not prove PDF production"):
            self.assertIn(requirement, pdf)
        self.assertIn('`references/pdf-format.md` | Full file, PDF mode at steps 3 to 7', (workflow / "CONTEXT.md").read_text())

    def test_operational_prospecting_invocations_resolve_registered_keys(self):
        paths = ("signal-prospecting/01-research/CONTEXT.md", "signal-prospecting/01-research/references/buying-signals.md",
                 "signal-prospecting/01-research/references/adoption.md", "signal-prospecting/02-outreach/CONTEXT.md",
                 "signal-prospecting/02-outreach/references/execution.md", "signal-prospecting/03-followup/references/execution.md",
                 "event-sequence/01-list-prep/references/scrubber.md", "event-sequence/01-list-prep/CONTEXT.md",
                 "event-sequence/03-launch/CONTEXT.md")
        registry = yaml.safe_load((CORE / "policy.yaml").read_text())["tooling"]["scripts"]
        for path in paths:
            text = (WORKSPACES / "prospecting" / "workflows" / path).read_text()
            operational = "\n".join(line for line in text.splitlines() if not line.startswith("|"))
            self.assertNotRegex(operational, r"workspaces/[^`\s]+\.(?:py|sql)")
            keys = re.findall(r"policy\.tooling\.scripts\.([a-z_]+)", operational)
            self.assertTrue(keys, path)
            for key in keys:
                self.assertIn(key, registry)
                self.assertTrue((ROOT / registry[key]).is_file())

    def test_post_write_hygiene_clock_and_customer_review_scope_remain_explicit(self):
        proposals = WORKSPACES / "pipeline" / "workflows" / "pipeline-review" / "references" / "proposals.md"
        text = proposals.read_text()
        self.assertIn("Per `rules#run_start`, record a fresh local-offset time", text)
        self.assertIn("pipeline-review post-write `hygiene_check`", text)
        self.assertIn("`--as-of` on those re-queried records", text)
        collect = WORKSPACES / "pipeline" / "workflows" / "customer-review" / "references" / "collect.md"
        self.assertIn("blocks expansion proposals", collect.read_text())
        self.assertIn("It never produces renewal notices or renewal holds", collect.read_text())


class PipelineSlackEvidence(unittest.TestCase):
    def setUp(self):
        self.workflow = workflow_path("pipeline-review")
        self.contract = (self.workflow / "CONTEXT.md").read_text()
        self.collect = (self.workflow / "references" / "collect.md").read_text()
        self.report = (self.workflow / "references" / "report-format.md").read_text()

    def test_policy_and_contract_route_slack_evidence(self):
        policy_text = (CORE / "policy.yaml").read_text()
        self.assertIn(
            "  slack_lookback_days: 14          # Slack DM and shared-channel window per deal or contact (pipeline-review, forecast-weekly, task-triage-speed-run)\n",
            policy_text,
        )
        self.assertEqual(yaml.safe_load(policy_text)["tooling"]["slack_lookback_days"], 14)
        self.assertIn("Slack", yaml.safe_load(self.contract.split("---\n", 2)[1])["reads"])
        self.assertIn("policy.tooling.slack_lookback_days", self.contract)
        contract_sections = sections(self.contract)
        self.assertIn("Saved Salesforce, Gmail, Calendar, and Slack results in the sandbox",
                      "\n".join(contract_sections["Inputs"]))
        self.assertIn("Check the freshest dated Salesforce, Gmail, Calendar, and Slack evidence",
                      "\n".join(contract_sections["Process"]))
        evidence_audit = next(line for line in contract_sections["Audit"] if line.startswith("| Evidence,"))
        self.assertIn("Salesforce, Gmail, Calendar, or Slack evidence", evidence_audit)

    def test_proposal_clauses_include_slack_and_keep_friday_pilot_exception(self):
        drafting=(workflow_path('task-triage-speed-run')/'references/next-steps.md').read_text()
        self.assertIn('Every clause traces to Salesforce, Gmail, Calendar, or Slack evidence',drafting)
        proposals=(self.workflow/'references/proposals.md').read_text()
        self.assertIn('rules#pilot_handoff',proposals)
        self.assertNotIn('Build each next-step proposal',proposals)

    def test_slack_collection_uses_named_buyers_and_bounded_read_only_searches(self):
        self.assertIn("FROM OpportunityContactRole", (ROOT / "workspaces/pipeline/references/deal-activity-reads.md").read_text())
        self.assertIn("even for deals not flagged by Gmail or Salesforce", self.collect)
        slack = self.collect.split("## Slack\n", 1)[1] + (CORE / "slack-evidence.md").read_text()
        for expected in ("Contact Roles and `Customer_Point_of_Contact__c`", "verified Contact and email",
                         "slack_direct", "slack_search_users", "Contact's last name as a `keywords` array",
                         "full name as `natural_language_query`", "multi-word last-name keyword in double quotes",
                         'response_format="detailed"', 'limit=20', "paging through all returned cursors",
                         "returned `Email:` value", "verified Salesforce Contact email, case-insensitive",
                         "The name is only the search key, never identity proof", "exact Contact email match",
                         "policy.tooling.slack_lookback_days", "run timezone", "Unix epoch seconds",
                         "slack_search_public_and_private", "string `after` and `before` parameters",
                         'content_types="messages"', 'include_bots=false', 'include_context=true',
                         'filters="with:<@SlackUserId>"', 'channel_types="im,mpim"',
                         'filters="from:<@SlackUserId>"', 'channel_types="public_channel,private_channel"',
                         'keywords=[]', 'natural_language_query=""', "verified Slack Connect channels",
                         "Keep date words and date filters out of `keywords`, `filters` and `natural_language_query`",
                         "returned message `ts` values", "only its own returned cursor", "until none remains",
                         "Save all search inputs, pages, and identity results in the sandbox",
                         "scheduled runs with no per-run consent pause", "read-only. Never post or react",
                         "Exclude bot messages from evidence and context", "returned permalink and date"):
            self.assertIn(expected, slack)

    def test_slack_search_never_uses_obsolete_query_parameter(self):
        search = "\n".join(sections((CORE / "slack-evidence.md").read_text())["Search"])
        self.assertNotRegex(search, r"\bquery\b")

    def test_slack_gaps_and_freshness_remain_explicit(self):
        slack = self.collect.split("## Slack\n", 1)[1] + (CORE / "slack-evidence.md").read_text()
        for expected in ("No Slack user means that contact is `not checked` for Slack", "rules#not_checked_means",
                         "rules#absence_conclusions", "absence is not evidence", "not full history",
                         "Slack is an added evidence source, not a required coverage gate",
                         "Missing identities and empty Slack results never set `run.process_status` to `incomplete`",
                         "run.slack_coverage_notes", "They do not add to the deal-level not-checked count"):
            self.assertIn(expected, slack)
        self.assertIn("freshest dated evidence across Gmail, Calendar, Salesforce, and Slack wins", self.collect)
        for expected in ("source `Slack`", "`date`, `who`, `title`, `link`, and `fact`",
                         "returned permalink", "freshest dated evidence across Salesforce, Gmail, Calendar, and Slack",
                         "once in each section that shows Gmail, Calendar, or Slack evidence",
                         "checker does not verify Slack coverage", "Missing Slack users or evidence are Slack not checked",
                         "These notes do not affect status, counts, withholding, or notification",
                         "Its existing affected-deal withholding and incomplete-run behavior stay unchanged",
):
            self.assertIn(expected, self.report)

    def test_slack_limits_gate_only_verified_user_status_changes(self):
        slack = self.collect.split("## Slack\n", 1)[1] + (CORE / "slack-evidence.md").read_text()
        for expected in ("A Slack user is verified only after an exact Contact email match",
                         "A failed identity lookup does not establish a verified Slack user",
                         "Withhold a buyer-status or commitment change for a Slack limit only when a search errored or was incomplete",
                         "for a contact on that deal with a verified Slack user",
                         "Needs your input with no write option until that search is repaired",
                         "Keep unrelated changes on the same deal and proposals on other deals eligible",
                         "Do not put the whole deal in `withheld` because of a Slack limit",
                         "separate them before assigning proposal labels",
                         "Positive Slack facts stay usable and win when fresher"):
            self.assertIn(expected, slack)
        for expected in ("no write option until the search is repaired", "Split mixed proposals before assigning labels",
                         "Do not add the deal to `withheld` for Slack alone",
                         "Preserve unrelated changes on the same deal and other deals",
                         "Positive Slack facts remain usable and win when fresher"):
            self.assertIn(expected, self.report)
        audit = next(line for line in sections(self.contract)["Audit"] if line.startswith("| Slack limits,"))
        self.assertIn("verified user's search errored or was incomplete", audit)
        self.assertIn("Unrelated changes remain eligible", audit)


class PilotPdfPolicyReference(unittest.TestCase):
    def test_pilot_pdf_example_cites_policy_confidentiality_label(self):
        pdf_format = (workflow_path('pilot-usage') / 'references' / 'pdf-format.md').read_text()
        self.assertIn('"confidentiality_label": "<policy.pilot_usage.pdf.confidentiality_label>"', pdf_format)
        self.assertNotIn('"Confidential"', pdf_format)


if __name__ == "__main__":
    unittest.main()
