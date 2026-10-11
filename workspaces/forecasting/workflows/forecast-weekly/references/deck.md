# Weekly bookings plan deck

## Target and approval

If Google Slides is deferred or not_used, or the presentation target is absent, skip deck reads and planning. State that D is unavailable and continue the supported forecast and CRM letters.
The target is Operator's slide in the configured shared deck `policy.forecast.deck.presentation_id`, edited through the gws CLI with api_credentials gws.
Resolve the slide at run time by `policy.forecast.deck.slide_title` with `{quarter}` set to the run quarter, for example Q4. Exactly one slide must match.
Never use slide positions or stored objectIds. Write nothing outside Operator's slide. Other sellers' slides and the manager's rollup are read only.
The repo has no deck template. Fields come from the live slide's shapes and table cells by label, per "Slide mapping".
Do not run the deck for the read-only tracking branch. The slide records the reviewed forecast, not unapproved CRM edits.
D is one write letter in the same forecast report. One reply covers the CRM letters and D. Nothing posts to the deck without D.
Snapshot D's scope with the other write letters per `rules#repo_currency`. Any later bucket or value change re-proposes D.
D is not proposed when mandatory coverage is not ready or its affected set is unknown or contains a contributing Opportunity Id.
Keep the reviewed totals unchanged and show the coverage gap. Do not remove affected deals to make the deck ready.
D is not proposed while any row is held, per `references/compute.md`. A helper-only partial never makes the deck ready. Resolve or override the hold, then rerun plan.
The plan's `operator_calls` lists every overridden row labeled Operator's call with its failed predicate and approving turn. Show them in the D block. A changed list re-proposes D.
Every target shape id comes from the current-run read and must match the approved D preview on replan, never a stored or policy id.

## Inputs and preview

After step 5, save the returned forecast_math JSON, its reviewed input, and one deck input in the sandbox.
Reviewed commit, upside and pull-in rows need `Name`. Their amounts use `policy.forecast.amount_field`, never the standard Amount as a fallback.
The deck input has `as_of`, `quarter_start`, `rows` keyed by those exact Opportunity Ids, and `support`, a list of zero through three short lines from the report's Asks.
Each `rows` value is the reviewed core-deal risk or buyer next step, or the backup required action. Do not invent or infer missing text.
Dates are ISO dates. `as_of` matches the reviewed input and is within its quarter. `quarter_start` is that quarter's first calendar day.
Read the deck with `gws slides presentations get` for the policy presentation id and save the JSON. This read is read only.
Save the current `coverage_check --scope forecast --since <run start with local offset> --json` output as `<coverage.json>`.
Run `policy.tooling.scripts.forecast_deck plan --presentation <get.json> --forecast <result.json> --reviewed <reviewed.json> --input <deck.json> --coverage <coverage.json>`.
Save the printed plan as the D preview. Its `fields` fill the D block of `references/report-format.md`, each as current → new.
The helper checks that returned arithmetic matches the reviewed input and current policy. A mismatch is needs-input, not permission to revise the call.
Exit 1 means D is not proposed. Show `D. Not proposed: <helper message>` and continue the rest of the report.

## Write on D

1. Re-read the deck with `gws slides presentations get` and save it as the fresh read.
2. Rerun coverage_check and save its current JSON. Rerun `plan` with the fresh read, the same reviewed inputs, fresh `--coverage <coverage.json>` and `--approved <D preview>`.
   Exit 1 means Operator's slide text or a value differs from the D preview. Stop and re-propose D. Never write the old preview.
3. Send the printed `batch_update` body in one `gws slides presentations batchUpdate`. It carries `writeControl.requiredRevisionId` from the fresh read.
   A revision conflict means the deck changed after the fresh read. Stop and re-propose D.
4. Read back with `gws slides presentations get`. Run `forecast_deck verify --plan <fresh plan> --before <fresh read> --after <readback>`.
   `verify` passes only when every field shows its new value and no other text on any slide changed.
5. After `readback` is `passed`, fetch Operator's slide with `gws slides presentations pages getThumbnail` using the plan's `slide_object_id`.
   Post the thumbnail in the forecast run thread with that week's report as the weekly record.
A failed readback is reported with the mismatch message and the deck link. Do not retry or repair without a new D.
Keep get JSON, plans and thumbnails in the sandbox or run thread, never in Git.

## Slide mapping

This section owns the mapping. `{q}` is the run quarter label, for example Q4.
A labelled money value is the first nonempty shape after its label shape on the slide. Groups are read in order.
SUPPORT NEEDED is the shape directly after its label. An empty text box is selected as empty. An empty shape that is not a text box holds D as ambiguous. It never resolves to the Gap note.

| Live slide field | Saved source and destination |
|---|---|
| Updated and Start date | Shape starting `Updated:`. Only the two dates change, as M/D. Updated is deck `as_of`. Start date is `quarter_start`, 10/1 for Q4 |
| {q} QUOTA | Manager's. Never written. Checked to equal the returned `target` from the policy quarter target, for example $650K = 650000. Mismatch stops D |
| {q} CALL | Returned `call`, booked plus commit |
| UPSIDE CALL | Returned call plus returned upside |
| GAP TO CALL | Returned `gap`, quota minus call |
| ARR CLOSED QTD | Returned `booked`, the table whose first cell is `Closed total`, row 0 column 1 |
| CORE DEALS TO HIT FORECAST | Commit rows only, the table with header Deal, Amount, Stage, Risk. Name, policy amount, normalized S# and deck row text |
| BACKUP PIPELINE | Upside then pull-in rows, the table with header Deal, Amount, Required action. Name, policy amount and deck row text |
| Backup total | Sum of all upside and pull-in amounts, including summarized rows, that table's `Backup total` row column 1 |
| SUPPORT NEEDED | Up to three deck support lines from Asks, one paragraph each, or None. when empty |
| CURRENT QUARTER QUALIFIED PIPELINE | Returned `qualified_pipeline`, using `policy.forecast.open_min_stage`, the table whose first cell starts `Qualified pipeline`, row 0 column 1 |

The title and other labels are never written. A missing or duplicated label, or a live table whose deal rows differ from
`policy.forecast.deck.core_rows` or `backup_rows`, exits 1 naming the field. Fix the inputs or ask Operator. Never guess a cell.
All money uses whole dollars with a dollar sign and commas, for example $1,817,650, never K or M abbreviations. Round half up only at display, preserving full Decimal amounts for sums.
A negative gap uses a leading minus before the dollar sign. Aggregate totals round their full sums, not the sum of already rounded display rows.
Reviewed Deal names use `policy.forecast.deck.name_character_cap`. Core Risk text uses `policy.forecast.deck.core_risk_character_cap`.
Other cells and each support line retain `policy.forecast.deck.cell_character_cap`. All caps include spaces and require single-line input without control characters.
Plan and verify enforce each column independently. These limits do not prove visual fit. Check the rendered thumbnail for wrapping.
Overlong text exits 1 naming the Opportunity or cell. Shorten it explicitly and rerun. Never silently truncate.
Fields whose current text already equals the new value send no request.

## Overflow

Core rows sort by amount descending, ties by Id. Backup normally lists sorted upside before sorted pull-ins.
If a section exceeds capacity, sort all its rows by amount descending, ties by Id, and fill the first capacity-minus-one rows.
The final row is `+N more` with the sum of every remaining amount. Its Stage and action cells are blank, never an invented common stage or risk.
The backup total covers all backup rows, including those summarized. Unused rows are blank. Never add rows, change fonts or resize the layout.
Readback is mechanical, not buyer-evidence review. The thumbnail is the visual check for wrapping.
