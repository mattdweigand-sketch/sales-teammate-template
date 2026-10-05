# Compute

Read at the Compute step.

Save one reviewed calculation input in the sandbox, then run `policy.tooling.scripts.forecast_math --input <reviewed.json>`.
The input contains `quarter` (`YYYY-Qn`), `booked`, current-quarter `deals`, and next-quarter candidate `pull_ins`.
Each row carries its Salesforce `Id` and `policy.forecast.amount_field` under that exact field name. Deals also carry reviewed `bucket` (`commit`, `upside`, or `excluded`).
Include `action`, `buyer_date` (ISO date or explicit null), and source `evidence` for upside and pull-in rows.
IDs must be unique across booked, deals, and pull_ins. Use exact source amounts, never a guessed zero for missing data. Resolve amounts needed for the call before publishing a complete calculation.

Within `policy.forecast.next_quarter_preview_days` of quarter end, supply optional `preview` with every next-quarter row, including rows without an amount.
Each preview row has `Id` and the policy amount field, with explicit null when missing. Preview IDs are unique within preview and may overlap pull_ins, but never booked or deals.
Omit preview outside that window. An empty list is a checked empty next quarter, not an omitted preview.

The helper owns Decimal arithmetic and ranking, not interpretation. It returns booked, call = booked + commit, upside, gap = target - call, positive buffer = call + upside - target,
and upside ranked by `policy.forecast.amount_field` until the gap is covered or the list ends, with the shortfall.
Targets come from policy. Use the returned values and `path_to_target`, never recalculate them in prose. Pull-ins remain separate.
Only when preview is supplied, returned `preview` contains `quarter`, `count`, `sum`, `missing_amount_count`, `top_three`, and `target`.
Its count includes every row. Its sum and top three use present amounts only, with ties ordered by Id. Missing amounts are counted, never treated as zero.
The label rolls forward one quarter, including Q4 to next-year Q1. The target is that quarter's policy target or `policy.forecast.target_default`.
When gap is zero or below, show `Target covered by $<n>` and omit Path. An absent buyer date is reported as none stated, never invented.
