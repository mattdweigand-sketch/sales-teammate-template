# Pipeline

Own call preparation, completed-interaction logging, pipeline hygiene, Task triage, pilot usage, and signed-deal execution.
Watch-sync owns read-only watch and deal-thread reconciliation proposals, never configuration edits.
Prepare read-only call briefs and proposals. Execute only the selected contract's approved actions.

## Entry

Read `workspaces/pipeline/CONTEXT.md` to select a workflow. Then load only its applicable Inputs rows, policy blocks, rule anchors, and named reference sections.
The root AGENTS.md also routes every named skill directly to its execution contract.

## Boundaries and handoffs

Each Opportunity and its Tasks have one proposing owner. An active deal thread owns its Opportunity's next step, fields, and Tasks.
pipeline-review owns other Opportunities in its scope. Task triage owns every remaining due Task. Other runs report such a record as owned elsewhere and propose nothing on it.
Forecasting keeps its approved ForecastCategoryName sync.

Each workflow keeps its existing approval grammar and readback gates under `rules#approval` and `rules#write_protocol`. Ownership does not expand the approved scope.
Verified Salesforce corrections from pipeline-review feed Forecasting. That workspace reads the corrected records under its own contract.
After a call, interaction-sync reads the completed interaction.
Coaching's Salesforce suggestions enter the responsible Pipeline workflow as evidence for a proposal, with Operator's approval before writes.
Route signed deals to close and pilot reports through `rules#pilot_handoff`. Coaching belongs to Deal Coaching.
Reports and approvals stay in run threads, records in Salesforce, drafts in Gmail, and saved results or PDFs in the sandbox. No run data enters the repo.
Authoring guidance lives in `_core/CONVENTIONS.md`. Criteria maintenance goes through Systems repo-maintenance and a repo PR.
