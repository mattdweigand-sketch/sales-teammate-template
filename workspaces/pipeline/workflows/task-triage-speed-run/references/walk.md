# Walk

## Presentation

Post one full proposal before asking. Every due, overdue or undated Task appears exactly once, numbered as proposed or blocked, including deal Tasks and the unthreaded Opportunity branch.
Use compact Task and Opportunity links, exact action evidence and source quotes. Keep unread evidence and ambiguous ownership labeled needs-input, never inferred from silence.
Prepare full Task follow-up drafts, including deal accounts, per `references/drafts.md`. Do not create them or write any record before approval.

## Readout

Post `top_actions --input <reviewed sandbox input> --sources <saved calls>` output unchanged first. Its candidate schema, source rules, ranking and limits live only in its docstring.
Build candidates from this run's existing Opportunity, Task, Event, Gmail, Calendar and Slack reads. Set coverage readiness and affected IDs from actual saved read review.
Missing or ambiguous reads withhold the affected deal. Unknown gap scope or incomplete process suppresses the whole Top 3, never creates an absence conclusion.
List every group from `references/grouping.md` with its count. Deal Tasks and unthreaded Opportunity Tasks stay in this same message, not a separate owner queue or approval.
Show Task gaps once as separate rows with source Opportunity, current next-step action and date, full new Task payload and no completion.
Future Tasks stay outside scheduled decisions per `rules#task_date_coordination`.
A completion row shows action evidence and the old Task Status and note. Name a verified existing next-action Task or show the new Task's Subject, date, OwnerId, WhatId, WhoId and Description.
For each deal current-action Task, show the exact current-to-new Next_Steps__c entry and complete Task payload together. Any history entry is displayed in that same row. One approval covers the pair.
For a draft-backed row, show the complete draft and the exact contingent next Task that first checks whether it was sent. No Task write happens until verified draft creation.
For a date row, quote its permitted source per `rules#task_date_coordination` and show current-to-new ActivityDate and the exact history-preserving note.
For a blocker, show the unchanged current date, intended action and missing evidence or prepared action. Never replace a blocker with a date roll.
No due Tasks after complete reads uses `No Tasks due.` but still shows any gap proposals. Incomplete reads never qualify. Never claim nothing changed after a verified write.

End with exactly one main-pass question:
`Approve all eligible numbered rows, select numbers, give exceptions or wording changes, add approved with a Recycle number, or skip?`

## Section walk

`all` covers every numbered proposed row in the displayed pass except Recycle and CRM corrections. Blockers and ambiguous ownership never gain authority from `all`.
Selecting a number approves only its displayed Task action or next-step plus Task pair, contingent draft, gap row or source-backed date and note.
No sending, other Opportunity field write or delegated Task approval.
Recycle needs `approved` with its number and remains subject to action evidence and next-Task gates. There is no Push option or date permission merely because Operator selects a row.

1. Interpret the reply against the full displayed proposal. Apply exact approved wording edits only to the named rows.
   A changed action, date without a qualifying source, unclear revision or unsupplied rewrite needs a revised row and fresh approval. Other valid approved rows may proceed.
2. Execute all approved rows and read them back per `references/writes.md` "Writes". Do not ask for confirmation again per group, draft, date map, or record.
   One approval covers draft verification, next-step write/readback, next-Task create/readback or verified existing replacement, then old-Task completion/readback. A failed or unverified draft
   gets no paired Task write.
3. Post one combined receipt for the approved pass to Operator before deal receipts per `references/writes.md` "Writes" receipt instructions.
4. Keep unapproved or failed rows together as one remaining batch with their original numbers, payloads and reasons.
   Accept a follow-up approval on that batch without re-walking the groups. Do not reopen verified rows or repeat successful writes.
   Reread any failed or unverified write before proposing a retry, never retry it automatically. `skip` declines the displayed batch. Do not ask for the same approval again.
5. After the main pass, ask CRM corrections one record per approval per `references/crm-corrections.md`.
   Neither `all` nor numbered main-pass selections approve a CRM correction. Missing prep-Task creates retain the separate explicit approval in `references/daily.md`.

Every completion needs matching action evidence and a verified next Task, per triage's limits in `rules#task_date_coordination` and one-sided `rules#followup_task`.
Name a verified existing next-action Task in the completion proposal. Future Tasks follow the scheduled and one-deal boundaries in that rule.
Never rename or date-roll the old Task to make it a different action. A Subject change for the next action belongs to the new Task.
Keep existing Description text below each approved `rules#note_prefix` line. Approval covers only the listed records and named fields.

Draft block metadata names the Task, prior email date and claim, To, CC, Subject and the full body and signature as flush-left chat text, not a code block or blockquote.
Before asking, verify every pending row appears once, the displayed count matches and there is one main-pass question. This is an instruction-level check, not a tool-enforced gate.
