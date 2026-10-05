---
cadence: [monthly, one-off]
reads: _core/policy.yaml (salesforce, tooling, pipeline, pilot_usage, momentum), _core/rules.md, references/, shared usage queries, Salesforce, Snowflake, bounded buyer evidence, thread receipts
writes: Salesforce Opportunities and Tasks, after approval; receipt in the run thread and Pipeline for on-demand
next: Pipeline hygiene owns actions on Accounts with open Opportunities; verified new records feed pipeline-review
---

# Customer Review

Short Adoption, Value and growth, and Account health assessments at 3, 6 and 12 calendar months after the first verified non-trial Closed Won.
Renewal notices use actual subscription dates, never customer age. `policy.pipeline.customer_review.schedule` is metadata, not automation activation or write approval.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `salesforce`, `tooling`, `pipeline.customer_review`, `pilot_usage`, `momentum` | Identity, milestones, schedule, renewal notices, stage, type and helpers |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#approval`, `rules#write_protocol`, `rules#scheduled_runs`, `rules#absence_conclusions`, `rules#note_prefix`, `rules#close_date_basis`, `rules#momentum` | Evidence and every write gate |
| Org tool | `call-transcript-skill` | Windowed Account-bound read-only search and transcript retrieval only when call evidence is needed | Existing call evidence rules |
| Core queries | `workspaces/pipeline/references/pilot-usage-queries.md` | "1. Roster and activity", "1b. Weekly trend", "2. Feature mix and models (slow table)", "3. Use-case sample (slow table)" | Bounded report-mode usage |
| Core lookup | `workspaces/pipeline/references/org-lookup.md` | "Fields" | Billed seats differ from roster and active users |
| Reference | `references/collect.md` | "Inventory", "Window and receipts", "Usage", "Buyer evidence", "Helper input" | Scheduled owned inventory or one named Account, anchor, carry-forward and complete evidence |
| Reference | `references/proposals.md` | "Review", "Numbered proposals", "Report and receipt" | Short milestone assessments, duplicates, numbered approvals, readback and receipt coverage |
| Per-run evidence | Scheduled run thread and Pipeline thread; sandbox | Receipt blocks in these two threads, current identity, complete records, selected usage results, bounded buyer reads, approvals and readbacks | No new state store or customer material in Git |

## Process

1. Start per `rules#run_start`. Record current user id and local-offset as-of. Choose scheduled mode or one named owned Account; no on-demand window advancement.
2. Read receipts per "Window and receipts". Scheduled window_start is the latest scheduled receipt's as_of, never the platform completed flag; without one use the policy's previous occurrence.
   Carry forward that receipt's held entries. Merge reviewed entries from both threads. Explicit on-demand reassessment is allowed; do not create another state store.
3. Collect complete owned Accounts and all related Opportunities across owners per "Inventory". Earliest verified non-trial Closed Won anchors age; missing or conflicting dates stay needs-input.
4. Run `policy.tooling.scripts.customer_review` per "Helper input" to partition due, held, suppressed and renewal rows; all other owned customers are not_due_count only.
   In catch-up windows assess only the latest milestone; keep earlier ones visible as superseded. Open Opportunities route actions to Pipeline hygiene, not a new Opportunity.
5. For selected assessments, match org and collect usage per "Usage"; collect buyer evidence per "Buyer evidence" from the previous milestone, or anchor for the first, through as_of.
   Re-run the helper with those results. Org or usage holds preserve renewal evidence; unknown billed seats and optional buyer context never hold a complete usage review.
6. Assess per "Review" and present short assessments and numbered proposals per "Numbered proposals". Wait for Operator under `rules#approval`.
7. Apply only approved labels after fresh identity, ownership, open-deal, duplicate and field reads. Use `rules#write_protocol` and native readback for every write.
8. Close per "Report and receipt", even on incomplete or early exits. End with one fenced `customer_review_receipt` including run-start as_of; reviewed requires usage_ready and assessment shown.
   Held includes unreadable usage and not reached, not missing buyer context or unknown billed seats. On-demand runs in Pipeline or sends its receipt there. No reply writes nothing.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 6 | Short assessments, evidence gaps and exact numbered record proposals | Operator approves named labels, corrects, skips or supplies missing evidence |

## Audit

| Check | Pass Condition |
|---|---|
| Anchor, before step 6 | Complete all-owner Opportunity pages. First verified non-trial Closed Won only; later wins never reset age. Invalid or conflicting anchors compute no milestone |
| Window and milestone, before receipt | Window start exclusive, as-of inclusive in policy timezone; month-end clamping. Receipt-derived window_start, held carry-forward and reviewed suppression. Latest catch-up only; on-demand never advances window_start |
| Scope, throughout | Account.OwnerId matches current user. Open deals permit assessment but route actions to Pipeline. On-demand reviews one named Account only |
| Usage, before step 6 | No guessed org. usage_ready requires complete usage. Unknown billed seats need a follow-up, not a hold. Buyer context is optional. Unknown data is not zero or demand |
| Renewal, before step 6 | Opportunity.Subscription_Cancel_Date__c drives notices independently of milestones and org holds. Past dates have null Task due dates; actual end dates, duplicates and required fields retain all gates |
| Writes, step 7 | Each exact numbered change has approval, fresh checks and native readback. No scheduled pre-approval |
| Boundaries, throughout | No outreach, drafts, schedule changes, paid tools, invented demand or dates, customer data in Git, or new state stores |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Assessments and numbered proposals | Run thread | Short milestone-specific assessment, dates, separate seats/activity, buyer evidence, renewal notices, Pipeline handoffs and unknowns |
| Approved Opportunity or Task | Salesforce, after approval | Exact approved fields and native readback; records feed pipeline-review |
| Receipt | Run thread; on-demand also Pipeline | Window and reviewed, held, superseded milestones plus record outcomes; one final fenced customer_review_receipt block |
