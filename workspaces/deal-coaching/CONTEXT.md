# Deal Coaching routes

Enter through `workspaces/deal-coaching/AGENTS.md` for ownership and boundaries. Then select one execution contract and its applicable Inputs rows.

## Task routing

| Task or event | Contract | Output and handoff | Human check |
|---|---|---|---|
| Call, deal, or pre-meeting coaching, or criteria refresh | `workflows/deal-coach/CONTEXT.md` | Coach thread reports and proposed criteria edits. Salesforce suggestions go to Pipeline | Operator approves exact criteria wording before a repo PR |

## Branch selection and handoffs

Route call preparation to `workspaces/pipeline/workflows/sales-call-prep/CONTEXT.md` through root `AGENTS.md`.
Deal-coach selects call-review, deal-review, pre-meeting, or criteria-refresh in its contract. Branch schedules remain in `policy.coach.schedule` and do not activate automations.
Coaching branches read only their selected deal and call evidence. Criteria-refresh loads only its named sections and any targeted reference wording.
Route Salesforce notes to the responsible Pipeline workflow through the Pipeline thread for Operator's approval. Pipeline owns execution and readback.
Approved criteria changes go to Systems repo-maintenance for a tested repo PR. A merged PR updates canonical references, while learning evidence stays in the Coach thread.
