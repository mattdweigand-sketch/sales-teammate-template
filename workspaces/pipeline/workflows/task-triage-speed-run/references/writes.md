# Writes and close

"Writes" applies only to the approved full pass or remaining batch. "Close" runs once at the end. No write is automatic.

## Writes

Apply approvals per `references/walk.md` "Section walk", never another approval per group, draft or paired Task create and completion.
Every proposal snapshots its actual sources per `rules#repo_currency`. Immediately before each approved write, require the unchanged saved scope and all native record gates.
Fresh-read the exact old Task, its native linkage and all related open Tasks before a completion or create. Stop on changed Status, ActivityDate, LastModifiedDate, Subject or Description.
Recheck action evidence and ownership. A closed Task, changed owner or ambiguous linkage stops the old proposal. Re-propose with fresh evidence, never reuse approval after a material change.
Skip Tasks interaction-sync already handled, verified against fresh native state and its receipt. A changed date alone does not prove handling. Never freeze every Task modified today.
Recheck Slack with fresh reviewed receipts before each write per `rules#run_start`. Record a fresh local-offset search window end and helper `--as-of`, without changing the original run start.
Use replies only as evidence of the matching Task action. Missing or incomplete results never prove absence or authorize a write.
Preserve history per `rules#note_prefix`. Every changed Task gets the displayed reason and source note, with raw existing Description below it unchanged.

- **Complete plus next Task.** Scheduled completion needs matching sent email, held call, reply, or a verified triage-created Gmail draft.
  One-deal source permission follows `rules#task_date_coordination`.
  Display the old Task payload and either the new Task's full payload or the verified existing next-action Task's Id and linkage in the same numbered row.
  A new Task has a new Subject and date, correct OwnerId, WhatId and WhoId, and Not Started status. Recheck duplicates before any create.
  When an open Task already holds the next action, name it as `reuse existing`. After approval, verify it still holds that action, write and read back any displayed next step, then complete the
  evidenced due Task and read it back. Create nothing.
  A next Task discovered after display changes the create payload. Re-propose completion with that Id for fresh approval, then complete without a duplicate. It is not a permanent completion blocker.
  Write and read the approved next step first for a deal pair. Create and read back the matching Task only when none already holds the next action.
  Then complete the old Task with its approved note and read it back.
  A failed create or readback leaves the old Task open and due. A completion failure after a verified create is partial. Report both actual records, never imply rollback or retry automatically.
  Apply this same pair to deal Tasks and the unthreaded Opportunity branch. Triage may create their approved follow-up Gmail drafts, never send email or write other Opportunity fields.
  For each deal current-action row, write its displayed Next_Steps__c entry first per `rules#next_steps` and `rules#next_steps_format`, preserving history.
  Then its matching Task and old Task completion follow the pair write order.
- **Task gap.** Re-read the Opportunity's next step and all related open Tasks immediately before the approved create. Require complete native reads and unchanged owner, links, action and date.
  A suitable Task discovered after display stops the create without a duplicate. Show the actual Task and revised outcome, never complete another Task under a gap approval.
  Create only the displayed Operator-owned Not Started Task and verify every field by native readback. A gap row never completes an old Task. Its displayed next-step entry and new Task follow the same
  pair write order.
- **Draft-backed pair.** Includes deal Task follow-ups. Wait for its displayed row's approval. Create and verify the exact Gmail draft per `references/drafts.md` before any paired Task write.
  A failed or unverified draft gets no next-step, completion or next-Task write. Existing drafts or notes that say a draft exists do not qualify as triage-created action evidence.
  Save the verified draft id and thread link in the next Task's approved note. Its Subject first checks whether that exact draft was sent; if not, flag `Draft not sent`.
- **Date move.** Displayed next-step entry first, then matching Task ActivityDate plus required note, with its quoted source per `rules#task_date_coordination`, including its one-deal exception only.
  Run `task_reschedule_check --phase proposal` before display and save baseline, baseline_links and exact payload. Immediately prewrite require fresh native reads and ready with that same payload.
  Follow `rules#task_date_coordination` and its native hasMore completeness, current-action review, note history and readback gates.
- **Recycle.** Requires `approved` with its Task number. `all` never covers Recycle or CRM corrections. An unresolved choice authorizes no write.
  Contact cooldown marking follows the displayed `policy.salesforce.cooldown_marker` and `policy.followup.cooldown_days`, preserving Description history.
  Recycle by itself never completes a due Task or changes its date. Completion still needs action evidence and the next Task in the same approval.
- **CRM corrections.** Follow the main pass, one record per approval per `references/crm-corrections.md`. Neither `all` nor main-pass selections approve them.

Before any paired write, fresh-read Next_Steps__c and stop for a changed baseline. Read Next_Steps__c back before its matching Task write, preserving all history.
Contact-only, meeting-prep and later milestone rows have no Opportunity next-step write. Read every changed record back, including `Description`. Verify every new Task field and every changed field
before `Verified in Salesforce`.
If a Task write fails after the next step was written, mark the row partial with the actual state of both sides and one corrective proposal. Never claim both applied.
Never repeat verified draft creation or a verified record write. Failed writes stay pending with the native error, actual state and one corrective proposal.
Skip an already-satisfied change without another note. No email is sent. Fresh reads are not an atomic lock or rollback mechanism.

**Receipts.** After approved writes, post the combined run receipt to Operator first with verified changes, skipped rows, partial pairs and failures.
Then send each affected deal thread a receipt of at most 3 lines with verified old/new Task links or partial results. Never ask it to act on triage items or ask Operator.
State the verified written next step and Task links in the receipt, never a request for another field or Task proposal.
Use the saved matcher session id. Send each deal receipt once with `pplx tm mail send <session id> "<message>"`.
Record the transport and outcome, never claim delivery without success.
Never wait, sleep or poll for a rate limit. A deal receipt never delays the run receipt or any write.
Run every `pplx` command as its own top-level line, never inside a script, function, loop or conditional, so its credentials apply.
List undelivered receipts in a follow-up line. Failed receipt delivery does not undo verified writes or authorize replay.

## Close

Fresh-query the run queue and run `closeout_check` with the current local-offset time. A nonempty due, overdue or undated queue still fails. Never loosen the helper or push dates to make it pass.
Show every remaining Task once with its blocker, missing evidence or explicit deferral. Ownership or a prepared action is not completion.
Report verified changes, partial pairs and remaining approvals in one combined receipt and remaining batch before deal receipts per "Writes" receipt instructions.
List any later undelivered receipts in a follow-up line. Keep native evidence in the sandbox.
Finish with `No emails sent.`. Daily notification suppression follows `references/daily.md`, never hides blockers, proposals or incomplete evidence.
