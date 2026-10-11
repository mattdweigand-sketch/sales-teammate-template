#!/usr/bin/env python3
"""Fetch the configured deployed branch and compare the scoped sources governing one write proposal.

Usage: workflow_revision_check.py --repo <checkout> --scope <sandbox.json>
       --phase snapshot|prewrite [--baseline <saved-result.json>]
Scope: {contract: <active CONTEXT.md>, sources: [{path, kind, selector?}]} or
{deal_thread_entry: workspaces/pipeline/AGENTS.md, sources: [...]}. A deal thread
need not claim or load a workflow it never ran.
Kinds are file bytes, Markdown section, rule anchor, policy key, or interface row.
Snapshot the actual consumed sections, keys and helpers, not all sibling Inputs.
The actual workflow contract or Pipeline entry, shared write/approval/currency rules and this helper's
registry, interface and bytes are always included. No automatic workflow loading.

Each invocation fetches the configured repository, remote and branch through Git authentication. It
never checks out, resets, stashes or modifies source/index files. Git's existing
object database and its configured tracking ref are updated. Saved evidence stays in the
sandbox. Relevant worktree/index differences hold; unrelated work is preserved.
Prewrite locks the saved scope and recomputes its old Git fingerprints instead
of trusting caller-written current hashes. Missing legacy baselines hold.

Outcomes: unchanged (exit 0), changed or needs-input (exit 1). Snapshot output
contains snapshot evidence to save unchanged with the displayed proposal.
Prewrite takes that full saved output. These outcomes never authorize a write.
The caller must declare all actually consumed sources, reread changed governing
instructions and obtain a fresh proposal/approval. Reads/approval, invocation at
the native write boundary and subsequent remote changes cannot be authenticated
or locked by this helper. No CRM, Gmail, Apollo or message calls.
"""

import argparse
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import urlsplit
from typing import Literal, NotRequired, TypedDict

import yaml


class WorkflowSourceSelection(TypedDict):
    path: str
    kind: Literal["file", "section", "rule", "policy", "row"]
    selector: NotRequired[str]


class WorkflowContractScope(TypedDict):
    contract: str
    sources: list[WorkflowSourceSelection]


class PipelineDealThreadScope(TypedDict):
    deal_thread_entry: Literal["workspaces/pipeline/AGENTS.md"]
    sources: list[WorkflowSourceSelection]


WorkflowRevisionScope = WorkflowContractScope | PipelineDealThreadScope


class WorkflowSourceFingerprint(TypedDict):
    source: WorkflowSourceSelection
    sha256: str


class WorkflowRevisionSnapshot(TypedDict):
    format: int
    target: dict[str, str]
    revision: str
    scope: WorkflowRevisionScope
    fingerprints: list[WorkflowSourceFingerprint]


class WorkflowRevisionChange(TypedDict):
    source: WorkflowSourceSelection
    reason: str


class WorkflowRevisionResult(TypedDict):
    status: Literal["unchanged", "changed", "needs-input"]
    reasons: list[str]
    changes: list[WorkflowRevisionChange]
    revision: NotRequired[str]
    snapshot: NotRequired[WorkflowRevisionSnapshot]


def _git_failure_reason(operation: str, return_code: int, stderr: bytes) -> str:
    text = stderr.decode("utf-8", errors="replace").lower()
    categories = (
        ("authentication or access denied", ("authentication failed", "permission denied", "could not read username", "could not read password", "error: 401", "error: 403", "returned error: 401", "returned error: 403")),
        ("requested deployment ref is missing", ("couldn't find remote ref", "could not find remote ref", "remote ref does not exist")),
        ("local tracking ref conflict", ("cannot lock ref", "non-fast-forward", "would clobber", "unable to update local ref", "reference broken")),
        ("transport connection failed", ("could not resolve host", "couldn't resolve host", "failed to connect", "connection refused", "connection reset", "unable to access")),
        ("remote unavailable or invalid repository", ("does not appear to be a git repository", "repository not found", "not a git repository")),
    )
    category = next((label for label, patterns in categories if any(pattern in text for pattern in patterns)), "unclassified Git failure")
    return f"Git operation failed: {operation} (exit {return_code}, {category})"


def _git_bytes(repo: Path, *arguments: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *arguments], capture_output=True, check=False, timeout=60)
    if result.returncode:
        raise ValueError(_git_failure_reason(arguments[0], result.returncode, result.stderr))
    return result.stdout


def _source_path(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", value):
        raise ValueError("source requires a repository-relative path")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or ".." in path.parts or str(path) != value or (path.parts[0] not in ("_core", "workspaces") and value not in ("AGENTS.md", "CONTEXT.md")):
        raise ValueError("source path is outside the scoped repository resources")
    return value


def _normalized_scope(scope: object) -> WorkflowRevisionScope:
    if not isinstance(scope, Mapping):
        raise ValueError("scope requires an execution contract or Pipeline deal-thread entry and consumed sources")
    if set(scope) == {"contract", "sources"}:
        entry = _source_path(scope["contract"])
        if not entry.startswith("workspaces/") or "/workflows/" not in entry or not entry.endswith("/CONTEXT.md"):
            raise ValueError("workflow scope must name one active execution contract")
        entry_kind = "contract"
    elif set(scope) == {"deal_thread_entry", "sources"}:
        entry = _source_path(scope["deal_thread_entry"])
        if entry != "workspaces/pipeline/AGENTS.md":
            raise ValueError("deal-thread scope requires the actual Pipeline workspace entry")
        entry_kind = "deal_thread_entry"
    else:
        raise ValueError("scope must name exactly one execution contract or Pipeline deal-thread entry and consumed sources")
    sources = scope["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("consumed source selections are missing")
    required = [
        {"path": entry, "kind": "file"},
        *({"path": "_core/rules.md", "kind": "rule", "selector": anchor}
          for anchor in ("write_protocol", "approval", "repo_currency")),
        {"path": "_core/policy.yaml", "kind": "policy", "selector": "tooling.scripts.workflow_revision_check"},
        {"path": "_core/policy.yaml", "kind": "policy", "selector": "tooling.governing_revision"},
        {"path": "_core/scripts/workflow_revision_check.py", "kind": "file"},
        {"path": "_core/scripts/interfaces.md", "kind": "row", "selector": "workflow_revision_check"},
        {"path": "_core/scripts/interfaces.md", "kind": "section", "selector": "Workflow revisions"},
    ]
    selected = {}
    for source in sources + required:
        if not isinstance(source, dict) or source.get("kind") not in ("file", "section", "rule", "policy", "row"):
            raise ValueError("source kind is invalid")
        path = _source_path(source.get("path"))
        kind, selector = source["kind"], source.get("selector")
        if set(source) != ({"path", "kind"} if kind == "file" else {"path", "kind", "selector"}):
            raise ValueError("source fields do not match its selection kind")
        if kind != "file" and (not isinstance(selector, str) or not selector.strip() or "\n" in selector or "\r" in selector):
            raise ValueError("source selector is missing or malformed")
        if kind in ("policy", "rule") and path != {"policy": "_core/policy.yaml", "rule": "_core/rules.md"}[kind]:
            raise ValueError("specialized selector must use its canonical source")
        if path in ("_core/policy.yaml", "_core/rules.md") and kind != {"_core/policy.yaml": "policy", "_core/rules.md": "rule"}[path]:
            raise ValueError("canonical policy and rules require scoped keys or anchors, not whole files or sections")
        normalized = {"path": path, "kind": kind, **({"selector": selector} if kind != "file" else {})}
        selected[json.dumps(normalized, sort_keys=True)] = normalized
    sources = [selected[key] for key in sorted(selected)]
    if entry_kind == "contract":
        return {"contract": entry, "sources": sources}
    return {"deal_thread_entry": "workspaces/pipeline/AGENTS.md", "sources": sources}


def _markdown_boundary_text(text: str) -> str:
    fence, width = None, 0
    lines = []
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)", line)
        if fence is not None:
            lines.append(re.sub(r"[^\r\n]", " ", line))
            if marker and marker[1][0] == fence and len(marker[1]) >= width and not marker[2].strip():
                fence = None
        elif marker and not (marker[1][0] == "`" and "`" in marker[2]):
            fence, width = marker[1][0], len(marker[1])
            lines.append(re.sub(r"[^\r\n]", " ", line))
        else:
            lines.append(line)
    return "".join(lines)


def _selected_bytes(content: bytes, source: WorkflowSourceSelection) -> bytes:
    kind, selector = source["kind"], source.get("selector")
    if kind == "file":
        return content
    text = content.decode("utf-8")
    if kind == "policy":
        value = yaml.safe_load(text)
        for key in selector.split("."):
            if not isinstance(value, dict) or key not in value:
                raise ValueError("selected policy key is missing")
            value = value[key]
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if kind == "row":
        matches = [line for line in text.splitlines() if line.startswith("| ") and
                   line.split("|")[1].replace("`", "").strip() == selector]
        if len(matches) != 1:
            raise ValueError("selected interface row is missing or ambiguous")
        return matches[0].encode()
    structure = _markdown_boundary_text(text)
    if kind == "rule":
        starts = list(re.finditer(r'^<a id="' + re.escape(selector) + r'"></a>.*$', structure, re.M))
        if len(starts) != 1:
            raise ValueError("selected rule anchor is missing or ambiguous")
        start = starts[0].start()
        boundary = re.search(r'^<a id=|^#{1,6} ', structure[starts[0].end():], re.M)
        end = starts[0].end() + boundary.start() if boundary else len(text)
    else:
        headings = list(re.finditer(r'^(#{1,6}) (.+)$', structure, re.M))
        matches = [heading for heading in headings if heading[2] == selector]
        if len(matches) != 1:
            raise ValueError("selected Markdown section is missing or ambiguous")
        start = matches[0].start()
        following = [heading for heading in headings if heading.start() > start and len(heading[1]) <= len(matches[0][1])]
        end = following[0].start() if following else len(text)
    return (text[start:end].rstrip() + "\n").encode()


def _git_source(repo: Path, revision: str, path: str) -> bytes:
    metadata = _git_bytes(repo, "ls-tree", revision, "--", path).decode().split()
    if len(metadata) != 4 or metadata[0] not in ("100644", "100755") or metadata[1] != "blob":
        raise ValueError("selected Git source is missing or not a regular file: " + path)
    return _git_bytes(repo, "show", revision + ":" + path)


def _fingerprints(repo: Path, revision: str, scope: WorkflowRevisionScope) -> list[WorkflowSourceFingerprint]:
    contents = {path: _git_source(repo, revision, path) for path in {source["path"] for source in scope["sources"]}}
    return [{"source": source, "sha256": hashlib.sha256(_selected_bytes(contents[source["path"]], source)).hexdigest()}
            for source in scope["sources"]]


def _repository_identity(value: str) -> str:
    """Normalize supported GitHub HTTPS/SSH identities without exposing credentials."""
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        raise ValueError("configured repository identity is missing or malformed")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        value = "https://github.com/" + value
    if value.startswith("git@"):
        match = re.fullmatch(r"git@([A-Za-z0-9.-]+):([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", value)
        if not match:
            raise ValueError("unsupported GitHub SSH repository identity")
        host, path = match.groups()
    else:
        try:
            parsed = urlsplit(value)
            host, port = parsed.hostname, parsed.port
        except ValueError:
            raise ValueError("repository URL is malformed") from None
        if (parsed.scheme not in ("https", "ssh") or not parsed.hostname or parsed.password
                or parsed.query or parsed.fragment or port
                or (parsed.scheme == "https" and parsed.username)
                or (parsed.scheme == "ssh" and parsed.username != "git")):
            raise ValueError("unsupported or credential-bearing repository URL")
        host, path = host, parsed.path.lstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host):
        raise ValueError("repository host is malformed")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", path):
        raise ValueError("repository must identify one owner and repository")
    owner, name = path.split("/")
    name = name.removesuffix(".git")
    if owner in (".", "..") or name in ("", ".", ".."):
        raise ValueError("repository identity is malformed")
    return host.lower() + "/" + owner.lower() + "/" + name.lower()


def _governing_target(repo: Path) -> dict[str, str]:
    policy = yaml.safe_load((repo / "_core/policy.yaml").read_text())
    if not isinstance(policy, dict) or policy.get("template", {}).get("mode") not in ("configured", "demo"):
        raise ValueError("onboard and deploy the configured workspace before write freshness checks")
    target = policy.get("tooling", {}).get("governing_revision")
    if not isinstance(target, dict) or set(target) != {"repository", "remote", "branch"}:
        raise ValueError("configure tooling.governing_revision for the deployed workspace")
    remote, branch, repository = target["remote"], target["branch"], target["repository"]
    if not isinstance(remote, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", remote):
        raise ValueError("configured remote is missing or unsafe")
    if not isinstance(branch, str) or branch.startswith("-"):
        raise ValueError("configured deployment branch is missing or unsafe")
    _git_bytes(repo, "check-ref-format", "refs/heads/" + branch)
    urls = _git_bytes(repo, "remote", "get-url", "--all", remote).decode().splitlines()
    if len(urls) != 1:
        raise ValueError("configured remote requires exactly one fetch URL")
    # Explicit fixture identities are allowed only in local demo rehearsal.
    if isinstance(repository, str) and repository.startswith("fixture:"):
        if policy.get("template", {}).get("mode") != "demo":
            raise ValueError("fixture repository is restricted to demo evidence")
        expected = Path(repository.removeprefix("fixture:"))
        if not expected.is_absolute() or expected.resolve() != Path(urls[0]).resolve():
            raise ValueError("fixture remote does not match the configured fixture identity")
        identity = "fixture:" + str(expected.resolve())
    else:
        identity = _repository_identity(repository)
        if _repository_identity(urls[0]) != identity:
            raise ValueError("fetch remote differs from the configured deployment repository")
    return {"repository": identity, "remote": remote, "branch": branch}


def check_workflow_revision(
    repo: Path, scope: WorkflowRevisionScope, *, phase: Literal["snapshot", "prewrite"],
    baseline: WorkflowRevisionResult | None = None,
) -> WorkflowRevisionResult:
    """Compare actual Git/local scoped bytes without granting write authority."""
    changes: list[WorkflowRevisionChange] = []
    try:
        repo = Path(_git_bytes(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        scope = _normalized_scope(scope)
        target = _governing_target(repo)
        if phase not in ("snapshot", "prewrite"):
            raise ValueError("snapshot or prewrite phase is required")
        if phase == "prewrite":
            if not isinstance(baseline, dict) or baseline.get("status") != "unchanged" or not isinstance(baseline.get("snapshot"), dict):
                raise ValueError("missing successful historical snapshot, refresh and present a new proposal")
            saved = baseline["snapshot"]
            if (type(saved.get("format")) is not int or saved["format"] != 2
                    or saved.get("scope") != scope or saved.get("target") != target):
                raise ValueError("saved scope is missing or cannot be substituted during prewrite")
            if not isinstance(saved.get("revision"), str) or not re.fullmatch(r"[0-9a-f]{40}", saved["revision"]):
                raise ValueError("historical snapshot revision is invalid")
            if baseline.get("revision") != saved["revision"] or baseline.get("changes") != [] or baseline.get("reasons") != []:
                raise ValueError("successful snapshot receipt is missing or inconsistent with its historical evidence")
        tracking = "refs/remotes/" + target["remote"] + "/" + target["branch"]
        _git_bytes(repo, "fetch", "--no-tags", target["remote"], "refs/heads/" + target["branch"] + ":" + tracking)
        revision = _git_bytes(repo, "rev-parse", tracking).decode().strip()
        current = _fingerprints(repo, revision, scope)
        if phase == "prewrite":
            _git_bytes(repo, "merge-base", "--is-ancestor", saved["revision"], revision)
            historical = _fingerprints(repo, saved["revision"], scope)
            if saved.get("fingerprints") != historical:
                raise ValueError("saved fingerprints do not match historical Git objects")
            for old, fresh in zip(historical, current):
                if old["sha256"] != fresh["sha256"]:
                    changes.append({"source": fresh["source"], "reason": "deployed branch scope changed"})
        for fingerprint in current:
            source = fingerprint["source"]
            local = repo / source["path"]
            if local.is_symlink() or not local.resolve().is_relative_to(repo) or not local.is_file():
                raise ValueError("actual used source is missing or unsafe: " + source["path"])
            for label, content in (("worktree", local.read_bytes()), ("index", _git_bytes(repo, "show", ":" + source["path"]))):
                if hashlib.sha256(_selected_bytes(content, source)).hexdigest() != fingerprint["sha256"]:
                    changes.append({"source": source, "reason": "actual local " + label + " scope differs from fresh deployed branch"})
        if changes:
            return {"status": "changed", "revision": revision, "changes": changes, "reasons": ["reread governing sources and re-propose with fresh approval"]}
        result: WorkflowRevisionResult = {"status": "unchanged", "revision": revision, "changes": [], "reasons": []}
        if phase == "snapshot":
            result["snapshot"] = {"format": 2, "target": target, "revision": revision, "scope": scope, "fingerprints": current}
        return result
    except (ValueError, TypeError, OSError, UnicodeError, yaml.YAMLError, subprocess.TimeoutExpired) as error:
        return {"status": "needs-input", "changes": changes, "reasons": [str(error)]}


def main() -> int:
    """Emit sandbox evidence, with no implicit approval or native writes."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=("snapshot", "prewrite"))
    parser.add_argument("--baseline", type=Path)
    arguments = parser.parse_args()
    try:
        scope = json.loads(arguments.scope.read_text())
        baseline = json.loads(arguments.baseline.read_text()) if arguments.baseline else None
        result = check_workflow_revision(arguments.repo, scope, phase=arguments.phase, baseline=baseline)
    except (OSError, ValueError) as error:
        result = {"status": "needs-input", "changes": [], "reasons": [str(error)]}
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "unchanged" else 1


if __name__ == "__main__":
    sys.exit(main())
