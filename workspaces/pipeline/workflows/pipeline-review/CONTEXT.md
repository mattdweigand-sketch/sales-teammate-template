---
cadence: daily
reads: _core/policy.yaml (salesforce, pipeline, tooling, forecast), _core/rules.md, references/, Salesforce, Gmail, Calendar, Slack
writes: Salesforce Opportunity and Task fields, on approval
next: forecast-weekly reads the corrected records on Friday; Closed Won routes to close
---

# Pipeline Review

Each weekday, flag deals in `policy.pipeline.stages` whose Salesforce record lags the evidence and propose the fix as clear recommendations and questions.
Friday adds the rollup, delta, lettered proposals, and one qualification pass over `policy.pipeline.early_stages`. Scheduled per `policy.pipeline.schedule` and `rules#scheduled_runs`.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `salesforce`, `pipeline`, `tooling` blocks | Values, scope, and the helper registry |
| Core policy | `_core/policy.yaml` | Weekday Top 3 only: `forecast.amount_field` | ARR ranking field |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#approval`, `rules#write_protocol`, `rules#scheduled_runs` | Run start, approval, and writes |
| Core rules | `_core/rules.md` | `rules#next_steps`, `rules#next_steps_format`, `rules#next_steps_review`, `rules#followup_task`, `rules#stage_move`, `rules#close_date_basis` | What a proposal may change |
| Core rules | `_core/rules.md` | `rules#calendar_search`, `rules#not_checked_means`, `rules#absence_conclusions` | Evidence limits |
| Core rules | `_core/rules.md` | `rules#pilot_handoff`, Friday only when Operator supplies a pilot report | Pilot report acceptance |
| Helper | `_core/scripts/interfaces.md` | "Interfaces", the `pipeline_render` row | Renders every output from the run file |
| Shared evidence | `_core/slack-evidence.md` | "Search", "Limits" at step 2 | Read-only Slack method and scoped gaps |
| Reference | `references/collect.md` | Full file, running the Friday or Other days branch of item 4 | Queries, searches, and helper runs |
| Reference | `references/triggers.md` | Full file | What flags a deal |
| Reference | `references/proposals.md` | "Every run", "Task review". Friday loads "Friday", "Friday qualification" and, with a supplied report, "Pilot report input". "Questions" in the walk, "Apply" after approval | Proposal scope |
| Reference | `references/report-format.md` | "Run file", "Top 3 actions today", "Approval boundary", "Next steps display", "Evidence", "Counts", "Coverage", "Friday additions" on Friday, "Notification" in scheduled runs | What the run file holds |
| Per-run evidence | Saved Salesforce, Gmail, Calendar, and Slack results in the sandbox | This run's window per `references/collect.md` | Deal state and activity |
| Per-run evidence | Pilot report pasted or linked in this thread | Fields named in `rules#pilot_handoff`, Friday only | Pilot facts for one Account |

## Process

1. Start per `rules#run_start`.
2. Collect per `references/collect.md`, using today's branch. Keep the original open count and the saved coverage JSON.
   Read Slack for every in-scope deal over `policy.tooling.slack_lookback_days` on both branches.
3. Flag deals per `references/triggers.md`.
   On Friday, review every early-stage deal per `references/proposals.md` "Friday qualification". No early-stage upward move is proposed.
4. Build clear recommendations and questions per `references/proposals.md` into the run file.
   Check the freshest dated Salesforce, Gmail, Calendar, and Slack evidence before drafting any proposal.
   On the weekday branch, rank evidence-backed deals needing Operator today per `references/report-format.md` "Top 3 actions today" using the existing reads.
   Post `policy.tooling.scripts.pipeline_render report` output unchanged as the final chat answer, for manual and scheduled runs.
5. Wait per `rules#approval`. Numbers or ranges for numbered clear recommendations, letters for lettered record proposals, `all` for every displayed numbered clear recommendation only, or `skip`.
   Each letter is one record per approval.
6. Apply only approved changes per `references/proposals.md` "Apply", then post the helper's receipt.
7. Walk each open question per `references/proposals.md` "Questions" with the helper's question mode, one at a time, applying and receipting a selected option before the next.
8. Close with the helper's `receipt --final`, which names each skipped, unanswered, deferred, or open item with its Account per `rules#approval`.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 4 | The report with numbered clear recommendations, Friday lettered record proposals, and listed questions | Which numbers, ranges, letters, `all`, or `skip` to apply |
| 7 | One question with its options and exact changes | One option label, `skip`, or an answer that becomes a new option |

## Audit

| Check | Pass Condition |
|---|---|
| Coverage, before step 4 output | The report renders from this run's saved `coverage_check` JSON. Exit 0, or the report reads `Coverage incomplete` and lists every affected deal as withheld |
| Render, before each output | `pipeline_render` exits 0. Its count, label, duplicate, and structure checks pass; output is posted unchanged |
| Evidence, before step 4 output | Every numbered or lettered proposal cites Salesforce, Gmail, Calendar, or Slack evidence, or on Friday an accepted pilot report. No write rests on an event-only activity or an unknown |
| Slack limits, before step 4 output | Missing Slack users or evidence alone add Coverage notes. Withhold only a buyer-status or commitment change when a verified user's search errored or was incomplete. Unrelated changes remain eligible |
| Tasks, before step 4 output | Each Task change passes `references/proposals.md` "Task review": same action, completion evidence, fresh candidates before a create |
| Pilot input, before step 4 output | A pilot report supports a proposal only on Friday after `rules#pilot_handoff` identity and field checks pass. Otherwise it is a question or held for Friday |
| Scope, before step 4 output | No proposal drafts or sends email, sets Closed Won, deletes or merges records, or changes OwnerId |
| Write verification, after steps 6 and 7 | Every record outcome is in the run file, no successful write repeats, and the `hygiene_check` rerun shows no MISSING or unresolved REVIEW next step and no `task_gap` on a written record |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Pipeline report | Run thread, final chat answer | `pipeline_render report` output |
| Questions | Run thread, one message each | `pipeline_render question` output |
| Salesforce updates | Opportunity and Task records, after approval only | The approved fields, read back per `rules#write_protocol` and checked by the step 6 and 7 audit. Forecast-weekly reads these verified records on Friday |
| Receipts and close | Run thread | `pipeline_render receipt` output, with `--final` at close |
| Notification | In-app, scheduled runs only | `pipeline_render notification` payload, sent unchanged when it says send |
| Run file and saved results | Sandbox | Run file, query results, and helper outputs, never Project Files |
