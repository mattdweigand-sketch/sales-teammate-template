---
cadence: weekly
reads: _core/policy.yaml (salesforce, pipeline, tooling, forecast), _core/rules.md, references/, Salesforce, Gmail, Calendar, Slack
writes: Salesforce Opportunity fields, on approval
next: forecast-weekly reads the corrected records on Friday; Closed Won routes to close
---

# Pipeline Review

Each weekly or requested run flags deals in `policy.pipeline.stages`, proposes blank-field fixes and leaves next-step or Task findings read-only for triage.
Every run includes the rollup, delta, lettered proposals and one qualification pass over `policy.pipeline.early_stages`. Scheduled per `policy.pipeline.schedule` and `rules#scheduled_runs`.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core freshness | `_core/rules.md`, `_core/scripts/interfaces.md` | `rules#repo_currency`, `workflow_revision_check`, "Workflow revisions" | Scoped proposal and prewrite evidence |
| Core policy | `_core/policy.yaml` | `salesforce`, `pipeline`, `tooling`, `forecast` blocks | Values, scope, and the helper registry |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#approval`, `rules#write_protocol`, `rules#note_prefix`, `rules#scheduled_runs`, `rules#task_date_coordination` | Run start, approval, and writes |
| Core rules | `_core/rules.md` | `rules#next_steps`, `rules#next_steps_format`, `rules#next_steps_review`, `rules#followup_task`, `rules#stage_move`, `rules#close_date_basis` | What a proposal may change |
| Core rules | `_core/rules.md` | `rules#calendar_search`, `rules#not_checked_means`, `rules#absence_conclusions`, `rules#handoff_delivery` | Evidence limits |
| Core rules | `_core/rules.md` | `rules#pilot_handoff`, Friday only when Operator supplies a pilot report | Pilot report acceptance |
| Helper | `_core/scripts/interfaces.md` | "Interfaces", `pipeline_render` and writes rows | Renders every output and rejects Task and next-step writes |
| Helper | `_core/scripts/interfaces.md` | "Interfaces", `deal_thread_match`, "Account session search", and `pipeline_render`, delivery rows | Verified ownership, per-Account searches and routing transport |
| Helper | `_core/scripts/interfaces.md` | "Interfaces", `hygiene_check` and `coverage_check` rows | Native findings and saved evidence readiness |
| Shared evidence | `_core/slack-evidence.md` | "Search", "Limits" at step 2 | Read-only Slack method and scoped gaps |
| Reference | `references/collect.md` | Full file, every weekly or requested run | Queries, searches, and helper runs |
| Reference | `workspaces/pipeline/references/triggers.md` | Full file | What flags a deal |
| Reference | `references/proposals.md` | "Every run", "Friday", "Friday qualification" for every weekly or requested run. "Questions" in the walk, "Apply" after approval. "Pilot report input" Friday only, when supplied | Proposal scope |
| Reference | `references/report-format.md` | "Run file", "Routed to deal threads", "Triage findings", "Approval boundary", "Next steps display", "Evidence", "Counts", "Coverage", "Friday additions", "Notification" in scheduled runs | What the run file holds |
| Shared reads | `workspaces/pipeline/references/deal-activity-reads.md` | "Opportunities", "Activity", "Account-domain Gmail" at step 2 | Native fields and reviewed domain threads |
| Per-run evidence | Saved Salesforce, Gmail, Calendar, and Slack results in the sandbox. Project pages and Account session searches in the sandbox | This run's window per `references/collect.md` | Deal state, activity and positive ownership evidence |
| Per-run evidence | Pilot report pasted or linked in this thread | Fields named in `rules#pilot_handoff`, Friday only | Pilot facts for one Account |

## Process

1. Start per `rules#run_start`.
2. Collect per `references/collect.md`, using the weekly scope on any requested date. Keep the original open count and the saved coverage JSON.
   Read Slack for every in-scope deal over `policy.tooling.slack_lookback_days` on every run.
3. Flag deals per `workspaces/pipeline/references/triggers.md`.
   Review every early-stage deal per `references/proposals.md` "Friday qualification". No early-stage upward move is proposed.
4. Build clear recommendations and questions per `references/proposals.md` into the run file.
   Check the freshest dated Salesforce, Gmail, Calendar, and Slack evidence before drafting any proposal.
   Post `policy.tooling.scripts.pipeline_render report` output unchanged as the final chat answer, for manual and scheduled runs.
5. Wait per `rules#approval`. Numbers or ranges for numbered clear recommendations, letters for lettered record proposals, `all` for every displayed numbered clear recommendation only, or `skip`.
   Each letter is one record per approval.
6. Apply only approved changes per `references/proposals.md` "Apply", then post the helper's receipt.
7. Walk each open question per `references/proposals.md` "Questions" with the helper's question mode, one at a time, applying and receipting a selected option before the next.
8. Close with the helper's `receipt --final`, which names each skipped, unanswered, deferred, or open item with its Account per `rules#approval`.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 4 | The report with numbered clear recommendations, lettered record proposals, and listed questions | Which numbers, ranges, letters, `all`, or `skip` to apply |
| 7 | One question with its options and exact changes | One option label, `skip`, or an answer that becomes a new option |
## Audit

| Check | Pass Condition |
|---|---|
| Coverage, before step 4 output | The report renders from this run's saved `coverage_check` JSON. Exit 0, or the report reads `Coverage incomplete` and lists every affected deal as withheld |
| Render, before each output | `pipeline_render` exits 0. Its count, label, duplicate, and structure checks pass; output is posted unchanged |
| Evidence, before step 4 output | Every numbered or lettered proposal cites Salesforce, Gmail, Calendar, or Slack evidence, or on Friday an accepted pilot report. No write rests on an event-only activity or an unknown |
| Slack limits, before step 4 output | Missing Slack users or evidence alone add Coverage notes. Withhold only a buyer-status or commitment change when a verified user's search errored or was incomplete. Unrelated changes remain eligible |
| Tasks, before step 4 output | Task and next-step issues stay in read-only triage rows. No Task or next-step change is routed or proposed. pipeline_render rejects both |
| Pilot input, before step 4 output | On Friday only, a pilot report supports a proposal after `rules#pilot_handoff` identity and field checks pass. Otherwise it is a question without a write |
| Scope, before step 4 output | No proposal drafts or sends email, sets Closed Won, deletes or merges records, or changes OwnerId |
| Write verification, after steps 6 and 7 | Every record outcome is in the run file, no successful write repeats, and fresh native readbacks verify every approved field. Remaining Task or next-step flags are read-only triage findings |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Pipeline report | Run thread, final chat answer | `pipeline_render report` output |
| Questions | Run thread, one message each | `pipeline_render question` output |
| Salesforce updates | Opportunity records, after approval only | The approved fields, read back per `rules#write_protocol` and checked by the step 6 and 7 audit. Forecast-weekly reads these verified records on Friday |
| Receipts and close | Run thread | `pipeline_render receipt` output, with `--final` at close |
| Notification | In-app, scheduled runs only | `pipeline_render notification` payload, sent unchanged when it says send |
| Run file and saved results | Sandbox | Run file, query results, and helper outputs, never Project Files |
