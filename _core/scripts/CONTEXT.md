# Scripts

Repo-wide helper catalog keyed in `policy.tooling.scripts`, which holds each path. Cross-workspace helpers live here. Workspace-only shared helpers live in the owner's scripts/.
Contract-only helpers live in that workflow or sequential stage's scripts/.
They check mechanics, not the truth of source claims or human approval. External writes still follow `rules#write_protocol`.

## Helpers

| Helper | Home | Callers |
|---|---|---|
| `onboard` | `_core/scripts/` | Local one-pass setup and readiness checks |
| `rehearse` | `_core/scripts/` | Scratch workflow simulations and regression suite |
| `event_list_prep` | `workspaces/prospecting/workflows/event-sequence/scripts/` | List Prep and Launch |
| `event_scrub_leads` | `workspaces/prospecting/workflows/event-sequence/01-list-prep/scripts/` | List Prep |
| `event_make_batches` | `workspaces/prospecting/workflows/event-sequence/01-list-prep/scripts/` | List Prep |
| `hygiene_check` | `_core/scripts/` | pipeline-review, forecast-weekly |
| `coverage_check` | `_core/scripts/` | pipeline-review, forecast-weekly |
| `forecast_notify` | `workspaces/forecasting/workflows/forecast-weekly/scripts/` | Forecast (weekly) automation |
| `pipeline_render` | `workspaces/pipeline/workflows/pipeline-review/scripts/` | pipeline-review, both pipeline automations |
| `forecast_math` | `workspaces/forecasting/workflows/forecast-weekly/scripts/` | forecast-weekly |
| `gmail_digest` | `_core/scripts/` | pipeline-review, forecast-weekly |
| `gmail_contact_stats` | `workspaces/pipeline/scripts/` | task-triage-speed-run, sales-call-prep |
| `closeout_check` | `workspaces/pipeline/workflows/task-triage-speed-run/scripts/` | task-triage-speed-run |
| `pilot_usage_build` | `workspaces/pipeline/workflows/pilot-usage/scripts/` | pilot-usage PDF mode |
| `pilot_resolve` | `workspaces/pipeline/workflows/pilot-usage/scripts/` | pilot-usage |
| `account_usage` | `workspaces/pipeline/scripts/` | pilot-usage identity, customer-review identity and counts |
| `customer_review` | `workspaces/pipeline/workflows/customer-review/scripts/` | customer-review |
| `prospect_common` | `workspaces/prospecting/scripts/` | Research, Outreach, Follow-up |
| `prospect_evidence_gate` | `workspaces/prospecting/scripts/` | Research Buying signals |
| `prospect_account_route` | `workspaces/prospecting/scripts/` | Research and Outreach route table |
| `prospect_privacy_check` | `workspaces/prospecting/scripts/` | Research Adoption, Outreach adoption context |
| `prospect_readback_check` | `workspaces/prospecting/scripts/` | Outreach, Follow-up |
| `prospect_scan_verdict` | `workspaces/prospecting/workflows/signal-prospecting/01-research/scripts/` | Research Buying signals |
| `prospect_outreach_gate` | `workspaces/prospecting/workflows/signal-prospecting/02-outreach/scripts/` | Outreach |
| `prospect_followup_gate` | `workspaces/prospecting/workflows/signal-prospecting/03-followup/scripts/` | Follow-up |
| `prospect_adoption_lookup` | `workspaces/prospecting/workflows/signal-prospecting/01-research/scripts/` | Research Adoption account lookup |

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
