# Customer review and proposals

## Review

Review the helper's inventory against native results. It is a mechanical check, not evidence of demand or approval.
Report billed seats or unknown, roster seats, active users over `policy.pilot_usage.window_days`, last-seven-day active users, weekly trend, idle seats, feature mix and supported use cases separately.
Assess only due milestones, in a few lines followed by numbered recommended actions. Already-reviewed matches show the receipt date, not a repeated scheduled assessment.
- 3 months, Adoption: billed versus roster versus 60-day and 7-day active users, weekly trend, idle seats, feature mix, buyer-reported barriers and support needs.
- 6 months, Value and growth: buyer-stated results, usage trend and any buyer evidence for more seats. Billed seats stay distinct from roster and activity.
- 12 months, Account health: sustained value, declining use or other risks, champion changes, open support issues, next-year plans and the actual subscription end date when known.
Read buyer evidence from the previous milestone date, or the anchor for the first milestone, through as_of in both modes. Unread sources are not checked. Recommendations are not demand inference.
Complete usage presented completes the review. Unknown billed seats need a follow-up to verify seats, not a hold.
Hold unreadable usage, including org mismatch, failed or incomplete queries or stale data.
Buyer context is optional. Failed reads are "not checked". No contact found becomes "no recent buyer contact since <date>" with dates searched, never a hold or invented absence.
End each assessment with numbered follow-ups drawn from usage facts and cite the numbers.
Propose training for idle seats, a seat conversation near or above billed seats, or declining-trend health checks.
Include a check-in for no recent contact. Add no fixed numeric threshold. Follow-ups may become Salesforce Task proposals with the existing approval, duplicate check and native readback gates.
Do not infer more purchased seats from members alone. No Gmail drafts or outreach.
When activity and buyer evidence support more seats, explain that evidence and the proposed increment. Show any idle seats, alternative adoption work, and uncertainty.
Expansion Opportunity proposals still require buyer evidence for demand. No expansion proposal for unknown enterprise status, mismatched org, incomplete usage, or any open Opportunity.
With any open Opportunity, the assessment remains read-only and recommended actions, including renewal work, hand off to Pipeline hygiene rather than new record proposals here.

For each reviewed current subscription, use `Opportunity.Subscription_Cancel_Date__c` for Subscription End Date.
Verified Salesforce subscription dates remain review evidence when org or usage is missing or conflicting. Unknown usage stays null and blocks expansion, not independent renewal evidence.
Renewal evidence is not automatic Task creation or proof that all proposal prerequisites are satisfied. Retain every Salesforce identity, date, duplicate, required-field, approval and readback gate.
Task due date is end date minus `policy.pipeline.customer_review.renewal_notice_days` calendar days. Scheduled future notices are bounded by the next policy occurrence.
The 12-month milestone never sets or substitutes for the subscription end date. Renewal notices remain independent even without a due milestone.
If notice is before today, report notice window passed with the subscription end date. Do not move it to today or invent a new date. Operator decides the follow-up.
Missing or ambiguous end dates stay needs-input. A trial end date is not the subscription renewal date or an expansion CloseDate.
Read renewal Opportunities linked by Renewed_from_Opportunity__c and open Tasks before proposing. Existing renewal work is linked, not duplicated.

## Numbered proposals

Every write is its own numbered proposal under `rules#approval`. `all` covers only the exact numbered ready proposals in this report.
Each proposal shows object, create or update, exact fields, current values for updates, evidence links, reason, duplicate check, and anything still unknown.
Items needing missing required fields are questions, not ready proposals. Changed fields after approval need a new numbered proposal.

An expansion Opportunity uses the reviewed AccountId, current OwnerId, `policy.pipeline.customer_review.expansion_type` for Type, and `policy.pipeline.customer_review.expansion_stage` for StageName.
Propose Name and buyer-supported CloseDate. Confirm any Salesforce-required fields by describe and fresh record evidence. Never invent Amount, ARR, seat demand, or a signature date.
The proposal's reason states seats versus active use, source org and window, buyer evidence, and the new-seat rationale. It is installed-base expansion, not ARR growth.

A renewal Task uses the reviewed source Opportunity Id for WhatId, current OwnerId, proposed Subject, and the exact notice date for ActivityDate.
Use Status Not Started and Priority Normal only after confirming those valid picklist values. Show the Description with `policy.salesforce.note_prefix` expanded for today.
The note links the source subscription, its end date, the renewal action, and the evidence. Include WhoId only for a reviewed customer Contact.
Check existing open Tasks on both Account and source Opportunity, including future-dated Tasks. Same renewal action and subscription means duplicate, regardless of Subject wording.

```sql
SELECT Id, WhatId, WhoId, OwnerId, Subject, Description, ActivityDate, Status, IsClosed
FROM Task
WHERE IsClosed = false AND (WhatId IN (<accountAndOpportunityIds>))
```

Scheduled runs propose and wait in their run thread under `rules#scheduled_runs`. No reply writes nothing. No pre-approval or automatic creation applies.
Before each approved label, re-read Account owner, all related open Opportunities, source subscription, existing renewals and Tasks, and required fields.
Recompute the notice against the current Pacific date after approval. A newly passed notice window becomes a question for Operator, never a past-dated Task.
Stop stale, duplicate, or newly out-of-scope proposals and report why. Apply only unchanged approved fields per `rules#write_protocol`.
Read each created or updated record natively, compare every approved field, and report mismatches without claiming success. Retrying a failed write requires a fresh duplicate check.

## Report and receipt

The scheduled report includes only helper-selected rows: due milestones, already-reviewed suppressions, superseded entries, holds or carries, unresolved anchors and renewal candidates in the window.
Every other owned customer is not_due_count only. Subscription-date needs-input on these unselected Accounts is one subscription_date_needs_input_count, not per-Account monthly flags.
Selected rows show won links, owner, org, evidence dates, separate seats and activity, renewal dates and status. On-demand shows only its named Account, including none due.
List open-deal Pipeline action handoffs with live Opportunity links. List unknowns and failed reads. Never claim a partial inventory is complete.
Number ready proposals across the whole report. Keep questions, skipped duplicates, and passed notice windows visibly separate.
The receipt lists approved labels, exact written records and readbacks, skipped or declined labels, pending approval, needs-input items, and failed or not-checked writes.
Say Nothing written if nothing was approved or verified. Salesforce records remain the handoff to pipeline-review. No outreach, schedule changes, or project files are produced.
Every run, including incomplete and early exits, ends with exactly one fenced JSON block named `customer_review_receipt` in its message:

```json
{"customer_review_receipt": {"mode": "scheduled", "window_start": "<ISO with offset>", "as_of": "<ISO with offset>",
 "reviewed": [{"account_id": "<Id>", "milestone_months": 3, "milestone_date": "<ISO date>"}],
 "held": [], "superseded": []}}
```

On-demand mode is `on_demand` and omits window_start, but includes as_of, the run-start ISO datetime with an offset. Reviewed entries take receipt_date from that block's as_of.
Only mode scheduled receipts supply the next window_start; an on-demand as_of never moves it. Native message timestamps are not the receipt clock.
Every reviewed, held and superseded entry carries account_id, milestone_months and milestone_date.
Reviewed requires usage_ready true and the assessment shown, not helper selection or approval of actions.
Held includes unreadable usage and not reached, including unresolved carry-forward entries. Buyer context and unknown billed seats never hold.
Missing anchors use null milestone_months and milestone_date.
Only mark earlier catch-up milestones superseded once their latest assessment actually completes; otherwise retain them as held. No receipt block means not reviewed.
Scheduled receipts stay in the scheduled run thread. On-demand runs in Pipeline or sends the same receipt block there. Never create a new state file or store.
