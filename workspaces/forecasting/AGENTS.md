# Forecasting

Own forecast-weekly, including evidence-based forecast calls, read-only quarter and year tracking, and quarter-end learning.
The same workflow routes the Friday manager update to its unsent Slack draft procedure.

## Entry

Read `workspaces/forecasting/CONTEXT.md` to select the branch. Its workflow contract owns the bounded Inputs, arithmetic, outputs, and human checkpoints.
The root AGENTS.md also routes forecast-weekly directly to its execution contract.

## Boundaries and handoffs

Read Pipeline's verified Salesforce corrections as records, without loading Pipeline workflow folders.
The forecast branch keeps its existing proposal approvals and readback gates under `rules#approval` and `rules#write_protocol`. Tracking writes no customer systems.
The forecast branch writes only ForecastCategoryName and Contact Email, plus Operator's slide in the shared bookings deck on D.
The manager-update branch creates only an unsent Slack draft in the runtime manager DM, never a sent message or Salesforce change.
CloseDate and Next Step corrections are evidence handoffs to Pipeline for its own approval.
Reports and weekly snapshots stay in the forecast thread, with saved query and calculation results in the sandbox. No state or lessons files enter the repo.
Quarter-end learning proposes numbered bucket edits for Operator's exact wording approval in the forecast thread.
Send approved wording, evidence, and the approval link to Systems repo-maintenance for a tested repo PR. Merged references govern later runs.
Authoring guidance lives in `_core/CONVENTIONS.md`. This workspace does not change library pointers or activate automations during a run.
