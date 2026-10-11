---
cadence: Friday
reads: >-
  _core/policy.yaml (pipeline, forecast, coach, prospecting, system_review, call_prep),
  _core/CONVENTIONS.md, references/, workspaces/systems/captures/, runs and threads, repo and tests, profiles, pointers, schedules, PRs, improvement tasks
writes: Teammate improvement tasks and evidence comments only
next: repo-maintenance or agent-configuration for approved repairs, domain teammate and Operator for policy proposals
---

# System Review

Friday Review includes Eval and an Improvement backlog after its scorecard. A typed `eval` request runs the same evaluation on demand and adds the proposal census and four-week kind table.
Only improvement task recording and evidence comments are allowed. Never apply repairs or change settings, forecasts, or sales policy.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `pipeline.schedule`, `forecast.schedule`, `forecast.tracking.pace_report`, `coach.schedule` | Canonical intended schedules |
| Core policy | `_core/policy.yaml` | `pipeline.customer_review.schedule`, `forecast.amount_field`, `forecast.targets`, `forecast.target_default` | Customer review timing and ARR field for the scorecard |
| Core policy | `_core/policy.yaml` | `system_review.schedule`, `call_prep.schedule`, `forecast.manager_update` | Other recurring schedules |
| Core policy | `_core/policy.yaml` | `system_review.preapproval` | Evidence bar for a proposed rule from linked complete typed `eval` evidence, otherwise not checked. Never write authority |
| Ownership | `_core/CONVENTIONS.md` | "Folder ownership", "Handoffs and state", "Cadence and library pointers", "Platform limits" | Domain and technical boundaries |
| Thread lookup | `_core/thread-locators.md` | "Teammate thread lookup" | Verified runtime owner destinations, never a complete deal inventory |
| Reference | `references/review.md` | "Evidence and scorecard", "Proposal outcomes", "Drift and failures", "Report and routing" | Review evidence, rates, and repair routes |
| Reference | `references/eval.md` | "Invocation", "Window and evidence", "Signals", "Proposals and task recording", "Capture nomination", "Monthly capture review", "Friday backlog" | Evaluation scope, proposal recording, capture steps and backlog |
| Reference | `workspaces/systems/workflows/process-capture/references/capture.md` | "Select a task", "Walk through decisions" | Bounded capture questions |
| Capture files | `workspaces/systems/captures/` | Full folder, Friday only | Capture dedupe and monthly review |
| Per-run evidence | Repository, tests, deployed revisions, live pointers, agent instructions, and automation settings | Current intended and actual state, run schedules and prompts | Drift and deployment checks |
| Per-run evidence | Responsible run threads and Systems review history, saved results in sandbox | Errors and Task trends. On a typed `eval` only, numbered proposals, kinds, outcomes and replies over its own four-week window | Health, and four-week rates on typed `eval` |
| Per-run evidence | Automation runs, Prospecting, Pipeline, Forecasting, Coach, Systems, and active deal threads, PRs, improvement tasks | Window since previous review. Reported forecast calls and Coach counts are copied only | Scorecard, improvement evidence and dedupe |

## Process

1. Select Friday Review or on-demand Eval and establish the previous-review window per `references/eval.md` "Invocation" and "Window and evidence". A typed `eval` adds its own four-week census window.
2. Read repo and test status, deployed revisions, pointers, schedules, and prompts per `references/review.md` "Drift and failures".
3. Read runs, responsible thread entries, active deal threads, merged PRs, and tasks per `references/eval.md` "Window and evidence". Friday scorecard evidence follows `references/review.md`.
4. Evaluate per `references/eval.md` "Signals". Compare settings and handoffs without inferring deployment from a merged PR or recomputing forecasts.
5. Dedupe and record at most 3 new ranked proposals per `references/eval.md` "Proposals and task recording". Read back each task and never apply its fix.
6. Friday only, prepare at most one capture step per `references/eval.md` "Capture nomination". Nominate one task or post one status line for an open capture, without waiting for a reply.
   First Friday of the month, also add the summary per `references/eval.md` "Monthly capture review".
7. Report per `references/review.md` "Report and routing" and `references/eval.md` "Friday backlog". No-new Eval uses the quiet receipt in "Proposals and task recording".
   A no-new typed `eval` still returns its census and kind table, or their partial and not-checked limits, with the one line.

## Checkpoints

None. Improvement task recording needs no approval pause. Repairs and policy decisions follow their owning workflow's approval rules.

## Audit

| Check | Pass Condition |
|---|---|
| Evidence, before report | Each finding cites actual settings or run evidence, with unavailable reads and uncertain causes labeled |
| Window, before proposals | Reads cover since the previous review, or 24 hours on the first run. Missing reads are not checked, never a claim of no findings |
| Drift, before report | Schedules and prompts were compared with the canonical intended configuration, or the comparison is not checked |
| Dedupe, before tasks | Open and declined improvement tasks were checked. A match gets only new evidence as a comment, never a duplicate task |
| Tasks, after recording | Each new proposal is read back as one open, unassigned task labeled improvement, with evidence, owner, exact fix, effort S, M, or L, and verification |
| Report, before output | At most 3 new proposals rank impact. Friday keeps its scorecard of seven lines or fewer, then the top-five backlog with age and closures. No-new Eval is one line, typed adds census and kind table. Repeated-correction questions follow the proposals, one per pattern. |
| Capture, before Friday output | At most one capture step. A same-edit capture question replaces that pattern's repeated-correction question. No repo or customer-system writes, no capture file writes and no customer examples in Git |
| Measurement, before output | Teammate and health scorecard lines use sourced counts. The approvals line and kind rates come only from a typed `eval` census over its own four-week window, or are not checked. A move needs two consecutive reviews of the same thread |
| Boundaries, throughout | Only improvement tasks and evidence comments are writes. Never assign or close tasks, apply repairs, change settings, recompute forecasts, set policy, or write customer systems |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Health report | Systems thread, supporting evidence in sandbox | Friday scorecard, Improvement backlog, at most 3 new ranked proposals, and repeated-correction questions. On-demand Eval uses the same evaluation and adds the census and kind table |
| Friday capture step | Systems thread, supporting evidence in sandbox | At most one nomination with owner, two real example links and one or two questions, or one status line for an open capture |
| Monthly capture summary | Systems thread, first Friday only | Each capture file with task, owner, status and age, plus re-edited applied captures recorded as improvement tasks |
| Improvement records | Teammate project tasks | Open, unassigned tasks labeled improvement. Existing matches get new evidence comments only, read back per `references/eval.md` |
| Repair or policy handoff | Systems thread and proposal task | Evidence, owner, exact fix, effort, and verification. Repairs follow repo-maintenance or agent-configuration, policy goes to the domain teammate and Operator |
| Quiet receipt | Systems thread | One Eval line when nothing is new. A typed `eval` adds its census and kind table or their limits. Friday keeps its scorecard and backlog. Suppress only that scheduled run's notification, not future runs |
