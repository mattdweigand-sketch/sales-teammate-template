#!/usr/bin/env python3
"""Render the pipeline-review report, question walk, write receipt, and notification.

Usage (run from the sandbox root with explicit sandbox paths):
  pipeline_render.py report       --run RUN.json --coverage COVERAGE.json [--sources DIR] [--policy PATH]
  pipeline_render.py question     --run RUN.json --label Q1 [--sources DIR] [--policy PATH]
  pipeline_render.py receipt      --run RUN.json [--labels 1,Q1-a,A] [--final] [--sources DIR] [--policy PATH]
  pipeline_render.py notification --run RUN.json --coverage COVERAGE.json [--sources DIR] [--policy PATH]
--sources is the saved tool-call folder, default the current run's call_external_tool folder.

This file owns the exact presentation. The workflow writes one reviewed run file per run
in the sandbox, and passes the saved `coverage_check --json` output for this run and scope.
The helper validates structure, reconciles counts, and checks labels. It never infers sales
facts, chooses actions, grants approval, or writes to any system. A clean render is not a
ready run: coverage and process status come from the inputs and are printed as given.

Exit 0 rendered to stdout. Exit 1 validation failed, errors on stderr, nothing on stdout.
Exit 2 unreadable input or usage error.

Run file keys
  run        id, date (YYYY-MM-DD), branch (weekday|friday), coverage_scope
             (pipeline-daily on weekday, pipeline on Friday), process_status (complete|incomplete),
             process_gaps (list, required when incomplete), thread_url and schedule (notification)
             slack_coverage_notes (optional list of {deal, name, contacts [names], reason}, one per deal)
  counts     open (Collect count, all stages), reviewed (hygiene plus Friday qualification), not_checked
  deals      every flagged deal once: id (006...), name, flags (trigger names)
  routed     optional list of {deal, name (Account), thread_url, reason}, owned by deal threads,
             counted separately from flagged deals and never eligible for local proposals
  today_actions  weekday report candidates from the existing reads, each with deal,
                 name, kind (buyer_reply|meeting|due|date_at_risk), date (YYYY-MM-DD),
                 reason (one line), evidence (list), size under policy.forecast.amount_field.
                 buyer_reply adds reply_reviewed true; blank size never falls back to Amount
  withheld   list of {deal, reason}; required, possibly empty, when coverage is not ready. It holds every
             flagged deal in the coverage `affected` list, or every flagged deal when `affected` is null
  blocks     clear recommendations: label ("1", "2"...), deal, status, next_step {current,
             proposed or null, optional current_full and proposed_full for a history change},
             changes (list), evidence (list), optional depends_on_unknown, superseded_by
  questions  label ("Q1"...), deal, status, context, question, next_step_current, evidence,
             options: label ("Q1-a"...), text, status, changes (empty for a factual answer)
  friday     Friday only: qualification [{deal, name, stage, action, summary, reviewed date/evidence}],
             rollup {stages [{stage, count, amount}], forecast {Commit, Best Case,
             Pipeline, Omitted}, this_quarter {count, amount}, later {count, amount}},
             since ("M/D"), delta [{kind, deal, text}], letters [{label "A"..., deal,
             deal_name, status, change, evidence, basis}]
  writes     one per record field attempted: label, object, id, field ("create" for a Task
             create), outcome (written|rejected|unverified|not_attempted), detail. Each write
             must match an approved change of its label; a change with no write is not attempted.
A change is {object Opportunity|Task, id, field, current, proposed, name}. Opportunity fields in
blocks and options: Next_Steps__c plus policy.pipeline required_fields and conditional_fields.
Letters add CloseDate, StageName, Amount. Task fields: ActivityDate, Subject, Status, Description.
Task updates add task_kind and same_action true; task_kind must match the field and value
(ActivityDate reschedule, Subject rename, Description update, Status Completed complete or
close_duplicate, other Status update). complete adds completion_evidence; close_duplicate adds
duplicate_of and appears only in question options.
mode "prepend" marks a new first line kept above existing text; question options and letters may
carry Next_Steps__c only this way. A Task create
is {object Task, action create, fields {Subject, ActivityDate, Status, WhoId, WhatId}, who_name,
linkage_verified true, candidates_refreshed true}. Salesforce, Operator, and Pilot report evidence is {date,
source, who, title, fact}. Gmail and Calendar evidence is {source, who, fact, source_id}, where source_id is an
email_id or event_id in the saved results; the helper fills date, title, and link from that record and rejects
them in the run file. Gmail evidence adds quote, copied verbatim from the saved message body. source_id and
quote are checked, never rendered.
Slack evidence is {date, source Slack, who, title, link, fact}, with its date and permalink from the saved message.
A block, option, or letter that changes Next_Steps__c carries a Task create or ActivityDate
reschedule, or followup_task: the Id of the kept open Task already on the new due date, or on a
letter the label of the letter holding the Task change (rules#followup_task).
Optional retained_milestones on a block, option, or letter is a list of
{task_id, event_id, due_date (YYYY-MM-DD), reason, action_verified true}. These are
reviewed later Tasks kept alongside the current follow-up, never a substitute for it.
Statuses: proposed, approved, written, partial, failed, skipped, deferred, superseded; questions
use open, answered, skipped, deferred, superseded.
"""
import argparse
import html
import json
import re
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "_core" / "scripts"))
from _saved_json import load_saved, parse_email_date, resolve_calls_dir
from hygiene_check import closed_lost_silence_eligible, is_blank

ROOT = Path(__file__).resolve().parents[5]
DEFAULT_POLICY = ROOT / "_core" / "policy.yaml"

ITEM_STATUSES = {"proposed", "approved", "written", "partial", "failed", "skipped", "deferred", "superseded"}
QUESTION_STATUSES = {"open", "answered", "skipped", "deferred", "superseded"}
WRITE_OUTCOMES = {"written", "rejected", "unverified", "not_attempted"}
OUTCOME_RANK = ("rejected", "unverified", "not_attempted", "written")
OUTCOME_TEXT = {"written": "Written", "rejected": "Rejected", "unverified": "Unverified", "not_attempted": "Not attempted"}
TASK_KINDS = {"reschedule", "rename", "complete", "update", "close_duplicate"}
TASK_FIELD_KINDS = {"ActivityDate": {"reschedule"}, "Subject": {"rename"}, "Description": {"update"}}
LETTER_ONLY_FIELDS = {"CloseDate", "StageName", "Amount"}
SCOPE_FOR_BRANCH = {"weekday": "pipeline-daily", "friday": "pipeline"}
CREATE_FIELDS = ("Subject", "ActivityDate", "Status", "WhoId", "WhatId")
COVERAGE_HIDDEN_PREFIXES = ("Domain-matched ", "Coverage ready.", "Report not ready:")
COVERAGE_FILE_LINE = re.compile(r"^\S+\.json: ")
QUOTE_MIN_CHARS = 12
ID_PREFIX = {"Opportunity": "006", "Task": "00T", "Contact": "003", "Event": "00U"}
BLOCK_LABEL = re.compile(r"^[1-9]\d*$")
QUESTION_LABEL = re.compile(r"^Q[1-9]\d*$")
LETTER_LABEL = re.compile(r"^[A-Z]{1,2}$")
EVIDENCE_SOURCES = {"Gmail", "Calendar", "Slack", "Salesforce", "Operator", "Pilot report"}
RETRIEVED_SOURCES = {"Gmail", "Calendar"}
TODAY_ACTION_ORDER = {"buyer_reply": 0, "meeting": 1, "due": 2, "date_at_risk": 3}

LIMITATION = "Email, Calendar, and Slack evidence is the retrieved set, not full history."
HISTORY_NOTE = "Only the latest next-step entry is shown. Older history stays unchanged."
LEGACY_NOTE = "Legacy `Next:` entries appear as stored."
EMPTY_BLOCKS = "No clear recommendations."
EMPTY_QUESTIONS = "No questions."
WALK_NOTE = "I walk these one at a time after the clear recommendations."
NO_CHANGES = "No Salesforce changes proposed."
NO_NEXT_STEP_CHANGE = "No next-step change."
SKIP_OPTION = "skip · Leave unchanged. Named at close."
APPROVE_WEEKDAY = "**Reply with numbers, ranges, all, or skip. all covers the numbered clear recommendations only.**"
APPROVE_FRIDAY = ("**Reply with numbers, ranges, all, letters, or skip. all covers the numbered clear "
                  "recommendations only. Each letter approves one record.**")
TITLE_WEEKDAY = "Pipeline review · {d}"
TITLE_FRIDAY = {"ready": "Friday pipeline review ready for approval",
                "complete": "Friday pipeline review complete",
                "incomplete": "Friday pipeline review incomplete"}


class RenderError(Exception):
    pass


def plain(text):
    """Comparable text: tags removed, entities decoded, whitespace collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", str(text or ""))).split())


def load_sources(folder):
    """Index saved Gmail messages by email_id and Calendar events by event_id. Unreadable files are skipped."""
    found = {"Gmail": {}, "Calendar": {}}
    for path in sorted(Path(folder).glob("output_*.json")) if Path(folder).is_dir() else []:
        try:
            result = load_saved(path)
        except (OSError, ValueError):
            continue
        if not isinstance(result, dict):
            continue
        for key, rows, source, rid in (("email_results", "emails", "Gmail", "email_id"),
                                       ("calendar_event_list", "events", "Calendar", "event_id")):
            page = result.get(key)
            for rec in (page.get(rows) if isinstance(page, dict) else None) or []:
                if isinstance(rec, dict) and rec.get(rid):
                    found[source][rec[rid]] = rec
    return found


def load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise RenderError(f"cannot read {path}: {exc}") from exc


def md(d):
    return f"{d.month}/{d.day}/{d.strftime('%y')}"


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
    """Record fields a label approves: a block's next step and changes, a letter's change, an option's changes."""
    keys = [change_key(c) for c in ([item["change"]] if isinstance(item.get("change"), dict) else item.get("changes") or [])]
    if (item.get("next_step") or {}).get("proposed") is not None:
        keys.insert(0, ("Opportunity", item.get("deal"), "Next_Steps__c"))
    return keys


def task_kinds_for(field, proposed):
    """The task_kind values a Task field and proposed value can honestly carry, or None for a field never changed here."""
    if field == "Status":
        return {"complete", "close_duplicate"} if proposed == "Completed" else {"update"}
    return TASK_FIELD_KINDS.get(field)


def record_outcomes(rows):
    """One outcome per (label, object, id) record: written only when every field row for it is written."""
    grouped = {}
    for w in rows:
        grouped.setdefault((str(w.get("label")), w.get("object"), w.get("id")), []).append(w.get("outcome"))
    return [min(v, key=OUTCOME_RANK.index) if all(o in OUTCOME_RANK for o in v) else "unverified"
            for v in grouped.values()]


class Run:
    def __init__(self, data, policy, coverage=None, sources=None):
        self.data = data
        self.policy = policy
        self.coverage = coverage
        self.sources = sources or {"Gmail": {}, "Calendar": {}}
        tz = ((policy.get("pipeline") or {}).get("schedule") or {}).get("daily", {}).get("tz")
        self.tz = ZoneInfo(tz) if tz else None
        self.errors = []
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
        self.block_fields = {"Next_Steps__c"}
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

    # ---- validation
    def check_id(self, obj, rid, where):
        pre = ID_PREFIX.get(obj)
        if not isinstance(rid, str) or len(rid) not in (15, 18) or (pre and not rid.startswith(pre)):
            self.err(f"{where}: {obj} id {rid!r} is not a valid {obj} Id")

    def check_evidence(self, items, where, required=True):
        if required and not items:
            self.err(f"{where}: needs at least one evidence item")
        for n, e in enumerate(items or [], 1):
            w = f"{where} evidence {n}"
            if e.get("source") in RETRIEVED_SOURCES:
                self.resolve_retrieved(e, w)
            if not e.get("date") or not e.get("fact"):
                self.err(f"{w}: date and fact are required")
            if e.get("source") not in EVIDENCE_SOURCES:
                self.err(f"{w}: source must be one of {sorted(EVIDENCE_SOURCES)}")
            if e.get("source") == "Slack" and not all(e.get(key) for key in ("who", "title", "link")):
                self.err(f"{w}: Slack evidence needs a sender, title, and returned permalink")
            link = e.get("link")
            if link and not re.match(r"^https://\S+$", link):
                self.err(f"{w}: link must be a returned https URL, never constructed")
            if link and not e.get("title"):
                self.err(f"{w}: a link needs a title to display")

    def resolve_retrieved(self, e, w):
        """Gmail and Calendar evidence must point at a saved record. Date, title, and link come from it."""
        src = e["source"]
        if "_resolved" in e:
            return
        supplied = [k for k in ("date", "title", "link") if e.get(k)]
        if supplied:
            self.err(f"{w}: {', '.join(supplied)} must come from the saved {src} record; remove from the run file")
        rec = self.sources[src].get(e.get("source_id"))
        if rec is None:
            self.err(f"{w}: source_id {e.get('source_id')!r} is not in this run's saved {src} results")
            return
        if src == "Gmail":
            quote = plain(e.get("quote"))
            bodies = [plain(rec.get(k)) for k in ("body_uncompressed", "body")]
            if len(quote) < QUOTE_MIN_CHARS:
                self.err(f"{w}: Gmail evidence needs a quote of at least {QUOTE_MIN_CHARS} characters from the message body")
            elif not any(quote in b for b in bodies):
                self.err(f"{w}: quote is not in the saved message body for {e.get('source_id')}")
            when = parse_email_date(rec.get("date"))
            title, link = rec.get("subject"), rec.get("web_link")
        else:
            start = str(rec.get("start") or "")
            when = datetime.fromisoformat(start.replace("Z", "+00:00")) if "T" in start else date.fromisoformat(start[:10])
            title, link = rec.get("title"), rec.get("html_link") or rec.get("web_link")
        if isinstance(when, datetime) and self.tz:
            when = when.astimezone(self.tz)
        e.update(date=md(when), title=title or None, link=link if link and str(link).startswith("https://") else None,
                 _resolved=True)

    def check_change(self, c, where, letter=False, option=False):
        obj = c.get("object")
        if obj not in ("Opportunity", "Task"):
            self.err(f"{where}: object must be Opportunity or Task")
            return
        if c.get("action") == "create":
            if obj != "Task":
                self.err(f"{where}: only a Task can be created")
                return
            f = c.get("fields") or {}
            for key in CREATE_FIELDS:
                if not f.get(key):
                    self.err(f"{where}: Task create needs {key}")
            extra = sorted(set(f) - set(CREATE_FIELDS))
            if extra:
                self.err(f"{where}: Task create fields {extra} are not displayed; remove them or propose them separately")
            if f.get("WhoId"):
                self.check_id("Contact", f["WhoId"], where)
            if f.get("WhatId"):
                self.check_id("Opportunity", f["WhatId"], where)
            if c.get("linkage_verified") is not True:
                self.err(f"{where}: Task create needs linkage_verified true")
            if c.get("candidates_refreshed") is not True:
                self.err(f"{where}: Task create needs candidates_refreshed true, refresh open Tasks first")
            if not c.get("who_name"):
                self.err(f"{where}: Task create needs who_name")
            return
        self.check_id(obj, c.get("id"), where)
        field = c.get("field")
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
        if obj == "Opportunity" and c.get("field") == "Next_Steps__c":
            if not (letter or option):
                self.err(f"{where}: put Next_Steps__c in next_step, not changes")
            elif c.get("mode") != "prepend":
                self.err(f"{where}: a Next_Steps__c change adds a first entry with mode prepend, history unchanged")
        if obj == "Task":
            kind = c.get("task_kind")
            if kind not in TASK_KINDS:
                self.err(f"{where}: Task update needs task_kind {sorted(TASK_KINDS)}")
            honest = task_kinds_for(field, c.get("proposed"))
            if honest is None:
                self.err(f"{where}: Task {field} is not a permitted change; only {sorted(TASK_FIELD_KINDS) + ['Status']}")
            elif kind in TASK_KINDS and kind not in honest:
                self.err(f"{where}: task_kind {kind} does not match {field} → {c.get('proposed')}; expected {sorted(honest)}")
            if c.get("same_action") is not True:
                self.err(f"{where}: Task update needs same_action true, never retarget a Task to another action")
            if kind == "complete" and not c.get("completion_evidence"):
                self.err(f"{where}: Task complete needs completion_evidence")
            if kind == "close_duplicate":
                if not option:
                    self.err(f"{where}: closing a duplicate Task is a question option, never a clear recommendation")
                self.check_id("Task", c.get("duplicate_of"), where)
                if c.get("duplicate_of") == c.get("id"):
                    self.err(f"{where}: duplicate_of must name a different Task")
            if not c.get("name"):
                self.err(f"{where}: Task update needs name (Subject)")

    def check_followup(self, item, changes, where, task_letters=()):
        """rules#followup_task: a next-step change carries its Task change or names the kept Task."""
        if any(c.get("object") == "Task" and (c.get("action") == "create" or c.get("task_kind") == "reschedule")
               for c in changes):
            return
        keep = item.get("followup_task")
        if keep and str(keep) in task_letters:
            return
        if keep:
            self.check_id("Task", keep, where)
            return
        self.err(f"{where}: a next-step change needs a Task create or reschedule, or followup_task "
                 f"naming the kept open Task (rules#followup_task)")

    def check_milestones(self, item, changes, where):
        """Show the reviewed exception without allowing it to replace the current follow-up."""
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
            self.err("weekday report needs today_actions as a list, empty when no supported action exists")
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
                self.err(f"{where} reason must use plain prose without semicolons, em dashes, or colons")
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
                if e.get("source") in RETRIEVED_SOURCES and e.get("_resolved") and e.get("date") != md(when):
                    self.err(f"{where} date must match the saved source in the run timezone")
                if kind == "buyer_reply" and e.get("source") == "Gmail":
                    record = self.sources["Gmail"].get(e.get("source_id"), {})
                    sender = parseaddr(record.get("from_") or "")[1].lower()
                    if "@" not in sender or sender.rsplit("@", 1)[1] in self.policy["tooling"]["internal_domains"]:
                        self.err(f"{where} buyer reply needs an external sender in the saved message")

    def today_action_lines(self):
        """Rank candidates and show only the strongest reason for each deal."""
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
            owner = " · in deal thread" if item["deal"] in {row["deal"] for row in self.data.get("routed") or []} else ""
            lines.append(f"- Priority {rank} · {deal}{owner} · {item['reason']}")
        if selected:
            lines += ["", "Use the proposal labels below for approvals."]
            if self.uses_retrieved([item["evidence"] for item in selected]):
                lines += ["", LIMITATION]
        else:
            lines.append("No supported actions to prioritize today.")
        return lines + [""]

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
        if p is not None and self.entry_prefix and not str(p).startswith(self.entry_prefix):
            self.err(f"{where}: proposed next step must start with {self.entry_prefix!r}")

    def validate(self, mode):
        if mode == "report" and self.run.get("branch") == "weekday":
            self.check_today_actions()
        r = self.run
        if r.get("branch") not in SCOPE_FOR_BRANCH:
            self.err("run.branch must be weekday or friday")
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
            if not isinstance(row.get("deal"), str):
                continue
            if row.get("deal") in routed_ids:
                self.err("routed: each deal appears once")
            routed_ids.add(row.get("deal"))
            for field in ("name", "reason", "thread_url"):
                value = row.get(field)
                if not isinstance(value, str) or not value.strip() or any(char in value for char in "\r\n"):
                    self.err(f"routed needs a one-line {field}")
            link = row.get("thread_url")
            try:
                parsed = urlparse(link) if isinstance(link, str) else None
                valid = (parsed is not None and parsed.scheme == "https" and parsed.hostname
                         and not parsed.username and not parsed.password and not re.search(r"\s", link))
            except ValueError:
                valid = False
            if not valid:
                self.err("routed needs an https deal-thread link")
            if row.get("deal") in self.deals:
                self.err("routed deals must be counted separately from local flagged deals")

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
            if ns.get("proposed") is not None and b.get("status") != "superseded":
                self.check_followup(b, b.get("changes") or [], where)
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
                    self.check_change(c, f"{owhere} change {n}", option=True)
                self.check_milestones(o, o.get("changes") or [], owhere)
                if o.get("status") != "superseded" and any(
                        c.get("field") == "Next_Steps__c" for c in o.get("changes") or []):
                    self.check_followup(o, o.get("changes") or [], owhere)
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
                self.check_milestones(l, [l["change"]], where)
                if l["change"].get("field") == "Next_Steps__c" and l.get("status") != "superseded":
                    self.check_followup(l, [], where, task_letters)
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
            keys = [self.record_key(c) for c in changes]
            if (item.get("next_step") or {}).get("proposed") is not None:
                keys.insert(0, ("Opportunity", item.get("deal"), "Next_Steps__c"))
            return keys

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
        covered = block_deals | question_deals | {w.get("deal") for w in self.data.get("withheld") or []}
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
        routed = len(self.data.get("routed") or [])
        return {"open": self.counts["open"], "reviewed": k, "flagged": f, "not_checked": u,
                "no_trigger": k - f - routed - u, "routed": routed, "blocks": len(blocks), "questions": len(questions),
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
        out += ["", "### Recommended next steps"]
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
                if not self.date or not closed_lost_silence_eligible(
                        row.get("last_buyer_activity"), datetime.combine(self.date, datetime.min.time()), self.policy,
                        row.get("evidence_complete"), row.get("upcoming_event")):
                    self.err("qualification Closed Lost needs reviewed silence and no upcoming Event")
            elif action == "next_step":
                try:
                    due = date.fromisoformat(row.get("next_step_date", ""))
                    if self.date and due < self.date:
                        raise ValueError("past date")
                except (TypeError, ValueError):
                    self.err("qualification next step needs a current or future next_step_date")
            elif action == "needs_input":
                if not any(question.get("deal") == identifier and question.get("status") == "open" for question in self.questions):
                    self.err("qualification needs_input must name an existing open question")
            else:
                self.err("qualification action must be closed_lost, next_step, or needs_input")
        items = self.blocks + self.letters + [{**option, "deal": question.get("deal")} for question in self.questions
                                             for option in question.get("options") or []]
        for item in items:
            row = rows.get(item.get("deal"))
            if not row or item.get("status") == "superseded":
                continue
            changes = item.get("changes") or ([item["change"]] if item.get("change") else [])
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
        if self.run["branch"] == "weekday":
            out += self.today_action_lines()
        out += ["## Routed to deal threads", ""]
        routed = self.data.get("routed") or []
        if routed:
            out += [f"{len(routed)} routed · counted separately from local proposals", ""]
            out += [f"- [{display(row['name'])}]({row['thread_url']}) · {display(row['reason'])}" for row in routed]
            out += [""]
        else:
            out += ["None.", ""]
        out += ["## Clear recommendations", ""]
        if blocks:
            for b in blocks:
                out += self.block_lines(b) + [""]
            if self.uses_retrieved([b["evidence"] for b in blocks]):
                out += [LIMITATION, ""]
        else:
            out += [EMPTY_BLOCKS, ""]
        out += ["## Needs your input", ""]
        if questions:
            out += ["  \n".join(f"{q['label']} · {self.deal_link(q['deal'])} · {display(q['context'])}" for q in questions), ""]
            if self.uses_retrieved([q["evidence"] for q in questions]):
                out += [LIMITATION, ""]
            out += [WALK_NOTE, ""]
        else:
            out += [EMPTY_QUESTIONS, ""]
        if self.run["branch"] == "friday":
            out += self.friday_lines() + [""]
        out += ["## Coverage", "", "  \n".join(self.coverage_lines()), ""]
        out += [f"{n(c['no_trigger'], 'reviewed deal', 'reviewed deals')} had no trigger · {c['not_checked']} not checked", ""]
        if c["blocks"] or c["letters"]:
            out.append(APPROVE_FRIDAY if self.run["branch"] == "friday" and c["letters"] else APPROVE_WEEKDAY)
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
        ready = self.coverage_ready() and self.process_complete()
        url = self.run["thread_url"]
        proposals = c["blocks"] + c["letters"]
        if self.run["branch"] == "weekday":
            if ready and proposals == 0 and c["questions"] == 0:
                return {"send": False, "status": "clean",
                        "reason": "No clear recommendations, no questions, and coverage ready."}
            status = "action" if ready else "incomplete"
            body = " · ".join(([] if ready else self.gap_summary()) + [self.counts_line()])
            payload = {"title": TITLE_WEEKDAY.format(d=d), "body": f"{body} · {url}", "channels": ["in_app"]}
        else:
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
