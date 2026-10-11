# Scripts

Repo-wide helper catalog keyed in `policy.tooling.scripts`, which holds each path. Cross-workspace helpers live here. Workspace-only shared helpers live in the owner's scripts/.
Contract-only helpers live in that workflow or sequential stage's scripts/.
They check mechanics, not the truth of source claims or human approval. External writes still follow `rules#write_protocol`.

## Helpers

| Helper | Home | Callers |
|---|---|---|
| `onboard` | `_core/scripts/` | Local one-pass setup and readiness checks |
| `rehearse` | `_core/scripts/` | Scratch workflow simulations and regression suite |
| `event_list_prep` | `workspaces/prospecting/workflows/event-sequence/scripts/` | Event List Prep and Launch |
| `event_launch_check` | `workspaces/prospecting/workflows/event-sequence/scripts/` | Event Launch |
| `event_scrub_leads` | `workspaces/prospecting/workflows/event-sequence/01-list-prep/scripts/` | Event List Prep |
| `event_make_batches` | `workspaces/prospecting/workflows/event-sequence/01-list-prep/scripts/` | Event List Prep |
| `hygiene_check` | `_core/scripts/` | pipeline-review, task-triage-speed-run, forecast-weekly |
| `coverage_check` | `_core/scripts/` | pipeline-review, forecast-weekly |
| `workflow_revision_check` | `_core/scripts/` | Write proposals and prewrite checks across customer-writing workflows |
| `forecast_notify` | `workspaces/forecasting/workflows/forecast-weekly/scripts/` | Forecast weekly and Monday tracking automations |
| `pipeline_render` | `workspaces/pipeline/workflows/pipeline-review/scripts/` | pipeline-review, Friday review automation |
| `top_actions` | `workspaces/pipeline/scripts/` | task-triage-speed-run |
| `deal_thread_match` | `workspaces/pipeline/scripts/` | pipeline-review, task-triage-speed-run, watch-sync, customer-review, interaction-sync |
| `task_reschedule_check` | `workspaces/pipeline/scripts/` | task-triage-speed-run, deal threads, existing Pipeline reschedule writers |
| `forecast_math` | `workspaces/forecasting/workflows/forecast-weekly/scripts/` | forecast-weekly |
| `forecast_deck` | `workspaces/forecasting/workflows/forecast-weekly/scripts/` | forecast-weekly |
| `gmail_digest` | `_core/scripts/` | pipeline-review, forecast-weekly |
| `gmail_contact_stats` | `workspaces/pipeline/scripts/` | task-triage-speed-run, sales-call-prep |
| `closeout_check` | `workspaces/pipeline/workflows/task-triage-speed-run/scripts/` | task-triage-speed-run |
| `pilot_usage_build` | `workspaces/pipeline/workflows/pilot-usage/scripts/` | pilot-usage PDF mode |
| `pilot_resolve` | `workspaces/pipeline/workflows/pilot-usage/scripts/` | pilot-usage |
| `account_usage` | `workspaces/pipeline/scripts/` | pilot-usage identity, customer-review identity and counts |
| `customer_review` | `workspaces/pipeline/workflows/customer-review/scripts/` | customer-review |
| `prospect_common` | `workspaces/prospecting/scripts/` | Research, Outreach, Follow-up, and Event List Prep and Launch through event_list_prep |
| `prospect_evidence_gate` | `workspaces/prospecting/scripts/` | Research Buying signals |
| `prospect_account_route` | `workspaces/prospecting/scripts/` | Research and Outreach route table |
| `prospect_privacy_check` | `workspaces/prospecting/scripts/` | Research Adoption, Outreach adoption context |
| `prospect_readback_check` | `workspaces/prospecting/scripts/` | Outreach, Follow-up |
| `prospect_scan_verdict` | `workspaces/prospecting/workflows/signal-prospecting/01-research/scripts/` | Signal Research Buying signals |
| `prospect_outreach_gate` | `workspaces/prospecting/workflows/signal-prospecting/02-outreach/scripts/` | Signal Outreach |
| `prospect_followup_gate` | `workspaces/prospecting/workflows/signal-prospecting/03-followup/scripts/` | Signal Follow-up |
| `prospect_adoption_lookup` | `workspaces/prospecting/workflows/signal-prospecting/01-research/scripts/` | Signal Research Adoption account lookup |

## Libraries

Import-only modules with no CLI and no `policy.tooling.scripts` key. Importers add their home to `sys.path`. Prefer these over a private copy of the same read.

| Library | Home | Importers |
|---|---|---|
| `_saved_json` | `_core/scripts/` | hygiene_check, coverage_check, gmail_digest, report_evidence, gmail_contact_stats, top_actions, closeout_check, pipeline_render, pilot-usage assembly |
| `report_evidence` | `_core/scripts/` | top_actions, pipeline_render |

`prospect_common` is also import-only but keyed in `policy.tooling.scripts`, so it stays in "Helpers".

## What to load

| Need | Load | Section/Scope |
|---|---|---|
| A helper's promise | `_core/scripts/interfaces.md` | Its row in "Interfaces" |
| Where helpers run and where their files go | `_core/scripts/interfaces.md` | "Running" |
| Saved-result wrappers and customer data in outputs | `_core/scripts/interfaces.md` | "Saved results" |
| Run-start and Event timestamps | `_core/scripts/interfaces.md` | "Timestamps" |
| Pilot PDF limits | `_core/scripts/interfaces.md` | "Pilot PDF" |
| A helper's arguments | The helper's `--help` | Full output |
| Tests | `_core/tests/` | Command in `_core/CONVENTIONS.md` "Tests and maintenance" |
