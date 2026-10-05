---
cadence: weekly
reads: _core/policy.yaml (salesforce, pipeline, forecast, tooling), _core/rules.md, references/, Salesforce, Gmail, Calendar, Slack, forecast thread
writes: forecast branch writes only Opportunity ForecastCategoryName and Contact Email on approval, tracking writes nothing
next: Pipeline for CloseDate and Next Step fixes, reports for Operator, approved quarter-end criteria edits go to Systems repo-maintenance for a repo PR
---

# Forecast Weekly

Forecast answers what will close this quarter using every allowed source. Tracking reports quarter and year pace from Salesforce.
Salesforce is the record. In forecast, fresher Calendar, Gmail, or Slack evidence decides the bucket and prompts a record proposal. Nothing is written without approval in the thread.
Select forecast by default or tracking for quarter and year pace. Schedules follow `policy.forecast.schedule`, `policy.forecast.tracking.pace_report`, and `rules#scheduled_runs`.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | Both branches load `salesforce`, `forecast`, `tooling`. Forecast also loads `pipeline` | Values and helper registry |
| Core rules | `_core/rules.md` | Both branches load `rules#run_start`, `rules#scheduled_runs`, `rules#not_checked_means` | Run start and evidence limits |
| Core rules | `_core/rules.md` | Forecast only, `rules#approval`, `rules#write_protocol`, `rules#calendar_search`, `rules#absence_conclusions` | Approval, writes, and collection |
| Core rules | `_core/rules.md` | Forecast only, `rules#next_steps`, `rules#next_steps_format`, `rules#next_steps_review`, `rules#close_date_basis` | What a CRM proposal may say |
| Helper | `_core/scripts/interfaces.md` | Both branches, "Interfaces", the `forecast_math` and `forecast_notify` rows | Arithmetic and deterministic notification gates |
| Reference | `references/collect.md` | Forecast only, "Salesforce" at step 2, "Calendar and Gmail" and "Slack" at step 3 | Queries and searches |
| Shared evidence | `_core/slack-evidence.md` | Forecast only, "Search", "Limits" at step 3, `policy.tooling.slack_lookback_days` | Same read-only Slack method as pipeline-review |
| Reference | `references/buckets.md` | Full file for forecast at step 4 and tracking at quarter end | Bucket tests and exact wording proposals |
| Reference | `references/compute.md` | Full file for forecast at step 5 and tracking at quarter end | Reviewed calculation input |
| Reference | `references/report-format.md` | Forecast only, Full file at step 6 and "After apply" at step 8 | The fixed report and thread snapshot |
| Reference | `references/tracking.md` | Tracking only, "Collect", "Calculate", "Report and alerts", "Notification gate", "Snapshots" at step 10 | Read-only pace tracking |
| Reference | `references/learning.md` | Tracking at quarter end only, "Quarter-end review", "Approval and delivery" | Evidence-led bucket edit proposals |
| Per-run evidence | Current Salesforce records and saved Salesforce, Gmail, Calendar, and Slack results in the sandbox | Forecast only, this quarter and next-quarter pull-ins | Includes verified Salesforce corrections from pipeline-review |
| Per-run evidence | Current Salesforce results in the sandbox and prior snapshots in the forecast thread | Tracking only, current year and previously open Opportunity Ids | Period totals, changes, and learning |

## Process

1. Start per `rules#run_start`. Select the branch. Tracking goes to step 10. Forecast resolves the target from `policy.forecast.targets`, else `policy.forecast.target_default`.
2. Collect Salesforce per `references/collect.md` "Salesforce".
3. Collect Calendar, Gmail, and Slack per `references/collect.md` "Calendar and Gmail" and "Slack". Tracking reads no Slack.
4. Bucket every in-scope deal and draft CRM proposals per `references/buckets.md`.
5. Compute with `forecast_math` per `references/compute.md`.
6. Run `policy.tooling.scripts.coverage_check --scope forecast --since <run start with local offset>`, then fill `references/report-format.md`.
   Exit 1 means the report is not ready; follow its instructions.
7. Wait per `rules#approval`. Reply with letters as the report shows them. Every proposal is one record per approval. `skip` is an answer.
8. Apply only approved ForecastCategoryName or Contact Email changes per `rules#write_protocol`. CloseDate and Next Step fixes are handoffs to Pipeline, never forecast writes.
9. Close with counts booked, per bucket, pull-ins, not checked, and proposals applied, taking scope and coverage from the step 6 output.
   Name each skipped or unanswered lettered proposal and each not-checked Account per `rules#approval`.
10. Tracking collects, calculates, and reports per `references/tracking.md`. At quarter end, propose criteria edits per `references/learning.md` and wait for Operator's wording approval.
    Scheduled Monday delivery calls `policy.tooling.scripts.forecast_notify --tracking-input <reviewed.json>` per "Notification gate" before notifying or suppressing.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 6 | The forecast report with lettered CRM gap and ForecastCategory proposals | Which letters to apply, or `skip`. Bucket calls stay Operator's |
| 10 | Numbered quarter-end bucket edits with evidence | Operator approves exact wording before a Systems repo-maintenance PR |

## Audit

| Check | Pass Condition |
|---|---|
| Coverage, before step 6 output | `coverage_check --scope forecast` exits 0 and its lines appear unchanged, or the report is labeled not ready per its instructions |
| Arithmetic, before steps 6 or 10 output | Every total, ratio, pace, and ranking comes from `forecast_math`, never recalculated in prose |
| Bucket reasons, before step 6 output | Every in-scope deal appears once with its bucket and quoted source; Calling plus Not in the call equals the in-quarter in-scope count |
| Sources, before step 6 output | Only `policy.forecast.sources` evidence is used, including read-only Slack. No warehouse reads. Pilot facts arrive only as corrected Salesforce state |
| Scope, before step 6 output | No StageName or Amount change (route to `pipeline-review`), no Closed Won (route to `close`), no drafted or sent email, no Operator-stated date treated as buyer-named |
| Writes | Only ForecastCategoryName and Contact Email can be approved here. CloseDate and Next Step fixes route to Pipeline with evidence and no transferred approval |
| Tracking, throughout | Complete owner-scoped Salesforce reads or an explicit not-checked result. No CRM, Gmail, Calendar, Slack, or repo writes. Silent scheduled output only per the tracking reference |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Forecast report | Run thread | `references/report-format.md` layout for Operator, with no automatic downstream workflow |
| Proposed changes | Inside the report | Lettered CRM gap and ForecastCategory proposals |
| Reviewed calculation input | Sandbox | JSON per `references/compute.md` |
| Salesforce updates | Opportunity ForecastCategoryName and Contact Email only, after approval | Approved fields read back per `rules#write_protocol` |
| Pipeline handoffs | Pipeline thread | CloseDate and Next Step correction evidence for its own review and approval, never applied by Forecasting |
| Apply receipt | Run thread | `references/report-format.md` "After apply" line, step 9 counts, named skipped items |
| Pace report, alerts, and snapshots | Forecast run thread | Tracking format and silence rule in `references/tracking.md`. Weekly calls stay in the thread |
| Approved criteria handoff | Forecast thread, to Systems repo-maintenance | Exact approved diff and evidence per `references/learning.md`, for a tested repo PR |
| Saved results | Sandbox | Query and helper outputs, never Project Files |
