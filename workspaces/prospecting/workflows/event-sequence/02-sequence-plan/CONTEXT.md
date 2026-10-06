---
cadence: one-off
reads: _core/policy.yaml (prospecting, email_voice), _core/rules.md, references/, viable prepared list and current receipts
writes: nothing
next: Launch with this exact E snapshot and native approval in the same run thread
---

# Sequence Plan

Prepare the exact enrollment proposal for a viable reviewed list. This stage creates no draft, sequence or customer record.
Empty preparation outcomes return to the coordinator before entry. Every enrichment operation retains its separate C approval.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `prospecting.event`, `prospecting.identity`, `prospecting.approval`, `prospecting.outreach.lint`, `email_voice` | Event timing, exact scope and copy |
| Core rules | `_core/rules.md` | `rules#event_sequence`, `rules#approval`, `rules#not_checked_means` | Exact approval and evidence limits |
| Reference | `../references/sequence.md` | "Copy and timing", "Approval" | Exact copy, timing and E proposal |
| Per-run evidence | Prospecting thread and sandbox | Viable prepared list, original rows, scrub and batch PASS, complete guard and C receipts, reply-check attachment and overrides | This run's prepared evidence |

## Process

1. Require the viable prepared list and complete supporting receipts from this run. Missing evidence stops entry and returns the gap to the coordinator.
2. Draft exact copy and timing per `../references/sequence.md` "Copy and timing", using event policy and email_voice with advisory outreach lint.
3. Present one exact enrollment proposal with the Apollo CRM-sync disclosure per `../references/sequence.md` "Approval".
   Attach the bounded reply-check receipt.
   Show exact contacts, exclusions and reasons, copy, mailbox, named schedule, intervals, timezone, expected local windows, intended enrollment, counts and every listed override.
4. Wait for approval of that exact E proposal under `rules#approval`. Edits require a revised exact proposal and approval. No C approval substitutes for E.
5. Hand Launch the saved exact E snapshot and matching native approval in this same run thread, with prepared evidence and receipts. Do not load Launch here.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 3 | Exact E contacts, exclusions, copy, timing, mailbox, schedule, counts, overrides and CRM-sync disclosure | Approve exactly shown, edit or skip. Edits need a revised exact proposal |

## Audit

| Check | Pass Condition |
|---|---|
| Intake | Prepared evidence is viable and complete. Every exclusion and hold has a reason and scrub/batch counts reconcile |
| Proposal | Exact list, copy, mailbox and schedule shown under rules#event_sequence, with bounded reply-check receipt and CRM-sync disclosure |
| Approval | Native approval in this same run thread matches this exact E snapshot. A skipped, unapproved or revised proposal cannot enter Launch |
| Scope, throughout | No Apollo calls, direct Salesforce writes or customer messages. Preserve configured event scope and distinct C and E approvals |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Exact proposal | Prospecting run thread | `../references/sequence.md` "Approval", including every exclusion and reason |
| Launch evidence | Prospecting thread and sandbox | Exact E snapshot, same-thread native approval, prepared list and complete supporting receipts |
