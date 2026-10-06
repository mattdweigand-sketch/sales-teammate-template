# Sales workspace routing

Route a task or event to its owning workspace. Read that workspace's AGENTS.md explicitly, then its CONTEXT.md and selected workflow contract.
Named skills go directly to their contracts through root `AGENTS.md`. Each execution contract owns its Inputs, approvals, and outputs.

## Task routing

| Task or event | Workspace | Output and handoff |
|---|---|---|
| Signal Prospecting or prepare configured event lists for Event Sequence | `workspaces/prospecting/CONTEXT.md` | Named-account reports, unsent drafts, approved follow-up Tasks or Apollo sequence. Open-Opportunity contacts go to Pipeline |
| Prepare for meetings, log interactions, review pipeline, triage Tasks, review pilots, or close deals | `workspaces/pipeline/CONTEXT.md` | Read-only briefs, approved customer-system work, and reports. Verified Salesforce corrections feed Forecasting |
| Coach calls or deals, or refresh coaching criteria | `workspaces/deal-coaching/CONTEXT.md` | Read-only coaching. Salesforce suggestions go to Pipeline. Approved criteria go to a repo PR |
| Forecast, track quarter or year pace, or review forecast learning | `workspaces/forecasting/CONTEXT.md` | Forecast reports, thread snapshots, and approved criteria proposals for a repo PR |
| Maintain the repo, configure agents, or review system health | `workspaces/systems/CONTEXT.md` | Tested PRs, authorized deployment receipts, verified settings, or improvement tasks and findings routed for repair |

## Shared resources

| Resource | Entry | Scope |
|---|---|---|
| Shared sales values, rules, helpers, and tests | `_core/CONTEXT.md` | Shared resources and their editors, loaded only as the selected contract requires |
| Architecture and maintenance | `_core/CONVENTIONS.md` | Authoring guidance and ICM handoffs, not a routine run prerequisite |
