# Collect

Read at the Collect and Evidence steps. Save every result in the sandbox.

## Collect the run

1. Use the userId and owner email from `rules#run_start`.
2. Query every open Task the user owns due today, overdue, or undated. No count or date cap unless the user sets one in this run.
   ```sql
   SELECT Id, Subject, Status, ActivityDate, Description, WhoId, WhatId, What.Name FROM Task
   WHERE OwnerId = '<userId>' AND IsClosed = false AND (ActivityDate <= TODAY OR ActivityDate = null) ORDER BY ActivityDate
   ```
3. One Contact query over the distinct Contact `WhoId` values (Id prefix `003`): `Id, FirstName, LastName, Name, Email, Title, AccountId, Description, Account.Name`.
   Apply `references/grouping.md` "Pipeline ownership" before Contact-based routing. Other Lead-linked Tasks go to Hold. Other Tasks with no Contact go under `CRM corrections needed` only.
   A Contact with no email is grouped per `workspaces/pipeline/workflows/task-triage-speed-run/references/grouping.md` (recipient unconfirmed).
4. Read Opportunities linked by Task `WhatId`, and open Opportunities on Accounts linked by Task `WhatId`.
   Retrieve `Id, Name, AccountId, Account.Name, IsClosed, StageName, Next_Steps__c`. Apply the ownership order in `references/grouping.md` "Pipeline ownership".
   Search current project sessions by Account name with `pplx project sessions list --search` and verify the exact `<Account> deal` title before excluding current-action Tasks.
   An ambiguous title or unavailable search is needs-input. Never infer absence of a deal thread from a failed search.
   Read their open Tasks linked by Opportunity or Account `WhatId`, including future Tasks, with `Id, Subject, ActivityDate, Description, WhatId`.
   Use these records to identify the current-action Task per `rules#followup_task` and `references/grouping.md`. A Contact association alone is not a Task link to the Account.
5. Report only the Tasks in this run. Never report future-Task counts.

## Gather evidence

1. Gmail: search Contact addresses at most `policy.tooling.gmail_search_max_addresses` per call and follow every returned pagination cursor. On a timeout, retry once with a smaller batch.
   Never-replied, unanswered counts, and recycle are bounded by `rules#absence_conclusions`.
2. Run `policy.tooling.scripts.gmail_contact_stats <owner email> <saved_output_json...> --as-of <run start with local offset> --only <a@x,b@y>` on the saved `search_email` outputs.
   It prints per-address sent count, last sent date, last inbound date and type (`substantive`, `ooo`, `bounce`, `calendar`),
   unanswered count since the last substantive reply, and the newest non-bounce message and thread id. A `bounce` type means recipient unconfirmed.
3. Calendar: one search per Task from `policy.tooling.calendar_lookback_days` behind today to `policy.tooling.calendar_lookahead_days` ahead,
   with the Account names (Contact name when no Account) as queries, per `rules#calendar_search`.
   Use the evidence to decide whether a Contact is active per `rules#contact_status` and whether a named meeting happened or moved. Scheduling alone does not prove attendance.
4. Existing drafts: list drafts once. Match `thread_id` against the thread ids from item 2. Read a draft only when its thread id is unmatched and it is a new message.
   A Task note that says a draft exists is not evidence; the draft list and the sent mail from item 2 are.
5. Read each Task Subject and Description for the intended ask.
6. Prior email body: for every Task that may get a draft, read the full body of the thread's newest message (`newest_message_id` from item 2)
   and, when that message is Operator's, the newest inbound reply in the same saved output if one exists.
   Note the specific claim, offer, or question it made. Drafting from Task notes alone is not allowed.
7. Automatic date move candidates also require the full body of Operator's actual last sent message to that Contact and its timestamp from the saved search results.
   Match it to `gmail_contact_stats` `last_sent` and verify that it asked or offered something after the Task's newest note date.
   Use `last_substantive` and `unanswered_since_last_substantive` with the saved inbound evidence to check for a substantive reply since that send.
   The helper's `newest_message_id` may be inbound, so it is not a substitute for reading the qualifying sent body. Missing or incomplete evidence never qualifies an automatic move.
8. For each automatic move candidate, perform both bounded reply checks after identifying the qualifying send.
   Read the full Gmail thread containing that sent message, including every message body.
   The sent message or a later message from Operator must be newest after ignoring bounces, out-of-office, and calendar notices.
   This full thread read is a retrieved fact, not a relevance-ordered search. A substantive inbound since the qualifying send blocks the move even if Operator emailed again afterward.
   Run the targeted search below using the Contact address and qualifying sent date, follow every pagination cursor, and read and classify the returned messages.
   ```text
   from:<Contact address> after:<sent date>
   ```
   The search must return no substantive message. Both the full thread check and targeted inbound search must pass.
   Any tool error, timeout, unread thread, incomplete pagination, or substantive inbound in either check makes the row needs-input, not an automatic move.
   This bounded two-check standard is the only absence conclusion used by `rules#auto_date_move`. It does not prove never-replied history or authorize any other absence-based write.

## Slack replies

Read each run Contact over `policy.tooling.slack_lookback_days` per `_core/slack-evidence.md` "Search", "Limits", and "Reply receipts".
Search DMs, group DMs, and verified relevant shared channels using the exact Contact identity, not every Account contact.
Save reviewed reply receipts, then rerun `gmail_contact_stats` with `--slack-replies <reviewed.json>` in addition to its existing arguments.
Keep its Gmail counts and both item 8 checks unchanged. `slack_reply_blocks_auto_move=true` vetoes an automatic date move, never authorizes one.
A substantive Slack reply at or after the qualifying send blocks an automatic move and puts the Task in Reply received / manual response.
Earlier replies inform history but do not veto a later qualifying send. Pipeline-owned Tasks remain in Pipeline review owns regardless of reply source.
Cite returned permalinks for reply facts. Missing users, results, or retrieval completeness never proves absence or replaces the two Gmail checks.
