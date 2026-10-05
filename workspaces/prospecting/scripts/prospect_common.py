"""Reused helpers for the gates. No CLI.

Policy loader, Markdown frontmatter parser, shared signals loader, policy clock, ISO parsing,
taxonomy tier walk, and the exit-2 error envelope.

Policy input uses prospecting.identity.timezone for clocks and date parsing.
load_policy returns the prospecting block from the canonical policy or the full fixture mapping.
"""
import json
import re
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

CORE = Path(__file__).resolve().parents[3] / "_core"
REFERENCES = Path(__file__).resolve().parents[1] / "references"
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def load_policy(core=CORE):
    path = Path(core) / "policy.yaml"
    policy = yaml.safe_load(path.read_text())
    return policy["prospecting"] if path.resolve() == (CORE / "policy.yaml").resolve() else policy


def markdown_document(path):
    """One Markdown document: script settings in frontmatter, prose for the agent."""
    text = Path(path).read_text()
    match = FRONTMATTER.match(text)
    if not match:
        raise ValueError(f"{Path(path).name} has no frontmatter block")
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter must be a mapping")
    body = text[match.end():].strip()
    if not body:
        raise ValueError("Markdown body is empty")
    return {"meta": meta, "body": body}


def load_taxonomy(core=CORE):
    return markdown_document((REFERENCES if Path(core).resolve() == CORE.resolve() else Path(core)) / "signals.md")["meta"]


def taxonomy_entry(tax, signal_type):
    """tier1 or tier2 entry with the id, plus its tier name. (None, None) when absent."""
    for tier in ("tier1", "tier2"):
        for t in tax["tiers"][tier]:
            if t["id"] == signal_type:
                return t, tier
    return None, None


def taxonomy_types(tax):
    """{id: {tier, freshness_days, source}} across every tier. prospect_evidence_gate.py reads it."""
    return {e["id"]: {"tier": tier, "freshness_days": e.get("freshness_days"), "source": e.get("source")}
            for tier, entries in tax["tiers"].items() for e in entries}


def policy_tz(policy):
    return ZoneInfo(policy["identity"]["timezone"])


def policy_now(policy):
    return datetime.now(policy_tz(policy))


def policy_today(policy):
    return policy_now(policy).date()


def parse_iso(s, policy=None):
    """Aware datetime from an ISO string. 'Z' accepted. A bare date is noon in the policy timezone
    when policy is given, else None. A naive timestamp returns None."""
    if not isinstance(s, str) or not s.strip():
        return None
    s = s.strip().replace("Z", "+00:00")
    if len(s) <= 10:
        if policy is None:
            return None
        return datetime.combine(date.fromisoformat(s), time(12, 0), tzinfo=policy_tz(policy))
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def error_json(exc):
    """Exit-2 envelope every gate prints. Same shape everywhere."""
    return json.dumps({"verdict": "error", "reason": f"{type(exc).__name__}: {exc}"})


INPUT_ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError, yaml.YAMLError, json.JSONDecodeError)
