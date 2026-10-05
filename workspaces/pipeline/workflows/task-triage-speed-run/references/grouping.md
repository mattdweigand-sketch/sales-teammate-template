# Grouping

Read at the Group step. Every Task in the run lands in exactly one group.

## Pipeline ownership

Check ownership before the numbered groups or Contact-based routing. Pipeline-review owns the current-action follow-up Task per `rules#followup_task`
for an open Opportunity whose `StageName` is in `policy.pipeline.stages`.
Match an open Task linked by `WhatId` to that Opportunity or its Account against the current action and due date in `Next_Steps__c`.
Use the Subject to identify the action and ActivityDate to check its due date. A shared date alone is not a match.
If multiple Tasks could match, the action or due date is unclear, the dates disagree, or the linkage evidence is incomplete, treat the candidate as ambiguous.
Put both identified current-action Tasks and ambiguous candidates in `Pipeline review owns`. Include the relevant Opportunity links and an ambiguity reason when needed.
Do not propose a date move, completion, Push, or Recycle for these Tasks. A clearly distinct action may enter the numbered groups only when the evidence rules out a current-action match.
At the Draft stage, an owned Task may still receive a follow-up Gmail draft if it meets the Draft email recommended evidence and recipient conditions below.
Recommend that draft only when none of the other numbered group conditions apply. Existing reply, recycle, and hold checks still govern whether a draft is appropriate.
This is draft-only work. The Task stays in `Pipeline review owns` with no number and no Task write.

## Auto date moves

After the pipeline ownership check, test the remaining Tasks for `rules#auto_date_move` before the other numbered groups.
A Task in `Pipeline review owns` never qualifies, including ambiguous ownership candidates. No completion, draft, recycle, CRM correction, or Opportunity change is pre-approved.
Identify the Contact and the Task's newest dated note in Description. Compare its written date with `gmail_contact_stats` `last_sent` in the run-start local offset.
The sent date must be strictly later than the note date. A missing or ambiguous note date or a same-day comparison does not qualify.
Require `unanswered_since_last_substantive` greater than zero. When `last_substantive` exists, its timestamp must be earlier than the qualifying sent message.
Otherwise establish no substantive inbound in verified evidence. A substantive reply at or after that send blocks the automatic move.
This includes Slack per `references/collect.md` "Slack replies". A positive `slack_reply_blocks_auto_move` veto sends the Task to Reply received / manual response.
Read that sent message's full body per `references/collect.md` "Gather evidence" item 7. It must ask or offer something, not just acknowledge or log an action.
Both bounded reply checks in `references/collect.md` "Gather evidence" item 8 must pass before an automatic move.
Read the full thread containing the qualifying send. That send or a later message from Operator must be newest apart from bounces, out-of-office, and calendar notices.
The fully paginated targeted inbound search after the sent date must return no substantive message. A substantive inbound since the qualifying send in either check blocks the move.
Any tool error, timeout, unread thread, or incomplete check is needs-input, not an automatic move. This two-check result is the only absence conclusion `rules#auto_date_move` relies on.
Use the first Monday through Friday after the run-start local date as the next business day. Skip Saturday and Sunday, not days based on an unstated holiday calendar.
For example, Thursday moves to Friday and Friday, Saturday, or Sunday moves to Monday. Use the run's local date, never the sandbox date or the old Task due date.
Apply qualifying moves per `references/writes.md` "Auto date moves" before the section walk, without an approval question.
Verified moves enter the unnumbered `Auto-moved` readout group with their links and old-to-new dates. Do not re-propose them in pending maps.
Failed or unverified moves remain pending with their links and errors. Do not automatically retry or claim they moved.

## Other Tasks

Active and cold per `rules#contact_status`, judged from the `gmail_contact_stats` reply evidence and the Calendar evidence in
`workspaces/pipeline/workflows/task-triage-speed-run/references/collect.md` "Gather evidence" items 2 and 3.

Assign each Task to one group, first match wins. Grouping is mechanical: the rules below decide, in order, from the "Gather evidence" results.
The Contact's active or cold status picks the hold window. The last sent date from "Gather evidence" item 2 decides whether the window applies.
Never apply the cold window to an active Contact. A send that completed the Task's ask is group 1, never Hold.
If a rule result looks wrong, keep the Task where the rule puts it and add one flag line under the readout.

1. **Reply received / manual response.** A substantive Slack reply is at or after Operator's last sent email,
   or a substantive Gmail reply or meeting with the Contact is newer than that email,
   Operator's send completed the Task's ask, the meeting moved, or the Task is internal prep. Propose Complete or a new date with a one-clause reason.
2. **Recycle decisions.** Cold Contact and unanswered count at least `policy.followup.recycle_after_unanswered`. An active Contact never recycles (`rules#contact_status`).
   Under `rules#absence_conclusions` the count is a retrieved-set measurement, so Recycle is offered as needs-input, never as a numbered write.
   Offer Push (move `policy.followup.cooldown_days`) or Recycle (complete the Task, write the Contact cooldown marker).
3. **Hold.** Any of these. Propose a date or Keep today. No draft.
   - Operator sent within the hold window with no reply: `policy.followup.sent_mail_hold_days_cold` for cold, `policy.followup.sent_mail_hold_days_active` for active.
   - An existing draft on the thread (reason `draft exists`).
   - A Lead-linked Task (reason `Lead-linked`).
   - A future cooldown marker on the Contact Description.
   - Recipient unconfirmed: no address Operator has sent to without a bounce, or last inbound type `bounce`. A missing Contact record alone is a CRM correction, not a hold.
   - The only channel is LinkedIn.
4. **Draft email recommended.** Confirmed recipient, no existing draft. Propose one draft and a date of today plus `policy.followup.next_date_days_active` or `policy.followup.next_date_days_cold`.
