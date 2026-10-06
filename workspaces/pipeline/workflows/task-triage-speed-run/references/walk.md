# Readout and single pass

Read while preparing the full proposal, interpreting its one main-pass reply, and handling the remaining batch.

## Presentation

Work in chat with stable Task numbers and markdown links. Use group headings and flat, flush-left record blocks.
Escape the period after each Task number (`21\.`) so Markdown does not nest subsequent text inside an ordered list.
Never indent email metadata or bodies, use blockquotes, or put drafts in code fences. No forms, tables, or cards. Nothing is written outside Salesforce and Gmail drafts.

## Readout

One message, all groups in the order of `references/grouping.md`, every Task listed. With no automatic write attempted, open with `**N Tasks in this run.** Nothing created or changed.`
Otherwise state the verified `Auto-moved` count and any pending automatic writes. Never claim nothing changed after an automatic write. Other pending rows use this line format.
`n\. [Account · FirstName](<policy.salesforce.record_url>) · <action or date> · <reason>`

Show `Routed to deal threads` first with unnumbered Task, Opportunity and destination links, the owner and actual delivery or blocker.
These rows have no local Task or draft proposal and are excluded from every approval map. A routed Task remains open in Salesforce.
Then show `Pipeline review owns` with one unnumbered line per Task, linking the Task and its Opportunity. No date move or completion proposal appears in that group.
For ambiguous matches, link the candidate Opportunities and state the ambiguity. These Tasks have no Task write and are not counted in numbered approval maps.
Include eligible owned drafts in that ownership group as unnumbered draft-only rows identified by Task link, with their full draft blocks. Do not duplicate them in another group.
Number only the other Tasks continuously across the remaining groups. The readout is the full proposal, not a preview before separate group approvals.
Show every proposed row in full, including blocked rows and their reasons. Keep the original Task numbers and group order.
Include Complete and date-map rows with exact note lines, Hold date moves, Push or Recycle choices, and every draft with exact To, any CC, Subject, and full body.
Show each Push date and note, and each Recycle choice's Contact email, Task and Contact IDs, completion note, and exact cooldown marker changes.
Keep-today Hold rows stay visible with no write. Recycle remains needs-input until explicitly approved with its number.
For each numbered draft, also show the current-to-new Task date and exact note lines outside the email body, under the same Task number. Do not create a second numbered row.
Show `CRM corrections needed` last when present, marked for separate per-record approval after the main pass. The main reply never approves those records.
After `Pipeline review owns`, show verified `Auto-moved` rows without numbers, with Task links and old-to-new dates. They are receipts, not approval proposals.
Keep failed or unverified automatic writes visible as pending. Reread them before any later proposal, and do not count them as verified moves.
End with exactly one approval question for the main pass.
`Approve all eligible numbered rows, select numbers, give exceptions or date or wording changes, add approved with a Recycle number, approve owned drafts by Task link, or skip?`

## Section walk

Qualifying `rules#auto_date_move` rows are applied and read back before this section walk without a question. Skip verified `Auto-moved` rows in every approval map.
The readout asks for approval once for the full main pass, not once per group stage or once per draft and date map.
Accept `all`, selected numbers, exceptions by number, exact date or wording changes by number, or `skip`, in one reply per `rules#approval`.
`all` covers every numbered proposed row in the displayed pass except Recycle and CRM corrections. Blocked rows stay needs-input and are never approved by `all`.
It includes displayed Push actions, Complete rows, Hold date moves, and numbered drafts with their shown Task dates and notes.
For a row still needing a Push or Recycle choice, do not infer a choice from `all` or a bare number. Accept `Push` with its number to approve the displayed Push date and note.
Recycle needs the word `approved` with its Task number, which may be in the same reply as other approvals. `all` never covers Recycle.
For example, `all except 4, Push 7, approved 9` excludes row 4, chooses the displayed Push for row 7, and explicitly approves Recycle for row 9.
Only rows actually offered those actions qualify. A bare number never approves Recycle, and exceptions override `all` for the named rows.

`Pipeline review owns` has no Task approval stage. Its drafts stay unnumbered and draft-only. `all` excludes their drafts.
Approve an owned draft by its Task link in the main reply or a follow-up reply. That approval never authorizes its Task date, completion, or note.
Keep them in their ownership group in the readout and out of every date-and-note map.

1. Interpret the reply against the full displayed proposal. Apply exact approved date or wording edits only to the named rows.
   If a requested change is ambiguous or needs a rewrite not supplied verbatim, show that revised row in the remaining batch and wait for its approval. Other approved rows can proceed.
2. Execute all approved rows and read them back per `references/writes.md` "Writes". Do not ask for confirmation again per group, draft, date map, or record.
   An approved numbered draft row approves its displayed Task date and note. Create and verify the draft first, then write that Task date and note.
   A failed or unverified draft gets no Task date or note write and is reported. It does not block other approved rows.
3. Post one combined receipt for the approved pass, including draft results, verified record changes, skipped rows, and failures with their Task numbers or owned Task links.
4. Keep unapproved or failed rows together as one remaining batch with their original numbers, proposed changes, and reasons. Do not reopen verified rows or repeat successful writes.
   Accept a follow-up approval on that batch without re-walking the groups. Apply and read back its approved rows, then post one combined receipt and the updated remaining batch.
   An explicit request for one named item authorizes only that item. Reread any failed or unverified write before proposing a retry, never retry it automatically.
   `skip` declines the displayed batch. Record skipped or explicitly deferred rows with their reasons and do not ask for the same approval again.
5. After the main pass, ask CRM corrections one record per approval per `workspaces/pipeline/workflows/task-triage-speed-run/references/crm-corrections.md`.
   Neither `all` nor numbered main-pass selections approve a CRM correction.

For each date map, show the default computed per `workspaces/pipeline/workflows/task-triage-speed-run/references/grouping.md` directly, or the user's stated date,
with the exact note and current-to-new values.
Exclude pipeline-owned Tasks from every date move or completion map, including changes requested during the walk. Route their Task decisions to pipeline-review.
Accept date corrections by Task number in the same approval. A separate date-selection turn is unnecessary.
Only qualifying `rules#auto_date_move` rows bypass an approved map. Every other date needs the user's explicit approval in the displayed map.

Every row keeps or names a next step.
Complete a Task only when another open Task holds the account's next step,
or the note states why there is none and the Task is not a deal's last open Task per `rules#followup_task`. Otherwise keep it open with a new date and, when needed, a new Subject.
The run query returns only due, overdue, and undated Tasks. Before citing another Task as the next step, query the future ones and name the Task by Id in the Complete row:
`SELECT Id, Subject, ActivityDate FROM Task WHERE OwnerId = '<userId>' AND IsClosed = false AND ActivityDate > TODAY AND (WhatId = '<WhatId>' OR WhoId = '<WhoId>')`.
Date map row shape, flush-left, with Markdown hard line breaks:

```text
14\. [Account, FirstName](<Task URL>)  
Keep open. Move 9/28 to 9/30.  
Current next step: <Task Description first line, verbatim>  
Proposed next step: <new rules#note_prefix line, dated the write date, new due date in the sentence>
```

A Complete row reads `Complete.` on the second line, and its proposed line names the Task holding the next step or the reason there is none.
A Subject change adds `New subject is <Subject>.` to the second line.

Approval covers only the listed records and named fields. A change to one row does not reopen an approved row.

Draft block shape below; render the contents as flush-left chat text, not a code block or blockquote. Use Markdown hard line breaks between metadata lines and signature lines.
Separate blocks with a horizontal rule.

```text
21\. [Account · FirstName](<Task URL>)  
Prior email · <date> · <specific claim or ask>  
To · <email>  
CC · <emails, omit when empty>  
Subject · <exact subject>

Hi FirstName,

<Full proposed body>

Best,  
Operator
```

Before the main-pass approval question, check that every pending row across all groups appears exactly once as proposed or blocked,
that the displayed count matches those rows, and that there is only one main-pass approval question. There is no separate permission to walk the sections.
For a follow-up batch, check the remaining rows without re-walking or reopening verified rows. CRM corrections retain their separate per-record questions.
This is an instruction-level check, not a tool-enforced gate.
