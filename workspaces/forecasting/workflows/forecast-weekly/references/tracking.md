# Quarter and year tracking

## Collect

Tracking is read-only. Use the run-start local date in `policy.forecast.tracking.pace_report` timezone as `as_of`.
Read the previous published Monday tracking snapshot from the forecast thread. A silent Monday carries that baseline forward. No baseline means an initial report, not proof of no change.
Use the current owner from run start. Retrieve every Salesforce page for the calendar year, the next `policy.forecast.tracking.forward_quarters` quarters,
and the `policy.forecast.tracking.created_arr_window_days` creation window, saving results in the sandbox.

```sql
SELECT Id, CreatedDate, CloseDate, IsClosed, IsWon, ForecastCategoryName, <policy.forecast.amount_field>
FROM Opportunity
WHERE OwnerId = '<userId>' AND ((CloseDate >= <year-start> AND CloseDate <= <latest-year-or-forward-quarter-end>)
  OR (CreatedDate >= <creation-window-start-UTC> AND CreatedDate < <day-after-as-of-start-UTC>))
```

Also reread every previously open Opportunity Id in the prior snapshot under the same owner, even if its CloseDate has left the year. Deduplicate by Id after resolving differing reads.
This prevents a Commit deal moved into another year from disappearing before comparison. A missing prior open record is not checked, never inferred closed or moved.
Query failures, incomplete paging, or missing values needed for totals block a complete pace report. Name the gap per `rules#not_checked_means` and do not suppress it as an unchanged run.
Retain all stages. Tracking uses Salesforce status and CloseDate, not the forecast branch's reviewed bucket assignments. Do not read Gmail or Calendar for this branch.

## Calculate

Save a reviewed JSON object in the sandbox, then run `policy.tooling.scripts.forecast_math --tracking --input <reviewed.json>`.
It contains `as_of` as YYYY-MM-DD, `records` from the complete reads, and optional `previous` containing the last returned tracking snapshot, including its period targets.
Each record carries the selected fields above. CreatedDate is an offset timestamp, converted to the pace timezone. IsClosed and IsWon must be Boolean.
Ids must be unique and dates valid. Amounts use the exact `policy.forecast.amount_field` name. Set `reads_complete: true` only after all required native pages and rereads succeed.
The helper reads only `policy.forecast`. A nonzero exit blocks the report and its error is shown. Use returned arithmetic without recomputing it in prose.

| Measure | Definition owned by the helper |
|---|---|
| Quarter target | Matching entry in `policy.forecast.targets`, otherwise `policy.forecast.target_default` |
| Year target | Sum of that year's four quarter targets, including explicit zero targets |
| Booked | IsWon records whose CloseDate is within the quarter or year |
| Gap | Target minus booked, floored at zero |
| Quarter linear pace | Quarter target times elapsed calendar days divided by days in the quarter, including the as-of day |
| Year linear pace | Sum of completed quarter targets plus current quarter target times elapsed quarter days divided by days in that quarter, including the as-of day |
| Pace behind | Shortfall below linear pace as a percentage of linear pace, floored at zero. Null when linear pace is zero |
| Required per week | Remaining gap times seven divided by calendar days after the as-of day. Null at period end when a positive gap remains |
| Open pipeline | Nonclosed records with CloseDate in the quarter. Year coverage uses only CloseDates from as-of through year end |
| Coverage | Open pipeline divided by remaining gap. Null when the target is covered |
| Concentration | Largest two open deals by the policy amount field, with Id as tie break, their share, and coverage excluding them |
| Forward coverage | Open pipeline divided by max(target less booked, zero), null when covered. Use each quarter's ramp target, else target_default |
| Forward coverage shortfall | max(coverage_min times remaining target less open pipeline, zero) |
| Forward required creation per week | Each forward coverage shortfall times seven divided by calendar days until that quarter starts. Sum the unrounded quarterly needs |
| Created ARR | Sum the policy amount field on all owned Opportunities created in the trailing configured local calendar days, including as_of, regardless of CloseDate or closed status |

No open pipeline gives a null concentration share. Null coverage means target covered, not zero coverage. A null required weekly amount with a positive gap means no days remain.
Monetary figures and percentages are rounded to two decimal places, coverage to four. Alert comparisons use unrounded values. Missing ARR for a contributing record is an error, never zero.

## Report and alerts

Monday pace reports follow `policy.forecast.tracking.pace_report`. This contract does not create or alter an automation.
Post two short lines, one per current period, with booked, target, gap, linear pace, required per week, and coverage. Add largest-two share and coverage without those deals.
Add one line showing each returned forward quarter's coverage against `policy.forecast.tracking.coverage_min`, target, pipeline and shortfall.
Add one line with created ARR in the configured window against the summed weekly creation need, showing each quarter's contribution to that need.
Use Opportunity links from `policy.salesforce.record_url` for the returned Ids. Do not invent buyer evidence from these totals.
Each alert is one or two lines with the affected Opportunity links. Aggregate alerts link the open deals behind the coverage or pace gap.
If there are no such records, say no open Opportunities rather than inventing a link.

- Closed Won or Closed Lost in the period appears when a record is new or changes closed outcome relative to the prior snapshot. Without a baseline, transition history is unverified.
- A previously open Commit deal alerts when its CloseDate leaves the quarter it was in. Merely advancing the calendar does not count as a date move.
- Coverage alerts below `policy.forecast.tracking.coverage_min` times the remaining gap.
- Pace alerts when behind linear pace by more than `policy.forecast.tracking.pace_behind_alert_percent` percent.

The helper returns period flags, record alerts, and `material_change`. Material changes include record membership, amounts, status, category, or CloseDate changes.
A period or target change, changed booked or open totals, or crossing a coverage or pace threshold also counts. Time passing alone within the same threshold state does not.
On a scheduled Monday with a verified baseline and `material_change` false, post nothing, including no close line or duplicate snapshot. A typed request still receives the current report.
Missing evidence or an unread prior snapshot is never a no-change conclusion. A new risk threshold crossing is reported even without a record change.

## Notification gate

For every scheduled Monday run, call `policy.tooling.scripts.forecast_notify --tracking-input <reviewed.json> --since <run start with offset>
--thread-url <run URL> --summary <four report lines> --process-status <ready|incomplete|review-needed>`.
The helper validates tracking math and the complete-read flag, then emits a notify decision and payload. This mode never requires forecast-only Gmail or Calendar coverage.
If `notify` is false, post nothing and run `pplx automation suppress-run-notification`. Otherwise send only the returned `payload` unchanged via the authorized notification tool.
Missing reads, invalid input or a non-ready process status yield an incomplete payload, never silence or a ready title. Helper execution failure is reported, not treated as unchanged.

## Snapshots

Attach the helper's returned snapshot to each published pace report in the forecast run thread. Use it as the next comparison input, never as a file in the repo.
Keep each week's forecast call and reviewed deal buckets with their Opportunity Ids, policy amounts, quarter, and call date in that week's forecast thread.
Link that call when doing quarter-end learning. A missing snapshot stays unknown and is not reconstructed from today's bucket or record state.
