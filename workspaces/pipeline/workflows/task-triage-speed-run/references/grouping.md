# Grouping

Read at the Group step. Every Task in the run lands in exactly one group, including deal Tasks in the same message and approval.

## Pipeline ownership

1. Use `deal_thread_match` on complete offset-bound project pages and bounded Account searches from `references/collect.md` "Collect the run".
   `owner` means read that deal thread's recent context yourself, read-only, without a message or wait. Save its session id and link for a post-write receipt.
   Include the due Task here as complete plus next Task on matching action evidence, an eligible follow-up draft or a blocker. Never send email.
   `local` continues below. `needs_input` or `incomplete` holds proposals on that record. Never guess ownership or omit a held Task.
2. Review current-action Tasks on in-scope Opportunities with no deal thread under "Unthreaded Opportunity Tasks". Ambiguous linkage or action equivalence stays needs-input.
3. Apply the write and context boundaries in `rules#task_date_coordination` and `rules#followup_task`.

## Unthreaded Opportunity Tasks

Under `rules#task_date_coordination`, triage completes and creates due current-action Tasks on open Opportunities in `policy.pipeline.stages` with no deal thread.
Match Subject and Description to the current action in `Next_Steps__c`, reviewing exact Opportunity or Account WhatId linkage per `rules#followup_task`. A shared date is not action equivalence.
Missing links, multiple candidate actions or uncertain evidence mean a blocker, never a guessed completion. Apply the same action-evidence and next-Task gates as every other triage row.
Build its paired next-step entry per `references/next-steps.md` "Draft", within `rules#followup_task`. Other Opportunity fields stay outside this contract.

## Task gaps

Include each verified gap from `references/collect.md` "Task gaps" once in the main message. Propose one Not Started Task from the current next-step action and date, with verified native links.
Name the source Opportunity and show OwnerId equal to the run user, Subject, ActivityDate, WhatId, WhoId and Description. No old Task completion is implied. Unknown evidence stays needs-input.

## Other Tasks

A first cold email on a Task with no open Opportunity belongs to Prospecting.
Confirm no open Opportunity from complete native Account reads, not a missing queue match. Keep the Task visible as a handoff blocker, never relax the recipient gate.

For a Task linked to a Closed Won or Closed Lost Opportunity, retain it in the queue and show the current stage.
Ask whether the action still belongs to Operator before proposing a new sales follow-up. Existing drafts stay blockers, and closing the Opportunity alone is not completion evidence.

Active and cold follow `rules#contact_status`, using retrieved Gmail reply and Calendar evidence from `references/collect.md` "Gather evidence".
Assign first match wins. Recycle counts are retrieved-set measurements under `rules#absence_conclusions`, never proof of no reply.

1. **Draft not sent.** When this Task follows a draft-only completion, check whether that exact draft was sent. If not, flag `Draft not sent`; do not draft a new follow-up or change its date.
2. **Action happened.** A sent email, held call or reply must establish that this Task's action happened. Quote and link the source. Scheduling or an unrelated message is not completion evidence.
   Propose completion with a verified existing next-action Task named, or create one with a new Subject and date, in the same approval. Review all related open Tasks first. Never create a duplicate.
3. **Buyer date or moved meeting.** Quote the buyer's new date or moved Event for any run Task, including a deal Task. Propose only that date and required note with `task_reschedule_check`.
   No buyer or meeting source means no date move. The scheduled-run evidence gate remains unchanged. One-deal source permission follows `rules#task_date_coordination`.
4. **Recycle decisions.** Cold Contact and unanswered count at least `policy.followup.recycle_after_unanswered` remains needs-input, and an active Contact never recycles (`rules#contact_status`).
   No Push option. Recycle never authorizes unsupported Task completion or a date roll. Its Contact cooldown marker uses `policy.followup.cooldown_days` only on explicit approval.
5. **Hold or prepare.** Keep the Task due or overdue when its action has not happened. Prepare a draft, call prep or a question, showing the blocker and unchanged current date.
   No new draft during `policy.followup.sent_mail_hold_days_active` or `policy.followup.sent_mail_hold_days_cold`, according to Contact status.
   Use `gmail_contact_stats --send-hold` and the matching `send_hold_active` or `send_hold_cold` value, never the date-only `last_sent`.
   A true hold blocks drafting. Missing or failed timestamp evidence stays needs-input. A false hold releases only this timing gate, not recipient, approval or draft-dedupe gates.
   Existing draft, Lead linkage, future cooldown marker, unconfirmed recipient or LinkedIn-only channel is a blocker, not completion evidence or permission to push.
   A recipient requires a verified address Operator sent to without a bounce. A missing Contact record is a separate CRM correction, not invented identity.
   For an eligible email action, prepare the full draft. Only after approval and verified triage creation does that draft qualify for complete plus next Task.
   When the stated action cannot be prepared but retrieved evidence supports a different action toward the same outcome, prepare that action's full draft as a numbered row, not a blocker.
   Name the original action, the evidence and the change in one line.
   A switch that changes legal terms is a recommended question row with the draft ready, so one answer approves it. The recipient, hold and existing-draft gates above still apply.
   When the Task's recipient bounced, propose a first email to another Contact on the same Account whose role fits the action, flagged `First email to this address`.
   This is the only exception to the verified-recipient gate.
   Its next Task first checks whether the draft was sent. Show that action, draft linkage and a date using `policy.followup.next_date_days_active` or `policy.followup.next_date_days_cold`.
   Those values date a new Task, never move the old one. Deal Task follow-up drafts follow these same recipient, prior-email, hold, approval and readback gates. Never send.
