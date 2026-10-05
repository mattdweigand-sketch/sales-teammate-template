# Writes and close

"Auto date moves" runs before the section walk. "Writes" applies to the approved full pass or remaining batch. "Close" runs once, at the end.

## Auto date moves

Apply only qualifying rows per `references/grouping.md` "Auto date moves" and `rules#auto_date_move`, before the section walk without a question.
Display each Task link, current and next-business-day dates, qualifying sent-message evidence, and the exact `rules#note_prefix` note line before writing.
Fresh-read the Task and recheck ownership and qualifying evidence immediately before writing. Rerun both bounded reply checks before the write.
Recheck Slack per `references/collect.md` "Slack replies" and rerun the helper with fresh reviewed receipts. Any substantive Slack reply at or after the send blocks the move.
For this triage pre-write reply recheck per `rules#run_start`, record a fresh local-offset time as the search window end and helper `--as-of`, not the original run start.
Apply the same lookback and pagination checks.
If the note, Contact, date, status, or evidence changed, skip and reassess without writing. A Task in `Pipeline review owns` never qualifies.
Require both the full thread read and fully paginated targeted inbound search per `references/collect.md` "Gather evidence" item 8 to pass.
Any tool error, timeout, unread thread, incomplete check, or substantive inbound since the qualifying send means needs-input with no automatic write.
Change only Task `ActivityDate` to the computed next business day and prepend the displayed reason to Description, keeping its history. No other field or action is pre-approved.
Date the new note with the run-start local date. It becomes the newest note, so the same sent email cannot qualify again.
If the Task already has that date, do not write or call it moved. Follow `rules#write_protocol` for each write and read both ActivityDate and Description back.
Combine verified results in the stage receipt as `Auto-moved` with each Task link, old-to-new date, and reason. Report failed or unverified writes as pending with the tool message.
Each verified receipt line names both `full thread read passed` and `targeted inbound search passed`, with the sent-message link and search window.
Never label an unverified write `Auto-moved`, never automatically retry it, and never include a verified move in a later date or completion map.

## Writes

Pipeline-owned current-action Tasks and ambiguous candidates per `references/grouping.md` get no Task write in triage.
Recheck ownership immediately before a Task write. If it is now pipeline-owned or ambiguous, skip it and add it to `Pipeline review owns` with its Opportunity link.
An approved Gmail draft for such a Task does not authorize a date move, completion, or Task note.

Apply approvals to the full proposal per `references/walk.md` "Section walk", never one approval per group or per draft and date map.
An approved numbered draft row covers its displayed Task date and note, but create and verify the draft per `references/drafts.md` before either Task write.
A failed or unverified draft gets no Task date or note write. Report it without blocking the other approved rows.
Recycle requires `approved` with its Task number. `all` never covers Recycle or CRM corrections, and an unresolved Push or Recycle choice authorizes no write.
CRM corrections follow the main pass with one record per approval per `references/crm-corrections.md`.

- Every Task change carries a note: a `rules#note_prefix` line on Task `Description` stating the change and the reason. Show it in the approved map or automatic move display.
- Date move: Task `ActivityDate` plus the note.
- Complete: Task `Status` = `Completed` plus the note.
- Recycle: complete the Task with its note, then prepend `policy.salesforce.cooldown_marker` to Contact `Description`, keeping existing text.
- Re-read each record immediately before writing. If its date or status changed since the proposal, skip it and say so.
- Read every changed record back, including `Description`. Report `Verified in Salesforce` only after readback. Report an unverified write as pending. A failed row does not block other rows.

Post one combined receipt for the approved pass, then keep unapproved or failed rows in one remaining batch with their original numbers or owned Task links.
Accept follow-up approval on that batch without re-walking. Reread failed or unverified writes before any retry proposal. Never repeat verified draft creation or a verified record write.

## Close

Before the close summary, re-run the `workspaces/pipeline/workflows/task-triage-speed-run/references/collect.md` "Collect the run" query and save the result.
Then run `policy.tooling.scripts.closeout_check <saved JSON> --as-of <run start with local offset>`; it exits nonzero when any open Task is still due today, overdue, or undated.
Report the helper's actual result, including a nonzero result when owned Tasks remain. Recheck their ownership on fresh Opportunity and Task records.
The triage run is complete only when the check passes or every remaining row has verified pipeline ownership or an explicit user deferral with its reason recorded.
List owned rows as handoffs to pipeline-review, not as completed or user-deferred Tasks. Keep ambiguous candidates in that handoff with the reason.
Report the final query result in the close summary. Any other remaining row without an explicit deferral needs a decision before close.

List: drafts created (unsent), Tasks completed, Tasks moved, Contacts recycled, CRM corrections applied, Tasks left for manual follow-through with reasons. End with `No emails sent.`
