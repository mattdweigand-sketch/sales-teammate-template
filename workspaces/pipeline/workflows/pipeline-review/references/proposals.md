# Proposals

Read when building proposals, "Questions" during the walk, and "Apply" after approval.
A flag is a finding; `workspaces/pipeline/workflows/pipeline-review/references/report-format.md` "Approval boundary" decides what is numbered.
Record every proposal, label, and status in the run file that report-format describes.

## Every run

For each deal flagged by `hygiene_check` or by `new_activity` (`workspaces/pipeline/workflows/pipeline-review/references/triggers.md`), show a numbered clear recommendation, a question, or both.
Next-step entries per `rules#next_steps` and `rules#next_steps_format`. Apply `rules#next_steps_review` before date-based proposals.
Build each next-step proposal from the deal's thread record in `workspaces/pipeline/workflows/pipeline-review/references/collect.md` item 4,
the newest message in either direction plus the next scheduled Event, never from Task dates alone.
When the user's last message is unanswered, the stored action is done, so propose the wait and a re-follow-up date, not a moved deadline.
When the buyer's last message names a date, meeting, or ask, the proposal carries it.
Every clause traces to Salesforce, Gmail, Calendar, or Slack evidence, or, on Friday only, to an accepted pilot report under "Pilot report input". No inferred buyer intent.
Deals with no trigger are counted, not listed in ordinary hygiene. S0 and S1 get the Friday qualification pass below, not weekday hygiene.

A clear recommendation is one block for one deal. It may hold the next-step entry, a blank required or conditional field with evidence, and the matching Task change under "Task review".
CloseDate, StageName, Closed Lost, and Amount stay Friday lettered proposals. One number approves only the displayed changes in its block.
`all` covers the numbered blocks displayed in the report, never questions, revised blocks, or letters.

## Task review

Every day for each clear recommendation or question option that sets or changes a next-step action, per `rules#followup_task`.
On Friday also for every live next step with `task_review_required`, as lettered proposals.

- Inspect `open_task_candidates` for the same action, reading the Task Description when its Subject is insufficient.
  Same due date does not prove the same action; a missing exact-date match does not prove no suitable Task exists.
- Reuse or reschedule the same-action Task with its exact Task ID before considering creation.
- Review `milestone_task_candidates` per `rules#followup_task`; put each reviewed later Task kept open in the proposal's `retained_milestones` (schema in `policy.tooling.scripts.pipeline_render`).
  A milestone never substitutes for the current-action Task.
- Complete a Task only with evidence that its action is done, cited in the change.
- Never rename an old Task into an unrelated action. A Subject change keeps the same action.
- Create a Not Started Task only when no suitable Task exists, linked to a verified Contact and the Opportunity.
  Rerun the Collect Task query for that Account first and review the fresh candidates, so no duplicate is created.
- An unresolved next-step date never supports a Task create or reschedule. Semantic action equivalence is a review decision; `task_gap` alone never authorizes creation.
  A Task whose right action is unclear, such as a duplicate with no completed action, is a question.

## Questions

Labels Q1, Q2 in report order. After the numbered blocks are applied, skipped, or deferred, walk the open questions one at a time with the helper's question mode.

- Each question carries brief factual context and evidence, one precise question, two or three options where useful, and the exact record and field changes for each write option.
  An option with no changes is a factual answer. Option labels are Q1-a, Q1-b; `skip` defers the question to the Close list.
- Selecting an option with changes approves exactly those changes. Apply them without a second confirmation.
- A factual answer, free text, or edit becomes a new option with the next unused letter and its exact changes, then waits for approval. Mark any option it replaces superseded.
- Read back every write before rendering the next question.
- Never reuse a label for a different or revised proposal in the run. A revised block takes the next unused number and the old one is marked superseded. Approval never transfers to a new label.

## Friday

Friday, add the rollup, the delta, and lettered record proposals, one record each:
- CloseDate move per `rules#close_date_basis`.
- StageName per `rules#stage_move`. Closed Lost only after `policy.pipeline.closed_lost_silence_days` of silence with no upcoming Event, or a stated buyer no.
- Amount only from a buyer-confirmed or user-supplied figure.
- Task changes under "Task review" for deals without a numbered block.

A record and field appear in one proposal only. A deal in a numbered block can still get a different letter, such as a CloseDate move.

## Friday qualification

Review every owned open deal in `policy.pipeline.early_stages` once on Friday. Keep findings in friday.qualification and the existing approval labels.
For S1 with a blank Amount under `policy.pipeline.early_required_fields`, propose Amount only from buyer evidence and set buyer_confirmed true on that letter after review.
ARR__c is a non-editable formula equal to Amount and zero when Amount is null, verified October 3, 2026. Propose Amount, never ARR__c.
If no buyer-supported figure exists, ask a Q-labeled question rather than copying a seat wish, user-supplied estimate, or an inferred amount.
Propose Closed Lost only after `policy.pipeline.closed_lost_silence_days` of reviewed buyer silence and no upcoming Event.
Record the last dated buyer activity, evidence_complete true only after the relevant reads and reconciliation, and upcoming_event false only after the fresh Event read.
Missing dates, partial searches, outbound follow-ups, and elapsed meetings never establish buyer silence. Positive newer buyer activity defeats an older silence conclusion.
Otherwise propose a dated next step supported by current buyer evidence, with its matching Task changes per "Task review". If the action or date is unknown, ask rather than invent it.
Never propose moving an early stage up. Amount and Closed Lost changes stay Friday letters with fresh reads, approval, and readback. Dated next steps use the existing record proposals.
Keep the full qualification list in the sandbox run file. The report shows at most ten rows plus the total reviewed count.

## Pilot report input

Friday only, and only when Operator supplies a `pilot-usage` report in this run's thread.
Accept it per `rules#pilot_handoff`: confirm its Account and org id against the Account read in `workspaces/pipeline/workflows/pipeline-review/references/collect.md` item 7,
then use its figures as evidence for that Account only.
It can support a lettered record proposal above, such as StageName per `rules#stage_move` or a next-step entry, that quotes the figures with their window and limits.
A missing handoff field or an identity mismatch goes to Needs your input. The report is record-proposal evidence, not a trigger, and it never authorizes a write or widens this run's reads.
On other days, list a supplied report as `Pilot report held for Friday review` with no proposal.

## Apply

Writes per `rules#write_protocol`, one record at a time.
The Next_Steps__c payload is the approved first entry per `rules#next_steps_format` with history unchanged, and no history note is added when none was proposed.
A block or option with several records is not atomic.
Record each record's outcome in the run file, keep successes, never repeat a successful write, and name each failure and any dependent change left unapplied.
Render the receipt with the helper's receipt mode; it never calls a partial block complete.
Re-query the written Opportunities, and the Collect Task and Event queries for their Accounts.
Per `rules#run_start`, record a fresh local-offset time for the pipeline-review post-write `hygiene_check` and use it as `--as-of` on those re-queried records.
The Collect files predate the writes and cannot verify them.
MISSING or unresolved REVIEW next-step status, or `task_gap`, on a written record fails verification.
