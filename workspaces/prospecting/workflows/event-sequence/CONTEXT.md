---
cadence: one-off
reads: _core/policy.yaml (prospecting), _core/rules.md, references/, current run evidence, conditional stage contracts
writes: approved Apollo enrichment and enrollment with CRM sync disclosed, no direct Salesforce writes
next: Pipeline thread for open-Opportunity contacts, Operator for replies, then end
---

# Event Sequence

Coordinate Operator's named-account event list of any size. Only existing Operator-owned Salesforce Accounts are eligible.
Apollo sends only under `rules#event_sequence`. A reply stops that contact and Operator takes over.

## Pipeline

| Stage | Trigger | Output | Human check | Contract route |
|---|---|---|---|---|
| List Prep | Event list and current run evidence | Prepared list, exclusions, receipts and batches, or no-recipient result | Approve each exact C spend separately | `01-list-prep/CONTEXT.md` |
| Sequence Plan | Viable prepared list and receipts | Exact E proposal and matching approval evidence | Approve exact list, copy, mailbox, schedule and overrides | `02-sequence-plan/CONTEXT.md` |
| Launch | Exact E snapshot with native approval in this run thread | Verified, partial or no-enrollment receipt and Pipeline handoff | Existing exact E approval. Changes require revision | `03-launch/CONTEXT.md` |

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `prospecting.identity`, `prospecting.event`, `prospecting.approval` | Account scope and approval boundary |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#event_sequence`, `rules#approval`, `rules#write_protocol`, `rules#not_checked_means` | Existing permission and evidence gates |
| Stage | `01-list-prep/CONTEXT.md` | Full contract only on List Prep entry | Intake and reviewed preparation |
| Stage | `02-sequence-plan/CONTEXT.md` | Full contract only with viable prepared evidence | Exact E proposal |
| Stage | `03-launch/CONTEXT.md` | Full contract only with matching same-thread E approval | Approved execution and verification |
| Reference | `references/readback.md` | "Handoff and close" only for early no-recipient close | Actual receipt and Pipeline delivery |
| Per-run evidence | Prospecting thread and sandbox | Current list, immutable run_start, stage results, exact approvals and receipts | No customer material in Git |

## Process

1. Start per `rules#run_start`, or resume this same run with its immutable run_start and saved evidence. Select only the stage whose entry evidence is complete.
2. Enter List Prep through its declared contract. Read no other stage Inputs yet.
3. With no recipients and no remaining enrichment, reconcile the result and close through `references/readback.md` "Handoff and close".
   Skip Sequence Plan and Launch, E approval, nonexistent-file audits and the pre-enrollment reply recheck. No customer-system writes occur in this close.
4. Otherwise enter Sequence Plan with the viable prepared list and all receipts. Enter Launch only with the exact E snapshot and native approval in this same run thread.
5. Return the actual verified, partial or no-enrollment receipt. Record the Pipeline handoff's actual delivery status. Replies go to Operator, then end.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | List Prep's exact C proposals | Approve each spend separately in List Prep or skip |
| 4 | Sequence Plan's exact E proposal | Approve it there, edit or skip. No repeat approval is added by the coordinator |

Early close has no customer-system writes. It may deliver the existing Pipeline handoff and reports the actual delivery status.

## Audit

| Check | Pass Condition |
|---|---|
| Entry | Selected stage has this run's complete evidence. Same-thread native approval matches the exact E snapshot before Launch |
| No enrollment | With no recipients and no remaining enrichment, close directly. Never load Plan or Launch, audit nonexistent files or run a reply recheck for the receipt |
| Loading | Only the entered stage and the coordinator's own Inputs are read. Shared references are not preloaded as a union of stage Inputs |
| Scope, throughout | Only Operator-owned Accounts. No direct Salesforce writes. Apollo CRM sync disclosed in every C and E proposal. Separate approvals for enrichment and real sends |
| Receipt | Every source row and actual stage outcome reconcile. Evidence gaps stay needs-input or partial. Pipeline delivery has a native receipt or remains pending |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Approved sequence | Apollo, after approval only | Launch's exact approved enrollment and full native readback |
| Receipt and handoff | Prospecting thread and Pipeline thread | Actual stage receipt or `references/readback.md` "Handoff and close" for early close |
| Saved results | Sandbox | List, approvals, receipts and helper results, never Git |
