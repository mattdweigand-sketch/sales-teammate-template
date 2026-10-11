# Collect

Read at the Collect and Evidence steps. Save every result in the sandbox.

## Collect the run

1. Use the userId and owner email from `rules#run_start`.
2. Query every open Task the user owns due today, overdue, or undated. No count or date cap unless the user sets one in this run.
   ```sql
   SELECT Id, Subject, Status, IsClosed, ActivityDate, LastModifiedDate, OwnerId, Description, WhoId, WhatId, What.Name FROM Task
   WHERE OwnerId = '<userId>' AND IsClosed = false AND (ActivityDate <= TODAY OR ActivityDate = null) ORDER BY ActivityDate
   ```
   This excludes future-dated Tasks. Future Tasks serve only the pre-create duplicate check, never this run's proposal maps. Missing or unreadable OwnerId holds the Task as needs-input.
   Fresh-read each candidate before proposing. Exclude it if now closed or future-dated. Save the complete native baseline per `rules#task_date_coordination`.
   For date proposals, read both related open Task sets and native Account and Opportunity links, review current-action IDs and run `task_reschedule_check --phase proposal` before display.
   Keep each unchanged native hasMore/totalSize/records result with its requested SOQL. Related queries use no LIMIT, OFFSET or due-date filter, even when the run queue is capped.
3. One Contact query over the distinct Contact `WhoId` values (Id prefix `003`): `Id, FirstName, LastName, Name, Email, Title, AccountId, Description, Account.Name`.
   Apply `references/grouping.md` "Pipeline ownership" before Contact-based routing. Lead-linked Tasks stay blocked. No Contact blocks an email recipient, not verified non-email action evidence.
   Missing Contact data needed for the action is a separate CRM correction. Never invent identity or complete a Task just because it lacks a Contact.
   A Contact with no email is grouped per `workspaces/pipeline/workflows/task-triage-speed-run/references/grouping.md` (recipient unconfirmed).
4. Read Opportunities linked by Task `WhatId`, and open Opportunities on Accounts linked by Task `WhatId`.
   Retrieve the shared "Opportunities" fields from `workspaces/pipeline/references/deal-activity-reads.md`. Apply the ownership order in `references/grouping.md` "Pipeline ownership".
   List all current project sessions with `pplx project sessions list <project> --limit <L> --offset <O>`, starting at 0 and advancing by L until a short page.
   Save each unchanged raw list bound to its requested offset in `pages` entries with `offset` and `sessions`, plus `limit`, `project_uuid`, and `accounts`.
   Each Account input has `account_id` and `account_name`. Run `deal_thread_match --input <sandbox.json>` before excluding current-action Tasks. Do not filter the project listing with `--search`.
   For every Account, including listed matches, call `session_list` with type `computer`, search `"<account_name> deal"` and limit `100`. A listing alone never proves absence or uniqueness.
   Save raw JSON in `account_searches` by account_id (null on failure or unavailable tool). Rerun the helper before routing or proposals. Missing search evidence never establishes an owner or local.
   Missing, failed, malformed or at-limit searches hold that Account only. Same-project exact matches merge by context_uuid with the listing. Ambiguity and collisions still hold.
   `owner` means triage calls `session_download_content` for the matched session id, then reads its `conversation.jsonl` itself, read-only. Save the exact session id, link and turns read.
   An unavailable or failed download tool leaves that thread context not checked. Never infer its contents.
   Send no message and wait for no reply before proposals. An unread or incomplete thread is a blocker, not permission to infer its next action.
   `local` follows the local or unthreaded Opportunity branch. `needs_input` or `incomplete` holds proposals on that record. Keep the session id for a short post-write receipt only.
   Read their open Tasks linked by Opportunity or Account `WhatId`, including future Tasks, with every native Task field required by `task_reschedule_check`.
   Identify current-action Tasks only from due, overdue or undated records per `references/grouping.md`. Future records serve only pre-create duplicate checks. A Contact alone is not an Account link.
5. Report only the Tasks in this run. Never report future-Task counts.

## Task gaps

Read the existing owned-open `policy.pipeline.stages` Opportunity scope and native activity per shared `workspaces/pipeline/references/deal-activity-reads.md` "Opportunities" and "Activity".
For each, read all related open Tasks on its Opportunity and Account with native OwnerId, IsClosed, ActivityDate, Subject, Description, WhoId and WhatId. No LIMIT, OFFSET or date filter.
Save unchanged native hasMore/totalSize/records results. Require hasMore false, count equal to records length and no error or paging contradiction before claiming a gap.
Review current-action equivalence without future Tasks. They never change gap decisions or dates. Immediately before a create, name an exact-action future duplicate instead of creating another.
Missing owner or linkage evidence holds the record. With no current-action Task, resolve the verified Contact Role and current next-step action and date, then propose a gap row.
Read matched deal context yourself, read-only. Prepare the next-step and Task row per `references/next-steps.md` "Draft" and "Findings". Unknown action, date or Contact stays needs-input.
Merge a Task gap with that deal's next-step row, never duplicate the action or count it as an extra due Task. They do not add future Tasks to the daily queue. No Task proposal goes to a deal thread.

## Friday early stages

On local Friday only, also read owned open `policy.pipeline.early_stages` Opportunities and native activity from the shared "Opportunities" and "Activity" sections.
Review their next steps once that week with the same "Draft" rules and paired approval as later stages, merging any already-due Task into one row. Monday to Thursday do not add this review.
Read buyer Gmail, Calendar and Slack evidence for those deals before proposing. A blank or passed entry is a review finding, never an inferred action or date.
An early-stage next-step proposal may name or create its approved matching current-action Task. Never emit automatic early-stage task_gap creates from this extension.
Keep missing actions, dates, ownership or incomplete reads blocked. Friday pipeline review's early-stage next-step findings remain read-only triage rows, not another proposal queue.

## Account-domain Gmail

For queue runs, apply shared `workspaces/pipeline/references/deal-activity-reads.md` "Account-domain Gmail" alongside known Contact searches, across every in-scope Account.
Page the incoming scan and flagged bidirectional domain threads. This includes a new stakeholder at a verified Account domain, not just known addresses or Contact Roles.
Save the reviewed newest message in either direction, unanswered status and next Event before drafting. A failed scan or unread flagged thread holds dependent pair proposals and ranking.
No sender address becomes a recipient or Salesforce Contact without verified identity. These results add reviewed Gmail evidence only, never native Salesforce activity.

## Gather evidence

1. Gmail: search Contact addresses at most `policy.tooling.gmail_search_max_addresses` per call and follow every returned pagination cursor. On a timeout, retry once with a smaller batch.
   Never-replied, unanswered counts, and recycle are bounded by `rules#absence_conclusions`.
2. Run `policy.tooling.scripts.gmail_contact_stats <owner email> <saved_output_json...> --as-of <run start with local offset> --only <a@x,b@y> --send-hold`
   on the saved `search_email` outputs.
   It prints per-address sent count, last sent date, last inbound date and type (`substantive`, `ooo`, `bounce`, `calendar`),
   unanswered count since the last substantive reply, and the newest non-bounce message and thread id. A `bounce` type means recipient unconfirmed.
   The optional hold output uses the latest actual sent timestamp and elapsed 24-hour periods. Equality releases the hold. Choose active or cold only from the verified Contact status.
3. Calendar: one search per Task from `policy.tooling.calendar_lookback_days` behind today to `policy.tooling.calendar_lookahead_days` ahead,
   with the Account names (Contact name when no Account) as queries, per `rules#calendar_search`.
   Within one run, collect each distinct term, window, and calendar identity once and reuse the result. Per-Task review, cap splitting, and fresh prewrite rereads stay.
   Use the evidence to decide whether a Contact is active per `rules#contact_status` and whether a named meeting happened or moved. Scheduling alone does not prove attendance.
4. Existing drafts: list drafts once. Match `thread_id` against the thread ids from item 2. Read a draft only when its thread id is unmatched and it is a new message.
   A Task note that says a draft exists is not evidence; the draft list and the sent mail from item 2 are.
5. Read each Task Subject and Description for the intended ask.
6. Prior email body: for every Task that may get a draft, read the full body of the thread's newest message (`newest_message_id` from item 2)
   and, when that message is Operator's, the newest inbound reply in the same saved output if one exists.
   Note the specific claim, offer, or question it made. Drafting from Task notes alone is not allowed.
7. For completion evidence, read the exact sent email, held-call source or reply proving this Task's action happened. Quote and link it, not just `last_sent` or a count.
   `newest_message_id` may be inbound and is not proof Operator completed an action. Missing evidence leaves the Task due or overdue; scheduled meetings do not prove attendance.
8. For a next Task following draft-only completion, read the exact saved draft id and thread and check sent mail for that draft. If not sent, flag `Draft not sent`, not a new follow-up.
   Compare verified To, CC, Subject, full body and thread with the actual sent message. A shared thread or similar text alone never proves that draft was sent.
   A missing draft read or ambiguous sent-message match is needs-input, never assumed sent. Existing drafts do not count as a draft triage created and verified in this approved pass.

## Slack replies

Read named buyer contacts on every in-scope deal, plus run Task contacts, over `policy.tooling.slack_lookback_days` per `_core/slack-evidence.md` "Search", "Limits", and "Reply receipts".
Resolve named buyers from Opportunity Contact Roles and Customer_Point_of_Contact__c to verified Salesforce Contacts and emails, reading a named Contact by ID when needed.
Deduplicate Contacts per deal. Search DMs, group DMs and verified relevant shared channels, not every Account contact. Page all identity and message cursors under the shared Search contract.
Slack watches never replace these reads. They miss app and bot messages and DM watches do not fire. The shared Search contract also excludes bots and limits usable shared channels.
Save reviewed reply receipts, then rerun `gmail_contact_stats` with `--slack-replies <reviewed.json>` in addition to its existing arguments.
Keep its Gmail counts unchanged. Use positive substantive Slack replies as linked action evidence only after matching the actual Task action; no helper flag authorizes a write.
Cite returned permalinks for reply facts. Missing users, results or retrieval completeness never proves absence. Ownership ambiguity remains a blocker regardless of reply source.

Use each Opportunity's verified Contact Role for existing Gmail and Calendar evidence reads, including flagged gap records without a due Task. Slack reads cover every in-scope deal above.
