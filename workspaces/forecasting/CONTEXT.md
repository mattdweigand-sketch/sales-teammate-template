# Forecasting routes

Enter through `workspaces/forecasting/AGENTS.md` for ownership and boundaries. The contract below selects the branch and bounds its Inputs.

## Task routing

| Task or event | Contract | Output and handoff | Human check |
|---|---|---|---|
| Forecast call, quarter or year pace, or quarter-end learning | `workflows/forecast-weekly/CONTEXT.md` | Forecast reports and snapshots in the thread. Approved corrections in Salesforce. Approved bucket edits go to a repo PR | Proposals and criteria require Operator's approval |
| Friday manager update | `workflows/forecast-weekly/CONTEXT.md` | Unsent Slack draft in the runtime manager DM, text and DM link in the run thread | Never send or overwrite an existing draft |

## Branch selection

Forecast follows `policy.forecast.schedule` or a typed forecast request. It reads corrected Salesforce state after Pipeline's review and retains its existing evidence coverage gate.
Tracking follows `policy.forecast.tracking.pace_report` or a typed tracking request. Its contract owns the no-change silence rule and keeps calculations in the helper.
At quarter end, tracking compares weekly call snapshots and outcomes. Its learning reference owns proposals and the approval handoff to Systems repo-maintenance.
Manager update follows `policy.forecast.manager_update` and selects only the manager-update procedure and its named inputs.
The schedule values describe cadence and do not create automations. All branch definitions stay in the workflow contract and its routed references.
