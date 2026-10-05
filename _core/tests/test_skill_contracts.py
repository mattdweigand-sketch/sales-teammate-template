"""Every contract and reference names only things that exist.

A saved project skill points to its declared workflow or stage contract, with an explicit branch when the contract is shared.
This test resolves what the repo's markdown references:

- the root holds only README.md, AGENTS.md, CONTEXT.md, .gitignore, .github/, _core/, and workspaces/
- every workflow has one declared workspace owner and an execution contract
- every `policy.<dotted>` key against _core/policy.yaml
- every `rules#<anchor>` against the anchors defined in _core/rules.md
- every backticked core, workspace, or workflow path against the checkout
- every `<script>.py` named in markdown against core, workspace and workflow scripts/
- every `policy.tooling.scripts` path exists
- every skill in the AGENTS.md table has a CONTEXT.md with cadence, reads, writes, next frontmatter
- shared rules have at least two workflow consumers, except visible auto_date_move and event_sequence permission exceptions

A cite that does not resolve fails here instead of at run time.
"""
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
          "agent-configuration": "systems", "system-review": "systems"}
SKILLS.update({'signal-scan': 'prospecting', 'signal-user-scan': 'prospecting', 'signal-outreach': 'prospecting', 'signal-followup': 'prospecting'})
SKILLS["watch-sync"] = "pipeline"
SKILLS["event-sequence"] = "prospecting"
CONTRACT_PATHS = {name: WORKSPACES / owner / "workflows" / name / "CONTEXT.md" for name, owner in SKILLS.items() if owner != "prospecting"}
SIGNAL_STAGES = {'signal-scan': 'research', 'signal-user-scan': 'research',
                 'signal-outreach': 'outreach', 'signal-followup': 'followup'}
CONTRACT_PATHS.update({name: WORKSPACES / 'prospecting' / 'workflows' / stage / 'CONTEXT.md'
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
    return sorted(path.parent for path in WORKSPACES.glob("*/workflows/**/CONTEXT.md"))


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

    def test_workflow_ownership_and_layout(self):
        dirs = skill_dirs()
        self.assertEqual(dirs, sorted({path.parent for path in CONTRACT_PATHS.values()}))
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
            self.assertLessEqual(entries, required | {"references", "scripts"}, workspace.name)
            for folder in entries & {"references", "scripts"}:
                self.assertTrue((workspace / folder).is_dir())
                self.assertTrue(layout_entries(workspace / folder), f"empty {workspace.name}/{folder}")
            for entry in ("AGENTS.md", "CONTEXT.md"):
                self.assertTrue((workspace / entry).is_file())
        paths = [str(p.relative_to(ROOT)).casefold() for p in WORKSPACES.rglob("*")]
        self.assertEqual(len(paths), len(set(paths)))

    def test_no_retired_workflow_paths(self):
        retired_group = "signal-" + "prospecting"
        retired_skill = "signal-" + "prospector"
        retired = re.compile(r"workspaces/0[1-5]-|workflows/0[1-8]-|" + retired_group + "|" + retired_skill)

        def check(path):
            self.assertNotRegex(path.read_text(), retired, str(path))

        self.assertFalse((ROOT / "workflows").exists())
        for base in (CORE, WORKSPACES, ROOT / ".github"):
            for path in base.rglob("*"):
                if path.is_file() and path.suffix in {".md", ".py", ".yaml", ".yml"}:
                    check(path)
        for entry in ("README.md", "AGENTS.md", "CONTEXT.md"):
            check(ROOT / entry)

    def test_script_registry_paths_exist(self):
        missing = [f"{k}: {v}" for k, v in self.policy["tooling"]["scripts"].items() if not (ROOT / v).is_file()]
        self.assertEqual(missing, [])
        helpers = (CORE / "scripts/CONTEXT.md").read_text().split("## Helpers\n", 1)[1].split("\n## ", 1)[0]
        homes = dict(re.findall(r"^\| `([a-z_]+)` \| `([^`]+)` \|", helpers, re.M))
        self.assertEqual(set(homes), set(self.policy["tooling"]["scripts"]))
        for key, target in self.policy["tooling"]["scripts"].items():
            self.assertEqual((ROOT / homes[key]).resolve(), (ROOT / target).parent.resolve(), key)

    def test_policy_keys_resolve(self):
        missing = []
        for f in self.files:
            for key in set(POLICY_REF.findall(f.read_text())):
                if key in POLICY_ALLOW or policy_has(self.policy, key):
                    continue
                missing.append(f"{f.relative_to(ROOT)}: policy.{key}")
        self.assertEqual(missing, [])

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
        for c in (ROOT, CORE, *layout_entries(WORKSPACES)):
            text = (c / "CONTEXT.md").read_text()
            for p in set(re.findall(r"`(\.\./[A-Za-z0-9_./-]+|[a-z-]+/[A-Za-z0-9_./-]+\.md)`", text)):
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
            cited = {k.split(".")[0] for p in d.rglob("*.md") for k in POLICY_REF.findall(p.read_text())}
            missing = sorted(cited - declared)
            if missing:
                gaps.append(f"{d.name}: reads omits {missing}")
        self.assertEqual(gaps, [])

    def test_rules_are_shared_except_explicit_workflow_approval_exceptions(self):
        """Shared rules have two consumers; explicit permission exceptions stay visible in core."""
        cited_by = {a: set() for a in self.anchors}
        for d in skill_dirs():
            text = "\n".join(p.read_text() for p in d.rglob("*.md"))
            for a in set(RULE_REF.findall(text)):
                if a in cited_by:
                    cited_by[a].add(d.name)
        self.assertEqual(cited_by.pop("auto_date_move"), {"task-triage-speed-run"})
        self.assertEqual(cited_by.pop("event_sequence"), {"event-sequence"})
        lonely = sorted(f"rules#{a} cited by {sorted(s)}" for a, s in cited_by.items() if len(s) < 2)
        self.assertEqual(lonely, [])

    def test_permission_exception_bodies_are_byte_identical(self):
        rules = (CORE / "rules.md").read_bytes()
        expected = {
            "auto_date_move": "3f00b2998177234143fdd82ce4e43cbeec4bc50dc6b15bd901e915b27a1884d6",
            "event_sequence": "419e66948351c6ecfd3f1d6314534760e823a97df33d1ff5a8978fbc33427b47",
        }
        for anchor, digest in expected.items():
            with self.subTest(anchor=anchor):
                marker = f'<a id="{anchor}"></a>**{anchor}**\n'.encode()
                body = rules.split(marker, 1)[1].split(b"\n\n", 1)[0]
                self.assertEqual(hashlib.sha256(body).hexdigest(), digest)



if __name__ == "__main__":
    unittest.main()
