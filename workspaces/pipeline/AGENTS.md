# Pipeline

Own call preparation, completed-interaction logging, pipeline hygiene, Task triage, pilot usage, and signed-deal execution.
Watch-sync owns read-only watch and deal-thread reconciliation proposals, never configuration edits.
Prepare read-only call briefs and proposals. Execute only the selected contract's approved actions.

## Entry

Read `workspaces/pipeline/CONTEXT.md` to select a workflow. Then load only its applicable Inputs rows, policy blocks, rule anchors, and named reference sections.
The root AGENTS.md also routes every named skill directly to its execution contract.
For an Internal ask poll, use that routing file's "Internal ask poll" entry instead of Salesforce Task triage.

## Boundaries and handoffs

Deal-thread, pipeline-review and triage write boundaries are defined only in `rules#task_date_coordination` and `rules#followup_task`.
Task triage handles due Tasks and one-deal commands in one message under `rules#task_date_coordination`, with its source, ownership and approval gates.
Triage reads deal context itself without a message or wait, then sends a receipt of at most 3 lines after approved writes. Deal threads do not ask Operator about triage items.
Triage prepares Task follow-up Gmail drafts on deal accounts too. Interaction-sync keeps full post-call Task behavior, including in deal threads.
The shared rule includes Operator's typed deal-thread commands alongside the existing workflow exceptions.
Use OwnerId equal to the run user for triage ownership. Other owners' Tasks keep current behavior. Missing or unreadable owner evidence holds that Task as needs-input.
Triage and interaction-sync receipts give verified written context, never a request for another next-step or Task proposal.
Apply the same canonical boundaries in any project thread. Outside deal threads, the one-deal command routes through the triage contract.
For reschedules, load `_core/scripts/interfaces.md` only for `task_reschedule_check` and "Task reschedule input".
Also load `policy.tooling.scripts.task_reschedule_check` and `policy.salesforce.note_prefix`.
Forecasting keeps its approved ForecastCategoryName sync.

Each workflow keeps its existing approval grammar and readback gates under `rules#approval` and `rules#write_protocol`. Ownership does not expand the approved scope.
Deal-thread proposals and approved writes also follow `rules#repo_currency` from `_core/rules.md`.
Load `_core/scripts/interfaces.md` only for `workflow_revision_check` and "Workflow revisions", plus `policy.tooling.scripts.workflow_revision_check`.
Use `deal_thread_entry` with this Pipeline AGENTS.md and only the deal action's actually consumed sources. Do not claim or load a workflow the deal thread never ran.

## Typed deal commands

Operator's typed command may request any change for that deal, including Tasks and next steps. Quote and link his source turn. No typed command is itself write approval.
Show the exact labeled proposal and write only after Operator's label approval under `rules#approval`, `rules#write_protocol` and `rules#repo_currency`, then read every changed record back.
Triage alone owns unprompted Task and next-step proposals. Receipts are context only. Never act unprompted on triage items or ask Operator about them.
No receipt to triage is needed because triage fresh-reads before its own writes.

For Task or next-step commands, use triage's one-deal mechanics, not its full queue, section walk, closeout or receipt delivery.
Load `workspaces/pipeline/workflows/task-triage-speed-run/references/next-steps.md` "One deal".
Load `workspaces/pipeline/workflows/task-triage-speed-run/references/writes.md` "Writes" for the pair's write mechanics.
Use `workspaces/pipeline/references/deal-activity-reads.md` "Opportunities" and "Activity" for the selected deal's fresh native state.
Load `rules#task_date_coordination`, `rules#followup_task`, `rules#next_steps`, `rules#next_steps_format`, `rules#next_steps_review` and `rules#note_prefix`.
Load `policy.pipeline.stages`, `policy.pipeline.early_stages` and `policy.salesforce.note_prefix`, plus only the other sources actually governing the command.
Show the exact next-step and current-action Task pair in one proposal, preserving note history. Recheck duplicates immediately before writing.
Never complete a current-action Task without its named replacement, new or verified existing. Keep non-current Tasks and retained milestones outside the one-deal pair.
For date moves use `task_reschedule_check` proposal and prewrite phases with the same displayed payload, native baselines and command provenance per its interface.
Use writer=triage with manual_one_deal for these mechanics, including a future current-action Task. This is not a workflow entry or permission for scheduled runs.
Keep `deal_thread_entry` and include those actually consumed sources in the proposal's revision scope. Changed records or scope stop the old approval.
Apply only the labeled pair's write mechanics from "Writes". No triage batch approval is implied. Other deal changes keep their applicable evidence, approval and readback gates.

## Other handoffs

Verified Salesforce corrections from pipeline-review feed Forecasting. That workspace reads the corrected records under its own contract.
After a call, interaction-sync reads the completed interaction.
Coaching's Salesforce suggestions enter the responsible Pipeline workflow as evidence for a proposal, with Operator's approval before writes.
Route signed deals to close and pilot reports through `rules#pilot_handoff`. Coaching belongs to Deal Coaching.
Reports and approvals stay in run threads, records in Salesforce, drafts in Gmail, and saved results or PDFs in the sandbox. No run data enters the repo.
Authoring guidance lives in `_core/CONVENTIONS.md`. Criteria maintenance goes through Systems repo-maintenance and a repo PR.
