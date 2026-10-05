# Resolve and pull

Read at the Resolve and Pull steps. Query bodies live in `workspaces/pipeline/references/pilot-usage-queries.md`.

## Resolve the pilot

One pilot per run. Prefer an explicit Opportunity Id. Otherwise ask for an Account and resolve exactly one eligible pilot.
An open paid trial or Opportunity with a trial end date is eligible unless its trial end date has passed.
A Closed Won paid trial is eligible only when `Trial_Expiration_Date__c` is today or later. Closed Lost and expired trials are ineligible.
Use the run-start Pacific date for today. With no Opportunity Id or Account, ask before running anything.

```sql
SELECT Id, AccountId, OwnerId, IsClosed, IsWon, Name, StageName, Amount, Deal_Type__c, Trial_Expiration_Date__c, Next_Steps__c, Owner.Name,
       Account.Name, Account.Admin_Organization_UUID__c, Account.Org_UUID__c
FROM Opportunity
WHERE OwnerId = '<userId>' AND Account.Name LIKE '<name>%'
  AND (Deal_Type__c = 'Paid Trial' OR Trial_Expiration_Date__c != null)
  AND (IsClosed = false OR (IsWon = true AND Deal_Type__c = 'Paid Trial' AND Trial_Expiration_Date__c >= <today>))
```
For an explicit Id replace only the Account-name predicate with `Id = '<opportunityId>'`. Use an exact AccountId predicate when supplied. Fetch all pages.
Save the complete record list in the sandbox. Run `policy.tooling.scripts.pilot_resolve` with `--input`, `--owner-id`, `--as-of`, and the supplied selector. See `--help` for arguments.
`--input` takes only the saved records list (a JSON array), not the full query response. Extract and combine the records from all completed pages before saving it.
More than one eligible match, ask. Org id is Admin first, otherwise Org. Differing ids stop with both shown. Neither set stops with `org id missing in Salesforce`.
Do not guess an org by name. In `pdf` mode, `Trial_Expiration_Date__c` null stops the run with `Trial_Expiration_Date__c missing`.

## Pull

Resolve `data_through` before SQL: yesterday in the warehouse timezone, or the requested historical date; in PDF mode cap the default at `Trial_Expiration_Date__c`.
Substitute the resolved org and dates and the policy values per `workspaces/pipeline/references/pilot-usage-queries.md`.
Run with `async_exec: true` on `policy.pilot_usage.warehouse`, `timeout: null`.
Record each returned submit handle; poll it to a terminal result and fetch every partition.

- `report`: submit independent queries 1, 1b, 2, 3, then poll. Handle failures per the report format.
- `pdf`: submit independent queries 1 and 4. Wait for grants.
  Put the resolved Salesforce metadata and `data_through` into the local review file with `approved: false`, then run the build helper's `window` action from the PDF reference.
  It writes the derived `pilot_start` into that file, the earliest non-voided grant on or before `data_through`.
  A `pilot_start` already in the file is kept as a reviewed override; use one only for a repeat pilot whose earlier grants are not this pilot, and say so in the review.
  Submit query 5 using these exact start/end dates. Any failed or incomplete selected result stops; never substitute another handle.
