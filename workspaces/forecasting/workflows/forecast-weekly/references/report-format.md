# Forecast report

Operator's own shape. Plain text. Dollar figures with commas, no cents unless the record has them. Record links use `policy.salesforce.record_url`.
Every deal in the evidence scope of `workspaces/forecasting/workflows/forecast-weekly/references/collect.md` "Calendar and Gmail"
appears exactly once under Calling, Held, Pull-in scope, or Not in the call.
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
- <Opportunity link> $<amount>. Operator's call, <bucket>, failed <failed_predicate>, approved <approved_turn>. <evidence clause>.
Forecast call $<call>[ · Subtotals incomplete, <n> held]
Gap to $<target> $<gap> | Target covered by $<n>

## Held (<n>)
Only when returned `status` is `incomplete`. One line per returned `held` row, with its original facts and held amount counted in no total.
- <Opportunity link> · <stage> · $<held_amount> · close <M/D> · <bucket> held · <failed_predicate> (<source>)

## Path to $<target>
1. <Opportunity link> | $<amount>. <Next line action>. Buyer date: <M/D only if the buyer wrote it, else none stated, "<buyer's words>">.
2. ...
<Call plus all upside reaches $<sum>, a $<buffer> buffer.> | <Upside does not cover the gap by $<n>.>

## Pull-in scope (<n>)
Every next-quarter deal in scope with `policy.forecast.amount_field` set, one line each. Never fall back to Amount.
- <Opportunity link> · $<amount> · close <M/D> · CANDIDATE · <proposal or order form out, buyer confirmed reviewing on M/D | buyer named M/D> (<source>) · <Next line action>
- <Opportunity link> · $<amount> · close <M/D> · not · <failed condition> (<source>)

## Not in the call (<n>)
Every in-quarter deal not under Calling or Held, one line each, with its bucket.
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

## Bookings deck (D)
D. Operator's slide in <deck link>, <changed> of <fields> fields change. Quota <quota> matches policy.
- <field>: <current> → <new>
- Operator's call: <Name> <bucket>, failed <failed_predicate>, approved <approved_turn>
(or `D. Not proposed: <forecast_deck message>`)
Reply with letters to apply, or `skip`.
```

Letter sequentially across Contact Email and ForecastCategory sync only, skipping D.
D is reserved for the deck slide per `references/deck.md`. Pipeline handoffs have no write-approval letters here and transfer no approval.
Bucket counts Calling (n) plus Held (n) plus Not in the call (n) equal the in-quarter in-scope count.
While any row is held, label every subtotal `Subtotals incomplete`, show `D. Not proposed`, and pass `--process-status incomplete` to the notification step.
An overridden row stays visible. Show it under its bucket and in the D block labeled Operator's call with the failed predicate and the approving turn, never as a clean row.
Within `policy.forecast.next_quarter_preview_days` of quarter end, show preview only from the returned `preview` values. Never sum or rank next-quarter rows in prose.
Add `<m> without ARR` only when returned `preview.missing_amount_count` is greater than zero. Render only the returned top three, which may contain fewer than three rows.
Keep the dated call and reviewed calculation input with each deal's Id and bucket in this run thread for quarter-end comparison. Never store weekly snapshots in the repo.

## After apply

Keep each write letter's saved source scope and baseline with its displayed proposal, separate from recalculated forecast evidence.
Relevant changes hold that old letter for a new proposal and approval per `rules#repo_currency`. Never silently reuse approval after recalculation.

```
<w> written · <s> skipped · <r> rejected
```

Held rows remain in qualified_pipeline when their original stage and CloseDate qualify. This is pipeline inventory. It does not add Held revenue to the forecast call.
