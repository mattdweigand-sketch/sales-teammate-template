# Customer review and proposals

## Review

Review the helper's inventory against native results. It is a mechanical check, not evidence of demand or approval.
Report billed seats or unknown, roster seats, active users over `policy.pilot_usage.window_days`, last-seven-day active users, weekly trend, idle seats, feature mix and supported use cases separately.
Use only supported work-related use cases in the assessment or customer-facing examples. Exclude personal, sensitive and unclear samples from themes and quotations.
If none qualify, say `No supported work-related use cases in the retrieved sample`. Never remove those queries from activity totals or infer that no work use occurred.
Assess only due milestones, in a few lines followed by numbered recommended actions. Already-reviewed matches show the receipt date, not a repeated scheduled assessment.
- 3 months, Adoption: billed versus roster versus 60-day and 7-day active users, weekly trend, idle seats, feature mix, buyer-reported barriers and support needs.
- 6 months, Value and growth: buyer-stated results, usage trend and any buyer evidence for more seats. Billed seats stay distinct from roster and activity.
- 12 months, Account health: sustained value, declining use or other risks, champion changes, open support issues, next-year plans and the actual subscription end date when known.
Read buyer evidence from the previous milestone date, or the anchor for the first milestone, through as_of in both modes. Unread sources are not checked. Recommendations are not demand inference.
Complete usage presented completes the review. Unknown billed seats need a follow-up to verify seats, not a hold.
Hold unreadable usage, including org mismatch, failed or incomplete queries or stale data.
Buyer context is optional. Failed reads are "not checked". No contact found becomes "no buyer contact retrieved, <dates searched>", never a hold or a statement of absence. Keep the check-in proposal.
End each assessment with numbered follow-ups drawn from usage facts and cite the numbers.
Propose training for idle seats, a seat conversation near or above billed seats, or declining-trend health checks.
Include a check-in for no recent contact. Add no fixed numeric threshold. Follow-ups may become Salesforce Task proposals with the existing approval, duplicate check and native readback gates.
Do not infer more purchased seats from members alone. No Gmail drafts or outreach.
When activity and buyer evidence support more seats, explain that evidence and the proposed increment. Show any idle seats, alternative adoption work, and uncertainty.
Expansion Opportunity proposals still require buyer evidence for demand. No expansion proposal for unknown enterprise status, mismatched org, incomplete usage, or any open Opportunity.
With any open Opportunity, the assessment remains read-only. Send recommended actions to its active deal thread first, otherwise to Pipeline hygiene.
Ask that owner to merge with any open proposal on the same record. Propose nothing on that record here.
Send once with `pplx tm mail send <deal-thread session id> "<message>"`. Record delivery or failure. Never wait, sleep or poll.
Failed or ambiguous routing stays needs-input for the handoff. Never claim delivery without a successful send.

Use `Opportunity.Subscription_Cancel_Date__c` only as known Subscription End Date context for account health.
Do not produce renewal notices, renewal Task proposals or renewal hold entries. The 12-month milestone never substitutes for the subscription end date.
A trial end date is not an expansion CloseDate.

## Numbered proposals

Every write is its own numbered proposal under `rules#approval`. `all` covers only the exact numbered ready proposals in this report.
Each proposal shows object, create or update, exact fields, current values for updates, evidence links, reason, duplicate check, and anything still unknown.
Items needing missing required fields are questions, not ready proposals. Changed fields after approval need a new numbered proposal.

An expansion Opportunity uses the reviewed AccountId, current OwnerId, `policy.pipeline.customer_review.expansion_type` for Type, and `policy.pipeline.customer_review.expansion_stage` for StageName.
Propose Name and buyer-supported CloseDate. Confirm any Salesforce-required fields by describe and fresh record evidence. Never invent Amount, ARR, seat demand, or a signature date.
The proposal's reason states seats versus active use, source org and window, buyer evidence, and the new-seat rationale. It is installed-base expansion, not ARR growth.

Check existing open Tasks on both Account and related Opportunities before a check-in proposal, including future-dated Tasks.
The same check-in action means duplicate, regardless of Subject wording.

```sql
SELECT Id, WhatId, WhoId, OwnerId, Subject, Description, ActivityDate, Status, IsClosed
FROM Task
WHERE IsClosed = false AND (WhatId IN (<accountAndOpportunityIds>))
```

Scheduled runs propose and wait in their run thread under `rules#scheduled_runs`. No reply writes nothing. No pre-approval or automatic creation applies.
Before each approved label, re-read Account owner, all related open Opportunities and Tasks, and required fields.
Stop stale, duplicate, or newly out-of-scope proposals and report why. Apply only unchanged approved fields per `rules#write_protocol`.
Read each created or updated record natively, compare every approved field, and report mismatches without claiming success. Retrying a failed write requires a fresh duplicate check.

## Report and receipt

The scheduled report includes only helper-selected rows: due milestones, already-reviewed suppressions, superseded entries, holds or carries and unresolved anchors.
Every other owned customer is not_due_count only.
Selected rows show won links, owner, org, evidence dates, separate seats and activity. On-demand shows only its named Account, including none due.
List open-deal Pipeline action handoffs with live Opportunity links. List unknowns and failed reads. Never claim a partial inventory is complete.
Number ready proposals across the whole report. Keep questions and skipped duplicates visibly separate.
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
Milestone reviewed, held and superseded entries carry account_id, milestone_months and milestone_date.
Reviewed requires usage_ready true and the assessment shown, not helper selection or approval of actions.
The reviewed receipt clock cannot precede the milestone date in the policy timezone. A valid receipt schema alone does not prove that usage or the assessment was completed.
Held includes unreadable usage and not reached, including unresolved carry-forward entries. Buyer context and unknown billed seats never hold.
Ignore old receipt entries with kind `renewal`. Do not copy them into reviewed, held or superseded output.
Missing anchors use null milestone_months and milestone_date.
Only mark earlier catch-up milestones superseded once their latest assessment actually completes; otherwise retain them as held. No receipt block means not reviewed.
Scheduled receipts stay in the scheduled run thread. On-demand runs in Pipeline or sends the same receipt block there. Never create a new state file or store.
