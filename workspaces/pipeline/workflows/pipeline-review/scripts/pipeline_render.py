#!/usr/bin/env python3
"""Render weekly pipeline-review report, questions, receipts and notification.

Usage: pipeline_render.py report|question|receipt|notification --run RUN.json
       [--coverage COVERAGE.json] [--sources DIR] [--policy PATH]
All runs use run.branch=friday and coverage_scope=pipeline, including requested runs.
Input counts, deals, routed, blocks, questions, friday and writes retain their shapes.
Blocks/options fill blank required or conditional Opportunity fields. Friday letters
add StageName, CloseDate, Amount and a narrow dated size-floor exception Description. No next-step or Task change is accepted anywhere.
next_step {current,proposed:null} and next_step_current are display-only context.
triage is read-only {deal,name,reason,triage_next_step:true|triage_task_gap:true|
triage_owned_task:<native open Task>}, with no changes, labels or delivery.
friday.qualification actions are closed_lost, triage or needs_input. closed_lost needs
reviewed silence, operator_stated_no {quote,date}, or explicitly reviewed lost_path_size.
Size-floor facts are caller-reviewed inputs, not inferred buyer intent or history.
Saved Gmail/Calendar source IDs and Gmail body quotes use shared evidence checks.
Statuses, counts, approved exact changes and readback outcomes still gate rendering.
No network, writes, approval inference or sales judgment. Exit 1 reports errors only.
"""
import argparse
import html
import json
import re
import sys
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "_core" / "scripts"))
from _saved_json import resolve_calls_dir
from hygiene_check import closed_lost_silence_eligible, is_blank, parse_mdy
from report_evidence import EvidenceMixin, load_sources, md, RETRIEVED_SOURCES

ROOT = Path(__file__).resolve().parents[5]
DEFAULT_POLICY = ROOT / "_core" / "policy.yaml"

ITEM_STATUSES = {"proposed", "approved", "written", "partial", "failed", "skipped", "deferred", "superseded"}
QUESTION_STATUSES = {"open", "answered", "skipped", "deferred", "superseded"}
WRITE_OUTCOMES = {"written", "rejected", "unverified", "not_attempted"}
OUTCOME_RANK = ("rejected", "unverified", "not_attempted", "written")
OUTCOME_TEXT = {"written": "Written", "rejected": "Rejected", "unverified": "Unverified", "not_attempted": "Not attempted"}
LETTER_ONLY_FIELDS = {"CloseDate", "StageName", "Amount", "Description"}
SCOPE_FOR_BRANCH = {"friday": "pipeline"}
COVERAGE_HIDDEN_PREFIXES = ("Domain-matched ", "Coverage ready.", "Report not ready:")
COVERAGE_FILE_LINE = re.compile(r"^\S+\.json: ")
ID_PREFIX = {"Opportunity": "006", "Task": "00T", "Contact": "003", "Event": "00U", "User": "005"}
BLOCK_LABEL = re.compile(r"^[1-9]\d*$")
QUESTION_LABEL = re.compile(r"^Q[1-9]\d*$")
LETTER_LABEL = re.compile(r"^[A-Z]{1,2}$")

LIMITATION = "Email, Calendar, and Slack evidence is the retrieved set, not full history."
HISTORY_NOTE = "Only the latest next-step entry is shown. Older history stays unchanged."
LEGACY_NOTE = "Legacy `Next:` entries appear as stored."
EMPTY_BLOCKS = "No clear recommendations."
EMPTY_QUESTIONS = "No questions."
WALK_NOTE = "I walk these one at a time after the clear recommendations."
NO_CHANGES = "No Salesforce changes proposed."
NO_NEXT_STEP_CHANGE = "No next-step change."
SKIP_OPTION = "skip · Leave unchanged. Named at close."
APPROVE_FRIDAY = ("**Reply with numbers, ranges, all, letters, or skip. all covers the numbered clear "
                  "recommendations only. Each letter approves one record.**")
TITLE_FRIDAY = {"ready": "Friday pipeline review ready for approval",
                "complete": "Friday pipeline review complete",
                "incomplete": "Friday pipeline review incomplete"}


class RenderError(Exception):
    pass






def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise RenderError(f"cannot read {path}: {exc}") from exc




def display(text):
    """Readable display only: HTML paragraph and break boundaries become newlines, entities decode."""
    if text is None:
        return "Empty"
    s = re.sub(r"(?i)<br\s*/?>", "\n", str(text))
    s = re.sub(r"(?i)</p>\s*<p[^>]*>", "\n", s)
    s = re.sub(r"(?i)</?p[^>]*>", "", s)
    s = html.unescape(s).strip()
    return s if s else "Empty"


def n(count, one, many):
    return f"{count} {one if count == 1 else many}"


def exact(text):
    return "Empty" if text in (None, "") else str(text)


def change_key(c):
    if c.get("action") == "create":
        return ("Task", None, "create")
    return (c.get("object"), c.get("id"), c.get("field"))


def write_key(w):
    return (w.get("object"), None if w.get("field") == "create" else w.get("id"), w.get("field"))


def expected_keys(item):
    """Record fields a label approves: a block's changes, a letter's change, an option's changes. Never Next_Steps__c."""
    return [change_key(c) for c in ([item["change"]] if isinstance(item.get("change"), dict) else item.get("changes") or [])]


def record_outcomes(rows):
    """One outcome per (label, object, id) record: written only when every field row for it is written."""
    grouped = {}
    for w in rows:
        grouped.setdefault((str(w.get("label")), w.get("object"), w.get("id")), []).append(w.get("outcome"))
    return [min(v, key=OUTCOME_RANK.index) if all(o in OUTCOME_RANK for o in v) else "unverified"
            for v in grouped.values()]


class Run(EvidenceMixin):
    def __init__(self, data, policy, coverage=None, sources=None):
        data = deepcopy(data)
        self.data = data
        self.resolved_evidence = set()
        self.policy = policy
        self.coverage = coverage
        self.sources = sources or {"Gmail": {}, "Calendar": {}}
        tz = ((policy.get("pipeline") or {}).get("schedule") or {}).get("friday", {}).get("tz")
        self.tz = ZoneInfo(tz) if tz else None
        self.errors = []
        self._task_ownership_states: dict[str, tuple[object, object, object]] = {}
        sf = policy.get("salesforce", {})
        self.record_url = sf.get("record_url", "").replace("{instance_url}", sf.get("instance_url", ""))
        self.url_objects = set(sf.get("record_url_objects", []))
        prefix = sf.get("note_prefix", "M/D/YY SR - ")
        self.run = data.get("run") or {}
        self.counts = data.get("counts") or {}
        self.deals = {d.get("id"): d for d in data.get("deals") or []}
        self.blocks = data.get("blocks") or []
        self.questions = data.get("questions") or []
        self.friday = data.get("friday") or {}
        self.letters = self.friday.get("letters") or []
        self.qualification = self.friday.get("qualification", [])
        self.writes = data.get("writes") or []
        try:
            self.date = date.fromisoformat(str(self.run.get("date")))
        except ValueError:
            self.date = None
        self.entry_prefix = prefix.replace("M/D/YY", md(self.date)) if self.date else None
        pp = policy.get("pipeline") or {}
        self.block_fields = set()
        for fields in (pp.get("required_fields") or {}).values():
            self.block_fields |= set(fields or [])
        self.block_fields |= {c.get("field") for c in pp.get("conditional_fields") or [] if c.get("field")}

    # ---- helpers
    def err(self, msg):
        self.errors.append(msg)

    def url(self, obj, rid):
        if obj in self.url_objects and rid:
            return self.record_url.replace("{Object}", obj).replace("{Id}", rid)
        return None

    def link(self, obj, rid, text):
        u = self.url(obj, rid)
        return f"[{text}]({u})" if u else f"{text} ({rid})"

    def deal_link(self, deal_id):
        d = self.deals.get(deal_id, {})
        return self.link("Opportunity", deal_id, d.get("name") or deal_id)

    def active(self, items):
        return [i for i in items if i.get("status") != "superseded"]

    def live_options(self, q):
        return [o for o in q.get("options") or [] if o.get("status") != "superseded"]

    def coverage_ready(self):
        c = self.coverage or {}
        return c.get("ready") is True and c.get("process_status") == "complete"

    def process_complete(self):
        return self.run.get("process_status") == "complete"

    def routing_rows(self, status):
        return [row for row in self.data.get("routed") or [] if row["delivery"]["status"] == status]

    # ---- validation
    def check_id(self, obj, rid, where):
        pre = ID_PREFIX.get(obj)
        if not isinstance(rid, str) or len(rid) not in (15, 18) or (pre and not rid.startswith(pre)):
            self.err(f"{where}: {obj} id {rid!r} is not a valid {obj} Id")



    def check_evidence(self, evidence, where):
        super().check_evidence(evidence, where)
        if any(isinstance(item, dict) and item.get("source") == "Pilot report" for item in evidence or []):
            if self.date is None or self.date.weekday() != 4:
                self.err(f"{where}: Pilot report input is Friday-only under rules#pilot_handoff")

    def check_change(self, c, where, letter=False):
        obj = c.get("object")
        if obj == "Task":
            self.err(f"{where}: pipeline-review cannot propose a Task change")
            return
        if c.get("field") == "Next_Steps__c":
            self.err(f"{where}: pipeline-review cannot propose a next-step change")
            return
        if not letter and not is_blank(c.get("current")):
            self.err(f"{where}: clear recommendations only fill blank required or conditional fields")
        if obj != "Opportunity":
            self.err(f"{where}: object must be Opportunity")
            return
        if c.get("action") == "create":
            self.err(f"{where}: only existing Opportunity fields can be changed")
            return
        self.check_id(obj, c.get("id"), where)
        field = c.get("field")
        if not letter and field in LETTER_ONLY_FIELDS:
            self.err(f"{where}: Opportunity {field} needs a Friday letter")
        if not field:
            self.err(f"{where}: field is required")
        elif obj == "Opportunity" and field not in self.block_fields | (LETTER_ONLY_FIELDS if letter else set()):
            allowed = "a Friday letter" if field in LETTER_ONLY_FIELDS else "any proposal here"
            self.err(f"{where}: Opportunity {field} is not a permitted change for {allowed}")
        if "proposed" not in c or c.get("proposed") in (None, ""):
            self.err(f"{where}: proposed value is required")
        if c.get("mode") not in (None, "prepend"):
            self.err(f"{where}: mode must be prepend when set")
        if c.get("mode") != "prepend" and "current" not in c:
            self.err(f"{where}: current value is required, use null for empty")
        if letter and field == "StageName":
            self.check_stage_move(c, where)

    def check_stage_move(self, c, where):
        """Every StageName change is checked against its source stage, in proposal and receipt modes alike.

        Closed Won and upward moves from policy.pipeline.early_stages are never proposed here, with or without a
        qualification row. Downward moves, S2+ upward moves and Closed Lost keep their other gates."""
        current, proposed = c.get("current"), c.get("proposed")
        source = re.match(r"S([0-5])(?:\b|\s|-)", current) if isinstance(current, str) else None
        if not source:
            self.err(f"{where}: StageName change needs its current source stage")
            return
        if proposed == "Closed Won":
            self.err(f"{where}: pipeline-review never proposes Closed Won")
            return
        target = re.fullmatch(r"S([0-5])", proposed) if isinstance(proposed, str) else None
        if not target and proposed != "Closed Lost":
            self.err(f"{where}: StageName proposal must be a policy stage or Closed Lost")
            return
        early = self.policy["pipeline"].get("early_stages", [])
        if f"S{source.group(1)}" in early and target and int(target.group(1)) > int(source.group(1)):
            self.err(f"{where}: pipeline-review never proposes an upward stage move from an early stage")

    def _check_task_ownership(self, task_state: object, expected_id: object, where: str) -> bool | None:
        """Classify reviewed native Task state without treating missing dates as undated evidence."""
        if not isinstance(task_state, dict):
            self.err(f"{where}: native task_state must include Id, OwnerId, IsClosed and ActivityDate")
            return None
        self.check_id("Task", task_state.get("Id"), where)
        if task_state.get("Id") != expected_id:
            self.err(f"{where}: task_state Id does not match the named Task")
        owner_id = task_state.get("OwnerId")
        user_id = self.run.get("user_id")
        for owner in (owner_id, user_id):
            if not isinstance(owner, str) or not re.fullmatch(r"[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?", owner):
                self.err(f"{where}: readable OwnerId and run.user_id required; Task needs-input")
                return None
        if not user_id.startswith("005"):
            self.err(f"{where}: run.user_id must identify the native run user; Task needs-input")
            return None
        if task_state.get("IsClosed") is not False or "ActivityDate" not in task_state:
            self.err(f"{where}: native task_state requires IsClosed false and ActivityDate")
            return None
        task_id = task_state.get("Id")
        if isinstance(task_id, str):
            key = task_id[:15]
            snapshot = (owner_id[:15], task_state["ActivityDate"], task_state["IsClosed"])
            if key in self._task_ownership_states and self._task_ownership_states[key] != snapshot:
                self.err(f"{where}: contradictory native Task ownership states; Task needs-input")
                return None
            self._task_ownership_states[key] = snapshot
        activity_date = task_state["ActivityDate"]
        if activity_date is None:
            return owner_id[:15] == user_id[:15]
        if not isinstance(activity_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", activity_date):
            self.err(f"{where}: task_state ActivityDate must be ISO date or null")
            return None
        try:
            date.fromisoformat(activity_date)
        except ValueError:
            self.err(f"{where}: task_state ActivityDate must be a valid date")
            return None
        if self.date is None:
            self.err(f"{where}: valid run.date required for Task ownership")
            return None
        return owner_id[:15] == user_id[:15]


    def check_milestones(self, item, changes, where):
        """Show the reviewed exception without allowing it to replace the current follow-up."""
        if "triage_owned_task" in item:
            triage_task = item["triage_owned_task"]
            task_id = triage_task.get("Id") if isinstance(triage_task, dict) else None
            owned = self._check_task_ownership(triage_task, task_id, where)
            if owned is False:
                self.err(f"{where}: triage_owned_task must be a Operator-owned open Task")
            if item.get("followup_task"):
                self.err(f"{where}: triage_owned_task and followup_task are alternative ownership paths")
        if "triage_task_gap" in item:
            self.check_id("User", self.run.get("user_id"), where)
            if not isinstance(self.run.get("user_id"), str) or not re.fullmatch(r"005[A-Za-z0-9]{12}(?:[A-Za-z0-9]{3})?", self.run["user_id"]):
                self.err(f"{where}: readable native run.user_id required for a Task gap")
            if item["triage_task_gap"] is not True:
                self.err(f"{where}: triage_task_gap must be true; a handoff label, never write authority")
            if "triage_owned_task" in item or item.get("followup_task"):
                self.err(f"{where}: Task gap and existing Task are alternative ownership paths")
        milestones = item.get("retained_milestones", [])
        if not isinstance(milestones, list):
            self.err(f"{where}: retained_milestones must be a list")
            return
        seen = set()
        followup_dates = [c.get("fields", {}).get("ActivityDate") if c.get("action") == "create" else c.get("proposed")
                          for c in changes if c.get("object") == "Task"
                          and (c.get("action") == "create" or c.get("field") == "ActivityDate")]
        for milestone in milestones:
            if not isinstance(milestone, dict):
                self.err(f"{where}: retained_milestones entries must be objects")
                continue
            tid = milestone.get("task_id")
            self.check_id("Task", tid, where)
            self.check_id("Event", milestone.get("event_id"), where)
            if not isinstance(tid, str):
                continue
            if tid in seen or tid == item.get("followup_task"):
                self.err(f"{where}: a retained milestone must be a distinct Task")
            seen.add(tid)
            if any(c.get("object") == "Task" and c.get("id") == tid for c in changes):
                self.err(f"{where}: a retained milestone Task cannot also be changed")
            try:
                due = date.fromisoformat(milestone.get("due_date", ""))
                if self.date and due <= self.date:
                    self.err(f"{where}: retained milestone must be in the future")
                if any(due <= date.fromisoformat(value) for value in followup_dates):
                    self.err(f"{where}: retained milestone must be later than the current follow-up")
            except (TypeError, ValueError):
                self.err(f"{where}: retained milestone needs due_date YYYY-MM-DD")
            if not milestone.get("reason") or milestone.get("action_verified") is not True:
                self.err(f"{where}: retained milestone needs reason and action_verified true after Event linkage review")




    def record_key(self, c):
        if c.get("action") == "create":
            f = c.get("fields") or {}
            return ("Task:create", f.get("WhatId"), (f.get("Subject") or "").strip().lower())
        return (c.get("object"), c.get("id"), c.get("field"))

    def check_next_step(self, ns, where):
        if not isinstance(ns, dict) or "current" not in ns or "proposed" not in ns:
            self.err(f"{where}: next_step needs current and proposed (null when unchanged)")
            return
        p = ns.get("proposed")
        if p is not None or ns.get("proposed_full") is not None:
            self.err(f"{where}: pipeline-review cannot propose a next-step change")
        if p is not None and self.entry_prefix and not str(p).startswith(self.entry_prefix):
            self.err(f"{where}: proposed next step must start with {self.entry_prefix!r}")

    def validate(self, mode):
        r = self.run
        if r.get("branch") not in SCOPE_FOR_BRANCH:
            self.err("run.branch must be friday for every weekly or requested run")
        if self.date is None:
            self.err("run.date must be YYYY-MM-DD")
        if not r.get("id"):
            self.err("run.id is required")
        if r.get("process_status") not in ("complete", "incomplete"):
            self.err("run.process_status must be complete or incomplete")
        if r.get("process_status") == "incomplete" and not r.get("process_gaps"):
            self.err("run.process_gaps must name each failed or unfinished step")
        slack_notes = r.get("slack_coverage_notes", [])
        if not isinstance(slack_notes, list):
            self.err("run.slack_coverage_notes must be a list")
        else:
            note_deals = set()
            for note in slack_notes:
                if not isinstance(note, dict):
                    self.err("Slack coverage notes must be objects with deal, name, contacts, and reason")
                    continue
                deal = note.get("deal")
                self.check_id("Opportunity", deal, "Slack coverage note")
                if isinstance(deal, str):
                    if deal in note_deals:
                        self.err("Use one Slack coverage note per deal with contacts grouped")
                    note_deals.add(deal)
                for key in ("name", "reason"):
                    value = note.get(key)
                    if not isinstance(value, str) or not value.strip() or any(char in value for char in "\r\n"):
                        self.err(f"Slack coverage note needs a one-line {key}")
                contacts = note.get("contacts")
                if not isinstance(contacts, list) or not contacts or not all(
                    isinstance(contact, str) and contact.strip() and not any(char in contact for char in "\r\n")
                    for contact in contacts
                ):
                    self.err("Slack coverage note contacts must be a nonempty list of one-line names")
                if isinstance(deal, str) and deal in self.deals and note.get("name") != self.deals[deal].get("name"):
                    self.err("Slack coverage note name must match the deal record")
        if mode in ("report", "notification"):
            if self.coverage is None or not isinstance(self.coverage, dict) or "lines" not in self.coverage:
                self.err("coverage must be the saved coverage_check --json output")
            if r.get("coverage_scope") != SCOPE_FOR_BRANCH.get(r.get("branch")):
                self.err(f"run.coverage_scope must be {SCOPE_FOR_BRANCH.get(r.get('branch'))} for {r.get('branch')}")
            if self.coverage is not None and not self.coverage_ready() and "withheld" not in self.data:
                self.err("coverage is not ready: list withheld proposals, or an empty list")
            if isinstance(self.coverage, dict) and not self.coverage_ready():
                affected = self.coverage.get("affected")
                must = set(self.deals) if affected is None else set(affected) & set(self.deals)
                held = {w.get("deal") for w in self.data.get("withheld") or []}
                for rid in sorted(must - held):
                    self.err(f"withheld: coverage affects {self.deals[rid].get('name')} ({rid}); list it as withheld")
        if mode == "notification" and not r.get("thread_url"):
            self.err("run.thread_url is required for the notification")
        for key in ("open", "reviewed", "not_checked"):
            if not isinstance(self.counts.get(key), int) or self.counts.get(key) < 0:
                self.err(f"counts.{key} must be a non-negative integer")
        ids = [d.get("id") for d in self.data.get("deals") or []]
        if len(ids) != len(set(ids)):
            self.err("deals: each flagged deal appears once")
        for d in self.data.get("deals") or []:
            self.check_id("Opportunity", d.get("id"), f"deal {d.get('name')}")
            if not d.get("name") or not d.get("flags"):
                self.err(f"deal {d.get('id')}: name and flags are required")
        for w in self.data.get("withheld") or []:
            if w.get("deal") not in self.deals or not w.get("reason"):
                self.err(f"withheld {w.get('deal')}: must name a flagged deal and a reason")
        routed = self.data.get("routed", [])
        if not isinstance(routed, list):
            self.err("routed must be a list")
            routed = []
        routed_ids = set()
        for row in routed:
            if not isinstance(row, dict):
                self.err("routed entries must be objects")
                continue
            self.check_id("Opportunity", row.get("deal"), "routed")
            if row.get("kind") != "deal_context":
                self.err("routed.kind must be deal_context; Task issues belong to triage")
            if row.get("deal") in routed_ids:
                self.err("routed: each deal appears once")
            routed_ids.add(row.get("deal"))
            for field in ("name", "reason", "thread_url"):
                value = row.get(field)
                if not isinstance(value, str) or not value.strip() or any(char in value for char in "\r\n"):
                    self.err(f"routed needs a one-line {field}")
            if not isinstance(row.get("thread_url"), str) or not row["thread_url"].startswith("https://"):
                self.err("routed needs an https deal-thread link")
            if row.get("deal") in self.deals:
                self.err("routed deals must be counted separately from local flagged deals")
            delivery = row.get("delivery")
            if not isinstance(delivery, dict):
                self.err("routed needs a delivery object")
            else:
                if delivery.get("command") != "mail_send":
                    self.err("routed delivery.command must be mail_send")
                if delivery.get("status") not in ("delivered", "failed"):
                    self.err("routed delivery.status must be delivered or failed")

        triage_deals = set()
        triage_rows = self.data.get("triage", [])
        if not isinstance(triage_rows, list):
            self.err("triage must be a read-only list")
            triage_rows = []
        for row in triage_rows:
            if not isinstance(row, dict):
                self.err("triage entries must be objects")
                continue
            self.check_id("Opportunity", row.get("deal"), "triage")
            if not isinstance(row.get("deal"), str) or row["deal"] not in set(self.deals) | routed_ids:
                self.err("triage must name a reviewed flagged or routed deal")
            else:
                triage_deals.add(row["deal"])
            for field in ("name", "reason"):
                value = row.get(field)
                if not isinstance(value, str) or not value.strip() or any(char in value for char in "\r\n"):
                    self.err(f"triage needs a one-line {field}")
            if any(field in row for field in ("changes", "delivery", "label")):
                self.err("triage findings have no writes, delivery commands or approval labels")
            if "triage_owned_task" not in row and "triage_task_gap" not in row and row.get("triage_next_step") is not True:
                self.err("triage needs native triage_owned_task, triage_task_gap true or triage_next_step true")
            self.check_milestones(row, [], "triage")
            native_task = row.get("triage_owned_task")
            if isinstance(native_task, dict) and isinstance(native_task.get("ActivityDate"), str) and self.date:
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", native_task["ActivityDate"]) and native_task["ActivityDate"] > self.date.isoformat():
                    self.err("triage: future Tasks never enter triage findings; only pre-create duplicate checks")

        labels = {}

        def claim(label, where):
            if label in labels:
                self.err(f"{where}: label {label} is already used by {labels[label]}; never recycle a label")
            labels[label] = where

        block_deals = set()
        for b in self.blocks:
            lab = str(b.get("label"))
            where = f"block {lab}"
            if not BLOCK_LABEL.match(lab):
                self.err(f"{where}: label must be a positive number")
            claim(lab, where)
            if b.get("status") not in ITEM_STATUSES:
                self.err(f"{where}: status must be one of {sorted(ITEM_STATUSES)}")
            if b.get("deal") not in self.deals:
                self.err(f"{where}: deal {b.get('deal')} is not a flagged deal")
            if b.get("status") != "superseded":
                if b.get("deal") in block_deals:
                    self.err(f"{where}: one active clear recommendation per deal")
                block_deals.add(b.get("deal"))
            if b.get("depends_on_unknown"):
                self.err(f"{where}: rests on an unknown; move it to Needs your input (rules#absence_conclusions)")
            self.check_next_step(b.get("next_step"), where)
            ns = b.get("next_step") or {}
            if ns.get("proposed") is None and not b.get("changes"):
                self.err(f"{where}: a clear recommendation needs at least one change")
            for n, c in enumerate(b.get("changes") or [], 1):
                self.check_change(c, f"{where} change {n}")
            self.check_milestones(b, b.get("changes") or [], where)
            self.check_evidence(b.get("evidence"), where)

        question_deals = set()
        for q in self.questions:
            lab = str(q.get("label"))
            where = f"question {lab}"
            if not QUESTION_LABEL.match(lab):
                self.err(f"{where}: label must look like Q1")
            claim(lab, where)
            if q.get("status") not in QUESTION_STATUSES:
                self.err(f"{where}: status must be one of {sorted(QUESTION_STATUSES)}")
            if q.get("deal") not in self.deals:
                self.err(f"{where}: deal {q.get('deal')} is not a flagged deal")
            if q.get("status") != "superseded":
                question_deals.add(q.get("deal"))
            for key in ("context", "question"):
                if not q.get(key):
                    self.err(f"{where}: {key} is required")
            if "next_step_current" not in q:
                self.err(f"{where}: next_step_current is required, use null for empty")
            live = self.live_options(q)
            if len(live) > 3:
                self.err(f"{where}: at most three live options")
            for o in q.get("options") or []:
                olab = str(o.get("label"))
                owhere = f"option {olab}"
                if not re.match(rf"^{re.escape(lab)}-[a-z]$", olab):
                    self.err(f"{owhere}: option labels look like {lab}-a")
                claim(olab, owhere)
                if o.get("status") not in ITEM_STATUSES:
                    self.err(f"{owhere}: status must be one of {sorted(ITEM_STATUSES)}")
                if not o.get("text"):
                    self.err(f"{owhere}: text is required")
                for n, c in enumerate(o.get("changes") or [], 1):
                    self.check_change(c, f"{owhere} change {n}")
                self.check_milestones(o, o.get("changes") or [], owhere)
            self.check_evidence(q.get("evidence"), where)

        if self.letters and r.get("branch") != "friday":
            self.err("lettered record proposals are Friday only")
        if r.get("branch") == "friday" and mode == "report":
            for key in ("rollup", "since", "delta", "qualification"):
                if key not in self.friday:
                    self.err(f"friday.{key} is required on Friday")
        self.check_qualification()
        expected = 0
        task_letters = {str(l.get("label")) for l in self.letters if (l.get("change") or {}).get("object") == "Task"}
        for l in self.letters:
            lab = str(l.get("label"))
            where = f"letter {lab}"
            if not LETTER_LABEL.match(lab):
                self.err(f"{where}: label must be a capital letter")
            claim(lab, where)
            if l.get("status") not in ITEM_STATUSES:
                self.err(f"{where}: status must be one of {sorted(ITEM_STATUSES)}")
            if isinstance(l.get("change"), dict):
                self.check_change(l["change"], where, letter=True)
                if l["change"].get("field") == "Description":
                    self.check_size_exception_letter(l)
                self.check_milestones(l, [l["change"]], where)
            else:
                self.err(f"{where}: one change, one record per letter")
            if not l.get("basis"):
                self.err(f"{where}: basis is required")
            self.check_evidence(l.get("evidence"), where)
            if len(lab) == 1:
                if ord(lab) - ord("A") != expected:
                    self.err(f"{where}: letters run A, B, C in order with no gaps")
                expected += 1

        for item in self.blocks + self.letters + [o for q in self.questions for o in q.get("options") or []] + self.questions:
            sup = item.get("superseded_by")
            if item.get("status") == "superseded":
                if not sup or sup not in labels:
                    self.err(f"label {item.get('label')}: superseded_by must name the new label")
                elif sup == str(item.get("label")):
                    self.err(f"label {item.get('label')}: cannot supersede itself")
            elif sup:
                self.err(f"label {item.get('label')}: superseded_by is set but status is {item.get('status')}")

        # One owner per record field across independently approvable proposals.
        # Options inside one question are alternatives, so they may repeat each other.
        # A fully written label is no longer approvable, so a later fix may target the same field.
        seen = {}

        def own(keys, owner, where, status=None):
            if status == "written":
                return
            for i, key in enumerate(keys):
                if key in keys[:i]:
                    self.err(f"{where}: {key[0]} {key[1]} {key[2]} appears twice; one change per record field")
                elif key in seen and seen[key] != owner:
                    self.err(f"{where}: {key[0]} {key[1]} {key[2]} is already proposed in {seen[key]}")
                seen.setdefault(key, owner)
            if [k[0] for k in keys].count("Task:create") > 1:
                self.err(f"{where}: one Task create per approval label")

        def keys_of(item):
            changes = [item["change"]] if isinstance(item.get("change"), dict) else item.get("changes") or []
            return [self.record_key(c) for c in changes]

        for b in self.active(self.blocks):
            owner = f"block {b.get('label')}"
            own(keys_of(b), owner, owner, b.get("status"))
        for l in self.active(self.letters):
            owner = f"letter {l.get('label')}"
            own(keys_of(l), owner, owner, l.get("status"))
        for q in self.active(self.questions):
            for o in self.live_options(q):
                own(keys_of(o), f"question {q.get('label')}", f"option {o.get('label')}", o.get("status"))

        # Every change targets the deal its heading or letter names.
        def targets(changes, deal, where):
            for c in changes:
                target = c.get("id") if c.get("object") == "Opportunity" else (c.get("fields") or {}).get("WhatId")
                if target and target != deal:
                    self.err(f"{where}: change targets {target}, not the deal it is shown under ({deal})")
        for b in self.active(self.blocks):
            targets(b.get("changes") or [], b.get("deal"), f"block {b.get('label')}")
        for q in self.active(self.questions):
            for o in self.live_options(q):
                targets(o.get("changes") or [], q.get("deal"), f"option {o.get('label')}")
        for l in self.active(self.letters):
            where = f"letter {l.get('label')}"
            self.check_id("Opportunity", l.get("deal"), where)
            if not l.get("deal_name"):
                self.err(f"{where}: deal_name is required")
            targets([l.get("change") or {}], l.get("deal"), where)

        for item in self.blocks + self.questions + self.letters:
            if item.get("deal") in routed_ids:
                self.err(f"label {item.get('label')}: routed deal is owned elsewhere; propose nothing here")

        # A withheld deal has nothing approvable.
        held = {w.get("deal") for w in self.data.get("withheld") or []}
        for item, deal in ([(b, b.get("deal")) for b in self.active(self.blocks)]
                           + [(l, l.get("deal")) for l in self.active(self.letters)]
                           + [(o, q.get("deal")) for q in self.active(self.questions) for o in self.live_options(q)
                              if o.get("changes")]):
            if deal in held:
                self.err(f"label {item.get('label')}: deal {deal} is withheld; remove the proposal or the withheld entry")

        flagged = set(self.deals)
        covered = block_deals | question_deals | triage_deals | {w.get("deal") for w in self.data.get("withheld") or []}
        missing = flagged - covered
        if missing:
            self.err(f"flagged deals with no clear recommendation, question, or withheld entry: {sorted(missing)}")
        k, u = self.counts.get("reviewed"), self.counts.get("not_checked")
        if isinstance(k, int) and isinstance(u, int) and len(flagged) + len(routed_ids) + u > k:
            self.err(f"counts: flagged {len(flagged)} plus routed {len(routed_ids)} plus not checked {u} exceeds reviewed {k}")
        if isinstance(self.counts.get("open"), int) and isinstance(k, int) and k > self.counts["open"]:
            self.err("counts: reviewed exceeds open")

        by_label = {str(b.get("label")): b for b in self.blocks}
        by_label.update({str(l.get("label")): l for l in self.letters})
        by_label.update({str(o.get("label")): o for q in self.questions for o in q.get("options") or []})
        done = set()
        for n, w in enumerate(self.writes, 1):
            where = f"write {n}"
            lab = str(w.get("label"))
            item = by_label.get(lab)
            if item is None:
                self.err(f"{where}: label {lab} is not a clear recommendation, option, or letter")
                continue
            if item.get("status") in ("superseded", "proposed", "skipped", "deferred"):
                self.err(f"{where}: label {lab} is {item.get('status')}; only approved labels are written")
            if w.get("outcome") not in WRITE_OUTCOMES:
                self.err(f"{where}: outcome must be one of {sorted(WRITE_OUTCOMES)}")
            if w.get("outcome") in ("rejected", "unverified", "not_attempted") and not w.get("detail"):
                self.err(f"{where}: {w.get('outcome')} needs detail")
            if w.get("object") not in ID_PREFIX:
                self.err(f"{where}: object must be Opportunity, Task, or Contact")
            else:
                self.check_id(w.get("object"), w.get("id"), where)
            if write_key(w) not in expected_keys(item):
                self.err(f"{where}: {w.get('object')} {w.get('id')} {w.get('field')} is not an approved change of {lab}")
            key = (lab, w.get("object"), w.get("id"), w.get("field"))
            if w.get("outcome") == "written":
                if key in done:
                    self.err(f"{where}: {w.get('object')} {w.get('id')} {w.get('field')} was already written for {lab}; never repeat a successful write")
                done.add(key)
        return self.errors

    # ---- counts
    def count_values(self):
        blocks = self.active(self.blocks)
        questions = self.active(self.questions)
        k, u = self.counts["reviewed"], self.counts["not_checked"]
        f = len(self.deals)
        routed = len(self.routing_rows("delivered"))
        failed = len(self.routing_rows("failed"))
        return {"open": self.counts["open"], "reviewed": k, "flagged": f, "not_checked": u,
                "no_trigger": k - f - routed - failed - u, "routed": routed, "routing_failed": failed,
                "blocks": len(blocks), "questions": len(questions),
                "letters": len(self.active(self.letters)),
                "written": sum(record_outcomes(self.reconciled(lab)).count("written")
                               for lab in dict.fromkeys(str(w.get("label")) for w in self.writes))}

    APPROVED_STATUSES = ("approved", "written", "partial", "failed")

    def approved_labels(self):
        """Every label Operator approved, in report order, whether or not a write was recorded."""
        items = self.blocks + self.letters + [o for q in self.questions for o in q.get("options") or []]
        return [str(i.get("label")) for i in items if i.get("status") in self.APPROVED_STATUSES]

    def reconciled(self, lab):
        """Write rows for a label plus a not-attempted row for each approved change with no write."""
        rows = [w for w in self.writes if str(w.get("label")) == lab]
        item = self.item_for(lab)[0]
        if item is None or (not rows and item.get("status") not in self.APPROVED_STATUSES):
            return rows
        tried = {write_key(w) for w in rows}
        return rows + [{"label": lab, "object": k[0], "id": k[1] or "", "field": k[2], "outcome": "not_attempted",
                        "detail": "no write recorded"} for k in expected_keys(item) if k not in tried]

    def counts_line(self):
        c = self.count_values()
        return (f"{n(c['open'], 'open deal', 'open deals')} · {c['reviewed']} reviewed · {c['flagged']} flagged · "
                f"{n(c['blocks'], 'clear recommendation', 'clear recommendations')} · "
                f"{n(c['questions'], 'question', 'questions')} · {n(c['written'], 'record written', 'records written')}")

    # ---- pieces
    def change_line(self, c):
        if c.get("action") == "create":
            f = c["fields"]
            who = self.link("Contact", f["WhoId"], c["who_name"])
            return (f"New Task · {f['Subject']} · ActivityDate {f['ActivityDate']} · Status {f['Status']} · "
                    f"Contact {who} · Opportunity {self.deal_link(f['WhatId'])}")
        if c["object"] == "Task":
            head = f"Task · {self.link('Task', c['id'], display(c.get('name')))}"
        else:
            head = "Opportunity"
        if c.get("mode") == "prepend":
            return f"{head} · {c['field']} · new first entry · {exact(c['proposed'])}"
        line = f"{head} · {c['field']} · {display(c.get('current'))} → {exact(c['proposed'])}"
        if c.get("task_kind") == "close_duplicate":
            line += f" · duplicate of {self.link('Task', c['duplicate_of'], 'Task ' + c['duplicate_of'])}"
        return line

    def evidence_line(self, e):
        parts = [str(e["date"]), e["source"]]
        if e.get("who"):
            parts.append(display(e["who"]))
        if e.get("title"):
            t = display(e["title"])
            parts.append(f"[{t}]({e['link']})" if e.get("link") else f"\"{t}\"")
        parts.append(display(e["fact"]))
        return "- " + " · ".join(parts)

    def uses_retrieved(self, evidence_lists):
        return any(e.get("source") in RETRIEVED_SOURCES | {"Slack"} for ev in evidence_lists for e in ev or [])

    def kept_task(self, item):
        rid = item.get("followup_task")
        lines = [f"Task kept · {self.link('Task', rid, 'Task ' + rid)}"] if rid and str(rid).startswith("00T") else []
        triage_task = item.get("triage_owned_task")
        if item.get("triage_task_gap") is True:
            lines.append("Triage owns the Task gap · no Task change")
        if triage_task:
            task_id = triage_task["Id"]
            lines.append(f"Triage owns Task {task_id} · {self.link('Task', task_id, 'Task')} · no Task change")
        for milestone in item.get("retained_milestones") or []:
            lines.append(f"Later milestone Task kept · {self.link('Task', milestone['task_id'], 'Task ' + milestone['task_id'])}"
                         f" · due {milestone['due_date']} · {self.link('Event', milestone['event_id'], 'Event ' + milestone['event_id'])}"
                         f" · {display(milestone['reason'])}")
        return lines

    def block_lines(self, b):
        ns = b["next_step"]
        out = [f"{b['label']}. {self.deal_link(b['deal'])}", "", "### Current next steps"]
        full = ns.get("proposed_full") is not None
        out.append(display(ns.get("current_full") if full else ns.get("current")))
        out += ["", "### Field recommendations"]
        if full:
            out.append(exact(ns["proposed_full"]))
        else:
            out.append(exact(ns["proposed"]) if ns.get("proposed") is not None else NO_NEXT_STEP_CHANGE)
        changes = b.get("changes") or []
        kept = self.kept_task(b)
        if changes or kept:
            out.append("")
            out += ["- " + self.change_line(c) for c in changes] + ["- " + k for k in kept]
        out += ["", "### Evidence"] + [self.evidence_line(e) for e in b["evidence"]]
        return out

    def shows_legacy(self):
        currents = [(b.get("next_step") or {}).get("current") for b in self.active(self.blocks)]
        currents += [q.get("next_step_current") for q in self.active(self.questions)]
        return any(display(c).startswith("Next:") for c in currents if c)

    def shown_coverage(self):
        """Checker lines for display, each once. Receipt JSON, ignored-file notes, and the checker's own verdict stay in
        the saved file. Per-file diagnostics stay there too and show as one count."""
        shown, per_file = [], 0
        for line in map(str, self.coverage.get("lines") or []):
            if line.startswith(COVERAGE_HIDDEN_PREFIXES) or ": ignored " in line:
                continue
            if COVERAGE_FILE_LINE.match(line):
                per_file += 1
            elif line not in shown:
                shown.append(line)
        if per_file:
            shown.append(f"{n(per_file, 'per-file diagnostic', 'per-file diagnostics')} kept in the saved coverage file.")
        return shown

    def status_line(self, linked=True):
        """One header line when coverage or the run is incomplete, or a deal is withheld. None otherwise."""
        held = [w["deal"] for w in self.data.get("withheld") or []]
        complete = self.coverage_ready() and self.process_complete()
        if complete and not held:
            return None
        names = [self.deal_link(d) if linked else display(self.deals[d]["name"]) for d in held]
        parts = ["Withheld" if complete else "Incomplete", f"{len(held)} withheld"] + ([", ".join(names)] if names else [])
        return " · ".join(parts + ["Details under Coverage."])

    def coverage_lines(self):
        lines = self.shown_coverage()
        for note in self.run.get("slack_coverage_notes") or []:
            contacts = ", ".join(dict.fromkeys(map(display, note["contacts"])))
            deal = self.link("Opportunity", note["deal"], display(note["name"]))
            lines.append(f"Slack not checked · {deal} · {contacts} · {display(note['reason'])}")
        for w in self.data.get("withheld") or []:
            lines.append(f"Withheld · {self.deal_link(w['deal'])} · {w['reason']}")
        if not self.process_complete():
            lines += [f"Run incomplete · {g}" for g in self.run.get("process_gaps") or []]
        return lines

    def operator_statement_valid(self, stated):
        if not isinstance(stated, dict) or not self.date:
            return False
        quote = stated.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            return False
        try:
            return date.fromisoformat(stated.get("date")) <= self.date
        except (TypeError, ValueError):
            return False

    def size_floor_exception(self, description):
        if description is None:
            return False
        if not isinstance(description, str) or not self.date:
            return None
        phrase = "Size floor exception, kept open by Operator "
        stamp = r"\d{1,2}/\d{1,2}/\d{2}"
        suffix = re.escape(self.policy["salesforce"]["note_prefix"].replace("M/D/YY", "", 1))
        pattern = rf"(?:(?P<prefix>{stamp}){suffix})?{re.escape(phrase)}(?P<decision>{stamp})"
        ambiguous = False
        for line in description.splitlines():
            if phrase not in line:
                continue
            match = re.fullmatch(pattern, line.strip())
            if match:
                try:
                    dates = [parse_mdy(value) for value in match.groups() if value]
                    if all(value <= self.date for value in dates):
                        return True
                except ValueError:
                    pass
            ambiguous = True
        return None if ambiguous else False

    def lost_path_destination(self, reviewed):
        if not isinstance(reviewed, dict):
            return None
        if reviewed.get("reason") not in {"buyer_deferral", "departed_sponsor"}:
            return None
        if not isinstance(reviewed.get("from_stage"), str) or not re.fullmatch(r"S[2-5]", reviewed["from_stage"]):
            return None
        if reviewed.get("evidence_complete") is not True or reviewed.get("buyer_step_within_three_months") is not False:
            return None
        if "employees" not in reviewed or "description" not in reviewed:
            return None
        employees = reviewed["employees"]
        if employees in (None, ""):
            answer = reviewed.get("operator_employee_count")
            if not self.operator_statement_valid(answer):
                return None
            employees = answer.get("value")
        floor = self.policy["pipeline"].get("worth_growing_min_employees")
        if type(employees) is not int or employees < 0 or type(floor) is not int or floor <= 0:
            return None
        exception = self.size_floor_exception(reviewed["description"])
        if exception is None:
            return None
        return "S1" if exception or employees >= floor else "Closed Lost"

    def check_size_exception_letter(self, letter):
        change = letter["change"]
        statement = letter.get("operator_size_exception")
        if not self.operator_statement_valid(statement):
            self.err("size-floor exception needs Operator's reviewed quote and dated instruction")
            return
        if "current" not in change or change["current"] is not None and not isinstance(change["current"], str):
            self.err("size-floor exception needs the exact native Description baseline")
        existing = self.size_floor_exception(change.get("current"))
        if existing is None:
            self.err("size-floor exception needs an unambiguous native Description baseline")
        elif existing is True:
            self.err("size-floor exception already exists, do not duplicate it")
        decision = date.fromisoformat(statement["date"])
        dated = lambda value: f"{value.month}/{value.day}/{value.year % 100:02d}"
        prefix = self.policy["salesforce"]["note_prefix"].replace("M/D/YY", dated(self.date), 1)
        expected = prefix + "Size floor exception, kept open by Operator " + dated(decision)
        if change.get("mode") != "prepend" or change.get("proposed") != expected:
            self.err("size-floor exception only permits the exact dated marker prepended with the note prefix")

    def check_qualification(self):
        if not isinstance(self.qualification, list):
            self.err("friday.qualification must be a complete reviewed list")
            return
        if self.qualification and self.run.get("branch") != "friday":
            self.err("qualification is Friday only")
        rows = {}
        for row in self.qualification:
            if not isinstance(row, dict):
                self.err("qualification rows must be objects")
                continue
            identifier = row.get("deal")
            self.check_id("Opportunity", identifier, "qualification")
            if identifier in rows:
                self.err("qualification deals must be distinct")
            rows[identifier] = row
            if row.get("stage") not in self.policy["pipeline"].get("early_stages", []):
                self.err("qualification stage must be an early stage from policy")
            if not row.get("name") or not row.get("summary"):
                self.err("qualification needs name and summary")
            action = row.get("action")
            if action == "closed_lost":
                if "lost_path_size" in row:
                    if row.get("stage") != "S1" or self.lost_path_destination(row["lost_path_size"]) != "Closed Lost":
                        self.err("qualification Closed Lost needs reviewed lost-path size below the floor without an exception")
                elif "operator_stated_no" in row:
                    if not self.operator_statement_valid(row.get("operator_stated_no")):
                        self.err("qualification Closed Lost on Operator's stated no needs his quote and a date on or before the run date")
                elif not self.date or not closed_lost_silence_eligible(
                        row.get("last_buyer_activity"), datetime.combine(self.date, datetime.min.time()), self.policy,
                        row.get("evidence_complete"), row.get("upcoming_event")):
                    self.err("qualification Closed Lost needs reviewed silence and no upcoming Event")
            elif action == "triage":
                if identifier not in {item["deal"] for item in self.data.get("triage", [])}:
                    self.err("qualification triage must name a read-only triage finding")
            elif action == "needs_input":
                if not any(question.get("deal") == identifier and question.get("status") == "open" for question in self.questions):
                    self.err("qualification needs_input must name an existing open question")
            else:
                self.err("qualification action must be closed_lost, triage, or needs_input")
        items = self.blocks + self.letters + [{**option, "deal": question.get("deal")} for question in self.questions
                                             for option in question.get("options") or []]
        for item in items:
            row = rows.get(item.get("deal"))
            if item.get("status") == "superseded":
                continue
            changes = item.get("changes") or ([item["change"]] if item.get("change") else [])
            basis = item.get("lost_path_size") if "lost_path_size" in item else (row or {}).get("lost_path_size")
            if "lost_path_size" in item and "lost_path_size" in (row or {}) and basis != row["lost_path_size"]:
                self.err("lost-path size letter and qualification must use the same reviewed facts")
            if "lost_path_size" in item or "lost_path_size" in (row or {}):
                destination = self.lost_path_destination(basis)
                for change in changes:
                    if change.get("field") == "StageName":
                        current = change.get("current")
                        stage = re.match(r"S([0-5])(?:\b|\s|-)", current) if isinstance(current, str) else None
                        if not stage or int(stage.group(1)) < 1 or not destination or change.get("proposed") != destination:
                            self.err("lost-path size StageName proposal needs the supported size-floor destination")
                        elif int(stage.group(1)) >= 2 and basis["from_stage"] != "S" + stage.group(1):
                            self.err("lost-path size origin must match the current S2+ stage")
                        elif stage.group(1) == "1" and destination == "S1":
                            self.err("lost-path size already at S1 stays open without a redundant stage proposal")
            if not row:
                continue
            for change in changes:
                if change.get("object") != "Opportunity":
                    continue
                if change.get("field") == "StageName" and (change.get("proposed") != "Closed Lost" or row.get("action") != "closed_lost"):
                    self.err("qualification never proposes an upward stage move")
                if change.get("field") == "Amount" and (row.get("stage") != "S1" or row.get("missing_amount") is not True
                                                        or not is_blank(change.get("current")) or item.get("buyer_confirmed") is not True):
                    self.err("qualification Amount needs a missing S1 Amount and reviewed buyer evidence")

    def friday_lines(self):
        fr = self.friday
        roll = fr.get("rollup") or {}
        stages = " | ".join(f"{s['stage']} {s['count']} · ${s['amount']:,}" for s in roll.get("stages") or [])
        fc = roll.get("forecast") or {}
        tq, later = roll.get("this_quarter") or {}, roll.get("later") or {}
        out = ["## Rollup", stages or "No open deals.",
               f"Commit ${fc.get('Commit', 0):,} · Best Case ${fc.get('Best Case', 0):,} · "
               f"Pipeline ${fc.get('Pipeline', 0):,} · Omitted {fc.get('Omitted', 0)}",
               f"Closing this quarter {tq.get('count', 0)}, ${tq.get('amount', 0):,}. "
               f"Later {later.get('count', 0)}, ${later.get('amount', 0):,}.", "",
               f"## Since {fr.get('since')}"]
        delta = fr.get("delta") or []
        out += [f"- {d['kind']} · {self.deal_link(d['deal']) if d.get('deal') in self.deals else self.link('Opportunity', d.get('deal'), d.get('name') or d.get('deal'))} · {d['text']}" for d in delta] or ["No changes."]
        out += ["", "## Qualification", f"{len(self.qualification)} early-stage deals reviewed. Showing {min(len(self.qualification), 10)}."]
        for row in self.qualification[:10]:
            deal = self.link("Opportunity", row["deal"], display(row["name"]))
            summary = display(row["summary"]).replace("\n", " ")
            out.append(f"- {deal} · {row['stage']} · {summary}")
        if not self.qualification:
            out.append("No early-stage deals.")
        out += ["", "## Record proposals"]
        letters = self.active(self.letters)
        if not letters:
            out.append("No record proposals.")
        for l in letters:
            ev = " ".join(self.evidence_line(e)[2:] for e in l["evidence"])
            deal = self.link("Opportunity", l["deal"], display(l["deal_name"]))
            out.append(f"{l['label']}. {deal} · {self.change_line(l['change'])} · {l['basis']} · {ev}")
            out.extend("   - " + line for line in self.kept_task(l))
        if any(e.get("source") == "Slack" for letter in letters for e in letter["evidence"]):
            out += ["", LIMITATION]
        return out

    # ---- modes
    def report(self):
        c = self.count_values()
        d = md(self.date)
        status = self.status_line()
        head = [self.counts_line()] + ([status] if status else [])
        blocks, questions = self.active(self.blocks), self.active(self.questions)
        if blocks or questions:
            head.append(HISTORY_NOTE + (" " + LEGACY_NOTE if self.shows_legacy() else ""))
        out = [f"# Pipeline review · {d}", "", "  \n".join(head), ""]
        out += ["## Routed to deal threads", ""]
        routed = self.routing_rows("delivered")
        if routed:
            out += [f"{len(routed)} routed · counted separately from local proposals", ""]
            out += [f"- [{display(row['name'])}]({row['thread_url']}) · {display(row['reason'])}"
                    f" · routed via {row['delivery']['command']}" for row in routed]
            out += [""]
        else:
            out += ["None.", ""]
        if self.data.get("triage"):
            out += ["## Triage owns Tasks and next steps", ""]
            for row in self.data["triage"]:
                deal = self.link("Opportunity", row["deal"], display(row["name"]))
                out += [f"- {deal} · {display(row['reason'])}"]
                out += [f"  - {line}" for line in self.kept_task(row)]
            out += [""]
        out += ["## Clear recommendations", ""]
        if blocks:
            for b in blocks:
                out += self.block_lines(b) + [""]
            if self.uses_retrieved([b["evidence"] for b in blocks]):
                out += [LIMITATION, ""]
        else:
            out += [EMPTY_BLOCKS, ""]
        out += ["## Needs your input", ""]
        failed = self.routing_rows("failed")
        if failed:
            out += [f"- [{display(row['name'])}]({row['thread_url']}) · routing failed, needs input"
                    f" · {row['delivery']['command']} · {display(row['reason'])}" for row in failed]
            out += [""]
        if questions:
            out += ["  \n".join(f"{q['label']} · {self.deal_link(q['deal'])} · {display(q['context'])}" for q in questions), ""]
            if self.uses_retrieved([q["evidence"] for q in questions]):
                out += [LIMITATION, ""]
            out += [WALK_NOTE, ""]
        elif not failed:
            out += [EMPTY_QUESTIONS, ""]
        if self.run["branch"] == "friday":
            out += self.friday_lines() + [""]
        out += ["## Coverage", "", "  \n".join(self.coverage_lines()), ""]
        out += [f"{n(c['no_trigger'], 'reviewed deal', 'reviewed deals')} had no trigger · {c['not_checked']} not checked", ""]
        if c["blocks"] or c["letters"]:
            out.append(APPROVE_FRIDAY)
        else:
            out.append(NO_CHANGES)
        return "\n".join(out).rstrip() + "\n"

    def question(self, label):
        questions = self.active(self.questions)
        q = next((x for x in questions if x.get("label") == label), None)
        if q is None:
            raise RenderError(f"question {label} is not an active question")
        if q.get("status") != "open":
            raise RenderError(f"question {label} is {q.get('status')}, not open")
        pos = questions.index(q) + 1
        out = [f"{q['label']} · {pos} of {len(questions)} · {self.deal_link(q['deal'])} · {display(q['context'])}", "",
               "### Current next steps", display(q.get("next_step_current")), "", "### Question", display(q["question"])]
        opts = [o for o in self.live_options(q) if o.get("status") == "proposed"]
        lines = []
        for o in opts:
            changes = o.get("changes") or []
            lines.append(f"- {o['label']} · {display(o['text'])}" + ("" if changes else " · no write"))
            lines += [f"  - {self.change_line(ch)}" for ch in changes] + [f"  - {k}" for k in self.kept_task(o)]
        lines.append(f"- {SKIP_OPTION}")
        out += [""] + lines + ["", "### Evidence"] + [self.evidence_line(e) for e in q["evidence"]]
        if self.uses_retrieved([q["evidence"]]):
            out += ["", LIMITATION]
        labels = ", ".join(o["label"] for o in opts)
        reply = f"Reply {labels}, or skip." if labels else "Reply with your answer, or skip."
        out += ["", f"**{reply} Any other answer becomes a new option before anything is written.**"]
        return "\n".join(out) + "\n"

    def item_for(self, label):
        for b in self.blocks:
            if str(b.get("label")) == label:
                return b, self.deal_link(b["deal"])
        for l in self.letters:
            if str(l.get("label")) == label:
                return l, self.link("Opportunity", l.get("deal"), display(l.get("deal_name")))
        for q in self.questions:
            for o in q.get("options") or []:
                if str(o.get("label")) == label:
                    return o, self.deal_link(q["deal"])
        return None, label

    def receipt(self, labels, final):
        written_labels = [str(w["label"]) for w in self.writes]
        wanted = labels or list(dict.fromkeys(written_labels + (self.approved_labels() if final else [])))
        out = ["**Receipt**", ""]
        totals = {k: 0 for k in WRITE_OUTCOMES}
        for lab in wanted:
            item, where = self.item_for(lab)
            if item is None:
                raise RenderError(f"label {lab} is not in this run")
            rows = self.reconciled(lab)
            if not rows:
                out += [f"{lab} · {where} · no write recorded", ""]
                continue
            records = record_outcomes(rows)
            n_ok = sum(1 for w in rows if w["outcome"] == "written")
            if n_ok == len(rows):
                state = "written"
            elif n_ok:
                state = "partial"
            elif all(w["outcome"] == "not_attempted" for w in rows):
                state = "approved, not attempted"
            else:
                state = "failed"
            out.append(f"{lab} · {where} · {state}")
            for outcome in records:
                totals[outcome] += 1
            for w in rows:
                target = self.link(w["object"], w["id"], w["object"]) if w["id"] else w["object"]
                line = f"- {OUTCOME_TEXT[w['outcome']]} · {target} · {w['field']}"
                if w.get("detail"):
                    line += f" · {display(w['detail'])}"
                out.append(line)
            if state == "partial":
                out.append(f"- {n_ok} of {len(rows)} changes written. Written changes are kept and not repeated.")
            out.append("")
        out.append(f"{n(totals['written'], 'record written', 'records written')} · {totals['rejected']} rejected · "
                   f"{totals['unverified']} unverified · {totals['not_attempted']} not attempted · "
                   f"{n(self.counts['open'], 'open deal', 'open deals')} at run start")
        if final:
            out += ["", "**Close**", ""] + self.close_lines()
        return "\n".join(out).rstrip() + "\n"

    def close_lines(self):
        c = self.count_values()
        skipped = [x for x in self.active(self.blocks) + self.active(self.letters) if x.get("status") == "skipped"]
        lines = [f"{n(c['open'], 'open deal', 'open deals')} · {c['reviewed']} reviewed · {c['flagged']} flagged · "
                 f"{c['blocks'] + c['letters']} proposed · {n(c['written'], 'record written', 'records written')} · "
                 f"{len(skipped)} skipped · {c['not_checked']} not checked"]
        named = []
        words = {"skipped": "Skipped", "deferred": "Deferred", "proposed": "Unanswered", "approved": "Approved, not attempted"}
        for b in self.active(self.blocks):
            if b.get("status") in words:
                named.append(f"{words[b['status']]} · {b['label']} · {self.deal_link(b['deal'])}")
        for l in self.active(self.letters):
            if l.get("status") in words:
                named.append(f"{words[l['status']]} · {l['label']} · {self.item_for(str(l['label']))[1]}")
        for q in self.active(self.questions):
            if q.get("status") in ("open", "skipped", "deferred"):
                word = {"open": "Unanswered", "skipped": "Skipped", "deferred": "Deferred"}[q["status"]]
                named.append(f"{word} · {q['label']} · {self.deal_link(q['deal'])}")
        return ["  \n".join(lines + named)] if named else lines

    def notification(self):
        c = self.count_values()
        d = md(self.date)
        ready = self.coverage_ready() and self.process_complete() and not c["routing_failed"]
        url = self.run["thread_url"]
        proposals = c["blocks"] + c["letters"]
        open_q = sum(1 for q in self.active(self.questions) if q.get("status") == "open")
        if ready and open_q == 0:
            status = "ready" if proposals else "complete"
        else:
            status = "incomplete"
        parts = [self.counts_line()]
        if status == "incomplete":
            gaps = self.gap_summary()
            if not self.process_complete():
                gaps += [f"Run incomplete · {g}" for g in self.run.get("process_gaps") or []]
            if open_q:
                gaps.append(f"Needs input · {n(open_q, 'open question', 'open questions')}")
            if c["routing_failed"]:
                gaps.append(f"Needs input · {n(c['routing_failed'], 'failed delivery', 'failed deliveries')}")
            parts = gaps + parts
        payload = {"title": TITLE_FRIDAY[status], "body": " · ".join(parts + [url]), "channels": ["in_app"]}
        if self.run.get("schedule"):
            payload["schedule_description"] = self.run["schedule"]
        return {"send": True, "status": status, **payload}

    def gap_summary(self):
        status = self.status_line(linked=False)
        return [status.replace(" · Details under Coverage.", "")] if status else []


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render pipeline-review output from the reviewed run file.")
    ap.add_argument("mode", choices=["report", "question", "receipt", "notification"])
    ap.add_argument("--run", required=True)
    ap.add_argument("--coverage")
    ap.add_argument("--label")
    ap.add_argument("--labels")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--policy", default=str(DEFAULT_POLICY))
    ap.add_argument("--sources", type=Path, help="Explicit saved connector result directory; required when multiple sessions exist")
    args = ap.parse_args(argv)
    try:
        policy = yaml.safe_load(Path(args.policy).read_text())
        data = load_json(args.run)
        coverage = load_json(args.coverage) if args.coverage else None
        sources = resolve_calls_dir(args.sources)
    except (OSError, ValueError, yaml.YAMLError, RenderError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.mode in ("report", "notification") and not args.coverage:
        print(f"{args.mode} needs --coverage", file=sys.stderr)
        return 2
    if args.mode == "question" and not args.label:
        print("question needs --label", file=sys.stderr)
        return 2
    run = Run(data, policy, coverage, load_sources(sources))
    errors = run.validate(args.mode)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    try:
        if args.mode == "report":
            out = run.report()
        elif args.mode == "question":
            out = run.question(args.label)
        elif args.mode == "receipt":
            labels = [x.strip() for x in args.labels.split(",")] if args.labels else None
            out = run.receipt(labels, args.final)
        else:
            out = json.dumps(run.notification(), ensure_ascii=False) + "\n"
    except RenderError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
