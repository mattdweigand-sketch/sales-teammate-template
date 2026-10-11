#!/usr/bin/env python3
"""Render Top 3 from reviewed triage candidates, never infer action meaning or authorize writes.

Usage: top_actions.py --input sandbox.json [--sources DIR] [--policy PATH]
Input: run {date YYYY-MM-DD, process_status complete|incomplete}, today_actions,
deals [{id,name}], withheld [{deal,reason}], coverage {ready,process_status,affected},
and optional routed ownership context. Triage binds coverage to its saved read review,
not an assertion that Gmail or Calendar provides complete history. Unknown affected
scope suppresses every candidate; named gaps suppress those deals. Missing read status
withholds ranking with a named reason. Coverage ready false with an empty affected
list is an unknown scope and withholds the ranking. Complete empty inputs remain
distinct. A colon, semicolon or em dash in a reason prints a warning to stderr and
keeps the action. Candidates contain deal, name, kind, date, reason, evidence, and size
under policy.forecast.amount_field only. buyer_reply needs reply_reviewed true and
a retrieved external Gmail message; meeting uses Salesforce or Calendar scheduled
today/tomorrow; due uses Salesforce current action deadlines; date_at_risk uses
reviewed Salesforce CloseDate. No additional searches, state, network or writes.
The ranking and three-deal limit live only here. Candidate evidence follows the
shared saved-source checker. Output is posted unchanged above triage approval rows.
"""
import argparse
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from email.utils import parseaddr
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '_core' / 'scripts'))
from _saved_json import resolve_calls_dir
from report_evidence import EvidenceMixin, load_sources, md, RETRIEVED_SOURCES

TODAY_ACTION_ORDER = {"buyer_reply": 0, "meeting": 1, "due": 2, "date_at_risk": 3}
LIMITATION = "Email, Calendar, and Slack evidence is the retrieved set, not full history."

class Actions(EvidenceMixin):
    def __init__(self, data, policy, sources):
        self.data = deepcopy(data)
        self.policy = policy
        self.sources = sources
        self.run = self.data.get('run') or {}
        self.coverage = self.data.get('coverage') or {}
        self.deals = {row['id']: row for row in self.data.get('deals', [])}
        self.errors = []
        self.warnings = []
        self.resolved_evidence = set()
        self.date = date.fromisoformat(self.run['date'])
        self.tz = ZoneInfo(policy['pipeline']['schedule']['task_triage']['tz'])

    def err(self, message):
        self.errors.append(message)

    def check_id(self, kind, value, where):
        if not isinstance(value, str) or len(value) not in (15,18) or not value.startswith('006') or not value.isalnum():
            self.err(f'{where}: {kind} id is not a valid Opportunity Id')

    def coverage_ready(self):
        return self.coverage.get('ready') is True and self.coverage.get('process_status') == 'complete'

    def process_complete(self):
        return self.run.get('process_status') == 'complete'

    def routing_rows(self, status):
        return [row for row in self.data.get('routed', []) if row.get('delivery', {}).get('status') == status]

    def link(self, kind, identifier, name):
        config = self.policy['salesforce']
        url = config['record_url'].format(instance_url=config['instance_url'], Object=kind, Id=identifier)
        return f'[{name}]({url})'

    def uses_retrieved(self, evidence_lists):
        return any(item.get('source') in RETRIEVED_SOURCES | {'Slack'} for rows in evidence_lists for item in rows)

    def today_action_size(self, item):
        value = item.get(self.policy["forecast"]["amount_field"])
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise ValueError("size must be numeric")
        try:
            amount = Decimal(str(value))
        except InvalidOperation as error:
            raise ValueError("size must be numeric") from error
        if not amount.is_finite() or amount < 0:
            raise ValueError("size must be finite and nonnegative")
        return amount


    def check_today_actions(self):
        """Validate reviewed candidates without inferring buyer intent or new work."""
        candidates = self.data.get("today_actions")
        if not isinstance(candidates, list):
            self.err("Top 3 needs today_actions as a list, empty when no supported action exists")
            return
        for item in candidates:
            if not isinstance(item, dict):
                self.err("today_actions entries must be objects")
                continue
            where = f"today action {item.get('deal')}"
            try:
                self.today_action_size(item)
            except ValueError as error:
                self.err(f"{where} {error}")
            self.check_id("Opportunity", item.get("deal"), where)
            for field in ("name", "reason"):
                value = item.get(field)
                if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n"):
                    self.err(f"{where} needs a one-line {field}")
            if isinstance(item.get("reason"), str) and any(c in item["reason"] for c in ";—:"):
                self.warnings.append(f"{where} reason should use plain prose without semicolons, em dashes, or colons")
            if item.get("deal") in self.deals and item.get("name") != self.deals[item["deal"]].get("name"):
                self.err(f"{where} name must match the deal record")
            kind = item.get("kind")
            if kind not in TODAY_ACTION_ORDER:
                self.err(f"{where} needs a supported action kind")
            evidence = item.get("evidence") or []
            self.check_evidence(evidence, where)
            sources = {e.get("source") for e in evidence}
            allowed = {"buyer_reply": {"Gmail"}, "meeting": {"Calendar", "Salesforce"},
                       "due": {"Salesforce"}, "date_at_risk": {"Salesforce"}}.get(kind, set())
            if not sources or not sources <= allowed:
                self.err(f"{where} evidence must support its action kind using existing workflow sources")
            if kind == "buyer_reply" and item.get("reply_reviewed") is not True:
                self.err(f"{where} needs reply_reviewed true after reading the thread in both directions")
            try:
                when = date.fromisoformat(item.get("date", ""))
                if when.isoformat() != item["date"]:
                    raise ValueError("date format")
            except (TypeError, ValueError):
                self.err(f"{where} needs date YYYY-MM-DD")
                continue
            if self.date:
                if kind == "meeting" and when not in (self.date, self.date + timedelta(days=1)):
                    self.err(f"{where} meeting must be today or tomorrow")
                if kind in ("due", "buyer_reply") and when > self.date:
                    self.err(f"{where} cannot use a future due date or email")
            for e in evidence:
                if e.get("source") in RETRIEVED_SOURCES and id(e) in self.resolved_evidence and e.get("date") != md(when):
                    self.err(f"{where} date must match the saved source in the run timezone")
                if kind == "buyer_reply" and e.get("source") == "Gmail":
                    record = self.sources["Gmail"].get(e.get("source_id"), {})
                    sender = parseaddr(record.get("from_") or "")[1].lower()
                    if "@" not in sender or sender.rsplit("@", 1)[1] in self.policy["tooling"]["internal_domains"]:
                        self.err(f"{where} buyer reply needs an external sender in the saved message")


    def today_action_lines(self):
        """Rank candidates and show only the strongest reason for each deal."""
        reasons = []
        if not self.process_complete():
            reasons.append("processing is incomplete")
        if not self.coverage_ready() and not self.coverage.get("affected"):
            reasons.append("evidence coverage scope is unknown")
        if reasons:
            return ["## Top 3 actions today", "", "Ranking withheld because " + " and ".join(reasons) + ".", ""]
        withheld = {item["deal"] for item in self.data.get("withheld") or []}
        if not self.coverage_ready():
            affected = (self.coverage or {}).get("affected")
            withheld.update(affected if affected is not None else [item["deal"] for item in self.data["today_actions"]])
        def ranking(item):
            size = self.today_action_size(item)
            return (TODAY_ACTION_ORDER[item["kind"]], item["date"], size is None,
                    -size if size is not None else Decimal(0), item["name"].casefold(), item["deal"], item["reason"])

        candidates = sorted(self.data["today_actions"], key=ranking)
        selected, seen = [], set()
        for item in candidates:
            if item["deal"] in withheld or not self.process_complete():
                continue
            if item["deal"] not in seen:
                selected.append(item)
                seen.add(item["deal"])
            if len(selected) == 3:
                break
        lines = ["## Top 3 actions today", ""]
        for rank, item in enumerate(selected, 1):
            deal = self.link("Opportunity", item["deal"], item["name"])
            owner = " · in deal thread" if item["deal"] in {row["deal"] for row in self.routing_rows("delivered")} else ""
            if item["deal"] in {row["deal"] for row in self.routing_rows("failed")}:
                owner = " · routing failed, needs input"
            lines.append(f"- Priority {rank} · {deal}{owner} · {item['reason']}")
        if selected:
            lines += ["", "Use the proposal labels below for approvals."]
            if self.uses_retrieved([item["evidence"] for item in selected]):
                lines += ["", LIMITATION]
        elif candidates:
            lines.append("Ranking withheld because all supported candidates have evidence gaps.")
        else:
            lines.append("No supported actions to prioritize today.")
        return lines + [""]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--sources')
    parser.add_argument('--policy', default=str(ROOT / '_core' / 'policy.yaml'))
    args = parser.parse_args()
    try:
        data = json.loads(Path(args.input).read_text())
        policy = yaml.safe_load(Path(args.policy).read_text())
        actions = Actions(data, policy, load_sources(resolve_calls_dir(args.sources)))
        actions.check_today_actions()
        if actions.errors:
            print('\n'.join(actions.errors), file=sys.stderr)
            return 1
        if actions.warnings:
            print('\n'.join(actions.warnings), file=sys.stderr)
        print('\n'.join(actions.today_action_lines()))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
