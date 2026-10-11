# Deal activity reads

Native Salesforce and reviewed Gmail query templates shared by Pipeline review and Task triage. Keep unchanged query results in the sandbox, fully paged with no count cap.

## Opportunities

Use all owned open Opportunities for weekly or requested review. Queue triage reads owned open `policy.pipeline.stages` deals, plus `policy.pipeline.early_stages` on local Friday only.
Monday through Thursday leave early stages alone except already-due Tasks. Automatic Task gaps remain limited to `policy.pipeline.stages`, never the early-stage extension.
One-deal mode binds the selected Account to exactly one open Opportunity in `policy.pipeline.stages` or `policy.pipeline.early_stages`. Deduplicate SELECT fields before querying.

```sql
SELECT Id, Name, AccountId, Account.Name, Account.NumberOfEmployees, Description, IsClosed, OwnerId, StageName, Amount, <policy.forecast.amount_field>, CloseDate, Next_Steps__c, ForecastCategoryName,
       <each policy.pipeline.required_fields and policy.pipeline.early_required_fields field, plus each policy.pipeline.conditional_fields field>
FROM Opportunity WHERE OwnerId = '<userId>' AND IsClosed = false <selected scope filter> ORDER BY CloseDate
```

## Activity

Bind IDs to the selected Opportunities and their Accounts. These activity reads do not replace reschedule preflight's separate complete native related-open-Task reads.

```sql
SELECT Id, Subject, ActivityDate, Status, IsClosed, OwnerId, Description, LastModifiedDate, WhatId, AccountId, WhoId, Who.Name FROM Task
WHERE (WhatId IN (<opp ids>) OR AccountId IN (<account ids>))
  AND (IsClosed = false OR ActivityDate = LAST_N_DAYS:<policy.pipeline.activity_query_days>)

SELECT Id, Subject, ActivityDate, StartDateTime, EndDateTime, WhatId, AccountId, WhoId, OwnerId FROM Event
WHERE (WhatId IN (<opp ids>) OR AccountId IN (<account ids>))
  AND (ActivityDate = LAST_N_DAYS:<policy.pipeline.activity_query_days> OR ActivityDate >= TODAY)

SELECT Id, Name, Email, AccountId FROM Contact WHERE AccountId IN (<account ids>) AND Email != null

SELECT OpportunityId, ContactId, Contact.Name, Contact.Email, Role, IsPrimary FROM OpportunityContactRole
WHERE OpportunityId IN (<opp ids>)
```

Use native Opportunity, Task and Event records with `hygiene_check <opps> --tasks <tasks> --events <events> --as-of <run start with local offset> --json`.
Never relabel Gmail or Calendar search results as Salesforce records. Their added `new_activity` findings remain reviewed evidence from the caller's existing reads.
Retain source IDs and links. Elapsed Events prove scheduling, not attendance. A held call requires action evidence and duplicate review before claiming it is unlogged.

## Account-domain Gmail

Map each in-scope Account to verified external Contact email domains, excluding `policy.tooling.internal_domains` and `policy.tooling.generic_email_domains`. Never guess from Account names.
An unknown domain or ambiguous Account match is not checked and holds dependent proposals. A new sender at a verified Account domain is reviewed even without a known Contact address.
Queue triage scans incoming mail since the previous scheduled run date from `policy.pipeline.schedule.task_triage` in its timezone. Monday starts last Friday. State both window bounds.
Search `after:<previous scheduled run date>` with `-from:<domain>` for each internal domain, then retain incoming external messages whose sender domain exactly matches an in-scope Account domain.
Follow every returned cursor and save unchanged paired inputs and pages. A timeout retries once, then records the affected evidence gap, never an empty successful scan.
The inbox scan detects evidence, not complete deal state. For each flagged Account, read its domain thread both ways with the query below over `policy.pipeline.activity_query_days`, fully paged.

```text
(from:@<verified Account domain> OR to:@<verified Account domain>) after:<policy.pipeline.activity_query_days ago>
```

Weekly or requested pipeline review uses that same domain-thread query for every in-scope Account. Its wider reads cover the incoming scan, so it does not repeat the narrower scan.
Read the full body and relevant thread before using a message. Domain membership alone never proves a verified Contact, recipient, Task action or buyer intent.
Keep detections as reviewed Gmail `new_activity`, with source IDs and returned links, never Salesforce activity. Apply `rules#absence_conclusions` to every empty or partial retrieved set.
