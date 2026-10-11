"""Every contract and reference names only things that exist.

A saved project skill points to its declared workflow or stage contract, with an explicit branch when the contract is shared.
This test resolves what the repo's markdown references:

- the root holds only README.md, AGENTS.md, CONTEXT.md, .gitignore, .github/, _core/, and workspaces/
- every workflow has one declared workspace owner and an execution contract
- every `policy.<dotted>` key against _core/policy.yaml
- every policy key in an execution contract and its loaded reference sections against its policy Inputs scopes
- every `rules#<anchor>` against the anchors defined in _core/rules.md
- every backticked core, workspace, or workflow path against the checkout
- every `<script>.py` named in markdown against core, workspace and workflow scripts/
- every `policy.tooling.scripts` path exists
- every skill in the AGENTS.md table has a CONTEXT.md with cadence, reads, writes, next frontmatter
- shared rules have at least two workflow consumers, except the visible event_sequence permission exception

A cite that does not resolve fails here instead of at run time.
"""
import ast
import hashlib
import re
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
WORKSPACES = ROOT / "workspaces"
CADENCE_VALUES = {"daily", "weekly", "monthly", "one-off"}

POLICY_REF = re.compile(r"(?<![A-Za-z0-9_])policy\.((?!yaml\b)[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*)")
RULE_REF = re.compile(r"rules#([a-z_]+)")
RULE_DEF = re.compile(r'<a id="([a-z_]+)"></a>')
REPO_PATH = re.compile(r"`((?:_core|workspaces|workflows)/[A-Za-z0-9_./<>-]+)`")
ROOT_ENTRIES = {".git", ".gitignore", ".github", ".pplx", "README.md", "AGENTS.md", "CONTEXT.md", "_core", "workspaces"}
SKILLS = {"sales-call-prep": "pipeline", "interaction-sync": "pipeline", "pipeline-review": "pipeline",
          "task-triage-speed-run": "pipeline", "forecast-weekly": "forecasting", "pilot-usage": "pipeline",
          "close": "pipeline", "customer-review": "pipeline", "deal-coach": "deal-coaching", "repo-maintenance": "systems",
          "agent-configuration": "systems", "system-review": "systems", "process-capture": "systems"}
SKILLS.update({'signal-scan': 'prospecting', 'signal-user-scan': 'prospecting', 'signal-outreach': 'prospecting', 'signal-followup': 'prospecting'})
SKILLS["watch-sync"] = "pipeline"
SKILLS["event-sequence"] = "prospecting"
CONTRACT_PATHS = {name: WORKSPACES / owner / "workflows" / name / "CONTEXT.md" for name, owner in SKILLS.items() if owner != "prospecting"}
SIGNAL_STAGES = {'signal-scan': '01-research', 'signal-user-scan': '01-research',
                 'signal-outreach': '02-outreach', 'signal-followup': '03-followup'}
SIGNAL_WORKFLOW = WORKSPACES / "prospecting/workflows/signal-prospecting"
EVENT_WORKFLOW = WORKSPACES / "prospecting/workflows/event-sequence"
EVENT_STAGE_ORDER = ("01-list-prep", "02-sequence-plan", "03-launch")
EVENT_STAGE_PATHS = {EVENT_WORKFLOW / stage / "CONTEXT.md" for stage in EVENT_STAGE_ORDER}
COORDINATOR_PATHS = {EVENT_WORKFLOW / "CONTEXT.md"}
OVERVIEW_PATHS = {SIGNAL_WORKFLOW / "CONTEXT.md"}
CONTRACT_PATHS.update({name: SIGNAL_WORKFLOW / stage / 'CONTEXT.md'
                      for name, stage in SIGNAL_STAGES.items()})
SKILL_BRANCHES = {'signal-scan': 'Buying signals', 'signal-user-scan': 'Adoption'}
CONTRACT_PATHS["event-sequence"] = WORKSPACES / "prospecting" / "workflows" / "event-sequence" / "CONTEXT.md"
SKILL_PATHS = {name: path.parent for name, path in CONTRACT_PATHS.items()}
SCRIPT_REF = re.compile(r"`([a-z_]+\.py)`")
AGENTS_ROW = re.compile(r"^\| `([a-z-]+)` \| `([^`]+)` \|", re.M)

# Policy sub-keys that contracts name in prose but that are dict members, list items, or
# placeholders rather than keys. Add here only with the reason.
POLICY_ALLOW = set()


def markdown_files():
    files = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CONTEXT.md", CORE / "CONVENTIONS.md", CORE / "rules.md", CORE / "CONTEXT.md",
             CORE / "scripts" / "CONTEXT.md", CORE / "scripts" / "interfaces.md",
             CORE / "templates" / "workflow-context-template.md", CORE / "slack-evidence.md"]
    files.extend(sorted(WORKSPACES.rglob("*.md")))
    return [f for f in files if f.exists()]


def skill_dirs():
    return sorted({path.parent for path in set(CONTRACT_PATHS.values()) | EVENT_STAGE_PATHS})


def owning_workflow(directory):
    parts = directory.resolve().parts
    index = parts.index("workflows")
    return Path(*parts[:index + 2])


def workflow_owner(directory):
    """The descriptive workflow parent, including for a nested stage."""
    while directory.parent.name != 'workflows':
        directory = directory.parent
    return directory


def input_reference_rows(contract):
    """Resolved Markdown Inputs citations only. Prose elsewhere is not a consumer."""
    text = contract.read_text().split('## Inputs\n', 1)[1].split('\n## ', 1)[0]
    for line in text.splitlines():
        if not line.startswith('|') or line.startswith(('| Source', '|---')):
            continue
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        for ref in re.findall(r'`([^`]+\.md)`', cells[1]):
            target = ROOT / ref if ref.startswith(('_core/', 'workspaces/')) else contract.parent / ref
            yield target.resolve(), cells[2]


def reference_consumers(reference, contracts=None):
    """Require owning Inputs. Shared stage references also require exact valid headings."""
    contracts = contracts if contracts is not None else [d / 'CONTEXT.md' for d in skill_dirs()]
    if not reference.is_file():
        return []
    home = reference.resolve().parent.parent
    flow = workflow_owner(home)
    shared = home == flow and any(flow.glob('*/CONTEXT.md'))
    real_headings = set(re.findall(r'^#{1,6} (.+)$', reference.read_text(), re.M))
    consumers = []
    for contract in contracts:
        if workflow_owner(contract.resolve().parent) != flow or (not shared and contract.resolve().parent != home):
            continue
        for target, scope in input_reference_rows(contract):
            if target != reference.resolve():
                continue
            named = re.findall(r'"([^"]+)"', scope)
            if shared and (not named or 'full file' in scope.lower() or not set(named) <= real_headings):
                continue
            if not scope or (named and not set(named) <= real_headings):
                continue
            consumers.append(contract)
    return consumers



def inputs_rows(text):
    if "## Inputs\n" not in text:
        return []
    section = text.split("## Inputs\n", 1)[1].split("\n## ", 1)[0]
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in section.splitlines()
            if line.startswith("| ")][1:]


def reference_is_loaded(contract, reference, text=None):
    if text is None:
        return contract in reference_consumers(reference, [contract])
    from unittest.mock import patch
    original = Path.read_text
    with patch.object(Path, 'read_text', lambda path, *a, **kw: text if path == contract else original(path, *a, **kw)):
        return contract in reference_consumers(reference, [contract])


def loaded_contract_text(directory):
    text = (directory / "CONTEXT.md").read_text()
    loaded = [text]
    for row in inputs_rows(text):
        for route in re.findall(r"`([^`]+\.md)`", row[1]):
            target = ROOT / route if route.startswith(("workspaces/", "_core/")) else directory / route
            if "references" in target.parts and target.is_file():
                source = target.read_text()
                scopes = re.findall(r'"([^"]+)"', row[2])
                if scopes:
                    for scope in scopes:
                        match = re.search(r"^#{1,6} " + re.escape(scope) + r"\n(.*?)(?=^#{1,6} |\Z)", source, re.M | re.S)
                        if match:
                            loaded.append(match.group(0))
                else:
                    loaded.append(source)
    return "\n".join(loaded)


def policy_input_scopes(text):
    scopes = set()
    for row in inputs_rows(text):
        if len(row) != 4 or "`_core/policy.yaml`" not in row[1]:
            continue
        quoted = re.findall(r"`([^`]+)`", row[2])
        candidates = quoted if quoted else row[2].split(",")
        for candidate in candidates:
            scope = candidate.strip().removeprefix("policy.")
            if re.fullmatch(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*", scope):
                scopes.add(scope)
    return scopes


def policy_scope_gaps(directory):
    scopes = policy_input_scopes((directory / "CONTEXT.md").read_text())
    return sorted(key for key in set(POLICY_REF.findall(loaded_contract_text(directory)))
                  if not any(key == scope or key.startswith(scope + ".") for scope in scopes))


def retired_signal_references(text, python=False):
    parent = "workspaces/prospecting/workflows/"
    direct = ("research", "outreach", "followup")
    retired = [parent + name + "/" for name in direct]
    retired += [parent + "signal-prospecting/" + name + "/" for name in ("prospect", *direct)]
    retired += [parent + "event-sequence/" + name for name in
                ("references/scrubber.md", "scripts/scrub_leads.py", "scripts/make_batches.py", "scripts/email_rules.json")]
    candidates = [text]
    if python:
        symbols = {}

        def resolve(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            if isinstance(node, ast.Name):
                return symbols.get(node.id, "")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Path" and node.args:
                return resolve(node.args[0])
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                return "/".join(part.strip("/") for part in (resolve(node.left), resolve(node.right)) if part)
            return ""

        for node in ast.parse(text).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        symbols[target.id] = resolve(node.value)
            candidates += [resolve(expression).strip("/") + "/" for expression in ast.walk(node)
                           if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Div)]
    violations = []
    for candidate in candidates:
        violations += [route for route in retired if re.search(r"(?<![A-Za-z0-9_-])" + re.escape(route), candidate)]
        children = re.findall(re.escape(parent + "signal-prospecting/") + r"([^\s`/\"']+)", candidate)
        violations += [child for child in children if child not in {"CONTEXT.md", "01-research", "02-outreach", "03-followup"}]
        children = re.findall(re.escape(parent + "event-sequence/") + r"([^\s`/\"']+)", candidate)
        violations += [child for child in children if child not in {"CONTEXT.md", "references", "scripts", *EVENT_STAGE_ORDER}]
    return violations


def layout_entries(directory):
    """Ignore Finder metadata while retaining every other unexpected entry."""
    return [path for path in directory.iterdir() if path.name != ".DS_Store"]


def skill_name(d):
    return d.name


def body_after_frontmatter(text):
    if text.startswith("---\n"):
        return text.split("---\n", 2)[2].lstrip("\n")
    return text


def frontmatter(text):
    if not text.startswith("---\n"):
        return None
    return yaml.safe_load(text.split("---\n", 2)[1])


def policy_has(policy, dotted):
    cur = policy
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return False
    return True


class SkillContractReferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = yaml.safe_load((CORE / "policy.yaml").read_text())
        cls.rules_text = (CORE / "rules.md").read_text()
        cls.anchors = set(RULE_DEF.findall(cls.rules_text))
        cls.scripts = {p.name for p in (CORE / "scripts").rglob("*.py")} | {p.name for p in WORKSPACES.rglob("scripts/**/*.py")}
        cls.files = markdown_files()

    def test_root_holds_only_the_entry_files(self):
        self.assertEqual(sorted(p.name for p in layout_entries(ROOT) if p.name not in ROOT_ENTRIES), [])

    def test_close_customer_type_stop_excludes_api(self):
        self.assertEqual(self.policy["close"]["customer_type_stop"], ["Sovereign AI"])

    def test_layout_ignores_only_finder_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            for name in (".DS_Store", "CONTEXT.md", "unexpected.txt"):
                (directory / name).touch()
            self.assertEqual({path.name for path in layout_entries(directory)}, {"CONTEXT.md", "unexpected.txt"})
        self.assertIn(".DS_Store", (ROOT / ".gitignore").read_text().splitlines())

    def test_private_reference_loads_through_symlinked_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workflow = root / "checkout/workspaces/pipeline/workflows/synthetic"
            reference = workflow / "references/evidence.md"
            reference.parent.mkdir(parents=True)
            reference.write_text("# Evidence\n")
            contract = workflow / "CONTEXT.md"
            contract.write_text('## Inputs\n\n| Source | File/Location | Section/Scope | Why |\n'
                                '|---|---|---|---|\n| Evidence | `references/evidence.md` | Full file | Check |\n')
            alias = root / "alias"
            alias.symlink_to(root / "checkout", target_is_directory=True)
            linked_contract = alias / contract.relative_to(root / "checkout")
            self.assertTrue(reference_is_loaded(contract, reference))
            self.assertTrue(reference_is_loaded(linked_contract, reference))

    def test_workflow_ownership_and_layout(self):
        dirs = skill_dirs()
        self.assertEqual(dirs, sorted({path.parent for path in set(CONTRACT_PATHS.values()) | EVENT_STAGE_PATHS}))
        self.assertEqual(set(WORKSPACES.glob("*/workflows/**/CONTEXT.md")), set(CONTRACT_PATHS.values()) | EVENT_STAGE_PATHS | OVERVIEW_PATHS)
        self.assertEqual({path.name for path in layout_entries(SIGNAL_WORKFLOW)},
                         {"CONTEXT.md", "01-research", "02-outreach", "03-followup"})
        self.assertIsNone(frontmatter((SIGNAL_WORKFLOW / "CONTEXT.md").read_text()))
        self.assertEqual({path.name for path in layout_entries(EVENT_WORKFLOW)},
                         {"CONTEXT.md", "references", "scripts", *EVENT_STAGE_ORDER})
        for d in dirs:
            self.assertTrue((d / "CONTEXT.md").is_file(), f"{d.name}/CONTEXT.md missing")
        for owner in set(SKILLS.values()):
            folder = WORKSPACES / owner / "workflows"
            expected = {path.relative_to(folder).parts[0] for path in dirs if path.is_relative_to(folder)}
            self.assertEqual({path.name for path in layout_entries(folder)}, expected, owner)
        self.assertEqual(sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("procedure.md")), [])
        self.assertEqual(sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("README.md")), ["README.md"])

    def test_workspace_entries_and_case_insensitive_paths(self):
        self.assertEqual({p.name for p in layout_entries(WORKSPACES)}, set(SKILLS.values()))
        self.assertEqual(set(SKILLS.values()), {"prospecting", "pipeline", "deal-coaching", "forecasting", "systems"})
        for workspace in layout_entries(WORKSPACES):
            entries = {p.name for p in layout_entries(workspace)}
            required = {"AGENTS.md", "CONTEXT.md", "workflows"}
            self.assertTrue(required <= entries, workspace.name)
            optional = {"references", "scripts"} | ({"captures"} if workspace.name == "systems" else set())
            self.assertLessEqual(entries, required | optional, workspace.name)
            for folder in entries & {"references", "scripts"}:
                self.assertTrue((workspace / folder).is_dir())
                self.assertTrue(layout_entries(workspace / folder), f"empty {workspace.name}/{folder}")
            for entry in ("AGENTS.md", "CONTEXT.md"):
                self.assertTrue((workspace / entry).is_file())
        paths = [str(p.relative_to(ROOT)).casefold() for p in WORKSPACES.rglob("*")]
        self.assertEqual(len(paths), len(set(paths)))

    def test_no_retired_workflow_paths(self):
        retired_skill = "signal-" + "prospector"
        retired = re.compile(r"(?:^|[^A-Za-z0-9_-])(?:workspaces/0[1-5]-|workflows/0[1-8]-|" + retired_skill + ")")

        def check(path):
            self.assertNotRegex(path.read_text(), retired, str(path))
            self.assertEqual(retired_signal_references(path.read_text(), path.suffix == ".py"), [], str(path))

        self.assertFalse((ROOT / "workflows").exists())
        for base in (CORE, WORKSPACES, ROOT / ".github"):
            for path in base.rglob("*"):
                if path.is_file() and path.suffix in {".md", ".py", ".yaml", ".yml"}:
                    check(path)
        for entry in ("README.md", "AGENTS.md", "CONTEXT.md"):
            check(ROOT / entry)

    def test_retired_path_guard_rejects_old_components_and_undeclared_stages(self):
        parent = "/".join(("workspaces", "prospecting", "workflows"))
        for child in ("research", "outreach", "followup"):
            self.assertTrue(retired_signal_references(parent + "/" + child + "/CONTEXT.md"))
            self.assertTrue(retired_signal_references("/sandbox/" + parent + "/" + child + "/CONTEXT.md"))
            code = f'WORKFLOWS = ROOT / "{parent}"\nSCRIPT = WORKFLOWS / "{child}" / "scripts"\n'
            self.assertTrue(retired_signal_references(code, python=True))
            self.assertFalse((ROOT / parent / child).exists())
        for child in ("prospect", "research", "outreach", "followup", "04-extra", "stages"):
            self.assertTrue(retired_signal_references(parent + "/signal-prospecting/" + child + "/CONTEXT.md"))
            self.assertFalse((SIGNAL_WORKFLOW / child).exists())
        for child in ("CONTEXT.md", "01-research/CONTEXT.md", "02-outreach/CONTEXT.md", "03-followup/CONTEXT.md"):
            self.assertEqual(retired_signal_references(parent + "/signal-prospecting/" + child), [])
        for child in ("references/scrubber.md", "scripts/scrub_leads.py", "scripts/make_batches.py", "scripts/email_rules.json", "04-extra/CONTEXT.md"):
            self.assertTrue(retired_signal_references(parent + "/event-sequence/" + child))
            parts = child.split("/")
            code = f'WORKFLOW = ROOT / "{parent}" / "event-sequence"\nSCRIPT = WORKFLOW' + ''.join(f' / "{part}"' for part in parts) + '\n'
            self.assertTrue(retired_signal_references(code, python=True))
        for child in ("CONTEXT.md", "references/prep.md", "references/readback.md", "references/sequence.md", "scripts/event_list_prep.py",
                      "01-list-prep/scripts/scrub_leads.py", "02-sequence-plan/CONTEXT.md", "03-launch/CONTEXT.md"):
            self.assertEqual(retired_signal_references(parent + "/event-sequence/" + child), [])

    def test_script_registry_paths_exist(self):
        missing = [f"{k}: {v}" for k, v in self.policy["tooling"]["scripts"].items() if not (ROOT / v).is_file()]
        self.assertEqual(missing, [])
        helpers = (CORE / "scripts/CONTEXT.md").read_text().split("## Helpers\n", 1)[1].split("\n## ", 1)[0]
        homes = dict(re.findall(r"^\| `([a-z_]+)` \| `([^`]+)` \|", helpers, re.M))
        self.assertEqual(set(homes), set(self.policy["tooling"]["scripts"]))
        for key, target in self.policy["tooling"]["scripts"].items():
            self.assertEqual((ROOT / homes[key]).resolve(), (ROOT / target).parent.resolve(), key)

    def test_catalog_callers_name_every_contract_that_loads_the_helper(self):
        catalog = (CORE / "scripts/CONTEXT.md").read_text()
        rows = {m.group(1): m.group(2) for m in re.finditer(r"^\| `([a-z_]+)` \| `[^`]+` \| ([^|]+) \|$", catalog, re.M)}
        for caller in ("pipeline-review", "task-triage-speed-run", "watch-sync", "customer-review", "interaction-sync"):
            self.assertIn(caller, rows["deal_thread_match"])
            self.assertIn("deal_thread_match", loaded_contract_text(ROOT / "workspaces/pipeline/workflows" / caller))
        self.assertIn("Event List Prep and Launch through event_list_prep", rows["prospect_common"])
        self.assertIn("closeout_check", rows["_saved_json"])
        self.assertIn("from _saved_json import", (ROOT / "workspaces/pipeline/workflows/task-triage-speed-run/scripts/closeout_check.py").read_text())
        self.assertIn("import prospect_common", (ROOT / "workspaces/prospecting/workflows/event-sequence/scripts/event_list_prep.py").read_text())
        batches = next(line for line in (CORE / "scripts/interfaces.md").read_text().splitlines() if line.startswith("| `event_make_batches` |"))
        for expected in ("Missing names or email are dropped and counted.", "Domain mismatches are held unless allowed.", "Missing Website is reported not checked."):
            self.assertIn(expected, batches)
        self.assertLessEqual(len(batches), 300)
        self.assertIn("| A task or event without a skill name | Root `CONTEXT.md`, then the owning workspace's AGENTS.md and CONTEXT.md |", (ROOT / "AGENTS.md").read_text())

    def test_import_only_core_libraries_are_cataloged(self):
        catalog = (CORE / "scripts/CONTEXT.md").read_text()
        libraries = catalog.split("## Libraries\n", 1)[1].split("\n## ", 1)[0]
        listed = set(re.findall(r"^\| `([a-z_]+)` \| `_core/scripts/` \|", libraries, re.M))
        import_only = {path.stem for path in (CORE / "scripts").glob("*.py") if "__main__" not in path.read_text()}
        self.assertEqual(listed, import_only)
        self.assertFalse(listed & set(self.policy["tooling"]["scripts"]))

    def test_policy_keys_resolve(self):
        missing = []
        for f in self.files:
            for key in set(POLICY_REF.findall(f.read_text())):
                if key in POLICY_ALLOW or policy_has(self.policy, key):
                    continue
                missing.append(f"{f.relative_to(ROOT)}: policy.{key}")
        self.assertEqual(missing, [])

    def test_inputs_cover_loaded_policy_keys(self):
        gaps = [f"{directory.relative_to(ROOT)}: policy.{key}"
                for directory in skill_dirs() for key in policy_scope_gaps(directory)]
        self.assertEqual(gaps, [], "\n".join(gaps))

    def test_policy_input_scopes_read_only_keys_in_policy_scope_cells(self):
        text = ('## Inputs\n\n| Source | File/Location | Section/Scope | Why |\n|---|---|---|---|\n'
                '| Policy | `_core/policy.yaml` | prospecting.outreach, prospecting.identity | policy.prospecting |\n'
                '| Policy | `_core/policy.yaml` | `pipeline.stages`, pipeline triage settings when deployed, `tooling` | Check |\n'
                '| Policy | `_core/policy.yaml` | Both branches load `forecast`. Also load `policy.salesforce.note_prefix` | Check |\n'
                '| Reference | `references/evidence.md` | `email_voice` | Check |\n')
        self.assertEqual(policy_input_scopes(text), {"prospecting.outreach", "prospecting.identity", "pipeline.stages",
                                                    "tooling", "forecast", "salesforce.note_prefix"})

    def test_policy_scope_gaps_honor_loaded_sections_and_key_ancestors(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            reference = directory / "references/evidence.md"
            reference.parent.mkdir()
            reference.write_text('# Evidence\n\n## Loaded\nUse policy.forecast.schedule.\n'
                                 '\n## Other stage\nUse policy.prospecting.event.steps.\n')
            contract = directory / "CONTEXT.md"
            template = ('## Inputs\n\n| Source | File/Location | Section/Scope | Why |\n|---|---|---|---|\n'
                        '| Policy | `_core/policy.yaml` | {scope} | Check |\n'
                        '| Reference | `references/evidence.md` | "Loaded" | Check |\n'
                        '\n## Process\n1. Use policy.forecast.amount_field.\n')
            contract.write_text(template.format(scope="forecast.amount_field"))
            self.assertEqual(policy_scope_gaps(directory), ["forecast.schedule"])
            contract.write_text(template.format(scope="forecast.amount"))
            self.assertEqual(policy_scope_gaps(directory), ["forecast.amount_field", "forecast.schedule"])
            contract.write_text(template.format(scope="forecast"))
            self.assertEqual(policy_scope_gaps(directory), [])
            contract.write_text(template.format(scope="forecast") + '2. Use policy.salesforce.note_prefix.\n')
            self.assertEqual(policy_scope_gaps(directory), ["salesforce.note_prefix"])
            contract.write_text(template.format(scope="forecast, salesforce.note_prefix") + '2. Use policy.salesforce.note_prefix.\n')
            self.assertEqual(policy_scope_gaps(directory), [])

    def test_rule_anchors_resolve(self):
        missing = []
        for f in self.files:
            for a in set(RULE_REF.findall(f.read_text())):
                if a not in self.anchors:
                    missing.append(f"{f.relative_to(ROOT)}: rules#{a}")
        self.assertEqual(missing, [])

    def test_repo_paths_resolve(self):
        missing = []
        for f in self.files:
            text = f.read_text()
            for p in set(REPO_PATH.findall(text)):
                if "<" in p:
                    continue  # pattern like workflows/<name>/
                target = ROOT / p
                if f.parent != ROOT and not target.exists():
                    target = (f.parent / p).resolve()
                if not target.exists():
                    missing.append(f"{f.relative_to(ROOT)}: {p}")
        self.assertEqual(missing, [])

    def test_relative_contract_paths_resolve(self):
        missing = []
        for c in (ROOT, CORE, *layout_entries(WORKSPACES), SIGNAL_WORKFLOW, *skill_dirs()):
            text = (c / "CONTEXT.md").read_text()
            for p in set(re.findall(r"`(\.\./[A-Za-z0-9_./-]+|[a-z0-9.-]+/[A-Za-z0-9_./-]+\.md)`", text)):
                if not (c / p).resolve().exists() and not (ROOT / p).exists():
                    missing.append(f"{c.name}/CONTEXT.md: {p}")
        self.assertEqual(missing, [])

    def test_scripts_resolve(self):
        missing = []
        for f in self.files:
            for s in set(SCRIPT_REF.findall(f.read_text())):
                if s not in self.scripts:
                    missing.append(f"{f.relative_to(ROOT)}: {s}")
        self.assertEqual(missing, [])

    def test_agents_table_matches_folders(self):
        agents = (ROOT / "AGENTS.md").read_text()
        rows = {name: body for name, body in AGENTS_ROW.findall(agents) if body.endswith("CONTEXT.md")}
        folders = {name: str(path.relative_to(ROOT)) for name, path in CONTRACT_PATHS.items()}
        self.assertEqual(rows, folders)
        for body in rows.values():
            self.assertTrue((ROOT / body).exists(), body)

    def test_contract_frontmatter(self):
        for d in skill_dirs():
            fm = frontmatter((d / "CONTEXT.md").read_text())
            self.assertIsNotNone(fm, f"{d.name}: no frontmatter")
            self.assertEqual(set(fm), {"cadence", "reads", "writes", "next"}, d.name)
            if d.name == "deal-coach":
                self.assertEqual(fm["cadence"], {
                    "call-review": "daily",
                    "pre-meeting": "daily",
                    "deal-review": "weekly",
                    "criteria-refresh": "monthly",
                }, d.name)
            elif d.name == "system-review":
                self.assertEqual(fm["cadence"], "Friday", d.name)
            elif d.name in {"interaction-sync", "sales-call-prep", "task-triage-speed-run"}:
                self.assertEqual(fm["cadence"], ["daily", "one-off"], d.name)
            elif d.name == "customer-review":
                self.assertEqual(fm["cadence"], ["monthly", "one-off"], d.name)
            else:
                self.assertIn(fm["cadence"], CADENCE_VALUES, d.name)

    def test_template_advertises_supported_monthly_and_list_cadences(self):
        template = (CORE / "templates/workflow-context-template.md").read_text()
        expected = "cadence: <daily | weekly | monthly | one-off, or a list such as [monthly, one-off]>"
        self.assertEqual(template.splitlines()[1], expected)
        for value, parsed in (("monthly", "monthly"), ("[monthly, one-off]", ["monthly", "one-off"])):
            with self.subTest(value=value):
                cadence = frontmatter(template.replace(expected, "cadence: " + value))["cadence"]
                self.assertEqual(cadence, parsed)
                values = cadence if isinstance(cadence, list) else [cadence]
                self.assertTrue(set(values) <= CADENCE_VALUES)

    def test_reads_declares_every_cited_policy_block(self):
        """The `reads` frontmatter names every top-level policy block the skill folder cites directly."""
        gaps = []
        for d in skill_dirs():
            text = (d / "CONTEXT.md").read_text()
            fm = frontmatter(text)
            m = re.search(r"_core/policy\.yaml \(([^)]*)\)", fm["reads"])
            declared = {b.strip() for b in m.group(1).split(",")} if m else set()
            cited = {key.split(".")[0] for key in POLICY_REF.findall(loaded_contract_text(d))}
            missing = sorted(cited - declared)
            if missing:
                gaps.append(f"{d.name}: reads omits {missing}")
        self.assertEqual(gaps, [])

    def test_rules_are_shared_except_explicit_workflow_approval_exceptions(self):
        """Shared rules have two consumers; explicit permission exceptions stay visible in core."""
        cited_by = {a: set() for a in self.anchors}
        for d in skill_dirs():
            text = loaded_contract_text(d)
            for a in set(RULE_REF.findall(text)):
                if a in cited_by:
                    cited_by[a].add(owning_workflow(d).name)
        self.assertEqual(cited_by.pop("event_sequence"), {"event-sequence"})
        lonely = sorted(f"rules#{a} cited by {sorted(s)}" for a, s in cited_by.items() if len(s) < 2)
        self.assertEqual(lonely, [])

    def test_permission_exception_bodies_are_byte_identical(self):
        rules = (CORE / "rules.md").read_bytes()
        expected = {
            "event_sequence": "419e66948351c6ecfd3f1d6314534760e823a97df33d1ff5a8978fbc33427b47",
        }
        for anchor, digest in expected.items():
            with self.subTest(anchor=anchor):
                marker = f'<a id="{anchor}"></a>**{anchor}**\n'.encode()
                body = rules.split(marker, 1)[1].split(b"\n\n", 1)[0]
                self.assertEqual(hashlib.sha256(body).hexdigest(), digest)



if __name__ == "__main__":
    unittest.main()
