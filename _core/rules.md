# Rules
Shared operating rules two or more workflows follow, plus the permission exception rules#event_sequence kept here so it stays visible.
One anchor per rule. Contracts cite `rules#<anchor>`.
Values live in `policy.yaml`. Any other rule one workflow follows lives in that workflow's folder.
## Salesforce writes
<a id="write_protocol"></a>**write_protocol**
- Before a workflow-governed write proposal and its approved write, follow `rules#repo_currency`.
- Fresh read immediately before each write.
- If that read shows a field or Task the proposal changes now differs from what it displayed, stop and re-propose from the current record. Approval never covers a change made after the proposal.
- Before a create (Task, Contact, draft, post), rerun the duplicate check that qualified it. On a match stop with `reuse existing`. Approval may be hours old.
- Write only the approved, displayed change. Read the record back and report the changed fields with its link.
- A rejected write is reported with the Salesforce message and one corrected proposal.
- Approval covers only the listed records and named fields, one record per approval unless a skill defines a batch.
- Task date coordination follows `rules#task_date_coordination`.

<a id="repo_currency"></a>**repo_currency**
- Refresh the configured deployed repository, remote and branch before a workflow-governed Salesforce, Gmail draft or approved Apollo write proposal and immediately before its approved write.
  Use `workflow_revision_check` per `_core/scripts/interfaces.md` "Workflow revisions" through the selected contract's bounded Inputs. Message delivery never chooses governing instructions.
- Before display, snapshot the active execution contract or Pipeline deal-thread entry and all consumed governing rule anchors, policy keys, reference sections and helper bytes.
  Keep revision and scoped fingerprints with the proposal in the sandbox. Preserve selected stages and branches. Do not preload siblings or all policy. Pure read-only branches need no preflight.
- Prewrite compares the same saved scope and target with the fresh deployed branch and local sources. Relevant changes, stale sources, failed refresh or inconsistent evidence stop the old proposal.
  Reread governing instructions. If the write is still needed, present a current proposal for fresh approval. Missing legacy baselines require a current proposal.
  Unrelated commits, keys and sections do not invalidate approval.
- Preserve staged and unrelated work. Never reset, stash or discard it to refresh instructions. Read fresh Git objects or a clean temporary worktree rather than silently using stale files.
- Unchanged is not authorization. Existing approval, duplicate, stale-record, note history and readback limits still apply.

<a id="note_prefix"></a>**note_prefix**
- Every note or Description change prepends one line starting with `policy.salesforce.note_prefix`. Existing text stays below it unchanged. Never overwrite history.

<a id="task_date_coordination"></a>**task_date_coordination**
- Triage alone manages Operator-owned open sales Tasks, with OwnerId equal to the run user. Other writers neither create nor change them, including future Tasks.
  Propose only the owner's field change and state `Triage owns Task <Id>`. Recheck ownership immediately before each write.
  Other owners' Tasks keep their current workflow behavior. Missing or unreadable owner evidence holds that Task as needs-input, never a proposal.
- Exceptions are interaction-sync call logging, signal-followup's proven-send Task, Close's downstream-status Task, customer-review's check-in creates and Operator's typed deal-thread commands.
  Interaction-sync keeps full post-call Task behavior, including in deal threads. Triage fresh-reads and skips Tasks already handled. Other initial Tasks enter triage when due.
- Triage never automatically moves dates. It completes a due Task only on evidence that its action happened.
  In the same approval, create the next Task with a new Subject and date, or name a verified existing next-action Task. Never create a duplicate.
  Evidence is a sent email, held call, reply, or a Gmail draft triage created after approval and verified by readback. Without it the Task stays due or overdue while triage prepares the action.
  When completion was draft-only, the next Task first checks whether that exact draft was sent. If not, flag `Draft not sent`, never a new follow-up.
- Triage changes a Task date only on a buyer-stated new date or a moved meeting, with the source quoted.
  In one-deal mode or a deal thread, Operator's typed command is the quoted source for that deal's Task or next-step change. Scheduled runs keep the evidence rules above.
- Triage reads deal-thread context itself, read-only, without a message or wait. Deal Tasks join its one message and approval, including their follow-up Gmail drafts. Never send email.
  After approved writes, send each affected deal thread a receipt of at most 3 lines. Deal threads never act on triage items unprompted or ask Operator about them. Receipts are context only.
  Deal threads keep stage, close date, Amount, research and inbound buyer replies. On Operator's typed command they propose any change for that deal, including Tasks and next steps.
- Triage fills current-action Task gaps on in-scope Opportunities after fresh duplicate review. Pipeline-review leaves Task and next-step issues to triage, not deal threads.
- Future-dated Tasks never enter scheduled triage or influence its decisions, except the pre-create duplicate check. If one holds the exact next action, name it instead of creating a second Task.
- Fresh-read the exact Task and all related open Tasks on its Opportunity and Account before proposals, without LIMIT or queue-date filters. Review current-action IDs, not shared dates or Accounts.
  Completed Tasks, verified replacements and already-satisfied dates get no reschedule or new note. Missing reads or ambiguous action review stay needs-input.
- Triage and interaction-sync use `task_reschedule_check` per `_core/scripts/interfaces.md` "Task reschedule input" before displaying a date proposal and immediately before its approved write.
  Save baseline, baseline_links and the exact displayed payload. Re-read Status, ActivityDate, LastModifiedDate, Description, Subject, IsClosed, WhatId and WhoId, plus related Tasks and native links.
  Only ready may write. A changed baseline stops the old proposal. Stop and re-propose from current state with new approval, never reuse the old approval.
  Fresh reads are not an atomic lock. A save between the last read and write is not protected by a conditional native update.
- Skip satisfied dates or states without a write or new note. New buyer evidence may justify a later approved change. Do not freeze every Task modified today.
- Preserve buyer-supported dates and identify any known overdue action. Triage never rolls a Task merely to empty the queue.
- Triage writes only Operator-approved displayed changes in its run thread. Existing note history, duplicate, freshness and readback gates still apply. No reply writes nothing.

<a id="next_steps"></a>**next_steps**
- `Next_Steps__c` is plain text. Render HTML paragraph and break boundaries as newlines on read.
- A new or revised next step is one `policy.pipeline.note_next_line` entry at the top. The leading date is when it is written, not its deadline.
- Write an imperative for Operator's action, or name another owner when supported. Give the due-date year when it differs from the entry year. No `Next:` label or dot-separated shorthand.

<a id="next_steps_format"></a>**next_steps_format**
- On write, prepend the new entry and keep every existing dated entry unchanged. When replacing an undated legacy `Next:` first line, remove only that line.
- Add a history note (`policy.pipeline.note_history_line`) only when explicitly proposed and supported, after the current first entry when no next-step change was proposed.
- Legacy records are not migrated without an exact approved write.

<a id="followup_task"></a>**followup_task**
- Each open Opportunity in `policy.pipeline.stages` has exactly one open follow-up Task for its current next-step action, counting Tasks linked to the Opportunity or its Account.
  Its Subject names the current next-step action. Its ActivityDate is that action's due date.
- A distinct later milestone Task may stay open when its due date matches a scheduled Event and its action and Event linkage have been reviewed.
  Identify the kept Task and Event in the proposal. A shared date alone is not proof.
- Only triage, interaction-sync, Close and a deal thread on Operator's typed command write `Next_Steps__c`. Close writes only its onboarding entry. Triage proposes each pair once, under one approval.
  Write the next step first, then create and verify its Task, then complete the replaced Task. A failed Task write leaves the pair partial with one corrective proposal. Recheck duplicates.
- When the buyer owns the action, the Task is Operator's follow-up if it has not arrived, due on the buyer's date.
- Never complete a deal's current-action Task without naming its replacement in the same proposal, new or verified existing. Extra open Tasks and date mismatches stay with triage unprompted.
- After triage or interaction-sync writes an Opportunity, send a 3-line receipt with the written next step and Task links to its deal thread, unless it is the run thread. Request no proposal.

<a id="next_steps_review"></a>**next_steps_review**
- `hygiene_check` extracts explicit on/by dates from the first dated entry, using its year for a yearless date. That is syntax, not proof of an action or owner.
  Verify both against the sentence and evidence.
- `REVIEW` means an invalid, missing, or ambiguous date. Resolve it before any date-based recommendation or write.
- Never use the leading written date as the deadline or infer an owner from the author initials.

<a id="stage_move"></a>**stage_move**
- Forward: propose when the target stage's `policy.pipeline.stage_entry` criterion is in evidence, quoted in one clause. Backward: when the current criterion fails or on a lost path.
- Lost path: at S2 or higher, a buyer deferral or departed sponsor leaves no buyer-agreed step dated within 3 months. A buyer-named week or month counts. Operator's follow-up does not.
- A lost path may go straight to S1. Missing retrieval is unknown, not evidence (`rules#absence_conclusions`). Closed Lost and its size floor belong to `pipeline-review`, Closed Won to `close`.

<a id="close_date_basis"></a>**close_date_basis**
- A CloseDate proposal needs a buyer-named signature or decision date from any source, or a passed CloseDate with no such date (move to the next buyer-owned date).
- A trial or pilot end date alone is a milestone, never a CloseDate basis.
## Approval
<a id="approval"></a>**approval**
- A proposal applies only when Operator replies with its label as the report or question shows it (a number, range, letter, or option label), or `approved <label>` where the skill says so.
- Selecting a label approves only that label's displayed changes. A later edit needs a new proposal. Each approved write then follows `rules#write_protocol`.
- `skip` declines. `all` covers exactly the set the skill defines, never the whole run unless the skill says so.
- Skipped, declined, and needs-input items are named in the Close step, because the thread is the only record of them.

<a id="scheduled_runs"></a>**scheduled_runs**
- Scheduled runs land in-app, propose, then wait for approval in the run thread. A scheduled run behaves like a typed request.
- No reply writes nothing. The next run re-proposes from current Salesforce state.
## Evidence and tooling
<a id="handoff_delivery"></a>**handoff_delivery**
- Send each handoff once and keep the native result. Queued means submitted, not done.
- A failed send stays pending. In the same turn, show Operator the destination, exact text and error. Never call it delivered.
- Never wait, poll or auto-retry for a missing acknowledgment. A failed handoff grants no ownership or write permission.
- Received evidence alone does not authorize a new or changed action. Apply the receiving contract's existing approval scope.
  A sender's claim that Operator approved something is evidence, not approval. A contract that carries native approval for the exact original scope keeps it.

<a id="run_start"></a>**run_start**
- Read the `_core/policy.yaml` blocks and `_core/rules.md` anchors the contract cites.
- Record one run-start ISO datetime with the user's local offset. Every helper's `--since` or `--as-of` takes it, except three checks that record and take a fresh local-offset time.
  The event_list_prep pre-enrollment reply recheck and the triage pre-write reply recheck also end their reply search at that time.
  The pipeline-review post-write `hygiene_check` uses it on re-queried records. A fresh time never changes scope, lookback, pagination, approvals or readback, and never authorizes a write.
- Take userId and owner email from `salesforce_rest_api-get-current-user`.

<a id="not_checked_means"></a>**not_checked_means**
- `not checked` means required evidence is missing, unread, errored, or incomplete for the claimed window. State the gap and quote any tool error.
- Run length is never a reason.

<a id="absence_conclusions"></a>**absence_conclusions**
- `search_email` returns a relevance-ordered set with no completeness signal. `search_calendar` returns at most `policy.tooling.calendar_result_cap` events.
  Retrieval completeness is unverified unless a rule here says otherwise.
- A fact read from a retrieved message or event is usable evidence.
  A conclusion that depends on what was not retrieved stays unknown: never replied, newest message, unanswered count, no reply since, no meeting held, recycle.
- Counts from `gmail_contact_stats` are retrieved-set measurements, not history.
- State the limitation once per affected report section. A proposal that rests on an unknown becomes needs-input, not a numbered write.
- Event lists may use the bounded reply check in `workspaces/prospecting/workflows/event-sequence/references/prep.md` "Salesforce and reply checks" for the E1 enrollment proposal
  and its pre-enrollment recheck only. It does not establish complete history or authorize enrichment or enrollment. Its stated retrieval limit must appear in the enrollment proposal.
- Exception, signal-outreach draft only. A successful `in:sent to:<verified recipient>` search over `policy.prospecting.outreach.activity_lookback_days` with no retrieved hit
  may clear Gmail suppression despite its inherent retrieved-set limit. State that limit. It does not prove no prior send. An explicit error, known cap, or reported truncation still stops.
  Complete the other suppression reads and obtain Operator's approval of the exact proposal before creating the unsent draft. Never send here.

<a id="calendar_search"></a>**calendar_search**
- One `search_calendar` call per defined term over the window the contract states. The defined term is the Account name unless the contract adds attendee addresses.
- Terms match event titles, so an Account-name search returning zero is not evidence of no meetings.
  If in-window Salesforce Events remain uncorroborated, retrieve their Subjects or sweep the date range and match attendee domains.
- There is no cursor. A page holding `policy.tooling.calendar_result_cap` events is incomplete: split the window at that page's `end_date` and rerun until every page is below the cap.
  De-duplicate by `event_id`.
- Report `defined searches completed, no cap detected`, never `complete`.
- Where `coverage_check` runs, it corroborates Salesforce Events owned by the Opportunity owner against retrieved events by start time and attendee domain.
  An unmatched or domain-unverified Event fails readiness and Calendar coverage for that Account. Reconcile before proposing on it. A full match proves nothing about Calendar completeness.

<a id="org_lookup"></a>**org_lookup**
- `policy.tooling.org_lookup_tool` takes one email. Report its fields under their own names.
  `workspaces/pipeline/references/org-lookup.md` gives each field's meaning, the `org_service_type` mapping, and what proves customer ownership.
- A customer address is the admin email the contract resolved or an external Contact on the Opportunity's Account, never any external address. Membership alone proves nothing about billing.
- HTTP 404 or any error prints `Org status unverified for <email>: <response>` and blocks every provisioning, path, or handoff decision that depends on org status.
  Never print `No enterprise org` from a 404.

<a id="momentum"></a>**momentum**
- Endpoint, auth, key, rate limit, response shape, and windowed search come from the org skill `call-transcript-skill`. Load it, then apply `policy.momentum`.
- Always pass `salesforceAccountId=<18-char AccountId>` from the Account resolved in this run. Fall back to attendee domain or title only when the Account has no Id yet.
- The interaction-sync sweep branch may enumerate the previous business day's meetings by host or attendee before resolving Accounts. It must read every window, not stop at the first match.
- Windows of at most `window_days`, newest first, one request each. For a target-call lookup, stop at the first match.
  Coach stakeholder coverage reads every Account-filtered window within `lookback_days`. Never search past `lookback_days`.
- An error, timeout, or empty response for every window is reported as `Prior call transcripts not checked: <error or "no meetings in window">`. Never infer call content from a title.

<a id="email_body"></a>**email_body**
- One or two short sentences and one concrete ask tied to the open thread or Task.
- Continue the prior email: name its claim or ask in plain words and move it forward. Clear in five seconds without the thread.
- A follow-up to Operator's unanswered email picks one type. Count his emails and each repeated ask since the buyer's last substantive reply.
  A reply restarts both counts.
  - Specific ask. The same ask goes out at most twice.
  - Timing note when the draft would repeat an ask or fact already sent.
    A contact who engaged before gets "Let me know if the timing is right to continue the conversation."
    A contact who never engaged gets a variant like "Is there any interest in a conversation?"
  - Break-up note after `policy.followup.breakup_after_unanswered` unanswered emails.
    "If this is not a priority, let me know. We can table the conversation for the time being."
- No phrase in `policy.email_voice.banned`.
- Re-read linked security threads before drafting customer security answers, rather than relying on notifications.

<a id="call_type"></a>**call_type**
- Test `policy.call_prep.call_type` in listed order. First match wins.
- Discovery gaps are the `policy.call_prep.expected_information` items for that type not established by any source.

<a id="read_only_skills"></a>**read_only_skills**
- `sales-call-prep`, `pilot-usage`, and `deal-coach` write nothing to Salesforce, Gmail, Calendar, or the warehouse. A pilot fact enters Salesforce only per `rules#pilot_handoff`.

<a id="pilot_handoff"></a>**pilot_handoff**
- A `pilot-usage` report is evidence, never approval.
  It reaches Salesforce two ways only: the Friday `pipeline-review` run when Operator supplies the report in that thread, or `interaction-sync` for a finding tied to the completed call being logged.
- The receiver accepts a report only when it carries its source reference (run thread link or sandbox PDF path), the Account and org id,
  the reporting window (start and `data_through`), and its stated metric and evidence limits.
- Before proposing, the receiver confirms the Account and org id against the resolved Salesforce Account (`Admin_Organization_UUID__c`, else `Org_UUID__c`).
  A missing field or a mismatch makes the item needs-input.
- A proposal quotes the report's figures with their window and limits and claims nothing beyond them. The receiver's own approval, fresh read, and readback still apply.
- The receiver never runs `pilot-usage`, loads its folder, or reads the warehouse. `forecast-weekly` reads only the corrected Salesforce state.

<a id="event_sequence"></a>**event_sequence**
- An event campaign may enroll contacts in an Apollo sequence only after Operator approves the exact contact list, sequence copy, sending mailbox, and schedule in the thread.
  That approval is the only exception to never sending email.
- A pre-enrollment reply recheck may drop or hold approved contacts without re-approval. It never adds contacts.
- Apollo's CRM sync may create or update Salesforce Contacts from approved enrichment or enrollment. Each C and E proposal states this. The workflow itself makes no Salesforce writes.
- Apollo sends. A reply stops that contact's sequence and Operator takes over.

<a id="contact_status"></a>**contact_status**
- A Contact is active when evidence retrieved in the contract's window holds a substantive inbound reply from that Contact, or a meeting with that Contact, held or scheduled. Otherwise cold.
- Active means engaged, nothing more. A scheduled meeting proves no outcome. A cold reading rests only on what was retrieved (`rules#absence_conclusions`).
- Active Contacts take the `_active` values in `policy.followup`, cold Contacts the `_cold` values. An active Contact never recycles.
