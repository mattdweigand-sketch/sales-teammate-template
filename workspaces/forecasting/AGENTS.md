# Forecasting

Own forecast-weekly, including evidence-based forecast calls, read-only quarter and year tracking, and quarter-end learning.

## Entry

Read `workspaces/forecasting/CONTEXT.md` to select the branch. Its workflow contract owns the bounded Inputs, arithmetic, outputs, and human checkpoints.
The root AGENTS.md also routes forecast-weekly directly to its execution contract.

## Boundaries and handoffs

Read Pipeline's verified Salesforce corrections as records, without loading Pipeline workflow folders.
The forecast branch keeps its existing proposal approvals and readback gates under `rules#approval` and `rules#write_protocol`. Tracking writes no customer systems.
Forecasting writes only ForecastCategoryName and Contact Email. CloseDate and Next Step corrections are evidence handoffs to Pipeline for its own approval.
Reports and weekly snapshots stay in the forecast thread, with saved query and calculation results in the sandbox. No state or lessons files enter the repo.
Quarter-end learning proposes numbered bucket edits for Operator's exact wording approval in the forecast thread.
Send approved wording, evidence, and the approval link to Systems repo-maintenance for a tested repo PR. Merged references govern later runs.
Authoring guidance lives in `_core/CONVENTIONS.md`. This workspace does not change library pointers or activate automations during a run.
