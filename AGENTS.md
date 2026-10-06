# Sales

Sales This reusable Sales system has five agent workspaces. The included runtime adapter targets Perplexity Computer. Salesforce is the record. Gmail, Calendar, and call transcripts are evidence.
External writes require the selected contract's approval and readback gates. Read-only workflows keep their stated scope. Run artifacts and customer material stay outside the repo.

## Setup gate

Read `policy.template.mode` before a routine run. Unconfigured mode routes to `_core/onboarding/CONTEXT.md`.
Normal onboarding records every integration choice in `policy.template.integrations`. Configuration still needs actual identity, schema, permission and adapter verification.
Before a live branch, check its used surfaces and current external verification receipts. Deferred or unavailable dependencies hold their affected operations.
Generated pointers list applicable integration names. File-only setup never grants readiness, write approval or schedule activation.
The scratch rehearsal alone uses demo state for fictional connector data and permits local simulation only.
Read the selected contract explicitly. Routing and folders do not install a skill or prove it was loaded.

## Entry routing

| Request | Entry |
|---|---|
| A named skill | Its contract in the Skills table below, then only its applicable Inputs rows |
| A task or event without a skill name | `CONTEXT.md` for the owning workspace, then its AGENTS.md and CONTEXT.md |
| Maintain the repo, agent configuration, or system health | `workspaces/systems/AGENTS.md`, then `workspaces/systems/CONTEXT.md`. Architecture stays in `_core/CONVENTIONS.md` |
| Find shared resources and their editors | `_core/CONTEXT.md` |

Routine sales runs go straight to their contract. They do not load the authoring conventions or another workflow's folder. Systems loads only its routed maintenance inputs.
Named skills use the direct routes below without relying on discovery of nested AGENTS.md files. Workspace entry files explain ownership and handoffs when routing a broader request.

## Workspaces

| Workspace | Role and boundaries | Task routing |
|---|---|---|
| Prospecting | `workspaces/prospecting/AGENTS.md` | `workspaces/prospecting/CONTEXT.md` |
| Pipeline | `workspaces/pipeline/AGENTS.md` | `workspaces/pipeline/CONTEXT.md` |
| Deal Coaching | `workspaces/deal-coaching/AGENTS.md` | `workspaces/deal-coaching/CONTEXT.md` |
| Forecasting | `workspaces/forecasting/AGENTS.md` | `workspaces/forecasting/CONTEXT.md` |
| Systems | `workspaces/systems/AGENTS.md` | `workspaces/systems/CONTEXT.md` |


## Skills

To run a named workflow, go straight to its stage or coordinator contract. Load only its applicable Inputs.

| Skill | Contract | Branch |
|---|---|---|
| `signal-scan` | `workspaces/prospecting/workflows/signal-prospecting/01-research/CONTEXT.md` | Buying signals |
| `signal-user-scan` | `workspaces/prospecting/workflows/signal-prospecting/01-research/CONTEXT.md` | Adoption |
| `signal-outreach` | `workspaces/prospecting/workflows/signal-prospecting/02-outreach/CONTEXT.md` | None |
| `signal-followup` | `workspaces/prospecting/workflows/signal-prospecting/03-followup/CONTEXT.md` | None |
| `event-sequence` | `workspaces/prospecting/workflows/event-sequence/CONTEXT.md` | None |
| `sales-call-prep` | `workspaces/pipeline/workflows/sales-call-prep/CONTEXT.md` | None |
| `interaction-sync` | `workspaces/pipeline/workflows/interaction-sync/CONTEXT.md` | Single call or sweep |
| `watch-sync` | `workspaces/pipeline/workflows/watch-sync/CONTEXT.md` | None |
| `pipeline-review` | `workspaces/pipeline/workflows/pipeline-review/CONTEXT.md` | None |
| `task-triage-speed-run` | `workspaces/pipeline/workflows/task-triage-speed-run/CONTEXT.md` | None |
| `pilot-usage` | `workspaces/pipeline/workflows/pilot-usage/CONTEXT.md` | None |
| `customer-review` | `workspaces/pipeline/workflows/customer-review/CONTEXT.md` | Scheduled or one named Account |
| `close` | `workspaces/pipeline/workflows/close/CONTEXT.md` | None |
| `deal-coach` | `workspaces/deal-coaching/workflows/deal-coach/CONTEXT.md` | None |
| `forecast-weekly` | `workspaces/forecasting/workflows/forecast-weekly/CONTEXT.md` | None |
| `repo-maintenance` | `workspaces/systems/workflows/repo-maintenance/CONTEXT.md` | None |
| `agent-configuration` | `workspaces/systems/workflows/agent-configuration/CONTEXT.md` | None |
| `system-review` | `workspaces/systems/workflows/system-review/CONTEXT.md` | None |
