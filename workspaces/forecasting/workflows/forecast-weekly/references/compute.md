# Compute

Read at the Compute step.

Save one reviewed calculation input in the sandbox, then run `policy.tooling.scripts.forecast_math --input <reviewed.json>`.
The input contains `as_of` (ISO date), `quarter` (`YYYY-Qn`), `booked`, current-quarter `deals`, and next-quarter candidate `pull_ins`.
Each row carries its Salesforce `Id` and `policy.forecast.amount_field` under that exact field name. Deals also carry reviewed `bucket` (`commit`, `upside`, or `excluded`).
At Bucket, supply `StageName` and `CloseDate` on deals and pull-ins, plus `last_activity_date` (ISO date or null) on deals: the reviewed latest activity across allowed sources.
Every current-quarter deal, including excluded rows, requires reviewed `buyer_delay_date`, `buyer_delay_evidence` and `blockers`. Missing review is needs-input, never an empty list.
Use explicit null for no buyer-stated delay and null evidence when no delay source applies. A stated delay needs an ISO date and a nonempty source reference.
`blockers` is the reviewed list of open buyer-side obstacles to signing. Use an empty list only after review finds none.
Each blocker has nonempty `description` and source `evidence`, plus `owner` as a reviewed name or explicit null and `date` as an ISO date or explicit null.
For S3 commit, review establishes that `buyer_date` is a buyer-named signature/decision date; the helper checks only that it is non-null and inside the quarter.
Include `action`, `buyer_date` (ISO date or explicit null), and source `evidence` for upside and pull-in rows.
IDs must be unique across booked, deals, and pull_ins. Use exact source amounts, never a guessed zero for missing data. Resolve amounts needed for the call before publishing a complete calculation.

Within `policy.forecast.next_quarter_preview_days` of quarter end, supply optional `preview` with every next-quarter row, including rows without an amount.
Each preview row has `Id` and the policy amount field, with explicit null when missing. Preview IDs are unique within preview and may overlap pull_ins, but never booked or deals.
Omit preview outside that window. An empty list is a checked empty next quarter, not an omitted preview.

The helper checks structure and fixed predicates, not full bucket validity. Two reviewed eligibility predicates hold a row instead of stopping the run.
A buyer delay past quarter end holds commit and upside (`buyer_delay_past_quarter_end`). An open blocker without a named owner and date holds commit (`commit_blocker_owner_date`).
A held row counts in no bucket sum, call, path or buffer. It keeps its original `qualified_pipeline` scope. Returned `status` is `incomplete` while any row is held, else `complete`.
Returned `held` lists each held row once with its original facts, `failed_predicate`, `hold` and `held_amount`. Structural or malformed input still fails the run and is never a held row.
Operator's call. After Operator types the override in the Forecasting thread, add one `operator_call` entry per deal to the input with `deal`, `bucket`, `predicate`, `reason` and `approved_turn`.
It overrides only that predicate on that deal and bucket. The row then counts once in its bucket and appears under returned `operator_calls` labeled "Operator's call" with the failed predicate.
An override that names another deal, bucket or predicate leaves the row held. Identity, amount, stage, activity and structure checks are never overridden.
Every predicate is evaluated. A row that also fails a predicate the override does not name stays held, with the remaining failures under `failed_predicates`.
Review establishes buyer attribution and whether an obstacle is open, not code.
The meaning of pull-in evidence remains a review judgment. Booked and pull-in rows do not require the current-quarter bucket-review fields.
Only pull-ins have a CloseDate bucket predicate (next quarter); they need no recent activity. A passed CRM CloseDate alone never rejects commit or upside.
The helper owns Decimal arithmetic and ranking, not interpretation. It returns booked, call = booked + commit, upside, gap = target - call, positive buffer = call + upside - target,
and upside ranked by `policy.forecast.amount_field` until the gap is covered or the list ends, with the shortfall.
Targets come from policy. Use the returned values and `path_to_target`, never recalculate them in prose. Pull-ins remain separate.
Returned `qualified_pipeline` sums the policy amount field over open deals at or above `policy.forecast.open_min_stage` with CloseDate inside the current quarter, regardless of bucket.
It excludes booked and pull-ins. Deals are open by this input's scope. Optional `IsClosed` must be Boolean and true rows are excluded from this total.
Every open row at or above that floor needs an ISO CloseDate and a present policy amount to calculate this total. A passed CloseDate still does not reject its reviewed bucket.
For the deck, add `Name` to every commit, upside and pull-in row. Missing metadata is needs-input, never invented.
Only when preview is supplied, returned `preview` contains `quarter`, `count`, `sum`, `missing_amount_count`, `top_three`, and `target`.
Its count includes every row. Its sum and top three use present amounts only, with ties ordered by Id. Missing amounts are counted, never treated as zero.
The label rolls forward one quarter, including Q4 to next-year Q1. The target is that quarter's policy target or `policy.forecast.target_default`.
When gap is zero or below, show `Target covered by $<n>` and omit Path. An absent buyer date is reported as none stated, never invented.
