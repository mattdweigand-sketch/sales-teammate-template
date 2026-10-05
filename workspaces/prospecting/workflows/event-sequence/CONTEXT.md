---
cadence: one-off
reads: _core/policy.yaml (prospecting, salesforce, email_voice, tooling), _core/rules.md, references/, event list, Salesforce, Gmail, Apollo
writes: approved Apollo enrichment and enrollment with CRM sync disclosed, no direct Salesforce writes
next: Pipeline thread for open-Opportunity contacts, Operator for replies, then end
---

# Event Sequence

Turn Operator's named-account event contact list of any size into one approved Apollo sequence. Only existing Salesforce Accounts owned by prospecting.identity.sfdc_user_id are eligible.
Apollo sends only under `rules#event_sequence`. A reply stops that contact and Operator takes over.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `prospecting.event`, `prospecting.identity`, `prospecting.salesforce`, `prospecting.approval`, `prospecting.outreach.lint`, `salesforce`, `email_voice`, `tooling` | Event values, read filters, copy, and helpers |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#event_sequence`, `rules#approval`, `rules#write_protocol`, `rules#absence_conclusions`, `rules#not_checked_means` | Intake, permission, and evidence limits |
| Helper | `_core/scripts/interfaces.md` | "Interfaces", event_list_prep, event_scrub_leads, event_make_batches rows | Deterministic list preparation, scrub, and batch checks |
| Reference | `references/prep.md` | "Intake" at step 1, "Salesforce and reply checks" at step 2, "Enrichment" and "Helper evidence" at step 3, "No enrollment" at steps 2-3 | List checks, credit approval, or no enrollment |
| Reference | `references/scrubber.md` | "Run", "Output Contract", "Operator Checklist", "Fail-Closed Model" at step 3 | Migrated scrub and audit process |
| Reference | `references/sequence.md` | "Copy and timing" at step 4, "Approval" at step 5, "Enrollment" at step 6 | Exact copy, mailbox, schedule, and authorized Apollo calls |
| Reference | `references/readback.md` | "Readback" at step 7, "Handoff and close" at step 8 | Counts, first send, stop on reply, partial failures, and Pipeline list |
| Per-run evidence | Event list and complete saved native results in sandbox | This list, event details, per-list overrides, exact approvals, and current records | Customer material and approval evidence, never Git |

## Process

1. Start per `rules#run_start`. Intake per `references/prep.md` "Intake", including the list, event, attendance dates, location, and ask.
2. Prep read-only per `references/prep.md` "Salesforce and reply checks". Complete exact Account matching, Apollo identity and active-sequence checks, invite-export matching, and reply reads.
   With no usable email, defer only exact-email checks until enrichment returns an address. Complete them and rerun the helper before E1. Unchecked rows stay needs_input.
   Exclude every Account outside Operator's named accounts. Missing evidence stays needs-input.
3. Enrich only helper enrichment_candidates whose sole exclusion is unverified_email per `references/prep.md` "Enrichment", with separate approval and CRM-sync disclosure for every C proposal.
   If no recipients remain and no enrichment remains to propose or perform, go straight to step 8 per `references/prep.md` "No enrollment". Check this after prep and each helper.
   Run event_list_prep again on reviewed evidence. Require event_scrub_leads scrub and audit-clean-output PASS, then event_make_batches checks, with domain mismatches held.
4. Draft exact copy and timing per `references/sequence.md` "Copy and timing", using event policy and email_voice with advisory outreach lint.
5. Present one exact enrollment proposal with the Apollo CRM-sync disclosure per `references/sequence.md` "Approval". Wait for approval of the list, copy, mailbox, schedule, and listed overrides.
6. Fresh-read ownership and open Opportunities. Outside named accounts always stops. Enroll only that approved snapshot per `references/sequence.md` "Enrollment" and `rules#write_protocol`.
   Recheck replies through the current time and rerun event_list_prep with fresh `--as-of`. Drop recent_reply and hold incomplete rechecks, without re-approval or additions.
   If none remain, skip Apollo and go to step 8. Ownership, Opportunity, copy, mailbox, or schedule changes still require a revised proposal.
7. Read back per `references/readback.md` "Readback", reporting the pre-enrollment copy result and comparing steps, recipients, scheduled subjects/counts, mailbox, first send and stop on reply.
8. Hand open-Opportunity contacts to the Pipeline thread per `references/readback.md` "Handoff and close". Report partial failures with one fix proposal, then end. Replies go to Operator.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | Candidates needing enrichment, operation, count, and estimated credits | Approve the first spend or skip |
| 3 | Each remaining enrichment operation and estimated credits, with waterfall separately | Approve that spend or skip, never inherited from another operation |
| 5 | Exact contacts, exclusions and reasons, copy, timing, mailbox, schedule, and per-list overrides | Approve exactly shown, edit, or skip. Edits need a revised exact proposal |

## Audit

| Check | Pass Condition |
|---|---|
| Prep, before step 5 | Every source row reconciles to one normalized contact or a reported duplicate. All guard reads complete, enrolled Accounts belong to Operator, exclusions have reasons, and overrides cannot expand account scope |
| Credits, before each step 3 spend | Operator approved that exact count and estimated credit spend. Waterfall search has its own approval |
| Hygiene, before step 5 | For a nonempty candidate list, scrub and independent audit both PASS. Batch counts reconcile, missing fields and domain mismatches remain held unless explicitly resolved |
| No enrollment, at steps 2-3 | With no recipients and no remaining enrichment, reconcile every row, skip steps 3-7 as applicable, and go to step 8 without Apollo writes |
| Approval, before step 6 | Exact list, copy, mailbox, and schedule approved under rules#event_sequence. Helper labels never authorize enrollment |
| Freshness, before step 6 | Reply recheck uses fresh --as-of and only drops or holds approved contacts. Ownership, Opportunity, copy, mailbox, or schedule changes require revision |
| Copy, before enrollment call | Saved create/update steps, touches, subject/body templates, merge variables, schedule and stop on reply match approval before add_contact_ids. Missing templates stop and ask Operator. Any mismatch stops with one fix proposal |
| Readback, after step 7 | Pre-enrollment copy result, scheduled subjects, counts, active state, stop on reply and first send match approval, with mailbox, recipient and sent-content checks when sent. Gaps stay partial with one fix proposal |
| Scope, throughout | Only Operator-owned Accounts, no scope override. No direct Salesforce writes. Apollo CRM sync disclosed in every C and E proposal. Separate approvals for enrichment and real sends, no email outside the approved sequence |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Exact proposal | Prospecting run thread | `references/sequence.md` "Approval", including every exclusion with its reason |
| Approved sequence | Apollo, after approval only | `references/sequence.md` "Enrollment", stop on reply enabled |
| Receipt | Prospecting run thread | `references/readback.md` "Readback" for enrollment, "Handoff and close" for no enrollment |
| Open-Opportunity handoff | Pipeline thread | `references/readback.md` "Handoff and close", source and native record links |
| Saved results | Sandbox | List, approvals, query pages, enrichment receipts, scrub audits, and batches, never Git |
