# Proposals

Read at the Propose step, and "Apply" again after approval. Letter every proposal. Show the full payload, current value to new value.
## Letters

Each approval covers one record, except a B next-step change and its matching Task changes, which stay together under B.
Interaction-sync call logging keeps full post-call Task behavior per `rules#task_date_coordination`, including in deal threads. B, C and F retain duplicate, stale-write, freshness and approval gates.
When E or F would cover several records, number them E1, E2 or F1, F2 and approve each on its own.

- **A. Completed-call Task.** Status Completed, TaskSubtype Call, ActivityDate the call date, WhoId the primary external Contact,
  WhatId the Opportunity (Account if none), OwnerId the userId from `rules#run_start`.
  Description line 1 is the exact source marker from `workspaces/pipeline/workflows/interaction-sync/references/reconcile.md` "Find the interaction".
  Then one `policy.salesforce.note_prefix` line with attendees, the quotes, commitments, and open items.
- **B. Opportunity update.** `Next_Steps__c` per `rules#next_steps` and `rules#next_steps_format`. `StageName` per `rules#stage_move` with supporting transcript evidence.
  Closed Lost stays with pipeline-review.
  Any `policy.pipeline.required_fields` value stated on the call, marked `buyer_confirmed` or `user_supplied` with speaker attribution.
  Amount and seat counts only from `policy.interaction.amount_source`; booking forms, seat requests, and wishes are not confirmation.
  If the move leaves S0 and `LeadSource` is blank, include `LeadSource` with its evidence (`policy.salesforce.validation_rules`).
  When B changes `Next_Steps__c`, include its matching follow-up Task change in B per `rules#followup_task`, with the full Task payload and current-to-new values.
  One `approved B` covers both sides. Never propose or apply a B change to `Next_Steps__c` without its matching Task payload.
  First review the open Tasks from "Reconcile" item 4 for the same action. Reuse one, or propose its reschedule by exact ID, before creating another.
  A new action completes the old Task and creates one, except a reviewed later milestone stays open per `rules#followup_task`.
  Same date alone is not the same action. When none fits, propose a Not Started Task whose Subject names the awaited item, linked to the Contact and Opportunity.
  The Task's ActivityDate is the action's due date, not the date the next-step entry is written.
- **C. Follow-up Task without a next-step change.** Use C only for Task changes not tied to a next-step change. Never split B's matching Task into C.
  With no open Opportunity, C is needs-input until Operator confirms the follow-up owner and Account linkage. A closed Opportunity does not establish an ongoing sales action.
  Review the open Tasks from "Reconcile" item 4 for the same action and reuse or reschedule by exact ID before creating another per `rules#followup_task`.
  When none fits, propose a Not Started Task whose Subject names the awaited item, linked to the Contact and Opportunity.
  Its due date is the buyer-stated date when the buyer owns the action,
  else today plus `policy.followup.next_date_days_active` (active) or `policy.followup.next_date_days_cold` (cold) per `rules#contact_status`.
- **D. Gmail follow-up draft.** Before proposing, run `list_drafts` and match `thread_id` against "Reconcile" item 6.
  An existing draft on that thread for the same follow-up is `reuse existing`: show its id and propose no new draft. Never edit it.
  When item 6 found no thread, read each listed draft with `get_draft` (`list_drafts` returns no recipients) and compare recipients and purpose.
  Same external recipients and same purpose is `reuse existing`. A partial match or unclear purpose is needs-input. No match allows a new thread.
  Follow `policy.email_voice` and `rules#email_body`. Reply in the item 6 thread when one exists, to the external attendees, cc Operator. Include links promised on the call.
  List materials mentioned on the call under `Suggested attachments` with the speaker who named each.
  Attach only what the user approves, from `policy.email_voice.collateral_path` or supplied by the user. Nudges get none. Never send.
- **E. Records.** Contact creates, Opportunity Contact Role adds, Contact Title fixes heard on the call.
- **F. Complete open Tasks.** One proposal per open Task tied to this call: Status Completed plus a `rules#note_prefix` line pointing at the call Task
  (A once applied, or the existing Task from "Reconcile" item 5). F applies only after that call Task is verified.
  Do not complete a Task retained for the still-open action in B or C, or separately propose in F a Task completion already included in B. Unrelated open Tasks are listed, not proposed.

## Pilot finding

Only a `pilot-usage` finding tied to the completed call being logged, supplied in this thread, and accepted per `rules#pilot_handoff`.
Confirm its Account and org id against the Account resolved in "Reconcile". It may appear in A's Description or in B, quoted with its window and limits.
It is never a buyer-confirmed Amount or seat count under `policy.interaction.amount_source`. A finding not tied to this call is listed, not proposed.

## Apply

Writes per `rules#write_protocol`. Rerun the item 5 duplicate query before A, the item 4 review before a new Task in B or C, and the D draft check before D.
Fresh-read native OwnerId before each Task write. Missing or unreadable ownership holds as needs-input. Stop and re-propose changed native state, never reuse approval after a material change.
For a date move, run `task_reschedule_check` in proposal and prewrite phases per its interface, using the non-triage mode. Save and compare the exact baseline, native links and displayed payload.
For an approved B next-step change, write the next step first, then its matching Task changes, then read both back per `rules#write_protocol`.
If a Task write fails, report B as partial with the actual state of both sides and one corrective proposal for the remaining Task change. Do not claim both applied.
`draft_email` returns no id; confirm with `list_drafts` and match the `thread_id`.

After verified Opportunity writes, use `deal_thread_match` with saved project pages and bounded Account searches per its interface.
Apply the receipt rule in `rules#followup_task` only when the matched deal thread differs from this run thread. Use the saved native session id, never guess a route.
Post the run result first, then send verified written next step and Task links once with `pplx tm mail send <session id> "<message>"`.
Never wait for a rate limit. Every `pplx` command is a top-level line, never inside a script or loop.
Unread or ambiguous routing and failed sends are disclosed without undoing or repeating verified writes. Receipts request no proposal.
