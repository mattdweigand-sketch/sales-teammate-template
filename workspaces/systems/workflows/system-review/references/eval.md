# Proactive system evaluation

## Invocation

Eval is part of the existing Friday Review. A typed `eval` request runs the same evaluation on demand.
Cadence remains Friday. There is no daily Eval branch, separate eval automation, or weekday schedule to activate.
On-demand Eval uses the previous-review window and does not reset the review baseline.
Only improvement task recording and evidence comments are allowed. Never execute repairs or change live settings, forecasts, or sales policy.

## Window and evidence

Record the run-start time with the user's local offset. Use the time since the previous review in the Systems thread, or 24 hours on the first run.
Use that time window for automation run `created_at` and merged PRs. Run threads keep their run's `created_at` window, not a turn baseline.
`pplx session get --download-content` returns `conversation.jsonl` with `turn`, `query`, and `answer` but no timestamps. Never infer thread-entry dates from those fields.
For each teammate and deal thread, read only turns later than its last-read turn number in the previous Friday review's Systems output.
The first Friday review sets each thread's baseline and posts its last-read turn number, without claiming historical turns belong to a timed window.
A newly encountered thread also gets a baseline. An unread prior baseline or incomplete thread read is not checked, not permission to reset or advance that baseline.
Post the last turn number actually read per teammate and deal thread in every Friday review's Systems output. Keep counts and baseline history out of Git.
On-demand Eval uses those baselines without advancing them. Prior review records support proposal history and dedupe without rereading earlier thread turns.
An unread baseline is not checked, not proof of a first run. State missing windows and tool errors rather than inventing counts or treating them as zero.

- List every Sales automation with `pplx automation list`, following its pages. Read every automation run in the window with `pplx automation runs <id>`.
  Follow returned cursors until the window is covered. Do not use `--responses`, which would omit non-reporting runs.
- Open a run thread only for failures, stuck receipts, or Operator's edits, rejections, or silence. Normal run records do not justify opening every run thread.
  Verify these signals from retrieved entries and turns, not notifications. Unread or incomplete threads are not checked, not evidence of silence.
  Classify stuck receipts per `references/review.md` "Drift and failures", keeping delivered receipts separate from failures.
  Friday Review additionally reads proposal-bearing run outputs as needed to verify workflow, kind, exact change, and Operator's outcome per `references/review.md` "Proposal outcomes".
  This is an exception to the run-thread restriction for proposal measurement, not permission to open every normal run thread.
- Read Pipeline, Forecasting, and Coach thread entries after their turn baselines, and deal threads with later turns. Keep evidence links and turn numbers.
  Read Prospecting and Systems entries too for numbered proposal outcomes and Friday scorecard counts per `references/review.md` "Proposal outcomes" and "Evidence and scorecard".
- Read PRs merged in the window, deployed revisions, and open improvement tasks. Check profile, pointer, and schedule drift per `references/review.md` "Drift and failures".
- Read the latest numbers reported by Forecasting only to rank impact in Eval, with their reported date and limits. Never recompute forecasts or set sales policy.
  Friday Review also copies the reported weekly calls and quarter-end accuracy for its scorecard, without recalculating either.

Read open project tasks with `pplx tm tasks list --project`. Read prior decline evidence in the Systems thread and its linked tasks and comments, even when the task is no longer open.
Use `pplx tm tasks get <id>` and task comments for linked declined proposals. Unreadable or incomplete dedupe evidence blocks new task creation and is reported as not checked.
Keep raw run evidence, customer material, and review history in the Systems thread or sandbox, never in Git.

## Signals

- A recurring failure or stuck run, supported by dated run evidence.
- The same edit or rejection twice, with links to both instances.
- Manual work Operator repeats that a workflow could prepare, without assuming approval to execute it.
- A no-op or duplicate run, with its unchanged or duplicated output established.
- A missed handoff, identifying the missing artifact, recipient, or required approval evidence.
- Drift from the profile, pointer, or schedule checks, verified from actual settings.
- A system gap against Operator's configured revenue objective, framed as a system change rather than a forecast or sales policy change.

## Proposals and task recording

Surface at most 3 new numbered proposals, ranked by impact. Each has evidence links, an owner, the exact fix, effort `S`, `M`, or `L`, and verification.
The owner is repo-maintenance, agent-configuration, or the domain teammate and Operator for policy. It is a proposed execution owner, not a task assignment.
Use Forecasting's latest reported numbers only for impact ranking. Unsupported impact remains unknown, never a recomputed forecast or a new policy.

Dedupe against open or declined improvement tasks by underlying issue, workflow, and intended fix, not title alone.
Add only new evidence to an existing task as a comment with `pplx tm tasks comments add <task-id> <comment-id> <body>`. Do not repeat evidence already recorded.
A declined match does not authorize a duplicate task, reopening, or execution. If dedupe cannot be verified, report the gap rather than creating a task.
Record each new proposal as one open, unassigned Teammate task labeled `improvement` with `pplx tm tasks create <title> --description <proposal> --label improvement`.
Keep its owner in the description. Do not call `tasks assign`. Never close, cancel, or reopen tasks during this workflow.
Read back each task or evidence comment. Verify status open, no execution assignment, label improvement, and the complete proposal for a new task.
Report a failed or unverified recording as such, including any created task ID. Do not claim it was recorded or retry blindly into a duplicate.
Task creation and evidence comments are the only durable writes. Repairs, configuration changes, and policy decisions retain their own approval gates.

If nothing is new after complete evidence reads and dedupe, post one line saying no new improvements. Comment-only additions do not need a new proposal notification.
Friday still keeps its scorecard and backlog, with the Eval result as that one line. A no-new typed Eval posts only the one line.
For a scheduled run, call `pplx automation suppress-run-notification` for that run only. This leaves its answer and future runs unchanged.
A typed Eval has no automation notification to suppress. Do not hide missing evidence or recording failures as a no-new result.

## Friday backlog

Immediately after the Friday scorecard, add an Improvement backlog section. List the top 5 open improvement tasks by impact, each with its link and age.
Age is elapsed time from task creation to this review's run-start time, not from its last evidence comment. Use reported forecast numbers only to rank impact.
Check all open improvement tasks for resolution, not only the five displayed. Propose closing any that new evidence resolved, linking that evidence.
Proposed closures concern existing tasks, not new improvement proposals. Never close the tasks here or treat resolution as permission to apply a repair.
The scorecard remains seven lines or fewer. The backlog is a separate section, followed by the new ranked proposals.
