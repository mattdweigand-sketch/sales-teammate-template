# Customer evidence

## Inventory

Use the current Salesforce user from `rules#run_start`. Account ownership, not Opportunity ownership, controls the review.
Scheduled inventory includes all owned customers, without a recent-win cutoff. On-demand adds the exact named Account Id or name predicate and reviews no other Account.

```sql
SELECT Id, Name, OwnerId, Admin_Organization_UUID__c, Org_UUID__c
FROM Account
WHERE OwnerId = '<userId>'
  AND Id IN (SELECT AccountId FROM Opportunity WHERE IsWon = true AND IsClosed = true
             AND (Deal_Type__c = null OR Deal_Type__c != 'Paid Trial'))
```

Fetch all pages. For these Account ids, query all Opportunities, not only won deals or Operator's deals.

```sql
SELECT Id, AccountId, OwnerId, Name, IsClosed, IsWon, StageName, Type, Deal_Type__c,
       CloseDate, Trial_Expiration_Date__c, Subscription_Cancel_Date__c, Renewed_from_Opportunity__c
FROM Opportunity
WHERE AccountId IN (<ownedAccountIds>)
```

Any open Opportunity still permits the milestone assessment, but routes recommended actions to Pipeline hygiene with no new Opportunity proposal.
List won and open Opportunity links. The anchor is the earliest verified non-trial Closed Won CloseDate; later wins never reset age.
Missing, invalid, future or conflicting anchor evidence is needs-input with no milestone computed. Paid Trial is excluded from the anchor.
Group by Account and keep all non-trial won Opportunity ids and subscription dates visible.
Do not sum historical purchases or collapse different contracts into one renewal date. Flag ambiguous or overlapping subscriptions for Operator.
Report unavailable pages as incomplete. Include held carry-forward Accounts in retrieval even when no new milestone falls in this window.

Pipeline confirmed on October 3, 2026 that `Opportunity.Subscription_Cancel_Date__c`, labeled Subscription End Date, is the renewal date.
Do not substitute other cancellation or deactivation fields, Account renewal dates, or automated renewal fields.

## Window and receipts

Use only fenced `customer_review_receipt` blocks in the scheduled run thread and Pipeline thread; their ids arrive in the prompt, never the contract.
Scheduled `--window-start` is the latest scheduled receipt's `as_of` in the scheduled run thread. A platform completed flag or a run without a receipt never advances window_start.
With no readable scheduled receipt, omit --window-start. The nominal run is the latest policy occurrence at or before as_of; start at the occurrence before that nominal run.
Late starts and no-receipt retries never collapse coverage to today's occurrence. Keep the actual run-start as_of and the renewal next-occurrence lookahead unchanged.
Use run-start for --as-of. The window is window_start exclusive to as-of inclusive in `policy.pipeline.customer_review.schedule.tz`.
Milestone dates are the anchor plus `policy.pipeline.customer_review.milestone_months` calendar months, clamped to month end and evaluated at local midnight.
Carry-forward is the previous scheduled receipt's held entries. Reviewed comes from both threads' reviewed entries; add receipt_date from each block's as_of, including on-demand blocks.
Only mode scheduled receipts in the scheduled run thread supply window_start. An on-demand as_of never advances that boundary.
An unresolved anchor may carry null milestone_months and milestone_date; keep it held until current evidence resolves the anchor, then select the latest due milestone.
Save those two derived JSON lists in the sandbox and pass --carry-forward and --reviewed. Missing or unread receipt evidence is not proof of review; report access gaps.
Suppress matching account_id, milestone_months and milestone_date, showing its receipt date. Held entries are due again, re-evaluated on current evidence, never silently dropped.
When several dates are due, including held dates, assess the latest only; earlier dates are superseded by that review. Preserve unresolved carry_forward_held in the final receipt.
On-demand selects one --account-id or --account-name and the latest milestone dated on or before today. It ignores reviewed suppression and never changes the scheduled window.
An explicit --milestone-months may reassess another policy milestone on or before today. Run in Pipeline or send its receipt there for scheduler suppression.
Renewal candidates include notice dates in this window and future dates through the policy's next occurrence, even without a milestone. Past notices never become past-dated Tasks.

## Usage

Match `Admin_Organization_UUID__c`, else `Org_UUID__c`. If both are present and differ, report both and stop that Account's usage. Missing ids stay needs-input.
Never find an org by name. Use an existing customer Contact email for `policy.tooling.org_lookup_tool` when billed seats or enterprise status need verification.
Require its `org_uuid` to match Salesforce. A mismatch holds usage. A failed billed-seat lookup alone makes seats unknown, not a hold when the Salesforce org and usage match.
Use `workspaces/pipeline/references/org-lookup.md` "Fields" to interpret `billing_quantity` and enterprise status.
Unknown enterprise status blocks expansion proposals. Members and roster seats never substitute for billed seats.
If billing quantity is missing, review the current subscription's OpportunityLineItems against the agreement rather than summing historical quantities.

```sql
SELECT OpportunityId, Product2.Name, Quantity, UnitPrice, TotalPrice
FROM OpportunityLineItem
WHERE OpportunityId IN (<reviewedCurrentSubscriptionIds>)
```

Mark billed seats unknown if current paid seat lines cannot be identified, and add a follow-up to verify seats. This does not hold the review. Never add credits or repeated subscriptions as seats.
For each resolved org, set data-through to yesterday in the warehouse timezone. Run the shared report queries 1, 1b, 2, and 3 in `workspaces/pipeline/references/pilot-usage-queries.md`.
Bind org id, fixed dates, policy window, sample cap, and internal-domain exclusions. Use `policy.pilot_usage.warehouse`, `async_exec: true`, and `timeout: null`.
Save each submit handle, poll it to terminal success, and fetch all partitions. Do not substitute handles across Accounts or orgs.
No slow-table query without the org and bounded dates. Report partial or failed reads as unknown, never zero.
Count roster seats as rows of query 1. Active users have window_queries above zero. Last-seven-day active users have l7_queries above zero.
Show query 1b's weekly trend and query 2's feature mix, plus idle seats as roster minus 60-day active users. Review query 3 for supported use cases, with sample day span and user count.
Complete usage means billed seats or explicit unknown, roster, 60-day and 7-day active users, weekly trend, idle seats and feature mix. Hold unreadable or incomplete usage, never unknown seats alone.
Do not print SQL or raw query text above `policy.pilot_usage.query_text_max_chars`. Activity does not prove demand, revenue, task completion, or available credits.

## Buyer evidence

Bind each selected Account and the helper's evidence_window before reads. Both modes read buyer evidence from the previous milestone date through as_of.
For the first milestone, start at the verified anchor. The scheduling window is not the buyer evidence window; a missing anchor or boundary stays not checked.
Read Salesforce Tasks, Events and notes for that Account and related deals within those dates. Search Gmail by its verified Contacts, fetch every page and full relevant threads.
For calls, load call-transcript-skill and apply `rules#momentum` and `policy.momentum`, including Account Id, window and lookback limits and error reporting.
Separate buyer statements from inferred interpretations. A failed or incomplete read is "not checked" with its dates. Buyer evidence is optional context and never holds the usage assessment.
If completed reads find no contact, flag "no recent buyer contact since <date>" with the dates searched and propose a check-in. Never claim absence from failed reads.

## Helper input

Keep all saved evidence and the normalized review JSON in the sandbox. Helper inputs are reviewed records, not independent proof of complete retrieval.
Run `policy.tooling.scripts.customer_review --input <sandbox_review_json> --as-of <run_start>` from the checkout. Optional --policy selects test policy.
Scheduled runs add receipt-derived --window-start, --carry-forward and --reviewed per "Window and receipts". On-demand adds exactly one Account selector, never --window-start.
The input has these keys.

| Key | Content |
|---|---|
| owner_id | Current Salesforce user id |
| accounts_complete, opportunities_complete | Boolean true only after every native page has been fetched |
| accounts | Account records from the owned inventory query |
| opportunities | All related Opportunity records, across all owners and stages |
| usage | Map keyed by Account Id, with org_uuid, data_through, complete, rows, weekly_trend, feature_mix and optional billed_seats |

Each usage entry's complete flag is true only after every selected report query succeeded and every partition was fetched.
Rows are query 1 dictionaries with user_email, window_queries, and l7_queries. A missing billed_seats is unknown, not zero.
weekly_trend holds query 1b rows with week_start, active_users and queries. feature_mix holds query 2 rows with kind, value, queries and users. Empty complete results are valid, not missing.
The helper sets usage_ready true only for due rows with a complete matching usage summary through yesterday. Buyer reads and unknown billed seats never block that boolean.
The helper rechecks org identity with `policy.tooling.scripts.account_usage`, ownership, open deals, date windows, and distinct usage counts.
It reports renewal notice dates from policy and leaves task_due_date null when the notice window passed. It never writes or approves records.
Stop on exit 2 or valid false and show the error. Unknown or invalid usage remains visible and blocks expansion proposals, not the independent renewal review.
Renewal Task proposals retain their existing Salesforce identity, date, duplicate, required-field, approval and readback gates.
