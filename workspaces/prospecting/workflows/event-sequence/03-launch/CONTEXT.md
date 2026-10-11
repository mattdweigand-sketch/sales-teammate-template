---
cadence: one-off
reads: _core/policy.yaml (prospecting, salesforce, tooling), _core/rules.md, scoped sequence/prep/readback sections, helper interfaces, approved snapshot, Salesforce, Gmail, Apollo
writes: approved Apollo enrollment with possible CRM sync disclosed, no direct Salesforce writes
next: Pipeline for open-Opportunity contacts, Operator for replies, then end
---

# Launch

Execute only the exact approved snapshot from this same Prospecting run thread. Never enrich, add or replace recipients, or load List Prep to rerun preparation.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core freshness | `_core/rules.md`, `_core/scripts/interfaces.md` | `rules#repo_currency`, `workflow_revision_check`, "Workflow revisions" | Original Plan and separate Launch-entry scope checks, separate from E and native receipts |
| Core policy | `_core/policy.yaml` | `prospecting.event`, `prospecting.identity`, `prospecting.salesforce`, `prospecting.approval`, `salesforce`, `tooling` | Fresh guards and authorized helper |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#event_sequence`, `rules#approval`, `rules#write_protocol`, `rules#absence_conclusions`, `rules#not_checked_means` | Exact existing authority, fresh recheck clock and honest evidence |
| Handoff rule | `_core/rules.md` | `rules#handoff_delivery` | Pipeline delivery result and visible failure |
| Shared sequence | `workspaces/prospecting/workflows/event-sequence/references/sequence.md` | "Enrollment" | Ordered authorized calls and native copy gate |
| Shared prep | `workspaces/prospecting/workflows/event-sequence/references/prep.md` | "Salesforce and reply checks", "Helper evidence" as needed for fresh checks | Bounded complete recheck and helper fields |
| Shared readback | `workspaces/prospecting/workflows/event-sequence/references/readback.md` | "Readback" when enrollment reached, "Handoff and close" | Native verification, zero-recipient close and actual Pipeline delivery |
| Helper | `_core/scripts/interfaces.md` | "Interfaces", event_list_prep and event_launch_check rows | Fresh eligibility and native pre-enrollment comparison |
| Per-run evidence | Exact E proposal and Operator's matching native approval in this same Prospecting run thread, sandbox native receipts | Original run_start, reviewed rows, full guards, approved copy/mailbox/schedule, batches and reconciled native state | No cross-thread or forwarded approval |

## Process

1. Verify the exact proposal's same-thread native E approval and actual preparation receipts. Retain immutable original run_start. Missing, cross-thread or invalid approval stops without writes.
   Recheck the saved Plan scope, then record a separate current Launch-entry baseline per "Workflow revisions". Do not invent a Launch baseline at E display.
2. Fresh-read ownership and open Opportunities. Keep an outreach-owner row only if its Account is still house-owned or a completed lookup still finds no Account under the approved policy.
   Anything else outside named accounts stops. Recheck replies per shared sequence "Enrollment" and prep "Salesforce and reply checks".
   Record a separate fresh local-offset recheck time, reset incomplete reply markers and rerun event_list_prep with fresh `--as-of`, never the old run-start clock for that recheck.
   Invoke `policy.tooling.scripts.event_list_prep` on the same saved reviewed rows, with complete recheck evidence.
3. Intersect the helper-eligible set with the approved snapshot. Drop recent_reply and hold incomplete rechecks without re-approval or additions, replacements or inherited recent-reply overrides.
   Ownership, Opportunity, identity, copy, mailbox or schedule changes still require a revised exact proposal. Report exact drops and holds with reasons.
4. If none remain, skip every Apollo call and close through shared "Handoff and close". Never create contacts or a sequence for an empty receipt. Report zero enrolled and no sends.
5. Otherwise create or reuse only approved contacts and create/update the approved sequence per shared "Enrollment". Save native responses and verify native copy before add_contact_ids.
   Immediately before each write, recheck both original Plan and Launch-entry baselines per `rules#repo_currency`. Failed current authority or payload checks still stop.
   A change after an Apollo call stops the next write. Report completed calls without replay, implied rollback or altered immutable E, run_start and preparation evidence.
   Run `policy.tooling.scripts.event_launch_check` before add_contact_ids. Enroll only its PASS payload. FAIL stops with one fix proposal. STOP for missing fields or unknown structure asks Operator.
   Require the approved schedule ID and confirmed sideloaded response. Report not_checked only outside the connector schema. Activate only remaining approved recipients in the existing ordered calls.
   Never blindly reenroll or retry sends.
6. Read back per shared "Readback", reporting the pre-enrollment copy result, steps, recipients, scheduled subjects/counts, mailbox, first send, stop on reply and sent content when sent.
7. Close through shared "Handoff and close" with actual recheck summary, drops/holds and CRM-sync status. Deliver the retained Pipeline list and report actual native delivery or pending status.
   Then end.
   Partial failures stop with one concrete corrective proposal. No rollback of sent mail, indefinite monitoring, Salesforce Tasks or signal-followup. Replies go to Operator.

## Checkpoints

None. Launch consumes Sequence Plan's exact existing E approval in this same run thread. No extra Launch approval is added.

## Audit

| Check | Pass Condition |
|---|---|
| Approval | Exact list, copy, mailbox and schedule have matching native E approval here, with current preparation evidence |
| Freshness, before writes | Reply recheck uses fresh --as-of and only drops or holds approved contacts. Ownership, Opportunity, identity, copy, mailbox or schedule changes require revision |
| Zero recipients | Stop before every Apollo call after recheck. Actual receipt shows recheck, exact drops/holds, zero enrolled, no sends, known enrichment CRM sync and Pipeline delivery |
| Copy, before enrollment call | Saved create/update steps, touches, subject/body templates, merge variables, schedule and stop on reply match approval before add_contact_ids. Missing templates stop and ask Operator |
| Readback | Pre-enrollment copy result, scheduled subjects, counts, active state, stop on reply and first send match approval, with mailbox, recipient and sent-content checks when sent. Gaps stay partial with one fix proposal |
| Scope | Operator-owned Accounts or approved outreach-owner rows still house-owned or missing, no other scope override, no direct Salesforce writes. Apollo sync disclosed, not inferred from enrollment counts |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Approved sequence | Apollo after approval and fresh checks | Shared sequence "Enrollment", remaining approved recipients and stop on reply |
| Verified or partial receipt | Prospecting run thread | Shared readback "Readback" and "Handoff and close", saved native results in sandbox, never Git |
| Zero-recipient receipt | Prospecting run thread | Actual recheck, exact dropped/held list with reasons, zero enrolled/no sends, known CRM-sync evidence and Pipeline delivery |
| Open-Opportunity handoff | Pipeline thread | Shared "Handoff and close", including override-enrolled contacts and actual delivery status |
