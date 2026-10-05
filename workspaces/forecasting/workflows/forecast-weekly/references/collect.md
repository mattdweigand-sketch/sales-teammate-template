# Collect

Read at the two Collect steps. Save every result in the sandbox.

## Salesforce

- Booked, open in quarter, and next quarter. Next-quarter S2+ rows with `policy.forecast.amount_field` set are pull-in scope; all next-quarter rows feed the preview
  when within `policy.forecast.next_quarter_preview_days` of quarter end.
  ```sql
  SELECT Id, Name, Amount, <policy.forecast.amount_field>, CloseDate, Account.Name FROM Opportunity
  WHERE OwnerId = '<userId>' AND StageName = 'Closed Won' AND CloseDate = THIS_QUARTER

  SELECT Id, Name, StageName, Amount, <policy.forecast.amount_field>, CloseDate, Next_Steps__c, ForecastCategoryName, AccountId, Account.Name FROM Opportunity
  WHERE OwnerId = '<userId>' AND IsClosed = false AND CloseDate = THIS_QUARTER

  -- next quarter: same fields, CloseDate = NEXT_QUARTER
  ```
- Tasks and Events for the deals above.
  ```sql
  SELECT Id, Subject, ActivityDate, Status, IsClosed, WhatId, AccountId, Who.Name FROM Task
  WHERE (WhatId IN (<opp ids>) OR AccountId IN (<account ids>)) AND ActivityDate != null
    AND (IsClosed = false OR ActivityDate = LAST_N_DAYS:<policy.forecast.activity_days>)

  SELECT Id, Subject, ActivityDate, StartDateTime, EndDateTime, WhatId, AccountId, OwnerId FROM Event
  WHERE (WhatId IN (<opp ids>) OR AccountId IN (<account ids>))
    AND (ActivityDate = LAST_N_DAYS:<policy.forecast.activity_days> OR ActivityDate >= TODAY)
  ```
- Run `policy.tooling.scripts.hygiene_check <opps> --tasks <tasks> --events <events> --as-of <run start with local offset> --json`.
  Use its `next`, `newest_note`, and `last_activity` values only, reading `next` per `rules#next_steps_review`.
  The Opportunity query omits `policy.pipeline.required_fields`, so its blank-field lines are not evidence here.
- Record counts. A query that errors stops the run; quote the message.

## Calendar and Gmail

Evidence scope: every S2+ deal with CloseDate in the current quarter, plus next-quarter S2+ deals with `policy.forecast.amount_field` set. Never fall back to Amount. For each Account in that scope:
- Contacts: `SELECT Id, Name, Email, AccountId FROM Contact WHERE AccountId IN (<in-scope account ids>) AND Email != null`.
- Calendar: per `rules#calendar_search`, the Account name as the defined term, `policy.tooling.calendar_lookback_days` back to `policy.tooling.calendar_lookahead_days` ahead.
  Record held meetings and accepted upcoming ones.
- Gmail: one search per Account, `from:@<account domain> after:<quarter start>`, then by Contact name when empty (`policy.forecast.gmail_query`). Page until no `next_cursor`.
  On a timeout, rerun that query once with `after:<run date minus policy.forecast.activity_days>`, never the full window.
  A successful rerun counts as checked for bucketing, and the report's Not checked line names the Account and the unread earlier window.
  A second timeout is `not checked` per `rules#not_checked_means`.
  After paging finishes, run `policy.tooling.scripts.gmail_digest` with all saved output pages for the query together, keeping their paired `input_` files beside them.
  The digest is an index. It cuts each body and marks the cut. Before recording a timing statement, order form status, or blocker,
  read the full body of the message that carries it, by the `email_id` the digest prints.
  Record last buyer message date, timing statements, order form status, blockers. Last buyer message date and any no-reply reading are bounded by `rules#absence_conclusions`.
- `not checked` per `rules#not_checked_means`.

## Slack

Use the same shared method as pipeline-review, `_core/slack-evidence.md` "Search" and "Limits", over `policy.tooling.slack_lookback_days`.
For every deal in the Calendar and Gmail evidence scope, read its named buyers from Contact Roles and `Customer_Point_of_Contact__c`.
Select that field in the open Opportunity queries, then query `OpportunityId, ContactId, Contact.Email` from `OpportunityContactRole` for those Opportunity IDs.
Resolve the customer point of contact to a verified Contact and email by ID as needed. Deduplicate per deal, never substitute every Account contact.
Read DMs, group DMs, and verified shared-channel deal messages even when Gmail or Salesforce flags no gap.
Fresher positive Slack evidence may change a bucket or proposal. Missing Slack alone never changes the bucket or invalidates other supported facts.
Report sender, date, supported fact, and returned permalink with each used fact. List Slack not-checked limits separately from the mandatory coverage checker.
A verified user's failed or incomplete search withholds only the affected buyer-status or commitment change, not unrelated proposals or the whole run.
Keep `coverage_check`'s required Salesforce, Gmail, and Calendar checks unchanged.
