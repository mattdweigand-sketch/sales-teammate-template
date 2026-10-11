# Helper interfaces
What each helper in `policy.tooling.scripts` promises. Read the row for the helper a contract names, and the section that applies.
Each executable's docstring and `--help` give its arguments.
Resolve each helper from its path in `policy.tooling.scripts`. Workflow helpers live under their owning workspace and locate shared resources from the repository root.

## Interfaces
| Helper | Interface |
|---|---|
| `workflow_revision_check` | `--repo` checkout, `--scope` sandbox JSON, `--phase snapshot\|prewrite`, `--baseline` saved snapshot result. Fetches main and compares selected Git/local/index sources. Unchanged, changed or needs-input. See "Workflow revisions". No write authority. |
| `event_launch_check` | `--input <sandbox.json> [--output <sandbox.json>]`. Inputs include approved, recheck, native_contacts, native_sequence and payload. Payload keys are the operation's only. `id` and `emailer_campaign_id` bind to the campaign. Wrapper or inner failure markers STOP. No writes. |
| `onboard` | setup validates one answer file and creates an absent separate destination. questions prints company schema. integrations prints every system interview. check reports routes, choices and pending live verification. |
| `rehearse` | --scratch takes an absent external directory. Configures demo, runs generic tests in a clean copy and all workflow scenarios with local doubles. No live connector calls. |
| `event_list_prep` | `<input> --as-of <offset timestamp> [--overrides <list.json>] [--outreach-owner-column <col> --outreach-owner-value <v>] [--output <out.json>]`. Owner flags together or neither. Labels exclusions, enrichment candidates and Apollo holds. Never authorizes enrollment |
| `event_scrub_leads` | `scrub <eligible.csv> --output-dir <fresh-dir> --clean-column-profile full`, then `audit-clean-output <clean_chunks> --report <audit.json>`. Both reports must PASS. Retain Website for batch checks. Uses adjacent email_rules.json. |
| `event_make_batches` | `<clean_chunks> --code <event-code> --output-dir <fresh-dir> [--allow <approved-emails.txt>]`. Missing names or email are dropped and counted. Domain mismatches are held unless allowed. Missing Website is reported not checked. Never authorizes sends. |
| `hygiene_check` | Reads Opportunity, Task, and Event results. Rejects wrong or unknown object types. Emits triggers, blank fields, next-step dates, activity receipts, Task and milestone candidates per `policy.pipeline` and `rules#followup_task`. Legacy `Next:` is REVIEW. |
| `coverage_check` | Checks saved calls over `--since`. Pipeline defaults to all open stages, including S0 and S1. Forecast uses `policy.forecast.open_min_stage`. Incomplete, errored, capped, unrelated or narrowed Task and Event results fail. Exit 1 means gaps. `--json` adds `affected`. |
| `coverage_check`, affected | In-scope Opportunity Ids whose proposals must be withheld. A gap tied to named deals affects those deals. Any other gap affects the whole scope. Null when the check failed. |
| `coverage_check`, Calendar | Defined terms need the full window. Supplemental Subject/date searches only corroborate Events. Capped searches need uncapped splits over their queried range. Split boundaries must meet. An uncorroborated owner Event fails coverage. |
| `forecast_notify` | Runs forecast coverage. Takes `--process-status ready\|incomplete\|review-needed`, `--summary`, `--thread-url`, `--schedule`. `--since` required for weekly, ignored for tracking. A ready title needs complete coverage and a ready report. Send unchanged in scheduled runs. |
| `forecast_notify`, tracking | `--tracking-input` builds summary lines from tracking math and validates `reads_complete`. Ignores `--summary`, `--since` not required. Lists `unavailable_prior` Ids. Emits `notify` and `payload`. Only complete, ready, unchanged runs are silent. Send unchanged. |
| `pipeline_render` | Modes `report`, `question`, `receipt` (`--final` adds the close), and `notification`. Reads the run file, coverage JSON, and saved results (`--sources`). Validates labels, counts, scope, writes, and evidence. Exit 1 prints errors only. Never renders incomplete coverage ready. |
| `pipeline_render`, evidence | Gmail and Calendar evidence IDs must resolve to saved records, which supply date, title, and link. Gmail quotes must match the saved body. Every `affected` flagged deal must be withheld. |
| `pipeline_render`, delivery | Routed rows require `delivery.command` (`mail_send` only, the retired `session_send` is rejected) and `delivery.status` (`delivered` or `failed`). Shows the command. Failed sends appear under needs-input and never suppress notifications. |
| `pipeline_render`, writes | Weekly scope only. Rejects next-step and Task changes, Closed Won, and early-stage upward moves in every mode. Blank-field blocks only. Stage letters accept reviewed `lost_path_size`. Description letters only prepend the dated `operator_size_exception` marker. |
| `top_actions` | `--input` reviewed triage JSON, `--sources` saved calls. Ranks existing evidence only, dedupes by deal, returns Top 3 unchanged. Schema and ranking live in its docstring. Missing read status or an empty affected scope withholds ranking. Reason punctuation only warns. No writes. |
| `deal_thread_match` | `--input` JSON with raw offset-bound `pages`, `limit`, `project_uuid`, `accounts` and `account_searches` for every Account. Exact normalized ownership. See "Account session search". Listing shape gaps hold all. Search gaps hold one. |
| `task_reschedule_check` | `--input` JSON, `--phase proposal\|prewrite`, `--as-of` run start with offset, `--note-prefix` policy value. Native snapshots and reviewed IDs per "Task reschedule input". Only ready has a date/note payload. Offline, not approval or an atomic lock. |
| `forecast_math` | `--input` reviewed forecast rows, or `--tracking` records and prior snapshot. `policy.forecast.open_min_stage` gates open totals. A failed delay or blocker predicate holds the row, `status` incomplete. `operator_call` overrides one named predicate. Optional `--policy`. |
| `forecast_deck` | `plan` takes `--presentation`, `--forecast`, `--reviewed`, `--input`, `--coverage`, optional `--approved`, `--policy`. Prints D, `operator_calls` and batchUpdate. `verify` takes `--plan`, `--before`, `--after`, optional `--policy`. Exit 1 on a held row, mismatch or long cells. |
| `gmail_digest` | Prints saved Gmail results newest first with ids, cut bodies marked `[truncated, N more chars]`, and attachment names. An index for choosing what to read in full, not the evidence. |
| `gmail_contact_stats` | Non-draft counts, dates, inbound type and newest non-bounce thread. `--only` selects addresses, `--as-of` needs an offset. `--send-hold` adds aware sent time and active/cold holds from policy.followup. UTC 24-hour periods, equality released. Retrieved-set limits apply. |
| `gmail_contact_stats --slack-replies <reviewed.json>` | Adds last substantive Slack reply and `slack_reply_blocks_auto_move`. Receipts follow `_core/slack-evidence.md` "Reply receipts". A positive veto blocks a move. No veto proves no absence or approval. |
| `closeout_check` | Reads the fresh closeout Task query with `--as-of` and its local offset. Complete empty results pass. Errors, incomplete results, and open due-today, overdue, or undated Tasks fail. |
| `pilot_usage_build` | `window` derives the pilot start from grants before task SQL. `build` binds three statement handles to org and window, then assembles, computes, renders, and prints, replacing the PDF only after it verifies. Command in the pilot-usage contract. |
| `pilot_resolve` | `--input`, `--owner-id`, `--as-of`, and one of `--opportunity-id`, `--account-id`, `--account-name`. Resolves exactly one eligible pilot and matching org from saved records. Exit 2 on ambiguity or invalid identity. |
| `account_usage` | `--input` takes Account, org_uuid, data_through, roster rows, and optional billed_seats. Returns matched org and distinct roster, active, and last-seven-day counts. No writes or sales decision. |
| `customer_review` | `--input`, `--as-of`; scheduled `--window-start`, `--carry-forward`/`--reviewed` lists; on-demand `--account-id`/`--account-name`, optional `--milestone-months`; `--policy`. Milestones and Pipeline open-deal actions. Ignores legacy renewal entries. No writes. |
| `prospect_common` | Loads Prospecting policy and shared signals. Supplies Markdown parsing, the policy clock and exit-2 error envelope. Outreach owns its private talk-track loader. |
| `prospect_evidence_gate` | Checks a receipt against fetched source text, attribution and dated qualification. Emits the live bundle schema or named rejection. Exit 2 is unusable input. |
| `prospect_account_route` | Requires a complete current Account read. Routes Operator-owned Accounts to scan, open deals to Pipeline, and other or absent Accounts out of Prospecting. Never claims Accounts. |
| `prospect_privacy_check` | Checks the exact adoption bundle schema, booleans and permitted claim. Rejects extra keys, email addresses and activity timestamps. |
| `prospect_readback_check` | Compares every approved field with native readback. Gmail mode rejects added To, CC or BCC recipients. Missing fields and type changes fail. |
| `prospect_scan_verdict` | Selects the newest qualified tier1, else tier2. Takes current --route. Qualified evidence cannot recommend Outreach for blocked or unresolved ownership. |
| `prospect_outreach_gate` | Requires a current Operator-owned Account without an open deal. Binds its domain and adoption ID to the bundle, then checks freshness, recipient, activity, suppression and draft claims. Allow is never approval. |
| `prospect_followup_gate` | Requires one proven native send, one matching Contact, owned Account, completed Task reads and a complete open Opportunity read. Any open Opportunity blocks. Emits a duplicate-free Task with the canonical note prefix and calendar-day due date. |
| `prospect_adoption_lookup` | Research Adoption read-only account SQL. Header defines bindings and fixed privacy-safe fields. Native success precedes the exact checked bundle. |

## Account session search
For every Account, call the `session_list` tool with type `computer`, search `"<account_name> deal"` and limit `100`. Save its unchanged raw JSON in `account_searches`, keyed by account_id.
The response is `{"sessions": [...]}`. Legacy saved raw lists remain accepted. Unknown response shapes hold that Account.
An empty sessions list is checked negative evidence. Null means unavailable or failed. Missing, malformed or at-limit (100+) searches hold only that Account, never establish local ownership.
Candidates need exact normalized `<Account> deal` titles, matching project.uuid and valid URLs. Merge both sources by context_uuid. Ambiguity and Account-name collisions still hold.
Ignore nonmatching titles and sessions with project null. Candidate-title sessions with malformed fields, project metadata or URLs hold that Account.
So does a row with no readable title or a multi-line title that could be this Account's candidate. Multi-line titles proved unrelated to every reviewed Account are ignored.
Search even listed owners. A short project page proves neither absence nor uniqueness. Save unchanged evidence in the sandbox. The helper makes no live calls.
## Task reschedule input
Save the exact native Task and Account records, plus the Opportunity with its AccountId when linked. Include Task type, Id, OwnerId, Subject, Status, IsClosed, ActivityDate, LastModifiedDate, WhatId,
WhoId and Description. Null Description is valid and stays null in the baseline. Read all related open Tasks on both WhatIds, including future Tasks, without adding them to triage's queue.
Supply unchanged `salesforce_rest_api-soql-query` results with records, totalSize and hasMore explicitly false, plus the unchanged requested SOQL for each result. Do not invent a done field.
Related queries select every baseline field with only WhatId and IsClosed=false filters. Never use LIMIT, OFFSET or queue-date filters. Optional ORDER BY and either predicate order are supported.
Incomplete or unsupported results stay needs-input. For Account-only Tasks use explicit null Opportunity, related_opportunity and related_opportunity_soql. No wrapper is unwrapped by this helper.
Review current-action IDs against those records and buyer evidence. Same date or Account alone is not equivalence. A replacement must be the single verified current-action ID, not an invented flag.

```json
{
  "writer": "triage",
  "task": {
    "attributes": {"type": "Task"}, "Id": "00T000000000001", "OwnerId": "005000000000001",
    "Subject": "Confirm pilot review", "Status": "Not Started", "IsClosed": false,
    "ActivityDate": "2026-10-06", "LastModifiedDate": "2026-10-07T02:06:31.000+0000",
    "WhatId": "006000000000001", "WhoId": null, "Description": null
  },
  "account": {"attributes": {"type": "Account"}, "Id": "001000000000001"},
  "opportunity": {"attributes": {"type": "Opportunity"}, "Id": "006000000000001", "AccountId": "001000000000001"},
  "related_account": {"records": [], "totalSize": 0, "hasMore": false},
  "related_opportunity": {"records": [{
    "attributes": {"type": "Task"}, "Id": "00T000000000001", "OwnerId": "005000000000001",
    "Subject": "Confirm pilot review", "Status": "Not Started", "IsClosed": false,
    "ActivityDate": "2026-10-06", "LastModifiedDate": "2026-10-07T02:06:31.000+0000",
    "WhatId": "006000000000001", "WhoId": null, "Description": null
  }], "totalSize": 1, "hasMore": false},
  "related_account_soql": "SELECT Id, OwnerId, Subject, Status, IsClosed, ActivityDate, LastModifiedDate, WhatId, WhoId, Description FROM Task WHERE WhatId = '001000000000001' AND IsClosed = false",
  "related_opportunity_soql": "SELECT Id, OwnerId, Subject, Status, IsClosed, ActivityDate, LastModifiedDate, WhatId, WhoId, Description FROM Task WHERE WhatId = '006000000000001' AND IsClosed = false",
  "current_action_task_ids": ["00T000000000001"],
  "desired_date": "2026-10-09", "note_line": "10/7/26 SR - Buyer requested Friday pilot review"
}
```

Interaction-sync and other permitted writers use writer=deal_thread, not authority. Scheduled triage keeps writer=triage without manual_one_deal and excludes future Tasks.
Manual triage keeps writer=triage and adds manual_one_deal with task_id, opportunity_id, command_text, command_url and source_kind=operator_typed_command. Only its current-action Task may be future.
Save returned manual_one_deal as baseline_manual_one_deal for prewrite. Identity, complete native reads, stale baseline and payload checks remain. Changed command provenance fails closed.
Run proposal before display. Save its ready baseline, baseline_links and payload with the exact proposal.
After the contract's approval, read the native records and queries again and review action IDs.
Run prewrite with those fresh inputs, saved baseline and baseline_links, and displayed_payload set to the original payload. Keep the original desired_date, note_line, run start and prefix.
Only ready may write its unchanged payload. No-op, stale and needs-input contain no payload. Stale requires a new proposal and approval. Never reuse ready output as a later freshness check.
Ready checks mechanics, not approval or source truth. OwnerId must be readable and unchanged. The caller checks ownership permission. Intent, equivalent actions and unseen Tasks remain unverified.
Save actual native hasMore, counts and records, paired with the query requested. A capped query's hasMore=false is not complete coverage. Model-made reads_complete flags are not evidence.
Read Id, ActivityDate and Description back natively after writing. A failed handoff grants no substantive ownership.
A failed or unverified write stays pending and needs fresh reads before a retry proposal.
Neither native update schema supports a conditional version argument. The final read and write are not atomic. A concurrent save in that interval can still be overwritten.

## Workflow revisions

The format-2 snapshot binds repository identity, remote and branch. Missing or changed targets and format-1 evidence hold the affected write.
Onboarding copies are Git-less. Publish actual configured bytes in an adopter-owned Git deployment before affected writes. Never use the source or unconfigured template remote.
Read-only branches and internal Slack drafts need no Git gate. Local `fixture:` remotes require demo mode and prove only local mechanics.

Before a write proposal, record the active execution contract or Pipeline deal-thread entry and every actually consumed governing source, including used helper bytes, imports and resources.
Select only the entered stage and chosen branch. Pure read-only branches need no check. Never preload siblings or widen policy scopes.
Source selection is the caller's responsibility, not inferred by this tool.
Each invocation fetches `policy.tooling.governing_revision` using configured Git access, then computes scoped Git objects and actual worktree/index content.
It never resets, stashes, checks out, discards or stages work.
Save this manifest and snapshot output with the displayed proposal in the sandbox, never Git or CRM. Do not use memory, message delivery or a model freshness flag as evidence.

```json
{"contract": "workspaces/pipeline/workflows/task-triage-speed-run/CONTEXT.md", "sources": [{"path": "_core/rules.md", "kind": "rule", "selector": "task_date_coordination"}, {"path": "_core/policy.yaml", "kind": "policy", "selector": "salesforce.note_prefix"}, {"path": "workspaces/pipeline/workflows/task-triage-speed-run/references/writes.md", "kind": "section", "selector": "Writes"}, {"path": "workspaces/pipeline/scripts/task_reschedule_check.py", "kind": "file"}]}
```

This is a selection example, not a complete scope for every triage proposal. Include all other sources actually governing the selected action, not the whole repo.
The helper always adds the actual full contract or Pipeline entry, write_protocol, approval, repo_currency, its registry key, interface row/section and executable bytes.
Workflow/stage manifests use `contract`. Deal threads instead use `deal_thread_entry` with `workspaces/pipeline/AGENTS.md` and their actual sources, never an invented workflow or sibling preload.

```json
{
  "deal_thread_entry": "workspaces/pipeline/AGENTS.md",
  "sources": [
    {"path": "_core/rules.md", "kind": "rule", "selector": "task_date_coordination"},
    {"path": "_core/policy.yaml", "kind": "policy", "selector": "salesforce.note_prefix"},
    {"path": "workspaces/pipeline/scripts/task_reschedule_check.py", "kind": "file"}
  ]
}
```

This deal-thread selection example also needs every other actually governing source. Prewrite cannot switch entry types or replace either saved scope.
Other selectors are file bytes, one Markdown section including children, one rule anchor, one policy key/block, or one uniquely named table row. Policy comparisons use parsed selected values.
Canonical rules and policy require scoped anchors or keys, never whole-file or section selectors.

```sh
python _core/scripts/workflow_revision_check.py --repo <checkout> \
  --scope <sandbox/scope.json> --phase snapshot > <sandbox/baseline.json>
python _core/scripts/workflow_revision_check.py --repo <checkout> \
  --scope <same sandbox/scope.json> --phase prewrite --baseline <sandbox/baseline.json>
```

Run snapshot before display and prewrite immediately before each approved write. Prewrite cannot substitute the saved scope. It validates saved fingerprints against historical Git objects too.
For staged E enrollment, Plan snapshots only its consumed sources before display. Launch rechecks that identical Plan baseline, then snapshots its own current applicable sources at entry.
Immediately before each Launch write, recheck both unchanged scopes. Keep both baselines with the existing exact E approval. No sibling preload or new approval grammar is added.
This proves Plan continuity plus current Launch sources and continuity since Launch entry, not unchanged Launch instructions since E display. Failed current authority or payload checks still stop.
Relevant main, worktree or index changes stop the old proposal. Reread changed instructions and present a current proposal with fresh approval.
Unrelated commits, keys or sections do not invalidate it.
Missing baseline/source, invalid scope, failed fetch or inconsistent evidence is needs-input. A legacy proposal cannot invent a historical snapshot, refresh and present a current proposal instead.
Git failures report a bounded error category and exit code, not raw stderr, credentials or URL userinfo. Unrecognized errors stay unclassified and fail closed, without retries or alternate transports.
If the current checkout is stale or contains relevant user edits, stop. Use a clean temporary worktree at fresh main and reread selected instructions.
Do not discard the original staged or unrelated work.
Unchanged exits 0, other outcomes exit 1. No result authorizes a native write or weakens existing approval, duplicate, stale-record, history, readback or automatic-move gates.
The tool cannot prove actual model reads, authenticate approval, force native-boundary invocation or lock a later main change.
Scope completeness remains a reviewed run responsibility.

## Running

Python 3.12 or later is required. The full test run needs PyYAML and pypdf.
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
