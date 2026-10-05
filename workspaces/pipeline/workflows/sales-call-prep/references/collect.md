# Collect

Read at the matching Process step. Each section is one source. Save every result in the sandbox.

## Resolve the calls

- Named person or company: calendar search by name, `policy.tooling.calendar_lookback_days` behind to `policy.tooling.calendar_lookahead_days` ahead.
  If no event, prep from Salesforce and say `No meeting found on the calendar.`
- Window ("today", "tomorrow", "this week", "each of these"): calendar search over that range. Keep events with at least one attendee whose domain is not in `policy.tooling.internal_domains`.
- Calendar retrieval per `rules#calendar_search`. Record per call: title, start, duration, link, external attendees with emails, internal attendees, booking-form text if present in the description.

## Salesforce

Per call, in this order, batching where possible:
1. Contacts by attendee email: `SELECT Id, Name, Email, Title, AccountId FROM Contact WHERE Email IN (<emails>)`. No match: search by name, then Account by email domain. Report unmatched attendees.
2. Account: Name, Website, Industry, NumberOfEmployees, Description, OwnerId.
3. Open Opportunities on the Account: Id, Name, StageName, Amount, CloseDate, Next_Steps__c, Deal_Type__c, Trial_Expiration_Date__c.
   Also read the most recent Closed Won Opportunity even when an open deal exists, so an expansion does not hide customer history; if neither exists, read the most recent closed Opportunity.
   Retain their IDs for activity queries; build `<activity WhatIds>` from the Account ID plus only the resolved Opportunity IDs.
   An active pilot needs current supporting evidence, not merely a populated expired trial date.
4. Activity in the last `policy.call_prep.history_days` days on the Account, resolved Opportunities, and Contacts, newest first. Three queries:
   ```sql
   -- notes and calls
   SELECT Subject, ActivityDate, Status, TaskSubtype, Description FROM Task
   WHERE (WhatId IN (<activity WhatIds>) OR WhoId IN (<ContactIds>)) AND (NOT Subject LIKE 'Email:%')
     AND ActivityDate = LAST_N_DAYS:<history_days> ORDER BY ActivityDate DESC

   -- logged emails: the same query with Subject LIKE 'Email:%'. These are long; read only the newest one per attendee for the full thread.

   SELECT Subject, StartDateTime, EndDateTime FROM Event
   WHERE (WhatId IN (<activity WhatIds>) OR WhoId IN (<ContactIds>)) AND StartDateTime = LAST_N_DAYS:<history_days> ORDER BY StartDateTime DESC
   ```
   A completed live call is a completed Task with `TaskSubtype` = 'Call', or an elapsed Event confirmed by such a Task or a transcript found in "Prior calls". Note whether one exists.
5. Flag record problems you see (wrong Account name, Closed Lost while active, missing Contact) under `CRM notes`. Do not fix them here.

## Gmail

Search attendee addresses, at most `policy.tooling.gmail_search_max_addresses` per call, following every returned pagination cursor.
An old Salesforce email log does not establish Gmail freshness; compare the newest source messages before choosing context.
Run `policy.tooling.scripts.gmail_contact_stats <owner email> <saved_outputs...> --as-of <run start with local offset> --only <a@x,b@y>` for counts and the newest thread.
Counts and newest-thread claims are bounded by `rules#absence_conclusions`. Read only the newest thread's messages for what was promised, asked, or sent.

## Prior calls

Search Momentum per `rules#momentum`. Take: date, attendees, buyer-stated facts as short quotes, commitments by either side, open questions.
If the search errors, write `Prior call transcripts not checked: <error>` per `rules#not_checked_means`.

## Example Product footprint

Call `policy.tooling.org_lookup_tool` for each external attendee email per `rules#org_lookup`.
Report `org_name`, `org_service_type`, `billing_status`, `billing_quantity`, and `member_count` as returned. A 404 or error writes `Org status unverified for <email>: <response>`.
Do not infer usage from seat requests or booking forms.

## Public research

Web search the company and each external attendee.
Keep at most `policy.call_prep.research_sources_max` dated sources per company: strategy, leadership changes, AI or data initiatives, funding or earnings, incumbent tools.
Person: current title, tenure, public statements. Cite each with a link and date. Drop anything you cannot date.
