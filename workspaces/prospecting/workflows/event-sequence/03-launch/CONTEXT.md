---
cadence: one-off
reads: _core/policy.yaml (prospecting, salesforce, email_voice, tooling), _core/rules.md, references/, approved snapshot, Salesforce, Gmail, Apollo
writes: approved Apollo enrollment with CRM sync disclosed, no direct Salesforce writes
next: Pipeline thread for open-Opportunity contacts, Operator for replies, then end
---

# Launch

Execute only the exact E snapshot with matching native approval in this same run thread. A helper verdict or another thread's approval is insufficient.
Apollo sends only under `rules#event_sequence`. A reply stops that contact and Operator takes over.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `prospecting.event`, `prospecting.identity`, `prospecting.salesforce`, `prospecting.approval`, `salesforce`, `email_voice`, `tooling` | Fresh guards, approved operation and helpers |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#event_sequence`, `rules#approval`, `rules#write_protocol`, `rules#absence_conclusions`, `rules#not_checked_means` | Existing permission and fresh evidence gates |
| Helper | `_core/scripts/interfaces.md` | "Interfaces", event_list_prep row | Fresh reply recheck on the approved rows |
| Reference | `../references/prep.md` | "Salesforce and reply checks", "Helper evidence" | Complete fresh guards and reply receipt |
| Reference | `../references/sequence.md` | "Enrollment" | Native copy gate and approved operation order |
| Reference | `../references/readback.md` | "Readback", "Handoff and close" | Complete verification, actual close and delivery |
| Per-run evidence | Prospecting thread and sandbox | Exact E snapshot and native approval in this same run thread, prepared rows, complete receipts, immutable run_start and current native records | Required approved entry evidence |

## Process

1. Require native approval in this same run thread matching the saved exact E proposal. Missing, mismatched or other-thread approval stops before any writes.
2. Fresh-read ownership and open Opportunities. Outside named accounts always stops. Recheck Apollo identity and replies through the current time per `../references/sequence.md` "Enrollment".
   Rerun `policy.tooling.scripts.event_list_prep` on the same reviewed rows with fresh `--as-of`. Drop recent_reply and hold incomplete rechecks, without re-approval or additions.
3. If no recipients remain, skip every Apollo call and close through `../references/readback.md` "Handoff and close" with the actual recheck receipt, drops and holds.
   Stop here before contact creation, sequence create/update, add_contact_ids or campaign approval. Ownership, Opportunity, copy, mailbox or schedule changes require a revised exact proposal.
4. Otherwise enroll only the remaining approved snapshot per `../references/sequence.md` "Enrollment" and `rules#write_protocol`.
   Save and compare native create/update copy before add_contact_ids. Missing templates or any mismatch stops with Operator input or one exact fix proposal. Never blindly reenroll.
5. Read back per `../references/readback.md` "Readback", comparing native copy, steps, recipients, scheduled subjects/counts, mailbox, first send and stop on reply.
6. Hand open-Opportunity contacts to Pipeline per `../references/readback.md` "Handoff and close". Report actual delivery and partial failures with one fix proposal, then end. Replies go to Operator.

## Checkpoints

None. Sequence Plan owns the exact E approval. Launch consumes matching same-thread native approval without a repeat pause and stops for revised approval on material changes.

## Audit

| Check | Pass Condition |
|---|---|
| Approval, before writes | Exact list, copy, mailbox and schedule approved under rules#event_sequence in this run thread. Helper labels never authorize enrollment |
| Freshness, before writes | Reply recheck uses fresh --as-of and only drops or holds approved contacts. Ownership, Opportunity, copy, mailbox or schedule changes require revision |
| Zero recipients | No remaining approved recipients stops before every Apollo call. Attach the actual recheck receipt and report drops and holds |
| Copy, before enrollment call | Saved create/update steps, touches, subject/body templates, merge variables, schedule and stop on reply match approval before add_contact_ids. Missing templates or mismatch stops |
| Readback, before close | Pre-enrollment copy result, scheduled subjects, counts, active state, stop on reply and first send match approval, with mailbox, recipient and sent-content checks when sent. Gaps stay partial with one fix proposal |
| Scope, throughout | Only Operator-owned Accounts. No direct Salesforce writes. Apollo CRM sync disclosed in every C and E proposal. No contacts added to the approved set |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Approved sequence | Apollo, after approval only | `../references/sequence.md` "Enrollment", stop on reply enabled |
| Receipt | Prospecting run thread | `../references/readback.md` "Readback" for enrollment, "Handoff and close" for zero recipients |
| Open-Opportunity handoff | Pipeline thread | `../references/readback.md` "Handoff and close", source and native record links with actual delivery status |
| Saved results | Sandbox | Exact E approval, native responses, reply and readback receipts, never Git |
