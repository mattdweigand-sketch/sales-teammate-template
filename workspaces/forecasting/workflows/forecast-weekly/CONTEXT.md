---
cadence: weekly
reads: _core/policy.yaml (salesforce, pipeline, forecast, tooling), _core/rules.md, references/, Salesforce, Gmail, Calendar, Slack, forecast thread
writes: forecast branch writes only Opportunity ForecastCategoryName and Contact Email on approval, and Operator's slide in the shared bookings deck on D,
  tracking writes nothing, manager update creates only an unsent Slack draft
next: Pipeline for CloseDate and Next Step fixes, reports for Operator, approved quarter-end criteria edits go to Systems repo-maintenance for a repo PR
---
# Forecast Weekly
Forecast calls the quarter. Tracking reports pace. Salesforce is the record. In forecast, fresher Calendar, Gmail or Slack evidence decides the bucket and prompts a record proposal.
Select forecast by default, tracking for pace, or manager update. Forecast and tracking follow `policy.forecast.schedule`, `policy.forecast.tracking.pace_report` and `rules#scheduled_runs`.
## Inputs
| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core freshness | `_core/rules.md`, `_core/scripts/interfaces.md` | Forecast only, `rules#repo_currency`, `workflow_revision_check`, "Workflow revisions" | Each displayed write letter, tracking excluded |
| Core policy | `_core/policy.yaml` | Forecast and tracking load `salesforce`, `forecast`, `tooling`. Forecast also loads `pipeline`. Manager update only `forecast.manager_update`, `forecast.amount_field` | Values, helper registry, schedule and amount field |
| Core rules | `_core/rules.md` | Forecast and tracking load `rules#run_start`, `rules#scheduled_runs`, `rules#not_checked_means`, `rules#handoff_delivery`; manager update only, `rules#absence_conclusions`, `rules#not_checked_means` | Run start and evidence limits |
| Core rules | `_core/rules.md` | Forecast only, `rules#approval`, `rules#write_protocol`, `rules#calendar_search`, `rules#absence_conclusions` | Approval, writes, and collection |
| Core rules | `_core/rules.md` | Forecast only, `rules#next_steps`, `rules#next_steps_format`, `rules#next_steps_review`, `rules#close_date_basis` | What a CRM proposal may say |
| Helper | `_core/scripts/interfaces.md` | Forecast and tracking, "Interfaces", `forecast_math`, `forecast_notify`; forecast only, `forecast_deck`, `coverage_check`, `hygiene_check`, `gmail_digest` | Arithmetic, notification gates, coverage, hygiene, digest, slide plan and readback |
| Thread lookup | `_core/thread-locators.md` | All branches, "Teammate thread lookup" | Verified runtime destinations and history |
| Reference | `references/manager-update.md` | Manager update only, Full file | Current sources, existing-draft check and unsent result |
| Reference | `references/collect.md` | Forecast only, "Salesforce" at step 2, "Calendar and Gmail" and "Slack" at step 3 | Queries and searches |
| Shared evidence | `_core/slack-evidence.md` | Forecast only, "Search", "Limits" at step 3, `policy.tooling.slack_lookback_days` | Same read-only Slack method as pipeline-review |
| Reference | `references/buckets.md` | Full file for forecast at step 4 and tracking when review is due or requested | Bucket tests and exact wording proposals |
| Reference | `references/compute.md` | Full file for forecast at step 5 and tracking when review is due or requested | Reviewed calculation input |
| Reference | `references/deck.md` | Forecast only, "Target and approval", "Inputs and preview", "Slide mapping", "Overflow" at step 6, Full file at step 11 | Shared deck target, D preview, mapping, safe write and thumbnail |
| Reference | `references/report-format.md` | Forecast only, Full file at step 6 and "After apply" at step 9 | The fixed report and thread snapshot |
| Reference | `references/tracking.md` | Tracking only, "Collect", "Calculate", "Report and alerts", "Notification gate", "Snapshots" at step 12 | Read-only pace tracking |
| Reference | `references/learning.md` | Tracking rollover checks or requested review, "Quarter-end review", "Approval and delivery" | Due prior-quarter review and bucket edit proposals |
| Per-run evidence | Current Salesforce records and saved Salesforce, Gmail, Calendar, and Slack results in the sandbox | Forecast only, this quarter and next-quarter pull-ins | Includes verified Salesforce corrections from pipeline-review |
| Per-run evidence | Current Salesforce results in the sandbox and prior snapshots in the forecast thread | Tracking only, current year and previously open Opportunity Ids | Period totals, changes, and learning |
## Process
1. Manager update follows `references/manager-update.md`, then stops before forecast or tracking steps. Its schedule is `policy.forecast.manager_update`.
   Otherwise start per `rules#run_start`. Tracking goes to step 12. Forecast resolves the target from `policy.forecast.targets`, else `policy.forecast.target_default`.
2. Collect Salesforce per `references/collect.md` "Salesforce".
3. Collect Calendar, Gmail, and Slack per `references/collect.md` "Calendar and Gmail" and "Slack". Tracking reads no Slack.
4. Bucket every in-scope deal and draft CRM proposals per `references/buckets.md`.
5. Compute with `forecast_math` per `references/compute.md`. Its returned `status` is the process status, incomplete while any row is held.
6. Run `policy.tooling.scripts.coverage_check --scope forecast --since <run start with local offset>`, build the D preview per `references/deck.md`, then fill `references/report-format.md`.
   Exit 1 means not ready, follow its instructions. Before display, snapshot each write letter's scope per `rules#repo_currency`.
7. Scheduled runs only. Run `policy.tooling.scripts.forecast_notify --since <run start with local offset> --thread-url <run URL> --process-status <status>`. Send its payload unchanged.
   Status is `ready` when step 5 returned `complete` and step 6 exited 0, `incomplete` when any row is held, otherwise `review-needed` when step 6 exited 1.
8. Wait per `rules#approval`. Reply with letters as the report shows them. Every proposal is one record per approval. `skip` is an answer.
9. Apply only approved ForecastCategoryName or Contact Email changes per `rules#write_protocol`. CloseDate and Next Step fixes are handoffs to Pipeline, never forecast writes.
10. Close with counts booked, per bucket, held, pull-ins, not checked, and proposals applied, taking scope and coverage from the step 6 output.
    Name each skipped or unanswered lettered proposal and each not-checked Account per `rules#approval`.
11. After closing counts, on D only, update Operator's slide in the shared deck per `references/deck.md` "Write on D" using `policy.tooling.scripts.forecast_deck`.
Post its thumbnail in the run thread.
12. Tracking follows `references/tracking.md`. Scheduled tracking runs check rollover receipts per `references/learning.md` before silence. Criteria edits wait for Operator's wording approval.
    Scheduled Monday delivery calls `policy.tooling.scripts.forecast_notify --tracking-input <reviewed.json>` per "Notification gate" before notifying or suppressing.
## Checkpoints
| After Step | Agent Presents | Human Decides |
|---|---|---|
| 6 | The forecast report with lettered CRM gap and ForecastCategory proposals | Which letters to apply, or `skip`. Bucket calls stay Operator's |
| 6 | D in the same report, each slide field as current → new | D or not. Nothing posts to the deck without D. A later bucket change re-proposes D |
| 12 | Numbered quarter-end bucket edits with evidence | Operator approves exact wording before a Systems repo-maintenance PR |
## Audit
| Check | Pass Condition |
|---|---|
| Coverage, before step 6 output | `coverage_check --scope forecast` exits 0 and its lines appear unchanged, or the report is labeled not ready per its instructions |
| Arithmetic, before steps 6 or 12 output | Every total, ratio, pace, and ranking comes from `forecast_math`, never recalculated in prose |
| Deck, after step 11 | Deck values come only from forecast_math and the reviewed input per deck.md, the fresh read matched the D preview, quota matched policy, only Operator's slide changed, and readback passed |
| Bucket reasons, before step 6 output | Every in-scope deal appears once with its bucket and quoted source; Calling plus Held plus Not in the call equals the in-quarter in-scope count |
| Sources, before step 6 output | Only `policy.forecast.sources` evidence is used, including read-only Slack. No warehouse reads. Pilot facts arrive only as corrected Salesforce state |
| Scope, before step 6 output | No StageName or Amount change (route to `pipeline-review`), no Closed Won (route to `close`), no drafted or sent email, no Operator-stated date treated as buyer-named |
| Writes | Only ForecastCategoryName, Contact Email and D for Operator's slide can be approved here. CloseDate and Next Step fixes route to Pipeline with evidence and no transferred approval |
| Tracking, throughout | Complete owner-scoped Salesforce reads or an explicit not-checked result. No CRM, Gmail, Calendar, Slack, or repo writes. Silent scheduled output only per the tracking reference |
## Outputs
| Artifact | Location | Format |
|---|---|---|
| Forecast report | Run thread | `references/report-format.md` layout for Operator, with no automatic downstream workflow |
| Bookings deck slide | Operator's slide in the shared deck on D, thumbnail in the run thread | Fields per references/deck.md, plan and get JSON in sandbox |
| Proposed changes | Inside the report | Lettered CRM gap and ForecastCategory proposals |
| Reviewed calculation input | Sandbox | JSON per `references/compute.md` |
| Salesforce updates | Opportunity ForecastCategoryName and Contact Email only, after approval | Approved fields read back per `rules#write_protocol` |
| Pipeline handoffs | Pipeline thread | CloseDate and Next Step evidence only, never applied by Forecasting. Pipeline makes its own source fingerprint, proposal and approval |
| Apply receipt | Run thread | `references/report-format.md` "After apply" line, step 10 counts, named skipped items |
| Pace report, alerts, and snapshots | Forecast run thread | Tracking format and silence rule in `references/tracking.md`. Weekly calls stay in the thread |
| Approved criteria handoff | Forecast thread, to Systems repo-maintenance | Exact approved diff and evidence per `references/learning.md`, for a tested repo PR |
| Manager update | Unsent Slack draft in the runtime manager DM, text and DM link in the run thread | `references/manager-update.md`, never send or overwrite an existing draft |
