# System health review

## Evidence and scorecard

Use the interval since the previous system review and its linked baseline. If that baseline is unavailable, state the available window and do not invent a comparison.
For teammate and deal threads, use turn baselines per `references/eval.md` "Window and evidence", not inferred timestamps.
Each Friday review posts the last turn number it read per teammate and deal thread in its Systems thread output. The first review sets the baseline for each thread.
The next review reads only later turns. Keep counts and baseline history in the Systems thread, never in Git. An unread thread is not checked and its baseline does not advance.
Read the responsible threads for rejected, skipped, or edited proposals. Identify the repo file likely causing each and label an unverified cause as a hypothesis.
Build the scorecard from complete retrieved evidence. State missing windows or unavailable counts rather than treating them as zero.

- Prospecting. Accounts researched, drafts approved, proven sends, event contacts enrolled, replies, meetings, and Pipeline handoffs, with source links.
- Pipeline. ARR created in 7 days from `ARR__c` on Opportunities created in that window, plus stage moves from field history.
- Forecasting. The reported weekly call against last week's reported call, plus quarter-end accuracy from Forecasting's existing check.
- Coach. Gaps closed since the last deal review and open gaps on deals closing this quarter. Copy only Coach's count line, never rescore deals.
- Systems. Failed or missed runs and Operator's approval replies per day, with schedule, run, and reply evidence.
- Health. Repo and tests, deployment, profile, pointer and schedule drift, with delivered receipt-open counts separate from failures.
- Approvals. Numbered proposal outcomes by workflow and kind, with the four-week approved-unchanged rate and a link to the kind table.

Use linked source records for Prospecting counts. A draft is not a proven send. Missing reads are not checked, never zero.
Use Opportunity creation dates (`CreatedDate`) for the Pipeline ARR window, not CloseDate. Stage moves need dated old and new values from field history.
Missing ARR amounts remain unknown. Copy Forecasting's reported calls and accuracy without recomputing forecasts or setting targets.
Retain Operator's replies per weekday by workflow and deal thread alongside daily totals.
Approvals versus rejections, keeping skipped or edited proposals distinguishable, come from the proposal outcome evidence.

## Proposal outcomes

Record every numbered proposal by workflow and kind, with its originating entry link, proposal number, date, exact proposed change, and Operator's outcome evidence.
Kinds describe the change, such as Task date move, Opportunity stage change, draft creation, or repository repair. Do not pool unlike kinds or workflows.
Outcomes are `approved unchanged`, `approved with edits`, `rejected`, or `no reply`. A later edit is not approval of the original wording.
Use the originating entry link and proposal number as identity. Later replies update that proposal's outcome, never add another proposal.
Include numbered Systems improvement proposals published in this review as no reply until Operator responds.
No reply requires a complete read through review time. Unread replies are not checked, not evidence of silence or rejection.

Report a separate kind table from the current review and the prior three Friday reviews in the Systems thread, covering four weeks.
Reconcile later outcome evidence for those proposals without counting a proposal twice. Keep the original proposal in its originating review window.
For each workflow and kind, show total proposals, each outcome count, and each outcome's four-week rate as that count divided by the total proposals for that kind.
The approved-unchanged rate includes edited approvals, rejections, and no replies in its denominator. A zero denominator has no rate, never a zero-percent claim.
If fewer than three prior reviews or incomplete proposal or reply reads are available, label the observed window and counts partial. The four-week rate is not checked.
Keep skipped actions distinguishable from numbered proposal outcomes. Include evidence links and limits, never an inferred approval.
Counts, outcome rows, and review history stay in the Systems thread, never in Git. Measurement grants no pre-approval and introduces no threshold or target.

## Drift and failures

Compare live schedules and prompts against the policy schedule blocks named in the contract. Include timezone, cadence, target workflow, and referenced paths.
Compare every recurring schedule with policy, including the following keys.
- `policy.pipeline.schedule.watch_sync`, `policy.pipeline.schedule.call_sweep`, `policy.pipeline.schedule.task_triage`, and `policy.pipeline.schedule.ask_nudges`.
- `policy.call_prep.schedule` and `policy.forecast.manager_update`.
- `policy.pipeline.customer_review.schedule`.
- `policy.system_review.schedule`.
Check active state against approval evidence separately. Policy values do not authorize enabling schedules. Eval introduces no daily or weekday schedule.
Use `policy.system_review.preapproval` only as the evidence bar for proposing a separately approved rule, never as permission to write or create a rule.
Check repo and test status, deployed revisions, current project-skill pointers, and the existence of their target contracts.
Run `pplx tm orchestrator list` to read the five live Teammate profiles. Compare workflow paths, ownership, and write limits with the repo.
Unreadable profiles are not checked.
Inspect failed runs, broken paths, unresolved pointer deployments, duplicate schedules, and handoffs missing their artifact, recipient, or required approval evidence.
For each teammate thread, report every run that started more than 30 minutes late or stalled during the review window.
Compare the expected scheduled occurrence with the actual run start in the schedule's timezone. Include the run link, both timestamps, delay, state, and output evidence.
Unread schedules, starts, or output locations are not checked. A stall needs retrieved evidence of stopped progress, not merely an in-progress label.
Use the output-location checks below to distinguish stalled work from a delivered receipt still open. Do not count a delivered receipt-open issue as a stall.
Propose a thread move only when the same thread shows a delay in two consecutive Friday reviews, with links to both reviews and their run evidence.
The proposal is to recreate that thread's runs in their own threads with results-only summaries. Recreating needs Operator's approval, never an automatic move.
Respect `_core/CONVENTIONS.md` "Platform limits" when proposing delivery changes. Connector events use new threads. Do not invent a schedule to bypass a limit.
For a run still in progress at review time that started before the review day, check its output location.
- For an existing thread, check the entry or turns after the run's start. For a new thread, check that session.
- When matching output exists, classify the run as `delivered, receipt open`. Count these separately as a platform receipt issue, not a failure.
- When no output exists, classify the run as a failed run. Unreadable output is not checked.
Read actual settings before calling drift. Unavailable settings are not checked. A merged PR proves neither a pointer update nor a completed deployment.
Keep automation identifiers, user identifiers, customer material, and raw run evidence in the Systems thread or sandbox, never in Git.

## Report and routing

Post a scorecard of seven lines or fewer for Friday Review. Add Improvement backlog immediately after it per `references/eval.md` "Friday backlog".
Use exactly the seven teammate, health, and approvals lines above. Put proposal-kind tables and per-thread delay or stall evidence outside the scorecard and after the backlog.
Follow with at most 3 new ranked proposals per `references/eval.md` "Proposals and task recording". Use compact lines and evidence links rather than copying run output.
Each proposal names the issue, supporting evidence, responsible owner, exact requested outcome, proposed fix, and verification criteria. Separate verified failures from uncertain causes.
Route repo files, tests, and reference defects to repo-maintenance. Route actual pointers, agent instructions, and automation settings to agent-configuration.
Domain decisions still belong to Pipeline, Forecasting, or Deal Coaching and Operator where required. Systems never substitutes its own sales policy, scores, forecast, or CRM values.
No repair runs automatically. The receiving workflow applies its existing approval and deployment gates. Keep the report and handoff in the Systems thread or sandbox.
