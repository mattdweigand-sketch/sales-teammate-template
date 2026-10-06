# Helper interfaces

What each helper in `policy.tooling.scripts` promises. Read the row for the helper a contract names, and the section that applies.
Each executable's docstring and `--help` give its arguments.
Resolve each helper from its path in `policy.tooling.scripts`. Workflow helpers live under their owning workspace and locate shared resources from the repository root.

## Interfaces

| Helper | Interface |
|---|---|
| `onboard` | setup validates one answer file and creates an absent separate destination. questions prints company schema. integrations prints every system interview. check reports routes, choices and pending live verification. |
| `rehearse` | --scratch takes an absent external directory. Configures demo, runs generic tests in a clean copy and all workflow scenarios with local doubles. No live connector calls. |
| `event_list_prep` | `<input.csv\|input.json> --as-of <local-offset timestamp> [--overrides <list-only.json>] [--output <sandbox.json>]`. Labels reviewed exclusions, enrichment candidates, Apollo identity holds, and catch-all sources. No network or customer writes, never authorizes enrollment. |
| `event_scrub_leads` | `scrub <eligible.csv> --output-dir <fresh-dir> --clean-column-profile full`, then `audit-clean-output <clean_chunks> --report <audit.json>`. Both reports must PASS. Retain Website for batch checks. Uses adjacent email_rules.json. |
| `event_make_batches` | `<clean_chunks> --code <event-code> --output-dir <fresh-dir> [--allow <approved-emails.txt>]`. Review counts and domain_mismatch.csv. Missing fields and domain mismatches remain held. Batches never authorize real sends. |
| `hygiene_check` | Reads Opportunity, Task, and Event results. Rejects wrong or unknown object types. Emits triggers, blank fields, next-step dates, activity receipts, Task and milestone candidates per `policy.pipeline` and `rules#followup_task`. Legacy `Next:` is REVIEW. |
| `coverage_check` | Checks saved Salesforce, Gmail, and Calendar calls for `--scope pipeline-daily`, `pipeline`, or `forecast` over the `--since` window. Incomplete, errored, capped, or unrelated-Account results do not count. Exit 1 means gaps. `--json` adds readiness, receipts, `affected`. |
| `coverage_check`, affected | In-scope Opportunity Ids whose proposals must be withheld. A gap tied to named deals affects those deals. Any other gap affects the whole scope. Null when the check failed. |
| `coverage_check`, Calendar | Uncapped windows covering a term's full range supersede capped or incomplete calls. Reports corroboration per `rules#calendar_search`. An uncorroborated Event owned by the deal owner fails coverage. |
| `forecast_notify` | Runs forecast coverage. Takes `--process-status ready\|incomplete\|review-needed`, `--summary`, `--thread-url`, and `--schedule`. Prints the payload. A ready title needs complete coverage and a ready report. Send unchanged only in an authorized scheduled run. |
| `forecast_notify`, tracking | `--tracking-input` validates tracking math and `reads_complete`. Emits `notify` and `payload`. Only complete, ready, unchanged baseline runs are silent. Tracking does not require Gmail/Calendar coverage. Send the returned payload unchanged. |
| `pipeline_render` | Modes `report`, `question`, `receipt` (`--final` adds the close), and `notification`. Reads run, coverage and saved results (`--sources`). Validates labels, counts, routed ownership, scope, writes and evidence. Exit 1 prints errors only. Incomplete coverage cannot be ready. |
| `pipeline_render`, evidence | Gmail and Calendar evidence IDs must resolve to saved records, which supply date, title, and link. Gmail quotes must match the saved body. Every `affected` flagged deal must be withheld. |
| `forecast_math` | `--input` takes reviewed forecast rows with optional next-quarter preview, or `--tracking` takes dated records and a prior snapshot. Decimal totals, preview, or quarter/year pace, coverage, concentration, and alerts. Reads `policy.forecast` with optional `--policy`. |
| `gmail_digest` | Prints saved Gmail results newest first with ids, cut bodies marked `[truncated, N more chars]`, and attachment names. An index for choosing what to read in full, not the evidence. |
| `gmail_contact_stats` | Prints per-address sent and inbound dates, inbound type, unanswered count, and newest non-bounce thread from saved Gmail results. `--only` takes addresses. `--as-of` needs the local offset. Counts are retrieved-set measurements (`rules#absence_conclusions`). |
| `gmail_contact_stats --slack-replies <reviewed.json>` | Adds last substantive Slack reply and `slack_reply_blocks_auto_move`. Receipts follow `_core/slack-evidence.md` "Reply receipts". A positive veto blocks a move. No veto proves no absence or approval. |
| `closeout_check` | Reads the fresh closeout Task query with `--as-of` and its local offset. Complete empty results pass. Errors, incomplete results, and open due-today, overdue, or undated Tasks fail. |
| `pilot_usage_build` | `window` derives the pilot start from grants before task SQL. `build` binds three statement handles to org and window, then assembles, computes, renders, and prints, replacing the PDF only after it verifies. Command in the pilot-usage contract. |
| `pilot_resolve` | `--input`, `--owner-id`, `--as-of`, and one of `--opportunity-id`, `--account-id`, `--account-name`. Resolves exactly one eligible pilot and matching org from saved records. Exit 2 on ambiguity or invalid identity. |
| `account_usage` | `--input` takes Account, org_uuid, data_through, roster rows, and optional billed_seats. Returns matched org and distinct roster, active, and last-seven-day counts. No writes or sales decision. |
| `customer_review` | `--input`, `--as-of`; scheduled `--window-start`, `--carry-forward`/`--reviewed` lists; on-demand `--account-id`/`--account-name`, optional `--milestone-months`; `--policy`. Milestones, independent notices, Pipeline open-deal actions. No writes or past-dated Tasks. |
| `prospect_common` | Loads Prospecting policy and shared signals. Supplies Markdown parsing, the policy clock and exit-2 error envelope. Outreach owns its private talk-track loader. |
| `prospect_evidence_gate` | Checks a receipt against fetched source text, attribution and dated qualification. Emits the live bundle schema or named rejection. Exit 2 is unusable input. |
| `prospect_account_route` | Requires a complete current Account read. Routes Operator-owned Accounts to scan, open deals to Pipeline, and other or absent Accounts out of Prospecting. Never claims Accounts. |
| `prospect_privacy_check` | Checks the exact adoption bundle schema, booleans and permitted claim. Rejects extra keys, email addresses and activity timestamps. |
| `prospect_readback_check` | Compares every approved field with native readback. Gmail mode rejects added To, CC or BCC recipients. Missing fields and type changes fail. |
| `prospect_scan_verdict` | Selects the newest qualified tier1, else tier2. Takes current --route. Qualified evidence cannot recommend Outreach for blocked or unresolved ownership. |
| `prospect_outreach_gate` | Requires a current Operator-owned Account without an open deal. Binds its domain and adoption ID to the bundle, then checks freshness, recipient, activity, suppression and draft claims. Allow is never approval. |
| `prospect_followup_gate` | Requires one proven native send, one matching Contact, owned Account and completed Task reads. Emits a duplicate-free Task with the canonical note prefix and calendar-day due date. |
| `prospect_adoption_lookup` | Research Adoption read-only account SQL. Header defines bindings and fixed privacy-safe fields. Native success precedes the exact checked bundle. |

## Running

Python 3.12 or later is required. CI tests Python 3.12 with PyYAML and pypdf per `.github/workflows/tests.yml`.
This is the full maintenance environment. A helper needs only the packages it actually imports, not every maintenance dependency.
Prepare an environment outside the repository and check its version and imports before execution.

```bash
python3.12 -m venv /tmp/sales-maintenance-venv
/tmp/sales-maintenance-venv/bin/python -m pip install PyYAML pypdf
/tmp/sales-maintenance-venv/bin/python --version
/tmp/sales-maintenance-venv/bin/python -c 'import yaml, pypdf'
source /tmp/sales-maintenance-venv/bin/activate
```

`policy.tooling.scripts.<key> <args>` means run the registered path, resolved in the checkout, with the prepared Python from the working directory this section names for that helper.
Resolve SQL keys through the registry too, then run their unchanged bindings through the named read-only connector, not Python.
Missing Python or packages is a prerequisite gap, not a repository defect. Report the unavailable prerequisite before running.
Use saved connector results for the current run.
Coverage and forecast notification run from the sandbox root. Pilot commands run from the checkout with explicit sandbox input/output paths, as the pilot-usage contract shows.
Pipeline rendering with its default `--sources` also runs from the sandbox root.
Other helpers take explicit saved-file paths. Keep inputs, review JSON, and outputs outside Project Files.

## Saved results

Saved calls use `~/.perplexity/sessions/<session-id>/tool_calls/call_external_tool`. Explicit `--calls-dir`, `--sources` or `--tool-calls` wins. Multiple sessions require an explicit path.
`_saved_json.py` handles supported core saved-result wrappers. Pass all Gmail pages together to digest/stats and retain their original paired `input_` files for cursor verification.
Pilot statement binding lives with the pilot helpers. Outputs can contain customer data. The digest prints message text, hygiene prints CRM fields, and pilot outputs include names and task
labels.
Do not publish saved inputs or diagnostic outputs as source.

## Timestamps

Run-start timestamp handling per `rules#run_start`. Query Event `StartDateTime` and `EndDateTime`. Date-only Events have unknown timing. An elapsed Event is not proof of attendance.
Every helper that takes a moment takes `--as-of` or `--since` with the local offset.

## Pilot PDF

Pilot PDF page count, size, font checksums, and category cap come from `policy.pilot_usage.pdf`. Printing uses headless Chromium and replaces the PDF only after validation.
Output paths inside Project Files are rejected.
Query submissions and polling remain in the pilot-usage contract. The local build entrypoint does not call connectors.
