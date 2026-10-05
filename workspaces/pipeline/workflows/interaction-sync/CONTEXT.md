---
cadence: [daily, one-off]
reads: _core/policy.yaml (salesforce, followup, email_voice, tooling, call_prep, momentum, interaction, pipeline), _core/rules.md, references/, Momentum, Salesforce, Gmail, Calendar
writes: Salesforce Task, Opportunity, Contact, Contact Role records and one unsent Gmail draft, on approval
next: pipeline-review picks up the logged activity; close on signature
---

# Interaction Sync

Log one completed call: one call in, one set of lettered proposals out. Salesforce is the record. Buyer-stated facts are quoted, not paraphrased into claims.
The scheduled sweep branch finds unlogged calls and routes evidence only. It never runs the approved-write steps below.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `salesforce`, `followup`, `email_voice`, `tooling`, `call_prep`, `momentum`, `interaction`, `pipeline` blocks | Markers, timing, voice, and field values |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#approval`, `rules#write_protocol`, `rules#note_prefix` | Run start, approval, and writes |
| Core rules | `_core/rules.md` | `rules#momentum`, `rules#calendar_search`, `rules#absence_conclusions`, `rules#call_type` | Finding the call and evidence limits |
| Core rules | `_core/rules.md` | `rules#next_steps`, `rules#next_steps_format`, `rules#followup_task`, `rules#stage_move`, `rules#contact_status`, `rules#email_body` | What proposals B, C, and D may say |
| Core rules | `_core/rules.md` | `rules#pilot_handoff`, only when a pilot finding tied to this call is supplied | Pilot finding acceptance |
| Reference | `references/reconcile.md` | "Find the interaction" at step 2; "Extract" at step 3; "Reconcile" at step 4 | Source marker, quotes, queries, and dedupe |
| Reference | `references/proposals.md` | Single call only, "Letters" at step 5, "Pilot finding" when supplied, "Apply" at step 7 | Proposal payloads A to F |
| Reference | `references/sweep.md` | Full file, sweep branch only | Release gate, complete call enumeration, dedupe, and read-only handoff |
| Per-run evidence | Current project deal threads and deployed Momentum rule | Sweep branch only | Routing and approved enumeration exception |
| Per-run evidence | Momentum transcript or Calendar event, and Salesforce and Gmail results saved in the sandbox | This call only | What happened and what the record holds |

## Process

1. Start per `rules#run_start`.
   If sweep was requested, follow `references/sweep.md` and stop after its handoff. Otherwise continue the single-call steps below.
2. Find the interaction and its stable source marker per `references/reconcile.md` "Find the interaction". Ask when the Account is ambiguous.
3. Extract quotes, commitments, and figures per `references/reconcile.md` "Extract".
4. Reconcile Contacts, Opportunity, Contact Roles, open Tasks, duplicates, and the newest thread per `references/reconcile.md` "Reconcile".
5. Letter every proposal per `references/proposals.md` "Letters".
6. Wait. Writes happen only on `approved <letter>` in this thread per `rules#approval`.
7. Apply per `references/proposals.md` "Apply" and `rules#write_protocol`.
8. Close by naming each applied, skipped, rejected, or needs-input letter per `rules#approval`, in five lines or fewer.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | Candidate Accounts with Ids, when the Account is ambiguous | Which Account the call belongs to |
| 5 | Lettered proposals A to F with full payloads | `approved <letter>` for each proposal to apply |

Sweep has no approval pause because it writes no customer records or drafts. Receiving a handoff never approves logging.

## Audit

| Check | Pass Condition |
|---|---|
| Identity, before step 3 | Momentum start date and attendee emails match the Calendar event, with no contradictory transcript date cues. Otherwise the run is needs-input, states the reason, and proposes nothing derived from that transcript |
| Source marker, before step 5 | Proposal A's Description line 1 is the exact Momentum or Calendar marker. Nothing is proposed with an invented or empty marker |
| Duplicate, before step 5 | The "Reconcile" item 5 check ran. A hit skips A and limits B, C, and F to what the existing Task lacks |
| Draft dedupe, before step 5 and again before creating D | The draft check in "Letters" D ran and found no same-purpose draft, or D shows `reuse existing` or needs-input |
| Evidence, before step 5 | Amounts and seats come only from `policy.interaction.amount_source`. Each figure is marked `buyer_confirmed` or `operator_stated` |
| Dependencies, before step 7 | B includes its matching Task for any next-step change, writes next step then Task, and reads both back. A failed Task write is partial with one corrective proposal. F waits for the verified call Task. D reruns the draft check |
| Scope, before step 5 | No Closed Won (route to `close`) or Closed Lost (route to `pipeline-review`) stage move, delete, merge, sent mail, or edit to a record not tied to this call |
| Sweep scope | Approved enumeration exception is deployed, every call is identity-checked, and no Salesforce or Gmail write occurs |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Proposed changes | Run thread | Lettered proposals A to F, current value to new value |
| Salesforce updates | Task, Opportunity, Contact, and Contact Role records, after approval only | The approved payload, read back per `rules#write_protocol`. Pipeline-review consumes the logged activity. A signature routes to close |
| Unsent Gmail draft | Gmail drafts, after approval only | One draft for Operator, in the "Reconcile" item 6 thread when one exists, verified with `list_drafts`. Never sent |
| Close summary | Run thread | Five lines or fewer naming every letter's disposition |
| Saved results | Sandbox | Transcript, query, and search outputs, never Project Files |
| Sweep handoff | Deal thread when available, otherwise Pipeline via notify-source | Call marker, title, date, Task proposals, and request for separately approved interaction-sync logging |
