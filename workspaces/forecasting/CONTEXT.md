# Forecasting routes

Enter through `workspaces/forecasting/AGENTS.md` for ownership and boundaries. The contract below selects the branch and bounds its Inputs.

## Task routing

| Task or event | Contract | Output and handoff | Human check |
|---|---|---|---|
| Forecast call, quarter or year pace, or quarter-end learning | `workflows/forecast-weekly/CONTEXT.md` | Thread reports and snapshots. Approved CRM corrections. Approved bucket edits to Systems for a PR | Forecast proposals and exact criteria wording require Operator's approval |

## Branch selection

Forecast follows `policy.forecast.schedule` or a typed forecast request. It reads corrected Salesforce state after Pipeline's review and retains its existing evidence coverage gate.
Tracking follows `policy.forecast.tracking.pace_report` or a typed tracking request. Its contract owns the no-change silence rule and keeps calculations in the helper.
At quarter end, tracking compares weekly call snapshots and outcomes. Its learning reference owns proposals and the approval handoff to Systems repo-maintenance.
The schedule values describe cadence and do not create automations. All branch definitions stay in the workflow contract and its routed references.
