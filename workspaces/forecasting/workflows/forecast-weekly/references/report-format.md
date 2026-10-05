# Forecast report

Operator's own shape. Plain text. Dollar figures with commas, no cents unless the record has them. Record links use `policy.salesforce.record_url`.
Every deal in the evidence scope of `workspaces/forecasting/workflows/forecast-weekly/references/collect.md` "Calendar and Gmail"
appears exactly once under Calling, Pull-in scope, or Not in the call.
Line 1 is the title, then every `coverage_check` output line unchanged, then `Notes as of <newest history-line date across in-scope deals>`,
appending `no notes written this week` when that date is before the current week's Monday.

```
# <Q3 2026> forecast · <M/D/YY>
<coverage_check output lines: coverage, Calendar, Salesforce Events, and any Not checked or gap lines>
Slack <contacts checked and per-deal not-checked limits, separate from mandatory coverage>
Notes as of <M/D/YY>[. no notes written this week]
Not checked: <source per deal, or none>

Booked $<booked> (<n> deals)
Calling (<n>)
- <Opportunity link> $<amount>. <evidence clause: stage, buyer-named date, last touch>.
Forecast call $<call>
Gap to $<target> $<gap> | Target covered by $<n>

## Path to $<target>
1. <Opportunity link> | $<amount>. <Next line action>. Buyer date: <M/D only if the buyer wrote it, else none stated, "<buyer's words>">.
2. ...
<Call plus all upside reaches $<sum>, a $<buffer> buffer.> | <Upside does not cover the gap by $<n>.>

## Pull-in scope (<n>)
Every next-quarter deal in scope with `policy.forecast.amount_field` set, one line each. Never fall back to Amount.
- <Opportunity link> · $<amount> · close <M/D> · CANDIDATE · <proposal or order form out, buyer confirmed reviewing on M/D | buyer named M/D> (<source>) · <Next line action>
- <Opportunity link> · $<amount> · close <M/D> · not · <failed condition> (<source>)

## Not in the call (<n>)
Every in-quarter deal not under Calling, one line each, with its bucket.
- <Opportunity link> · <stage> · $<amount or "not set"> · close <M/D> · <upside | excluded> · <failed commit condition, and for excluded the failed upside condition> (<source>)

## <returned preview.quarter> preview
<preview.count> deals, $<preview.sum>[, <m> without ARR]. Top: <preview.top_three links and amounts, or none>. Target $<preview.target>.

## Asks
- <who>: <what, for which deal, by when>
(or `None.`)

## Pipeline handoffs (<n>)
- <Opportunity link> CloseDate or Next Step correction, current value to proposed value, source and date. Pipeline owns review, matching Task and approval.

## CRM gaps and sync (<n>)
A. <Contact link> Email <old> → <new>. Evidence: replies from <new> on <M/D>.
B. <Opportunity link> ForecastCategoryName <current> → <proposed> (<bucket>). Per `workspaces/forecasting/workflows/forecast-weekly/references/buckets.md` and policy.forecast.forecast_category_map.
Reply with letters to apply, or `skip`.
```

Letter sequentially across Contact Email and ForecastCategory sync only. Pipeline handoffs have no write-approval letters here and transfer no approval.
Bucket counts Calling (n) plus Not in the call (n) equal the in-quarter in-scope count.
Within `policy.forecast.next_quarter_preview_days` of quarter end, show preview only from the returned `preview` values. Never sum or rank next-quarter rows in prose.
Add `<m> without ARR` only when returned `preview.missing_amount_count` is greater than zero. Render only the returned top three, which may contain fewer than three rows.
Keep the dated call and reviewed calculation input with each deal's Id and bucket in this run thread for quarter-end comparison. Never store weekly snapshots in the repo.

## After apply

```
<w> written · <s> skipped · <r> rejected
```
