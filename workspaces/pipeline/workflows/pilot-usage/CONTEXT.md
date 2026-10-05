---
cadence: one-off
reads: _core/policy.yaml (salesforce, tooling, pilot_usage), _core/rules.md, references/, Salesforce, Snowflake
writes: nothing; PDF mode writes to the sandbox only
next: none directly; a report reaches Salesforce only per rules#pilot_handoff, through the Friday pipeline-review or a call logged by interaction-sync
---

# Pilot Usage

Answer one question for one pilot: is it being used, by whom, for what. Read-only per `rules#read_only_skills`. Salesforce names the pilot; the warehouse supplies the numbers.
Run only when requested. There is no recurring pilot health check.
Mode `report` (default) prints in chat. Mode `pdf` builds the customer deliverable when the request says pdf, deliverable, customer report, or send to the customer.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `salesforce`, `tooling`, `pilot_usage` blocks | Warehouse, windows, PDF limits, and the helper registry |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#read_only_skills`, `rules#pilot_handoff` | Run start, no writes, and what the report must carry |
| Reference | `references/resolve.md` | "Resolve the pilot" at step 2; "Pull" at step 3 | Pilot identity and query execution |
| Core queries | `workspaces/pipeline/references/pilot-usage-queries.md` | Report mode, sections 1, 1b, 2, 3 | Report query bodies |
| Core queries | `workspaces/pipeline/references/pilot-usage-queries.md` | PDF mode, sections 1, 4, 5 | PDF query bodies |
| Reference | `references/report-format.md` | Full file, report mode at step 4 | The chat report |
| Reference | `references/pdf-format.md` | Full file, PDF mode at steps 3 to 7 | Review file, build commands, and page checks |
| Per-run evidence | Salesforce results and warehouse submit handles and results saved in the sandbox | This pilot, org, and window | The numbers |

## Process

1. Start per `rules#run_start`.
2. Resolve one pilot and its org id per `references/resolve.md` "Resolve the pilot". An explicit Opportunity Id selects that pilot, including an unexpired paid Closed Won trial.
3. Resolve `data_through` and submit the mode's queries per `references/resolve.md` "Pull". In PDF mode this runs the build helper's `window` action before query 5.
4. Report mode: print the report per `references/report-format.md`.
   Cluster the `policy.pilot_usage.use_case_sample` most recent queries into at most `policy.pilot_usage.use_case_themes_max` themes,
   stating the day span and user count, per the query 3 notes in `workspaces/pipeline/references/pilot-usage-queries.md`.
   Then go to step 8.
5. PDF mode: pull Salesforce Contacts on the Account for display names. A seat with no Contact keeps the email local part.
6. PDF mode: draft the review file per `references/pdf-format.md` into `policy.pilot_usage.pdf.output_dir`, show the drafts in chat, numbered, and wait.
   Categories, task categories, display names, participation notes, and every narrative are your drafts from the task titles and rows. Set `approved: true` only after approval.
   Apply corrections to the file, not to the scripts.
7. PDF mode: run `policy.tooling.scripts.pilot_usage_build build` with the exact three submit handles and flags in `references/pdf-format.md`.
   Stop on any non-zero exit or `"valid": false`, reporting it verbatim. Render both pages to images, inspect them, then share the PDF in the thread.
8. Close in one line: pilot reported, mode, and `Nothing written`.
   In PDF mode add credits used of granted, the PDF path, org id, and window, or `PDF drafts not approved, review file at <path>` when the build did not run.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 6 | Numbered drafts of categories, task categories, display names, participation notes, and narratives | Approve or correct the drafts before the build runs |

## Audit

| Check | Pass Condition |
|---|---|
| Identity, before step 3 | Exactly one pilot and one org id. Differing `Admin_Organization_UUID__c` and `Org_UUID__c` stop the run with both shown; none set stops with `org id missing in Salesforce`; no org is guessed by name |
| Results, before step 4 or 7 | Every selected submit handle reached a terminal result with every partition fetched. No other handle is substituted |
| Handoff fields, before step 4 or 8 output | The report or close line carries the source, org id, window, and limits `rules#pilot_handoff` needs |
| PDF build, before sharing | The build exits 0 with `"valid": true`, and both page images show no clipped or overlapping text |
| Scope, throughout | No email or outreach drafted. No SQL, and no query string over `policy.pilot_usage.query_text_max_chars` characters, printed anywhere including the PDF. Nothing enters Project Files |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Usage report | Run thread | `references/report-format.md` block for Operator. A supplied report reaches Friday pipeline-review or interaction-sync only per `rules#pilot_handoff` |
| Review file | `policy.pilot_usage.pdf.output_dir` in the sandbox | JSON per `references/pdf-format.md` "Review file", PDF mode |
| Customer PDF | `policy.pilot_usage.pdf.output_dir`, shared in the thread | Two pages per `policy.pilot_usage.pdf`, built after the step 6 review for Operator to share. Any Salesforce handoff follows `rules#pilot_handoff` |
| Close line | Run thread | One line per step 8 |
| Saved results | Sandbox | Query results and helper outputs, never Project Files |
