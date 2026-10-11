# Proactive system evaluation

## Invocation

Eval is part of the existing Friday Review. A typed `eval` request runs the same evaluation on demand.
Cadence remains Friday. There is no daily Eval branch, separate eval automation, or weekday schedule to activate.
On-demand Eval uses the previous-review window and does not reset the review baseline.
A typed `eval` request also collects the proposal census and four-week kind table per `references/review.md` "Proposal outcomes".
That census uses its own complete four-week window ending at the run start and labels partial coverage. Friday Review collects no census.
Friday Review keeps failures, drift, repeated corrections, capture and backlog.
Only improvement task recording and evidence comments are allowed. Never execute repairs or change live settings, forecasts, or sales policy.

## Window and evidence

Record the run-start time with the user's local offset. Use the time since the previous review in the Systems thread, or 24 hours on the first run.
Use that time window for automation run `created_at` and merged PRs. Run threads keep their run's `created_at` window, not a turn baseline.
Call `load_sessions` in Code Mode with the verified session context UUID, not the URL task ID.
Read its `memory/sessions/<week>/<short_id>/conversation.md`, including `first_entry_at`, `last_entry_at` and each entry's UTC timestamp.
Normalize the review window to UTC. Window thread entries by their timestamps, never by turn numbers.
The thread's window is complete only when `first_entry_at` is at or before the window start, or `session_get` confirms the session was created after the window start.
Otherwise report the uncovered span as not checked and do not advance that thread's baseline. Missing or unreadable timestamp evidence also stays not checked.
If `load_sessions` is unavailable or fails, fall back to `session_download_content` for the context UUID and read its `conversation.jsonl`.
An undated fallback cannot prove a timed window complete. Never infer thread-entry dates from `turn`, `query` or `answer`.
If both reads are unavailable or fail, mark that thread context not checked. Never infer its contents.
Turn numbers are export-local positions, not durable entry identities. Never select new entries by comparing turn numbers across exports.
For each teammate and deal thread, use the timestamped window boundary in the previous Friday review's Systems output.
Retain the retrieved source in the sandbox and link its snapshot, context UUID, coverage timestamps and any uncovered span in the review output.
The first Friday review sets each thread's baseline from its verified coverage, without claiming historical turns belong to a timed window.
A newly encountered thread also gets a baseline. An unread prior baseline or incomplete thread read is not checked, not permission to reset or advance that baseline.
Native entry IDs are not required when timestamp coverage is verified. Do not advance its baseline or count unread outcomes when required coverage is incomplete.
Missing entries or status-only answers do not prove complete retrieval. Request complete source evidence rather than guessing the lost window.
Keep counts and baseline history out of Git.
On-demand Eval uses those baselines without advancing them. Prior review records support proposal history and dedupe without rereading earlier thread turns.
An unread baseline is not checked, not proof of a first run. State missing windows and tool errors rather than inventing counts or treating them as zero.

- List every automation for a relevant Sales duty Operator owns with `pplx automation list`, following its pages, whether its collection is project-bound or null.
  Record each one's owner, source, approval or exception, and actual expiry evidence. Unrelated personal automations are not read.
  Listing an exception transfers no ownership and changes no settings. Read every automation run in the window with `pplx automation runs <id>`.
  Follow returned cursors until the window is covered. Do not use `--responses`, which would omit non-reporting runs.
- Open a run thread only for failures, stuck receipts, or Operator's edits, rejections, or silence. Normal run records do not justify opening every run thread.
  Verify these signals from retrieved entries and turns, not notifications. Unread or incomplete threads are not checked, not evidence of silence.
  Classify stuck receipts per `references/review.md` "Drift and failures", keeping delivered receipts separate from failures.
  A typed `eval` additionally reads proposal-bearing run outputs as needed to verify workflow, kind, exact change, and Operator's outcome per `references/review.md` "Proposal outcomes".
  This is an exception to the run-thread restriction for proposal measurement, not permission to open every normal run thread.
- Read Pipeline, Forecasting, Coach and deal thread entries within their verified timestamp windows. Keep evidence links and export-local turn numbers for navigation only.
  Read Prospecting and Systems entries too for Friday scorecard counts per `references/review.md` "Evidence and scorecard".
  A typed `eval` reads them over its four-week window for numbered proposal outcomes per `references/review.md` "Proposal outcomes".
- Read PRs merged in the window, deployed revisions, and open improvement tasks. Check profile, pointer, and schedule drift per `references/review.md` "Drift and failures".
- Read the latest numbers reported by Forecasting only to rank impact in Eval, with their reported date and limits. Never recompute forecasts or set sales policy.
  Friday Review also copies the reported weekly calls and quarter-end accuracy for its scorecard, without recalculating either.

Read open project tasks with `pplx tm tasks list --project`. Read prior decline evidence in the Systems thread and its linked tasks and comments, even when the task is no longer open.
A returned `next_cursor` means the task inventory is incomplete. If the installed CLI cannot consume it, report dedupe not checked and create no tasks.
Never invent a cursor option or treat a full 100-task page as complete. Request a complete authorized inventory with open tasks and linked decline evidence.
Use `pplx tm tasks get <id>` and task comments for linked declined proposals. Unreadable or incomplete dedupe evidence blocks new task creation and is reported as not checked.
Keep raw run evidence, customer material, and review history in the Systems thread or sandbox, never in Git.

## Signals

- A recurring failure or stuck run, supported by dated run evidence.
- The same edit or rejection twice, with links to both instances.
- Manual work Operator repeats that a workflow could prepare, without assuming approval to execute it.
- A no-op or duplicate run, with its unchanged or duplicated output established.
- A missed handoff, identifying the missing artifact, recipient, or required approval evidence.
- Drift from the profile, pointer, or schedule checks, verified from actual settings.
- A system gap against the reviewed targets in `policy.forecast.targets` or `policy.forecast.target_default`, framed as a system change rather than a forecast or sales policy change.

For each same-edit or same-rejection pattern, ask Operator one question, with both links, asking what was wrong. Ask once per pattern, never per proposal.
Skip a pattern whose reason Operator already gave. Without his answer the cause stays a labeled hypothesis. Never infer his reason from the edit.
Record his answer as an evidence comment on the matching improvement task, with the reply link. It replaces the hypothesis as the cause evidence for that fix.

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
Friday still keeps its scorecard and backlog, with the Eval result as that one line. Friday collects no census.
A no-new typed Eval posts the one line plus the requested census and four-week kind table, or their partial and not-checked limits. Zero new improvements never drops the census.
For a scheduled run, call `pplx automation suppress-run-notification` for that run only. This leaves its answer and future runs unchanged.
A typed Eval has no automation notification to suppress. Do not hide missing evidence or recording failures as a no-new result.

## Capture nomination

Friday only, add at most one capture step in the Systems thread. This is part of the existing review, not a new automation or schedule. On-demand Eval adds no capture step.
First read the capture files in `workspaces/systems/captures/` and Operator's prior declines in the Systems thread.
Dedupe by recurring task and owning workflow across confirmed, applied, retired and declined captures, not title alone.
Incomplete capture-file or decline reads are not checked and block a new nomination. Keep real examples in the Systems thread or sandbox, never Git.
If a capture is open, meaning a `confirmed` file or an unfinished capture in the Systems thread, post one status line instead of nominating another task.
State what it waits on, such as a second case or wording approval. Never prepare a trial during system-review.
Otherwise choose at most one recurring task from this week's "Signals", either the same edit or rejection twice or repeated manual work, with no existing capture file or prior Operator decline.
Post its owning workflow, two real example links and the first one or two questions per
`workspaces/systems/workflows/process-capture/references/capture.md` "Select a task" and "Walk through decisions". A nomination is only a suggestion until Operator selects the task.
For a same-edit nominee, its capture question replaces that pattern's repeated-correction question in "Signals". Ask once per pattern, never both questions.
Questions wait for no reply. Operator's answer continues the capture in the Systems thread under the process-capture contract, not as a repair or wording approval.
No repo or customer-system writes. Do not write capture files here or place customer examples in Git. Existing improvement task recording is unchanged.

## Monthly capture review

On the first Friday of each month, add one capture summary after the capture step. This is part of the existing review, not a new schedule. On-demand Eval skips it.
List each file in `workspaces/systems/captures/` with its task, owner, status and age. An unread folder is not checked.
Flag an `applied` capture when its owning workflow drew the same edit or rejection again in "Signals" since its applied date. Link both instances.
Record each flag as an improvement task per "Proposals and task recording", proposing revision or retirement. It counts within the 3 new proposals.
Never edit capture files. Revision and retirement go through process-capture and repo-maintenance after Operator agrees.

## Friday backlog

Immediately after the Friday scorecard, add an Improvement backlog section. List the top 5 open improvement tasks by impact, each with its link and age.
Age is elapsed time from task creation to this review's run-start time, not from its last evidence comment. Use reported forecast numbers only to rank impact.
Check all open improvement tasks for resolution, not only the five displayed. Propose closing any that new evidence resolved, linking that evidence.
Proposed closures concern existing tasks, not new improvement proposals. Never close the tasks here or treat resolution as permission to apply a repair.
The scorecard remains seven lines or fewer. The backlog is a separate section, followed by the new ranked proposals.
