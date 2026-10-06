# Rules

Shared operating rules two or more workflows follow, plus the permission exceptions kept here so they stay visible, rules#auto_date_move and rules#event_sequence.
One anchor per rule. Contracts cite `rules#<anchor>`.
Values live in `policy.yaml`. Any other rule one workflow follows lives in that workflow's folder.

## Salesforce writes

<a id="write_protocol"></a>**write_protocol**
- Fresh read immediately before each write.
- If that read shows a field or Task the proposal changes now differs from what it displayed, stop and re-propose from the current record. Approval never covers a change made after the proposal.
- Before a create (Task, Contact, draft, post), rerun the duplicate check that qualified it. On a match stop with `reuse existing`. Approval may be hours old.
- Write only the approved, displayed change. Read the record back and report the changed fields with its link.
- A rejected write is reported with the Salesforce message and one corrected proposal.
- Approval covers only the listed records and named fields, one record per approval unless a skill defines a batch.

<a id="note_prefix"></a>**note_prefix**
- Every note or Description change prepends one line starting with `policy.salesforce.note_prefix`. Existing text stays below it unchanged. Never overwrite history.

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
- In a workflow that writes both, a next-step change carries its Task change in the same proposal.
  Same action with a new date moves the Task. A new action completes the old Task and creates one, except a reviewed later milestone stays open. No current-action Task creates one.
- When the buyer owns the action, the Task is Operator's follow-up if it has not arrived, due on the buyer's date.
- Never complete a deal's current-action Task without its replacement in the same proposal. An extra open Task without a reviewed milestone is a question to keep or complete.
- A workflow that writes only one side, Tasks in `task-triage-speed-run`, leaves the match to `pipeline-review`, which flags it as `task_gap`.

<a id="next_steps_review"></a>**next_steps_review**
- `hygiene_check` extracts explicit on/by dates from the first dated entry, using its year for a yearless date. That is syntax, not proof of an action or owner.
  Verify both against the sentence and evidence.
- `REVIEW` means an invalid, missing, or ambiguous date. Resolve it before any date-based recommendation or write.
- Never use the leading written date as the deadline or infer an owner from the author initials.

<a id="stage_move"></a>**stage_move**
- Forward: propose when the target stage's `policy.pipeline.stage_entry` criterion is in evidence, quoted in one clause.
- Backward: propose only when evidence shows the current stage's criterion is no longer met. Missing retrieval is unknown, not evidence (`rules#absence_conclusions`).
- Closed Lost belongs to `pipeline-review`. Closed Won belongs to `close`.

<a id="close_date_basis"></a>**close_date_basis**
- A CloseDate proposal needs a buyer-named signature or decision date from any source, or a passed CloseDate with no such date (move to the next buyer-owned date).
- A trial or pilot end date alone is a milestone, never a CloseDate basis.

## Approval

<a id="approval"></a>**approval**
- A proposal applies only when Operator replies with its label as the report or question shows it (a number, range, letter, or option label), or `approved <label>` where the skill says so.
- Selecting a label approves only that label's displayed changes. A later edit needs a new proposal. Each approved write then follows `rules#write_protocol`.
- `skip` declines. `all` covers exactly the set the skill defines, never the whole run unless the skill says so.
- Skipped, declined, and needs-input items are named in the Close step, because the thread is the only record of them.

<a id="auto_date_move"></a>**auto_date_move**
- Disabled when `policy.template.auto_date_move` is false. Propose the date move and wait for exact approval.
- In `task-triage-speed-run` only, a Task date move to the next business day is pre-approved when Operator emailed the Task's Contact after the Task's newest note,
  that email asked or offered something, and no substantive reply has arrived.
- Apply it without a question, read it back per `rules#write_protocol`, and list it in the stage receipt as `Auto-moved` with its link.
- It never covers completions, other dates, drafts, recycles, CRM corrections, Opportunity fields, or a Task `pipeline-review` owns.

<a id="scheduled_runs"></a>**scheduled_runs**
- Scheduled runs land in-app, propose, then wait for approval in the run thread. A scheduled run behaves like a typed request.
- No reply writes nothing. The next run re-proposes from current Salesforce state.
- `rules#auto_date_move` is disabled in the template. Enabling it requires a separate exact rule review and approval.

## Evidence and tooling

<a id="run_start"></a>**run_start**
- Read the `_core/policy.yaml` blocks and `_core/rules.md` anchors the contract cites.
- Record one run-start ISO datetime with the user's local offset.
  Every helper's `--since` or `--as-of` takes it, except three checks that record and take a fresh local-offset time.
  The event_list_prep pre-enrollment reply recheck and the triage pre-write reply recheck also end their reply search at that time.
  The pipeline-review post-write `hygiene_check` uses it on re-queried records.
  A fresh time never changes scope, lookback, pagination, approvals or readback, and never authorizes a write.
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
  and its pre-enrollment recheck only.
  It does not establish complete history or authorize enrichment or enrollment. Its stated retrieval limit must appear in the enrollment proposal.

<a id="calendar_search"></a>**calendar_search**
- One `search_calendar` call per defined term over the window the contract states. The defined term is the Account name unless the contract adds attendee addresses.
- Terms match event titles, so an Account-name search returning zero is not evidence of no meetings.
  If in-window Salesforce Events remain uncorroborated, retrieve their Subjects or sweep the date range and match attendee domains.
- There is no cursor. A page holding `policy.tooling.calendar_result_cap` events is incomplete: split the window at that page's `end_date` and rerun until every page is below the cap.
  De-duplicate by `event_id`.
- Report `defined searches completed, no cap detected`, never `complete`.
- Where `coverage_check` runs, it corroborates Salesforce Events owned by the Opportunity owner against retrieved events by start time and attendee domain.
  An unmatched or domain-unverified Event fails readiness and Calendar coverage for that Account. Reconcile before proposing on it.
  A full match proves nothing about Calendar completeness.

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
- Windows of at most `window_days`, newest first, one request each. Stop at the first match. Never search past `lookback_days`.
- An error, timeout, or empty response for every window is reported as `Prior call transcripts not checked: <error or "no meetings in window">`. Never infer call content from a title.

<a id="email_body"></a>**email_body**
- One or two short sentences and one concrete question tied to the open thread or Task.
- Continue the prior email: restate its claim or ask in plain words and move it forward. Clear in five seconds without the thread.
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
