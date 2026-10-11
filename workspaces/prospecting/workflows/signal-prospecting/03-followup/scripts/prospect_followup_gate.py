#!/usr/bin/env python3
"""Check one follow-up packet and emit the exact Salesforce Task to propose. signal-followup calls this once per send.

Usage:
    python3 workspaces/prospecting/workflows/signal-prospecting/03-followup/scripts/prospect_followup_gate.py --packet packet.json [--core _core] [--today YYYY-MM-DD]
    --today is for tests. Default is today in identity.timezone.
    --core supplies both policy reads, the prospecting block and salesforce.note_prefix, from one policy.yaml.

Policy input requires prospecting.identity.timezone, prospecting.identity.sfdc_user_id,
prospecting.followup.due_calendar_days, prospecting.followup.closed_statuses, prospecting.followup.task.Subject,
prospecting.followup.task.Status, prospecting.followup.task.Priority, prospecting.followup.task.TaskSubtype,
prospecting.followup.task.Description, and shared salesforce.note_prefix.

packet.json
    {
      "sent": [ {"message_id": "...", "thread_id": "...", "subject": "...", "sent_at": "<aware ISO-8601>", "to": "x@acme.com"} ],   # live Gmail in:sent hits
      "account": {"id": "001...", "owner_id": "005..."},
      "contacts": [ {"id": "003...", "email": "x@acme.com"} ],                # Contacts on the Account whose Email matches the recipient
      "tasks": [ {"id": "00T...", "subject": "...", "description": "...", "status": "Not Started"} ],  # existing Tasks on the Contact, any status
      "open_opportunities": [ {"id": "006..."} ],   # live open Opportunity read on the Account (prospecting.salesforce.open_opportunity), empty when none
      "signal": {"signal_type": "ai_exec_appointment", "angle": "Model flexibility"}   # from the approved outreach verdict in the thread
    }

Checks, in order. Every failing check names its reason. Checks 1 through 7 all run before the verdict. Check 8 runs
only when they pass.
    1. proof: exactly one sent hit. Zero is no proof. Two or more is ambiguous
    2. signal: signal_type and angle are nonempty labels from the approved outreach verdict. Preserve historical
       labels instead of revalidating a sent message against today's talk track
    3. sent fields: the hit carries message_id, thread_id, subject, sent_at, to. Each missing key is its own reason
    4. owner: account.owner_id equals identity.sfdc_user_id
    5. contact: exactly one contact with a nonempty string id, email equals sent.to case-insensitively
    6. duplicate: tasks must be a list (the live Task read on the Contact,
       empty when none). A missing or null tasks field blocks. No task whose subject equals the proposed Subject,
       whose description contains the message id, or which is open with a subject starting with the
       followup.task.Subject prefix ("Follow up:")
    7. open Opportunity: open_opportunities must be a list (the live open Opportunity read on the Account, empty when
       none). A missing or null field blocks. Any open Opportunity blocks, Pipeline owns that Account
    8. due date: sent_at is an aware timestamp not after now. identity.timezone send date + followup.due_calendar_days.
       Blocks when the due date is before today (--today overrides both today and now)


Exit 0 allow with the Task fields. Exit 1 block with reasons. Exit 2 unusable input, meaning a packet the checks cannot
read (not JSON, sent not a list, account not an object with id and owner_id). The exit 2 envelope is
{"verdict": "error", "reason": "..."}. Never a traceback. Always JSON on stdout.
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
import prospect_common  # noqa: E402

CORE = prospect_common.CORE


def due_date(sent, policy):
    """Pacific send date plus the configured calendar-day interval."""
    return sent.astimezone(prospect_common.policy_tz(policy)).date() + timedelta(days=policy["followup"]["due_calendar_days"])


def note_prefix(core=CORE):
    """salesforce.note_prefix from the same policy.yaml that --core selects."""
    return yaml.safe_load((Path(core) / "policy.yaml").read_text())["salesforce"]["note_prefix"]


def check(packet, policy, today=None, now=None, prefix_template=None):
    if now is None:
        now = datetime.combine(today, datetime.max.time(), tzinfo=prospect_common.policy_tz(policy)) if today else prospect_common.policy_now(policy)
    today = today or now.date()
    fp = policy["followup"]
    reasons = []
    sent = packet.get("sent") or []
    acct = packet.get("account")
    if not isinstance(sent, list):
        raise ValueError("sent must be a list of Gmail in:sent hits")
    if not isinstance(acct, dict) or not acct.get("id"):
        raise ValueError("account must be an object with id and owner_id")
    if len(sent) == 0:
        return {"verdict": "block", "reasons": ["no sent proof"]}
    if len(sent) > 1:
        return {"verdict": "block", "reasons": [f"ambiguous: {len(sent)} plausible sent messages"]}
    s = sent[0]
    sig = packet.get("signal") or {}
    stype, angle = sig.get("signal_type"), sig.get("angle")
    for label, value in (("signal_type", stype), ("angle", angle)):
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"signal {label} must be a nonempty label from the approved outreach verdict")
    if not isinstance(s, dict):
        raise ValueError("sent hit must be an object")
    for k in ("message_id", "thread_id", "subject", "sent_at", "to"):
        if not s.get(k):
            reasons.append(f"sent hit missing {k}")

    if acct.get("owner_id") != policy["identity"]["sfdc_user_id"]:
        reasons.append("account owner is not identity.sfdc_user_id")

    contacts = packet.get("contacts") or []
    if not isinstance(contacts, list):
        raise ValueError("contacts must be a list")
    if len(contacts) != 1:
        reasons.append(f"contact match count {len(contacts)}, need exactly 1")
    else:
        contact = contacts[0]
        if not isinstance(contact, dict):
            raise ValueError("contact must be an object")
        if not isinstance(contact.get("id"), str) or not contact["id"].strip():
            reasons.append("contact needs a nonempty string id")
        if (contact.get("email") or "").lower() != (s.get("to") or "").lower():
            reasons.append("contact email does not equal recipient")

    subject = fp["task"]["Subject"].format(gmail_subject=s.get("subject") or "")
    prefix = fp["task"]["Subject"].split("{")[0].strip()
    tasks = packet.get("tasks")
    if not isinstance(tasks, list):
        reasons.append("tasks missing or not a list. Read the Contact's Tasks and pass the list, empty when there are none")
        tasks = []
    for t in tasks:
        subj = t.get("subject") or ""
        is_open = (t.get("status") or "") not in fp["closed_statuses"]
        if subj == subject or (s.get("message_id") and s["message_id"] in (t.get("description") or "")):
            reasons.append(f"duplicate Task {t.get('id')}")
            break
        if is_open and subj.startswith(prefix):
            reasons.append(f"open follow-up Task already exists {t.get('id')}")
            break

    opportunities = packet.get("open_opportunities")
    if not isinstance(opportunities, list):
        reasons.append("open_opportunities missing or not a list. Read the Account's open Opportunities and pass the list, empty when there are none")
    elif opportunities:
        ids = ", ".join(str(o.get("id") if isinstance(o, dict) else o) for o in opportunities)
        reasons.append(f"open Opportunity {ids} on the Account. Pipeline owns this account")

    if reasons:
        return {"verdict": "block", "reasons": reasons}

    sent_ts = prospect_common.parse_iso(s["sent_at"])
    if sent_ts is None:
        return {"verdict": "block", "reasons": ["sent_at needs a timezone"]}
    due = due_date(sent_ts, policy)
    if sent_ts > now:
        return {"verdict": "block", "reasons": [f"sent_at {s['sent_at']} is after now. Not a proven send"]}
    if due < today:
        return {"verdict": "block", "reasons": [f"due date {due.isoformat()} is before today. Send is older than the follow-up window"]}

    if prefix_template is None:
        prefix_template = note_prefix()
    prefix = prefix_template.replace("M/D/YY", f"{today.month}/{today.day}/{today:%y}")
    task = {"Subject": subject, "WhatId": acct["id"]}
    if contacts:
        task["WhoId"] = contacts[0]["id"]
    task.update({
        "OwnerId": policy["identity"]["sfdc_user_id"],
        "Status": fp["task"]["Status"],
        "Priority": fp["task"]["Priority"],
        "TaskSubtype": fp["task"]["TaskSubtype"],
        "ActivityDate": due.isoformat(),
        "Description": prefix + fp["task"]["Description"].format(message_id=s["message_id"], thread_id=s["thread_id"],
                                                        signal_type=stype, angle=angle),
    })
    return {"verdict": "allow", "task": task}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", required=True)
    ap.add_argument("--core", default=str(CORE))
    ap.add_argument("--today", help="YYYY-MM-DD, tests only. Default is today in identity.timezone")
    a = ap.parse_args()
    try:
        core = Path(a.core)
        packet = json.loads(Path(a.packet).read_text())
        policy = prospect_common.load_policy(core)
        out = check(packet, policy, date.fromisoformat(a.today) if a.today else None, prefix_template=note_prefix(core))
    except prospect_common.INPUT_ERRORS as e:
        print(prospect_common.error_json(e))
        return 2
    print(json.dumps(out, indent=2))
    return 0 if out["verdict"] == "allow" else 1


if __name__ == "__main__":
    sys.exit(main())
