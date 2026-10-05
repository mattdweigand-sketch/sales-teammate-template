#!/usr/bin/env python3
"""Deterministic hygiene check for pipeline-review.

Usage: hygiene_check.py <opps.json> --as-of ISO_DATETIME_WITH_OFFSET
                        [--tasks tasks.json] [--events events.json] [--policy PATH] [--json]

Inputs are saved Salesforce query outputs (Opportunity, Task, Event). For every
open deal in policy.pipeline.stages it emits one line:
  triggers it can compute from Salesforce (policy.pipeline.triggers): next_passed,
    new_activity (inbound 'Email: <<' Task or elapsed Event after the newest note),
    blank_field, date_at_risk, stale, task_gap
  blank required and conditional fields, next-step status, newest note date,
  last activity, next upcoming Event, open Tasks
Deals below the scope report only whether Next_Steps__c is empty.
Note dates and dated entries are recognised by policy.salesforce.note_prefix
('M/D/YY SR - '); required_fields accumulate from the lowest stage in
policy.pipeline.stages; date_at_risk's stage gate is
policy.pipeline.date_at_risk_below_stage.
A required field counts as blank when it is None, '', False, or 0 (Amount 0 is
blank). Events require end timestamps to count as elapsed. Elapsed does not
prove held. Deviation from the stale policy text: a date-only (timing-unknown)
Event and an open Task never count as activity, so stale can fire even when one
sits inside stale_days. --as-of carries the run's local offset and sets the local
date. A first line in the retired `Next:` format is REVIEW, never parsed. Activity
evidence retains record IDs and linkage for report verification.
"""
import argparse
import datetime as dt
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from _saved_json import load_records

ORD = {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4, "S5": 5}
DEFAULT_NOTE_PREFIX = "M/D/YY SR - "   # policy.salesforce.note_prefix; used when a policy dict lacks it
MDY_RE = r"\d{1,2}/\d{1,2}/\d{2,4}"


def note_regexes(prefix=DEFAULT_NOTE_PREFIX):
    """Turn the note_prefix pattern ('M/D/YY SR - ') into the note-date and dated-entry regexes."""
    placeholder = re.match(r"[MDY/]+", prefix)
    if not placeholder:
        raise ValueError(f"note_prefix must start with an M/D/YY date placeholder: {prefix!r}")
    literal = re.escape(prefix[placeholder.end():].rstrip())
    return (
        re.compile(rf"\b({MDY_RE}){literal}"),
        re.compile(rf"^(?P<written>{MDY_RE}){literal}\s*(?P<action>.+)$"),
    )


NOTE_RE, DATED_NEXT_STEP_RE = note_regexes()
NEXT_STEP_DUE_DATE_RE = re.compile(
    r"\b(?:on|by)\s+(?P<date>\d{1,2}/\d{1,2}(?:/\d{2,4})?)(?![\d/])",
    re.I,
)
# Subject prefix of an inbound email Task written by the org email sync. Documented
# constant; policy.pipeline.triggers.new_activity quotes the same literal.
INBOUND = "Email: <<"


@dataclass(frozen=True)
class ParsedNextStep:
    status: Literal["OK", "MISSING", "REVIEW"]
    action: str | None = None
    due_date: dt.date | None = None
    format: Literal["dated_sentence"] | None = None
    review_reason: str | None = None


def parse_next_step_line(line: str, dated_re=DATED_NEXT_STEP_RE) -> ParsedNextStep:
    """Extract deadlines conservatively; a written date or author is not a deadline or owner."""
    if line.startswith("Next:"):
        return ParsedNextStep("REVIEW", line, review_reason="Legacy Next: line; rewrite as a dated entry")
    dated = dated_re.fullmatch(line)
    if not dated:
        return ParsedNextStep("MISSING")
    try:
        written = parse_mdy(dated["written"])
    except ValueError:
        return ParsedNextStep(
            "REVIEW", dated["action"], format="dated_sentence",
            review_reason="Invalid entry date",
        )
    matches = list(NEXT_STEP_DUE_DATE_RE.finditer(dated["action"]))
    if not matches:
        return ParsedNextStep(
            "REVIEW", dated["action"], format="dated_sentence",
            review_reason="No explicit on/by action due date; verify the sentence",
        )
    try:
        deadlines = {
            parse_mdy(
                match["date"] if match["date"].count("/") == 2
                else f"{match['date']}/{written.year}"
            )
            for match in matches
        }
    except ValueError:
        return ParsedNextStep(
            "REVIEW", dated["action"], format="dated_sentence",
            review_reason="Invalid action due date",
        )
    if len(deadlines) != 1:
        return ParsedNextStep(
            "REVIEW", dated["action"], format="dated_sentence",
            review_reason="Multiple possible action due dates; verify which is the deadline",
        )
    return ParsedNextStep(
        "OK", dated["action"], deadlines.pop(), format="dated_sentence"
    )


def parse_mdy(s):
    m, d, y = s.split("/")
    y = int(y)
    return dt.date(y + 2000 if y < 100 else y, int(m), int(d))


def parse_iso(s):
    return dt.date.fromisoformat(s[:10]) if s else None


def parse_activity_timestamp(value: str | None) -> dt.datetime | None:
    """Reject timestamps without offsets rather than inventing a timezone."""
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Activity timestamp must include a timezone offset")
    return parsed


def classify_event_timing(
    start: dt.datetime | None, end: dt.datetime | None, as_of: dt.datetime
) -> str:
    """A date or invitation alone cannot establish that a meeting has ended."""
    if start and end and end < start:
        return "timing_unknown"
    if start and start > as_of:
        return "upcoming"
    if end and end <= as_of:
        return "elapsed"
    if start and end and start <= as_of < end:
        return "in_progress"
    return "timing_unknown"


def activity_receipt(activity: dict | None) -> dict | None:
    """Retain the exact source record so summaries cannot silently change scope."""
    if activity is None:
        return None
    return {
        key: value.isoformat() if isinstance(value, (dt.date, dt.datetime)) else value
        for key, value in activity.items()
    }


def clean_text(s):
    s = re.sub(r"<br\s*/?>|</p>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'")


def stage_ord(stage):
    return ORD.get((stage or "")[:2], -1)


def is_blank(v):
    # 0 and 0.0 are blank on purpose: an Amount of 0 is not a filled-in Amount.
    return v is None or v == "" or v is False or v == 0


def load_typed_records(path, expected, argument):
    """Reject the wrong Salesforce object before it can produce plausible hygiene flags."""
    rows = load_records(path)
    prefixes = {"Opportunity": "006", "Task": "00T", "Event": "00U"}
    for row in rows:
        declared = (row.get("attributes") or {}).get("type")
        prefix = str(row["Id"])[:3]
        inferred = next((kind for kind, value in prefixes.items() if value == prefix), None)
        if (declared and declared != expected) or (inferred and inferred != expected) or not (declared or inferred):
            raise ValueError(f"{argument} ({path}): expected {expected} records; "
                             f"record {row['Id']} has type {declared or inferred or 'unknown'} (Id prefix {prefix})")
    return rows


def closed_lost_silence_eligible(last_buyer_activity, as_of, policy, evidence_complete, upcoming_event):
    if evidence_complete is not True or upcoming_event is not False or not last_buyer_activity:
        return False
    try:
        last = dt.date.fromisoformat(last_buyer_activity)
    except (TypeError, ValueError):
        return False
    silence_days = (as_of.date() - last).days
    return silence_days >= policy["pipeline"]["closed_lost_silence_days"]


def check(rec, pol, acts, as_of):
    today = as_of.date()
    pp = pol["pipeline"]
    stage = rec.get("StageName") or ""
    so = stage_ord(stage)
    acct = (rec.get("Account") or {}).get("Name") or rec.get("AccountId") or ""
    text = clean_text(rec.get("Next_Steps__c"))
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out = {"Id": rec.get("Id"), "Account": acct, "Stage": stage, "triggers": []}
    scope = {s[:2] for s in pp["stages"]}
    early_scope = {s[:2] for s in pp.get("early_stages", [])} if today.weekday() == 4 else set()
    note_re, dated_re = note_regexes((pol.get("salesforce") or {}).get("note_prefix") or DEFAULT_NOTE_PREFIX)

    if stage[:2] not in scope | early_scope:
        out["next_steps_empty"] = not lines
        return out

    # required and conditional fields, cumulative from the lowest in-scope stage
    required = []
    qualification = stage[:2] in early_scope
    out["review_scope"] = "qualification" if qualification else "hygiene"
    required_scope = early_scope if qualification else scope
    required_fields = pp.get("early_required_fields", {}) if qualification else pp["required_fields"]
    scope_min = min(stage_ord(s) for s in required_scope)
    for s, o in ORD.items():
        if scope_min <= o <= so:
            required += required_fields.get(s) or []
    for c in ([] if qualification else pp.get("conditional_fields") or []):
        if all(rec.get(k) == v for k, v in (c.get("when") or {}).items()):
            required.append(c["field"])
    out["blank_fields"] = [f for f in required if is_blank(rec.get(f))]

    # Only the first entry is current; older dated entries remain history.
    parsed_next = parse_next_step_line(lines[0], dated_re) if lines else ParsedNextStep("MISSING")
    out["next"] = parsed_next.status
    if parsed_next.format:
        out["next_format"] = parsed_next.format
    if parsed_next.review_reason:
        out["next_review_reason"] = parsed_next.review_reason
    if parsed_next.status == "OK":
        d = parsed_next.due_date
        assert d is not None
        out["next_action"] = parsed_next.action
        out["next_date"] = d.isoformat()
        if d < today:
            out["next_passed_days"] = (today - d).days
            out["triggers"].append("next_passed")
    if out["blank_fields"] or out["next"] != "OK":
        out["triggers"].append("blank_field")

    notes = []
    for raw_date in note_re.findall(text):
        try:
            notes.append(parse_mdy(raw_date))
        except ValueError:
            continue  # A malformed entry must not abort every account's review.
    newest_note = max(notes) if notes else None
    out["newest_note"] = newest_note.isoformat() if newest_note else None

    # activity
    # Activity linked to the Opportunity or to its Account. The org email sync logs most Email Tasks on the Account.
    items, seen = [], set()
    for a in acts.get(rec.get("Id"), []) + acts.get(rec.get("AccountId"), []):
        k = a.get("id") or (a["date"], a["subject"], a["kind"])
        if k not in seen:
            seen.add(k); items.append(a)
    for a in items:
        if a["kind"] == "event":
            a["timing"] = classify_event_timing(a.get("start"), a.get("end"), as_of)
    past = [
        a for a in items if a["date"] and a["date"] <= today
        and a["kind"] != "open_task"
        and (a["kind"] != "event" or a["timing"] == "elapsed")
    ]
    upcoming = [
        a for a in items if a["kind"] == "event"
        and (a["timing"] in ("upcoming", "in_progress")
             or (a["timing"] == "timing_unknown" and a["date"] and a["date"] > today))
    ]
    open_tasks = [a for a in items if a["kind"] == "open_task"]
    last = max(past, key=lambda a: a["date"]) if past else None
    nxt_ev = min(upcoming, key=lambda a: a["date"]) if upcoming else None
    out["last_activity"] = f"{last['date']} {last['subject']}" if last else None
    out["last_activity_evidence"] = activity_receipt(last)
    out["upcoming_event"] = f"{nxt_ev['date']} {nxt_ev['subject']}" if nxt_ev else None
    out["upcoming_event_evidence"] = activity_receipt(nxt_ev)
    out["unverified_events"] = [
        activity_receipt(a) for a in items
        if a["kind"] == "event" and a["timing"] in ("elapsed", "timing_unknown")
    ]
    out["open_tasks"] = [f"{a['date']} {a['subject']}" for a in open_tasks]
    out["open_task_candidates"] = [activity_receipt(a) for a in open_tasks]
    out["task_review_required"] = out.get("next") == "OK" and "next_passed_days" not in out
    # Later Tasks on scheduled Event dates are milestone candidates, not proven action
    # matches. task_review_required still requires review of their subjects and linkage.
    live = out.get("next") == "OK" and "next_passed_days" not in out
    due = dt.date.fromisoformat(out["next_date"]) if live else None
    milestones = []
    followups = []
    for task in open_tasks:
        events = [event for event in upcoming if event["timing"] == "upcoming"
                  and event["id"] and task["date"] and due and task["date"] > due
                  and event["date"] == task["date"]]
        if len(events) == 1 and sum(t["date"] == task["date"] for t in open_tasks) == 1:
            milestones.append({"task": activity_receipt(task), "events": [activity_receipt(e) for e in events]})
        else:
            followups.append(task)
    out["milestone_task_candidates"] = milestones
    out["task_gap"] = len(followups) != 1 or (live and followups[0]["date"] != due)
    if out["task_gap"]:
        out["triggers"].append("task_gap")

    buyer = [a for a in past if a["kind"] in ("inbound", "event")]
    buyer = [a for a in buyer if newest_note is None or a["date"] > newest_note]
    if buyer:
        b = max(buyer, key=lambda a: a["date"])
        out["new_activity"] = f"{b['date']} {b['subject']}"
        out["new_activity_evidence"] = activity_receipt(b)
        out["triggers"].append("new_activity")

    close = parse_iso(rec.get("CloseDate"))
    risk_gate = stage_ord(pp["date_at_risk_below_stage"])
    if close and (close < today or (so < risk_gate and (close - today).days <= pp["close_warning_days"])):
        out["triggers"].append("date_at_risk")

    cutoff = today - dt.timedelta(days=pp["stale_days"])
    next_live = out.get("next") == "OK" and "next_passed_days" not in out
    if not any(a["date"] >= cutoff for a in past) and not upcoming and not next_live:
        out["triggers"].append("stale")
    return out


def index_activity(tasks, events, timezone=dt.timezone.utc, inbound_prefix=INBOUND):
    acts = defaultdict(list)
    for t in tasks:
        d = parse_iso(t.get("ActivityDate"))
        subj = t.get("Subject") or ""
        closed = t.get("IsClosed") or t.get("Status") == "Completed"
        if not closed:
            kind = "open_task"
        elif subj.startswith(inbound_prefix):
            kind = "inbound"
        else:
            kind = "task"
        rec_ = {
            "id": t.get("Id"), "date": d, "subject": subj, "kind": kind,
            "what_id": t.get("WhatId"), "account_id": t.get("AccountId"),
            "contact": (t.get("Who") or {}).get("Name"), "contact_id": t.get("WhoId"),
        }
        acts[t.get("WhatId")].append(rec_)
        if t.get("AccountId") and t.get("AccountId") != t.get("WhatId"):
            acts[t.get("AccountId")].append(rec_)
    for e in events:
        start = parse_activity_timestamp(e.get("StartDateTime"))
        end = parse_activity_timestamp(e.get("EndDateTime"))
        d = start.astimezone(timezone).date() if start else parse_iso(e.get("ActivityDate"))
        ev = {
            "id": e.get("Id"), "date": d, "subject": e.get("Subject") or "", "kind": "event",
            "start": start, "end": end, "what_id": e.get("WhatId"),
            "account_id": e.get("AccountId"),
        }
        acts[e.get("WhatId")].append(ev)
        if e.get("AccountId") and e.get("AccountId") != e.get("WhatId"):
            acts[e.get("AccountId")].append(ev)
    return acts


def fmt(o):
    head = f"{o['Account']} | {o['Stage']} | {o['Id']}"
    if "next_steps_empty" in o:
        return f"{head} | out of scope | Next_Steps__c {'EMPTY' if o['next_steps_empty'] else 'present'}"
    nxt = o["next"]
    if nxt == "OK":
        nxt = f"OK {o['next_date']} ({o['next_action']})"
        if "next_passed_days" in o:
            nxt += f" PASSED {o['next_passed_days']}d"
    parts = [
        head,
        "triggers: " + (", ".join(o["triggers"]) or "none"),
        "blank: " + (", ".join(o["blank_fields"]) or "none"),
        "next: " + nxt,
        "newest note: " + (o["newest_note"] or "none"),
        "last activity: " + (o["last_activity"] or "none"),
        "upcoming: " + (o["upcoming_event"] or "none"),
    ]
    if o.get("next_review_reason"):
        parts.append("next-step review: " + o["next_review_reason"])
    if o.get("new_activity"):
        parts.append("new activity: " + o["new_activity"])
        evidence = o.get("new_activity_evidence") or {}
        parts.append("activity source: " + str(evidence.get("id")))
        if evidence.get("kind") == "event":
            parts.append("elapsed calendar event; attendance unverified")
    unknown_events = [e for e in o.get("unverified_events", []) if e.get("timing") == "timing_unknown"]
    if unknown_events:
        parts.append(f"event timing unknown: {len(unknown_events)}; verify before reporting")
    if o["open_tasks"]:
        parts.append("open tasks: " + "; ".join(o["open_tasks"]))
    if o.get("task_gap"):
        parts.append(f"task_gap: {len(o['open_tasks'])} open Tasks, need one current-action Task on the next-step date; review existing actions before creating")
    if o.get("milestone_task_candidates"):
        parts.append("milestone task review: verify later Tasks match their scheduled Events before retaining")
    if o.get("task_review_required"):
        parts.append("task review: compare existing actions, then reuse/reschedule or propose create")
    return " | ".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("opps")
    ap.add_argument("--tasks")
    ap.add_argument("--events")
    ap.add_argument("--policy", default=str(Path(__file__).resolve().parents[1] / "policy.yaml"))
    ap.add_argument("--as-of", required=True, help="Run timestamp with offset; also sets the local date")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    pol = yaml.safe_load(Path(a.policy).read_text())
    try:
        as_of = parse_activity_timestamp(a.as_of)
        today = as_of.date()
        opps = load_typed_records(a.opps, "Opportunity", "opps")
        tasks = load_typed_records(a.tasks, "Task", "--tasks")
        events = load_typed_records(a.events, "Event", "--events")
        acts = index_activity(tasks, events, as_of.tzinfo, pol["pipeline"].get("inbound_subject_prefix", INBOUND))
    except ValueError as exc:
        ap.error(str(exc))
    results = [check(r, pol, acts, as_of) for r in opps]

    if a.json:
        print(json.dumps(results, indent=1))
        return
    for o in results:
        print(fmt(o))
    scoped = [o for o in results if "blank_fields" in o]
    flagged = [o for o in scoped if o["triggers"]]
    print(
        f"-- {len(results)} open deals as of {today}. In scope: {len(scoped)}. Flagged: {len(flagged)}. "
        + ", ".join(f"{t}: {sum(1 for o in scoped if t in o['triggers'])}" for t in pol["pipeline"]["triggers"])
        + f". Activity sources: tasks {'yes' if a.tasks else 'no'}, events {'yes' if a.events else 'no'}."
    )


if __name__ == "__main__":
    main()
