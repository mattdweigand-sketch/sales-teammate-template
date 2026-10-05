---
cadence: Friday
reads: >-
  _core/policy.yaml (pipeline, forecast, coach, prospecting, system_review, call_prep),
  _core/CONVENTIONS.md, references/, runs and threads, repo and tests, profiles, pointers, schedules, PRs, improvement tasks
writes: Teammate improvement tasks and evidence comments only
next: repo-maintenance or agent-configuration for approved repairs, domain teammate and Operator for policy proposals
---

# System Review

Friday Review includes Eval and an Improvement backlog after its scorecard. A typed `eval` request runs the same evaluation on demand.
Only improvement task recording and evidence comments are allowed. Never apply repairs or change settings, forecasts, or sales policy.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `pipeline.schedule`, `forecast.schedule`, `forecast.tracking.pace_report`, `coach.schedule` | Canonical intended schedules |
| Core policy | `_core/policy.yaml` | `system_review.schedule`, `call_prep.schedule`, `forecast.manager_update` | Other recurring schedules |
| Core policy | `_core/policy.yaml` | `system_review.preapproval` | Evidence bar for a proposed rule, never write authority |
| Ownership | `_core/CONVENTIONS.md` | "Folder ownership", "Handoffs and state", "Cadence and library pointers", "Platform limits" | Domain and technical boundaries |
| Reference | `references/review.md` | "Evidence and scorecard", "Proposal outcomes", "Drift and failures", "Report and routing" | Review evidence, rates, and repair routes |
| Reference | `references/eval.md` | "Invocation", "Window and evidence", "Signals", "Proposals and task recording", "Friday backlog" | Evaluation scope, proposal recording, and backlog |
| Per-run evidence | Repository, tests, deployed revisions, live pointers, agent instructions, and automation settings | Current intended and actual state, run schedules and prompts | Drift and deployment checks |
| Per-run evidence | Responsible run threads and prior three Friday reviews in Systems, saved results in sandbox | Numbered proposals, kinds, outcomes, replies, errors and Task trends | Health and four-week rates |
| Per-run evidence | Automation runs, Prospecting, Pipeline, Forecasting, Coach, Systems, and active deal threads, PRs, improvement tasks | Window since previous review. Reported forecast calls and Coach counts are copied only | Scorecard, improvement evidence and dedupe |

## Process

1. Select Friday Review or on-demand Eval and establish the previous-review window per `references/eval.md` "Invocation" and "Window and evidence".
2. Read repo and test status, deployed revisions, pointers, schedules, and prompts per `references/review.md` "Drift and failures".
3. Read runs, responsible thread entries, active deal threads, merged PRs, and tasks per `references/eval.md` "Window and evidence". Friday scorecard evidence follows `references/review.md`.
4. Evaluate per `references/eval.md` "Signals". Compare settings and handoffs without inferring deployment from a merged PR or recomputing forecasts.
5. Dedupe and record at most 3 new ranked proposals per `references/eval.md` "Proposals and task recording". Read back each task and never apply its fix.
6. Report per `references/review.md` "Report and routing" and `references/eval.md` "Friday backlog". No-new Eval uses the quiet receipt in "Proposals and task recording".

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
| Report, before output | At most 3 new proposals rank impact. Friday keeps its scorecard of seven lines or fewer, then the top-five backlog with age and proposed closures. No-new Eval is one line |
| Measurement, before Friday output | Seven scorecard lines use sourced counts. Kind rates cover current and prior three reviews, or are not checked. A move needs two consecutive reviews of the same thread |
| Boundaries, throughout | Only improvement tasks and evidence comments are writes. Never assign or close tasks, apply repairs, change settings, recompute forecasts, set policy, or write customer systems |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Health report | Systems thread, supporting evidence in sandbox | Friday scorecard, Improvement backlog, and at most 3 new ranked proposals. On-demand Eval uses the same evaluation |
| Improvement records | Teammate project tasks | Open, unassigned tasks labeled improvement. Existing matches get new evidence comments only, read back per `references/eval.md` |
| Repair or policy handoff | Systems thread and proposal task | Evidence, owner, exact fix, effort, and verification. Repairs follow repo-maintenance or agent-configuration, policy goes to the domain teammate and Operator |
| Quiet receipt | Systems thread | One Eval line when nothing is new. Friday keeps its scorecard and backlog. Suppress only that scheduled run's notification, not future runs |
