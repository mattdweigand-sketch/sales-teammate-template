---
cadence: one-off
reads: _core/policy.yaml (prospecting), _core/rules.md, conditional stage contracts, shared close section, current run evidence
writes: approved Apollo enrichment and enrollment with CRM sync disclosed, no direct Salesforce writes
next: Pipeline thread for open-Opportunity contacts, Operator for replies, then end
---

# Event Sequence

Coordinate Operator's named-account event contact list of any size through three stages in this agent session.
Existing Salesforce Accounts owned by prospecting.identity.sfdc_user_id are eligible.
Event lists Operator names also admit rows marked with Operator as outreach owner for house-owned or missing Accounts under the approved policy.
Apollo sends only under `rules#event_sequence`. A reply stops that contact and Operator takes over. No new workers, loops or stage-state files are added.

## Pipeline

| Stage | Trigger | Output | Human check | Contract route |
|---|---|---|---|---|
| List Prep | Event list or valid prep resume | Prepared rows, guards, scrub/audit PASS and reconciled batches, or no-enrollment evidence | Each C spend separately, waterfall separately | `01-list-prep/CONTEXT.md` |
| Sequence Plan | Viable prepared list with actual receipts | Exact E proposal and same-thread native approval | Exact list, copy, mailbox, schedule and overrides | `02-sequence-plan/CONTEXT.md` |
| Launch | Exact approved snapshot and same-thread E approval | Verified, partial or no-enrollment receipt and Pipeline handoff | Existing exact E approval, no repeat pause | `03-launch/CONTEXT.md` |

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `prospecting.identity`, `prospecting.event.outreach_owner_scope` | Named-account owner and approved outreach-owner scope |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#event_sequence`, `rules#approval`, `rules#write_protocol`, `rules#not_checked_means`, `rules#handoff_delivery` | Run identity, delegated authority and honest receipt |
| Stage | `01-list-prep/CONTEXT.md`, `02-sequence-plan/CONTEXT.md`, `03-launch/CONTEXT.md` | Only the selected stage when entered | Never preload the union of stage Inputs |
| Close reference | `workspaces/prospecting/workflows/event-sequence/references/readback.md` | "Handoff and close" only when closing early | Reconciliation and actual Pipeline delivery |
| Per-run evidence | Current Prospecting run thread and sandbox native results | Original run_start, rows, guards, approvals and actual stage outputs | Resume evidence, never a folder label or forwarded approval |

## Process

1. Start per `rules#run_start`, or retain the immutable original run_start on a valid resume. Select entry from actual current evidence, without resetting approval scope or windows.
2. Enter List Prep unless actual scoped preparation evidence already permits Sequence Plan or an exact same-thread E approval and reconciled native state permit Launch.
3. With no recipients and no enrichment remaining to propose or perform, reconcile every row and close directly through shared "Handoff and close".
   Do not load Sequence Plan, Launch or "Readback" for a nonexistent sequence. Skip empty-file audits and launch-only checks, including the pre-enrollment recheck.
4. Otherwise enter Sequence Plan with a viable prepared list. Enter Launch only with Operator's exact native E approval for that proposal in this same Prospecting run thread.
5. Return the actual verified, partial or closed-with-no-enrollment receipt. Deliver the retained open-Opportunity list to Pipeline and report delivered or pending native status, then end.
   A failure stops with one concrete corrective proposal. Approved replanning is a new scoped invocation, never an automatic Launch-to-Plan loop.

A change to a live sequence after Launch is a mutation. This covers adding or removing contacts, editing copy, schedule or mailbox, and pausing or resuming.
A mutation needs a new exact proposal in this Prospecting run thread and Operator's native approval of that proposal under `rules#approval` and `rules#write_protocol`.
The original E approval never covers a mutation. Read the native sequence back after the approved change. An unavailable readback is not checked, never assumed applied.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | List Prep's exact C proposals, with estimated credits and CRM-sync disclosure | Each spend separately under its stage, waterfall separately |
| 4 | Sequence Plan's exact E proposal in this run thread | Exact contacts, copy, mailbox, schedule and listed overrides under its stage |

The stages own these reviews. The coordinator adds no repeat approval or approval for an early close without customer-system writes.

## Audit

| Check | Pass Condition |
|---|---|
| Entry | Only the selected stage loads, with actual required evidence and one immutable run identity |
| Scope, throughout | Operator-owned Accounts or approved outreach-owner rows, no other scope override. No direct Salesforce writes. Apollo CRM sync disclosed in every C and E proposal |
| Approval | Separate exact C approvals and exact same-thread E approval precede their respective writes. Helper labels never authorize enrollment |
| No enrollment | With no recipients and no remaining enrichment, close without nonexistent-file audits, E approval, Launch entry or an unneeded recheck |
| Receipt | Actual status, exclusions, holds and known CRM-sync evidence are shown. Pipeline handoff delivery is verified or pending, never inferred |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Stage evidence and approvals | Prospecting run thread and sandbox, never Git | Actual reviewed rows, guard receipts, C/E proposals, native approvals and results |
| Approved sequence | Apollo, only when Launch is reached after approval | Shared sequence "Enrollment", stop on reply enabled |
| Receipt | Prospecting run thread | Stage's verified or partial readback, or shared "Handoff and close" for no enrollment |
| Open-Opportunity handoff | Pipeline thread | Shared "Handoff and close", including source links and actual delivery status |
