# Collect

Read at the Collect step. Save each query result in the sandbox. Deduplicate SELECT fields before querying.
For pagination, use only the exact cursor returned by that same search; continue until no `next_cursor` and retain all pages. Salesforce queries must also be complete.
Page one call at a time. Print only date, sender, subject, and snippet per message. The saved page stays whole.
Resume from the last `next_cursor`, never page one. Retry a failed page once with the same cursor, then record a gap per item 5.
`<userId>` comes from `rules#run_start`.

1. Opportunities. Record the original open count.
   Find active deal threads by Account name with `pplx project sessions list --search` in the current project.
   Verify the exact title `<Account> deal` for that Opportunity's Account, the same title check used in Task triage. Keep the verified session id and link.
   An ambiguous title or unavailable search is needs-input, not proof that no deal thread exists. Hold proposals on that record until ownership is verified.
   Verify the thread belongs to the resolved Opportunity. An Account title alone never assigns a Task among several possible Opportunities.
   On weekdays, also select `<policy.forecast.amount_field>` for Top 3 ranking, deduplicating it with the other fields.
   ```sql
   SELECT Id, Name, StageName, Amount, CloseDate, Next_Steps__c, ForecastCategoryName, Account.Name, AccountId,
          <each field under policy.pipeline.required_fields and policy.pipeline.early_required_fields, plus each policy.pipeline.conditional_fields field>
   FROM Opportunity WHERE OwnerId = '<userId>' AND IsClosed = false ORDER BY CloseDate
   ```
2. Tasks, Events, and Contacts for those deals. Retain undated open Tasks for action-reuse review; they do not establish activity. Last touch uses both Opportunity and Account linkage.
   ```sql
   SELECT Id, Subject, ActivityDate, Status, IsClosed, WhatId, AccountId, WhoId, Who.Name FROM Task
   WHERE (WhatId IN (<opp ids>) OR AccountId IN (<account ids>))
     AND (IsClosed = false OR ActivityDate = LAST_N_DAYS:<policy.pipeline.activity_query_days>)

   SELECT Id, Subject, ActivityDate, StartDateTime, EndDateTime, WhatId, AccountId, WhoId, OwnerId FROM Event
   WHERE (WhatId IN (<opp ids>) OR AccountId IN (<account ids>))
     AND (ActivityDate = LAST_N_DAYS:<policy.pipeline.activity_query_days> OR ActivityDate >= TODAY)

   SELECT Id, Name, Email, AccountId FROM Contact WHERE AccountId IN (<account ids>) AND Email != null

   SELECT OpportunityId, ContactId, Contact.Name, Contact.Email, Role, IsPrimary FROM OpportunityContactRole
   WHERE OpportunityId IN (<opp ids>)
   ```
   Account domains come from external Contact emails, excluding `policy.tooling.internal_domains` and `policy.tooling.generic_email_domains`.
   Use a verified Contact ID for Task linkage; a name alone is insufficient.
3. Run `policy.tooling.scripts.hygiene_check <opps> --tasks <tasks> --events <events> --as-of <run start with local offset> --json`.
   Its source receipts own mechanical triggers, last touch, and field checks. Event-only `new_activity` is displayed as elapsed, attendance unverified, never a write basis.
   Keep `task_review_required` and `open_task_candidates` for Task review per `workspaces/pipeline/workflows/pipeline-review/references/proposals.md` "Task review".
   `task_gap` is a trigger. Task review decides the fix; review `milestone_task_candidates` per `rules#followup_task` before retaining a later Task alongside the current follow-up.
4. Collect Gmail, Calendar, and Slack for deals in `policy.pipeline.stages`. Run the Slack section on both branches, even for deals not flagged by Gmail or Salesforce.
   Friday also includes every deal in `policy.pipeline.early_stages`, even without a mechanical trigger. Review enough dated buyer evidence to test `policy.pipeline.closed_lost_silence_days`.
   If the activity window is shorter than that threshold, extend the Friday Account-thread read to cover it. Incomplete retrieval never proves silence.
   After paging finishes, pass all saved output pages for each Gmail query together to `policy.tooling.scripts.gmail_digest`, keeping their paired `input_` files beside them.
   The digest is an index that cuts each body and marks the cut. Read the full body, by the `email_id` it prints, of any message a proposal rests on.
   Derive `new_activity` from these results per `workspaces/pipeline/workflows/pipeline-review/references/triggers.md`.
   For every flagged deal, record the newest message in either direction with its date, whether the user's last message was answered, and the next scheduled Event.
   No next-step proposal is built without this thread record.
   The freshest dated evidence across Gmail, Calendar, Salesforce, and Slack wins for each supported fact, not stale wording from another source.
   Calendar scheduling never proves an outcome. Put unresolved contradictions in questions rather than choosing an unsupported write.
   - Friday. For every in-scope Account domain, search `(from:@<domain> OR to:@<domain>) after:<policy.pipeline.activity_query_days ago>`, fully paged.
     Search Calendar by Account name over `policy.tooling.calendar_lookback_days` through `policy.tooling.calendar_lookahead_days`, per `rules#calendar_search`.
     These complete Account reads cover the narrower inbox scan, so do not run it. Also query the week's field history:
     ```sql
     SELECT OpportunityId, Opportunity.Name, Opportunity.Account.Name, Field, OldValue, NewValue, CreatedDate
     FROM OpportunityFieldHistory
     WHERE Opportunity.OwnerId = '<userId>' AND CreatedDate > <previous Friday run start> AND Field IN ('created', 'StageName', 'CloseDate')
     ```
   - Other days, including manual weekend runs. State the window from the previous scheduled run date (Monday starts last Friday).
     Run one inbox search `after:<that date>` minus `-from:<domain>` for every `policy.tooling.internal_domains`, and Calendar by in-scope Account name
     from that date through `policy.tooling.calendar_lookahead_days`, per `rules#calendar_search`. Keep only matching external Account domains.
     This scan finds triggers, not complete deal state. For every flagged deal, also read its domain thread in both directions with
     `(from:@<domain> OR to:@<domain>) after:<policy.pipeline.activity_query_days ago>`, fully paged, and use its Calendar results.
5. Coverage. Friday: `policy.tooling.scripts.coverage_check --scope pipeline --since <run start with local offset> --json`.
   Other days: `policy.tooling.scripts.coverage_check --scope pipeline-daily --since <run start with local offset> --hygiene <step 3 JSON output> --json`.
   Save the output in the sandbox; the report and notification both render from that file. Rerun and save again after evidence changes or a gap is repaired.
   Reconcile any unmatched or domain-unverified Salesforce Event before proposing on its Account; zero Account-name results cannot pass this check.
   Search its Subject or sweep the date range, splitting below `policy.tooling.calendar_result_cap`, match attendee domains, save results, and rerun per `rules#calendar_search`.
   Exit 1 means not ready: finish missing checks and rerun.
   If a gap cannot be resolved, label the report incomplete, disclose it, and withhold affected proposals. Do not silently exclude test-looking records or invent domains.
6. `not checked` per `rules#not_checked_means`. Whether the user's last message was answered, and the newest message, are bounded by `rules#absence_conclusions`.
   Preserve errors and reconciliation evidence. Subjects alone support metadata-only notes, not email-body conclusions.
7. Friday, only when Operator supplies a `pilot-usage` report in this thread. Take the `AccountId` from the item 1 Opportunity the report links or Operator names, never by matching a name.
   Run `SELECT Id, Name, Admin_Organization_UUID__c, Org_UUID__c FROM Account WHERE Id = '<AccountId>'` and save the result.
   No linked or named Opportunity in item 1, or no Account row returned, makes the report needs-input. This read feeds only the `rules#pilot_handoff` identity check.
   It reads no warehouse data and approves no write.

## Slack


For every in-scope deal, use its named buyer contacts from Contact Roles and `Customer_Point_of_Contact__c`.
Resolve that field to a verified Contact and email from saved Salesforce records. Read the Contact by ID when needed. An unclear identity or missing email is Slack not checked, never a name guess.
Deduplicate contacts per deal. Do not replace the named buyers with every Account contact.

Follow `_core/slack-evidence.md` "Search" and "Limits" for every selected contact.

- Slack is an added evidence source, not a required coverage gate. No Slack user or no Slack evidence means Slack not checked for that contact, listed in Coverage.
  Group contacts in one compact line per deal using `run.slack_coverage_notes` per `references/report-format.md` "Coverage".
  Missing identities and empty Slack results never set `run.process_status` to `incomplete` or withhold a proposal by themselves. They do not add to the deal-level not-checked count.
- Withhold a buyer-status or commitment change for a Slack limit only when a search errored or was incomplete for a contact on that deal with a verified Slack user.
  List the limitation in that proposal's section. Put the affected change in Needs your input with no write option until that search is repaired.
  Keep unrelated changes on the same deal and proposals on other deals eligible. Do not put the whole deal in `withheld` because of a Slack limit.
  If a row mixes status and unrelated changes, separate them before assigning proposal labels. Slack limits alone do not make the run incomplete.
- Positive Slack facts stay usable and win when fresher. Missing Slack evidence does not invalidate supported Salesforce, Gmail, or Calendar facts.
  Keep the Salesforce, Gmail, and Calendar checker behavior and its saved output unchanged. Slack notes do not repair or bypass its required checks.
