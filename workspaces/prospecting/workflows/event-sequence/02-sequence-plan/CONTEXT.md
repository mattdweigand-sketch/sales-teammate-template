---
cadence: one-off
reads: _core/policy.yaml (prospecting, email_voice, tooling), _core/rules.md, scoped sequence sections, helper interface, viable prepared list and native receipts
writes: nothing
next: Launch only after exact E approval in this Prospecting run thread
---

# Sequence Plan

Present the exact enrollment proposal from a viable prepared list. This stage performs no enrichment, sequence creation, enrollment or sending.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core freshness | `_core/rules.md`, `_core/scripts/interfaces.md` | `rules#repo_currency`, `workflow_revision_check`, "Workflow revisions" | E proposal scope only, no Launch preload or writes |
| Core policy | `_core/policy.yaml` | `tooling.scripts.workflow_revision_check` | Shared freshness helper path |
| Core policy | `_core/policy.yaml` | `prospecting.event`, `prospecting.identity`, `prospecting.approval`, `prospecting.outreach.lint`, `email_voice` | Event schedule, exact proposal and copy voice |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#event_sequence`, `rules#approval`, `rules#write_protocol`, `rules#not_checked_means` | Original run identity and exact enrollment authority |
| Shared sequence | `workspaces/prospecting/workflows/event-sequence/references/sequence.md` | "Copy and timing", "Approval" | Exact copy, mailbox, schedule, reply receipt and displayed E grammar |
| Per-run evidence | Viable prepared list and native receipts in this Prospecting run thread and sandbox | Original and reviewed rows, guards, C approvals/results, scrub/audit PASS, reconciled batches, holds and Pipeline list | Actual evidence, not a sibling contract or helper label |

## Process

1. Retain original run_start and validate the viable list's actual supporting receipts, identity, full source-row reconciliation and complete deferred address checks.
   Missing or invalid preparation stops and returns its gap to the coordinator. Empty outcomes belong to the coordinator, not a second close path here.
2. Draft every subject, body, personalization variant and LinkedIn task instruction per shared sequence "Copy and timing". Resolve the mailbox and absolute local schedule.
3. Snapshot this stage's consumed sources per `rules#repo_currency`, then present the exact enrollment proposal with Apollo CRM-sync disclosure per shared sequence "Approval".
   Attach the saved reply-check receipt file, not a sandbox path.
   Wait for approval of the list, copy, mailbox, schedule and listed overrides under its displayed E label in this same Prospecting run thread. Edits need a revised exact proposal.
4. Pass only this approved snapshot and its matching native approval message to Launch. A matching label from another thread, forwarded approval or past campaign does not qualify.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 3 | Exact contacts, exclusions and reasons, full copy and personalization, mailbox, future schedule, expected counts, overrides, CRM sync and attached reply receipt | Approve exactly shown under its E label here, edit or skip |

No separate list-only or copy-only approval is added.

## Audit

| Check | Pass Condition |
|---|---|
| Preparation | Viable recipients and every source row reconciled, required native guards, C approvals, enrichment results, scrub/audit PASS and batches available |
| Proposal | Exact recipients, supported copy, personalization, future schedule, correct mailbox, stop on reply, counts and disclosed overrides/CRM sync |
| Receipt | Reply window endpoints, query shapes, checked contacts, replies and holds shown, saved receipt attached to the thread message |
| Approval | Native approval matches this exact E proposal and this same run thread. Helper labels, forwarded messages and prior campaigns never authorize enrollment |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Exact E proposal and native approval | This Prospecting run thread | Shared sequence "Approval", immutable approved list, copy, mailbox, schedule and overrides |
| Approved handoff | Current run thread and sandbox | Approved E snapshot, saved Plan source scope/baseline, original run_start and native preparation/approval evidence for `workspaces/prospecting/workflows/event-sequence/03-launch/CONTEXT.md` |
