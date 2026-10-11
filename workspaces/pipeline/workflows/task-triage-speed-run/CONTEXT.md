---
cadence: [daily, one-off]
reads: _core/policy.yaml (salesforce, pipeline, followup, email_voice, tooling, momentum, forecast), _core/rules.md, references/, Salesforce, Gmail, Calendar, Slack, Momentum, deal threads
writes: Salesforce Next_Steps__c, Task and Contact fields, Contact creates, unsent Gmail drafts, after approval only
next: deal-thread receipts after approved writes, interaction-sync for held calls needing logging
---
# Task Triage Speed Run
Prepare actions on Operator's due, overdue and undated Tasks in one chat pass. Without action evidence keep the Task due. Salesforce is authoritative. Gmail and Calendar are evidence.
## Inputs
| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core freshness | `_core/rules.md`, `_core/scripts/interfaces.md` | `rules#repo_currency`, `workflow_revision_check`, "Workflow revisions" | Scoped proposal and prewrite evidence |
| Core policy | `_core/policy.yaml` | `salesforce`, `pipeline`, `forecast.amount_field`, `followup`, `email_voice`, `tooling` | Ownership, new-Task dates, voice and registry |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#approval`, `rules#write_protocol`, `rules#note_prefix`, `rules#followup_task`, `rules#task_date_coordination` | Evidence and approved writes |
| Core rules | `_core/rules.md` | `rules#contact_status`, `rules#calendar_search`, `rules#absence_conclusions`, `rules#handoff_delivery` | Active or cold, and evidence limits |
| Core rules | `_core/rules.md` | `rules#email_body`, while preparing the full proposal | Draft wording |
| Core rules | `_core/rules.md` | `rules#next_steps`, `rules#next_steps_format`, `rules#next_steps_review` | Exact paired next-step entry and preserved history |
| Shared evidence | `_core/slack-evidence.md` | "Search", "Limits", "Reply receipts", `policy.tooling.slack_lookback_days` | Positive reply evidence, never absence proof |
| Reference | `references/collect.md` | "Collect the run", "Task gaps" at steps 2 and 9. "Friday early stages" on local Friday. "Gather evidence", "Account-domain Gmail", "Slack replies" at step 3 | Native state and reviewed evidence |
| Reference | `references/grouping.md` | Full file, at step 4 | Ownership, unthreaded Opportunity branch and group gates |
| Reference | `references/walk.md` | "Presentation", "Readout", "Section walk" at steps 5 to 8 | One full proposal, approval and remaining batch |
| Reference | `references/drafts.md` | Full file, preparing at step 5 and creating at steps 7 and 8 | Exact draft and contingent complete-plus-next pair |
| Reference | `references/writes.md` | "Writes" at steps 7 and 8, "Close" at step 9 | Approved writes, native verification and honest closeout |
| Reference | `references/crm-corrections.md` | Full file, only for a CRM correction candidate | Separate record approval and exact fields |
| Per-run evidence | Native results, project pages and Account session searches in the sandbox, plus read-only deal context | Tasks, in-scope deals and verified Contacts | State, action evidence, ownership and blockers |
| Reference | `references/daily.md` | "Morning pass" and "Approval and delivery", scheduled run only. "Meeting preparation" only on an explicit typed request such as `prep tasks` | Completed actions, quoted dates, receipts and requested prep Tasks |
| Core policy and rules | `_core/policy.yaml`, `_core/rules.md` | `momentum`, `rules#momentum` | Completed-call evidence |
| Helper | `_core/scripts/interfaces.md` | `task_reschedule_check`, "Task reschedule input" | Quoted date proposals and native hasMore preflight |
| Shared reads | `workspaces/pipeline/references/deal-activity-reads.md` | "Opportunities", "Activity" at step 2, "Account-domain Gmail" at step 3 | Native scopes and domain discovery |
| Shared triggers | `workspaces/pipeline/references/triggers.md` | Full file, at steps 3 to 5 | Mechanical flags and reviewed activity |
| Reference | `references/next-steps.md` | "One deal" at step 2; "Draft", "Findings" at step 5 | One-deal entry and paired proposal |
| Helper | `_core/scripts/interfaces.md` | `hygiene_check`, `top_actions` | Native hygiene and unchanged Top 3 output |
| Helper | `_core/scripts/interfaces.md` | `deal_thread_match`, "Account session search" | Validated page shape, every Account searched and verified ownership |

## Process

1. Start per `rules#run_start`.
2. For a one-deal command, follow `references/next-steps.md` "One deal" instead of the full queue.
   Otherwise collect Tasks, Contacts and gaps per `references/collect.md`. Local Friday adds "Friday early stages". Daily runs also follow `references/daily.md`.
   Read matched deal context yourself without a message or wait. Include those rows once in this main pass.
3. Gather Gmail, Calendar, Slack, draft and prior-email evidence per `references/collect.md` "Gather evidence", "Account-domain Gmail" and "Slack replies".
4. Review ownership and the unthreaded Opportunity branch, then assign each Task to one group per `references/grouping.md`. Ambiguity stays needs-input.
5. Prepare paired next-step rows per `references/next-steps.md` "Draft" and "Findings", and full drafts per `references/drafts.md` without creating them. No write is automatic.
   Post every proposed or blocked row per `references/walk.md` "Readout", ending with one main-pass approval question.
6. Wait for Operator per `rules#approval` and `references/walk.md` "Section walk". No reply writes nothing.
7. Apply approved rows and read them back per `references/writes.md` "Writes". One row covers its displayed next-step and Task pair, draft or gap create. No extra question per record.
8. Keep failures and unapproved rows in one remaining batch per `references/walk.md` "Section walk". CRM corrections retain one record per approval.
9. Close per `references/writes.md` "Close". Daily suppression applies only to no due or overdue Tasks, no gap, next-step or prep proposals, no prioritized actions and complete evidence.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 5 | One full proposal with every group, exact pairs and full drafts, including one-deal mode | `all` except Recycle and CRM corrections, numbers, exceptions or edits, or `skip`. `approved` with a Recycle number |
| 8 | One CRM correction after the main pass | One record per approval |

## Audit

| Check | Pass Condition |
|---|---|
| Group coverage, before step 5 | Every pending row appears once as proposed or blocked, including deal Tasks. Count matches and there is one main question. Instruction-level, not tool-enforced |
| Slack, before step 5 | Every in-scope deal has paged named-buyer reads under _core/slack-evidence.md. Watches never replace them. Missing identities or searches stay not checked, not buyer silence. Bots and unverified channels remain excluded |
| Draft basis, before step 5 | Full prior email read per `references/collect.md` "Gather evidence", never Task notes alone |
| Recycle, before steps 7 and 8 | Needs-input until `approved` with its number, never covered by `all`. Active Contacts never recycle. No unsupported completion or Push |
| Ownership, before steps 5, 7 and 8 | Read-only deal context, never delegate unprompted Task proposals. Typed deal commands follow Pipeline AGENTS.md. Deal drafts keep approval and readback. Gaps need complete native reads, ambiguity holds |
| Dates, before steps 5, 7 and 8 | Date source permission follows rules#task_date_coordination, with unchanged native preflight. New Task dates are displayed and approved, never silent queue pushes |
| Readback, after steps 7 and 8 | Action evidence and new-Task readback or verified existing next-action Task precede completion. Verify all Task fields and draft content. Failures stay partial. No blind retry |
| Closeout, before step 9 | Fresh closeout shows every remaining due, overdue or undated Task and blocker. A failing closeout is disclosed, never fixed by pushing dates |
| Scope, throughout | No sending email, delete, merge, unapproved bulk update, financial field or Opportunity write except Next_Steps__c. Contact OwnerId changes need their own separate approval. CRM corrections keep separate approval |
## Outputs

| Artifact | Location | Format |
|---|---|---|
| Readout | Run thread | `references/walk.md` "Readout" |
| Proposed changes | Run thread | One message, exact next-step and Task pairs, gap rows or source-backed dates, blockers, full Task follow-up drafts and one main question |
| Unsent Gmail drafts | Gmail drafts, after approval only | `references/drafts.md`, verified before paired Task writes |
| Salesforce updates | Next_Steps__c, Task and Contact records, after approval only | Exact displayed fields and native readback per `references/writes.md` "Writes" |
| Receipts | Run thread and affected deal threads | Combined run receipt. Deal receipts at most 3 lines with the verified written next step and Task links, never delegated Task proposals or questions |
| Close summary | Run thread | `references/writes.md` "Close", ending `No emails sent.` |
| Saved results | Sandbox | Native evidence and helper outputs, never Project Files or Git |
