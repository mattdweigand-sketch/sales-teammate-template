---
cadence: [daily, one-off]
reads: _core/policy.yaml (salesforce, pipeline, followup, email_voice, tooling, momentum), _core/rules.md, references/, Salesforce, Gmail, Calendar, Slack, Momentum, project deal threads
writes: Salesforce Task and Contact fields, Contact creates, unsent Gmail drafts, on approval or rules#auto_date_move
next: pipeline-review for remaining pipeline-owned Tasks
---

# Task Triage Speed Run

Clear Operator's due, overdue, and undated Salesforce Tasks in one chat pass, acting as Operator in Salesforce and Gmail. Salesforce is the authority for Tasks and Contacts; Gmail and Calendar
are evidence.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `salesforce`, `pipeline.stages`, pipeline triage settings when deployed, `followup`, `email_voice`, `tooling` | Ownership scope, timing values, voice, and the helper registry |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#approval`, `rules#auto_date_move`, `rules#write_protocol`, `rules#note_prefix`, `rules#followup_task` | Run start, approval, and writes |
| Core rules | `_core/rules.md` | `rules#contact_status`, `rules#calendar_search`, `rules#absence_conclusions` | Active or cold, and evidence limits |
| Core rules | `_core/rules.md` | `rules#email_body`, while preparing the full proposal | Draft wording |
| Shared evidence | `_core/slack-evidence.md` | "Search", "Limits", "Reply receipts", `policy.tooling.slack_lookback_days` | Slack reply guard, never absence proof |
| Reference | `references/collect.md` | "Collect the run" at step 2 and step 9; "Gather evidence" and "Slack replies" at step 3 | Queries, searches, and helper runs |
| Reference | `references/grouping.md` | Full file, at step 4 | Group rules and hold windows |
| Reference | `references/walk.md` | "Presentation", "Readout", and "Section walk" at steps 5 to 8 | Full proposal, one main question, and remaining batch |
| Reference | `references/drafts.md` | Full file, preparing drafts at step 5 and creating approved drafts at steps 7 and 8 | How a follow-up is written and verified |
| Reference | `references/writes.md` | "Auto date moves" at step 5; "Writes" at steps 7 and 8; "Close" at step 9 | Automatic move, write, and close rules |
| Reference | `references/crm-corrections.md` | Full file, only when the CRM corrections group has a candidate | Evidence and fields for record fixes |
| Per-run evidence | Saved Salesforce, Gmail, Calendar, and Slack results in the sandbox | This run's Tasks and Contacts | Task state and Contact activity |
| Reference | `references/daily.md` | Full file, scheduled daily run only | Completed actions, buyer dates, deal-thread routing, and missing prep Tasks |
| Core policy and rules | `_core/policy.yaml`, `_core/rules.md` | `momentum`, `rules#momentum` | Daily completed-call evidence |

## Process

1. Start per `rules#run_start`.
2. Collect every Task in the run and its Contacts per `references/collect.md` "Collect the run".
   Daily runs also follow `references/daily.md`. Route deal-thread rows before proposing or applying date moves here, without duplicating them in the main pass.
3. Gather Gmail, Calendar, Slack, draft, and prior-email evidence per `references/collect.md` "Gather evidence".
4. Check pipeline-review ownership before assigning each Task to one group per `references/grouping.md`.
5. Apply qualifying automatic date moves per `references/writes.md` "Auto date moves". Prepare every draft per `references/drafts.md` without creating it.
   Post one full proposal with every group and row per `references/walk.md` "Readout", ending with one approval question for the main pass.
6. Wait for the main-pass reply per `rules#approval` and `references/walk.md` "Section walk". Apply its numbered selections, exceptions, and exact date or wording changes.
7. Execute approved rows per `references/writes.md` "Writes". Create and verify each approved draft before its Task date and note, then read back and post one combined receipt.
8. Keep unapproved or failed rows in one remaining batch. Accept follow-up approval without re-walking, apply and receipt it, and never reopen verified rows.
   After the main pass, ask CRM corrections one record per approval per `references/crm-corrections.md`.
9. Close per `references/writes.md` "Close".
   Daily runs suppress notification only when there are no due or overdue Tasks, no prep proposals, and no incomplete evidence to report.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 5 | Full proposal with every group, maps, and full drafts | `all` except Recycle and CRM corrections, numbers, exceptions or edits by number, or `skip`. `approved` with a Recycle number. Owned drafts by Task link |
| 8 | One CRM correction after the main pass | One record per approval |

## Audit

| Check | Pass Condition |
|---|---|
| Group coverage, before the step 5 question | Every pending row across all groups appears exactly once as proposed or blocked, the displayed count matches, and there is one main-pass approval question. Instruction-level, not tool-enforced |
| Draft basis, before the full proposal | Each draft continues the prior email read in `references/collect.md` "Gather evidence" item 6. None is drafted from Task notes alone |
| Recycle, before steps 7 and 8 | Recycle stays needs-input until `approved` with its number. `all` never covers it, and no active Contact is offered Recycle |
| Ownership, before steps 5, 7, and 8 | Current-action Tasks under `rules#followup_task` for open Opportunities in `policy.pipeline.stages` get no date move or completion proposal or write. Ambiguous candidates stay pipeline-owned |
| Dates, before steps 5, 7, and 8 | Every date to be written appears in a map Operator approved, except qualifying next-business-day moves under `rules#auto_date_move`. Pipeline-owned Tasks never qualify |
| Readback, after steps 5, 7, and 8 | Every changed record is read back, including `Description`, before `Verified in Salesforce` or `Auto-moved`. Every new draft is read back before `Draft ready` |
| Closeout, before the step 9 summary | `closeout_check` passes on a fresh query, or every remaining row has verified pipeline ownership or an explicit user deferral with its reason |
| Scope, before steps 5, 7, and 8 | No mail is sent. No delete, merge, bulk update outside an approved map, financial field, Opportunity edit, or Contact `OwnerId` change without its own separate approval, never bundled into another proposal |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Readout | Run thread | `references/walk.md` "Readout" line format |
| Proposed changes | Run thread, one full proposal for the main pass | Every group, exact maps, full draft blocks, and one question per `references/walk.md` "Readout" |
| Unsent Gmail drafts | Gmail drafts, after approval only | Per `references/drafts.md`, verified by readback for Operator |
| Salesforce updates | Task and Contact records, after approval or pre-approval under `rules#auto_date_move` | Per `references/writes.md` "Auto date moves" or "Writes", read back. Salesforce holds the updated queue |
| Receipts | Run thread | One combined receipt for the approved pass and one remaining batch |
| Close summary | Run thread | Per `references/writes.md` "Close", ending `No emails sent.` |
| Pipeline-owned Task handoff | Run thread | Remaining owned rows and ambiguous candidates with reasons, for pipeline-review per `references/writes.md` "Close" |
| Saved results | Sandbox | Query and helper outputs, never Project Files |
