# Follow-up execution

## Send proof

Operator names a recipient, a subject, or a Gmail draft. Run a live Gmail `from:<policy.prospecting.identity.owner_email> in:sent to:<email>` search and keep hits whose subject and
date match. Record message id, thread id, subject, aware sent timestamp, recipient. A draft, a thread summary, or memory is never proof.
A send whose computed due date is before today is blocked. The due date is the send date in `policy.prospecting.identity.timezone` plus `policy.prospecting.followup.due_calendar_days`.
Do not move that date forward to bypass the gate.

## Salesforce reads

Account by the recipient's domain (Id, OwnerId). Contacts on that Account where `Email = '<recipient>'` (Id, Email). Tasks on those Contacts, any status (Id, Subject, Status, Description).
Open Opportunities on the Account where `policy.prospecting.salesforce.open_opportunity` (Id). Pass the complete list as `open_opportunities`, empty when there are none.
Read only. Exactly one current Account owned by `policy.prospecting.identity.sfdc_user_id` and one matching Contact are required. Missing or ambiguous Accounts or Contacts stop.

## Packet and gate

Build the packet in the shape from the gate docstring. `signal.signal_type` and `signal.angle` preserve the historical labels from the approved outreach verdict.
Use the verdict shown in this thread. Operator may supply those historical labels here when the outreach ran elsewhere.
Absent in the thread, ask Operator, never guess. Do not read another session or infer labels from the sent body. Do not look them up in today's talk track.
Run `policy.tooling.scripts.prospect_followup_gate --packet <p.json>`. Any
`block` ends the run. Report the reasons. Do not work around them.

## Proposal

The gate applies policy.salesforce.note_prefix to Description per rules#note_prefix. Report in the format below with the gate's `task` object as Proposal 1. Stop and wait. Approval covers
those exact fields. Any change to a field, the recipient, or the sent message is a new
proposal.

## Write and readback

After approval create one Task with exactly those fields. SOQL the returned Id with every approved field (rules#write_protocol).
Run `policy.tooling.scripts.prospect_readback_check --expected <approved-task.json> --actual <returned-record.json>` on the exact gate Task and returned record.
A missing field or mismatch stops. Report it without repairing or repeating the write.

## Report

```
Send: <recipient> | "<subject>" | <sent_at Pacific> | message <id>
Salesforce: Account <Id> owner Operator | Contact <Id> | existing Tasks: <n>
Sync Task: <Id or not yet landed>   (advisory, never blocks)
Gate: allow

Proposal 1. Salesforce Task
  Subject, WhatId, WhoId, OwnerId, Status, Priority, TaskSubtype, ActivityDate, Description as emitted by the gate

After approval:
Created: <Task Id> | readback: match / mismatch on <fields>
```

## Boundaries

- Creating a Contact or an Event. The one Task is the only write.
- Sending or drafting email. That is `signal-outreach`.

## Sales authority

Approval, native readback and failed-write handling follow rules#approval and rules#write_protocol.
