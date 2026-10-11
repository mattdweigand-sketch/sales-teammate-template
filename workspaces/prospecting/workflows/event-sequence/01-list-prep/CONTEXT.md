---
cadence: one-off
reads: _core/policy.yaml (prospecting, salesforce, tooling), _core/rules.md, scoped prep and scrubber sections, helper interfaces, event list, Salesforce, Gmail, Apollo
writes: approved Apollo enrichment with possible CRM sync disclosed, no direct Salesforce writes
next: Sequence Plan with a viable prepared list, otherwise no-enrollment evidence to the coordinator
---

# List Prep

Prepare Operator's named-account event list without authorizing enrollment. Missing evidence stays needs-input. Helpers supply proposals, never approval.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core freshness | `_core/rules.md`, `_core/scripts/interfaces.md` | `rules#repo_currency`, `workflow_revision_check`, "Workflow revisions" | Enrichment proposal and prewrite evidence |
| Core policy | `_core/policy.yaml` | `prospecting.event`, `prospecting.identity`, `prospecting.salesforce`, `prospecting.approval`, `salesforce`, `tooling` | Event exclusions, identity, complete reads and helpers |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#event_sequence`, `rules#approval`, `rules#write_protocol`, `rules#absence_conclusions`, `rules#not_checked_means` | Original run, separate spend approval and bounded evidence |
| Shared prep | `workspaces/prospecting/workflows/event-sequence/references/prep.md` | "Intake", "Salesforce and reply checks", "Enrichment", "No enrollment", "Helper evidence" | Canonical guards, enrichment and early-close result |
| Scrubber | `references/scrubber.md` | "Run", "Output Contract", "Operator Checklist", "Fail-Closed Model" | Full-column hygiene and standalone audit |
| Helper | `_core/scripts/interfaces.md` | "Interfaces", event_list_prep, event_scrub_leads, event_make_batches rows | Shared list helper and private scrub/batch tools |
| Per-run evidence | Event list and complete saved native results in sandbox and current run thread | Original rows, event details, run_start, overrides, exact C approvals and guard receipts | This list only, no sibling contract as evidence |

## Process

1. Retain the immutable original run_start per `rules#run_start`. Intake and normalize per shared prep "Intake", preserving every original row and duplicate reason.
2. Prep read-only per shared prep "Salesforce and reply checks". Complete exact Account matching, Apollo identity and active-sequence checks, invite-export matching and bounded reply reads.
   With no usable email, defer only exact-email checks until enrichment returns an address. Complete them and rerun the helper before E1. Unchecked rows stay needs_input.
   Exclude every Account outside Operator's named accounts except approved outreach-owner rows per shared prep. Review exact domain aliases explicitly.
   Retain open-Opportunity contacts for Pipeline even when an event override permits enrollment.
3. Enrich only helper enrichment_candidates whose sole exclusion is unverified_email per shared prep "Enrichment", with separate approval and CRM-sync disclosure for every C proposal.
   Each spend, including waterfall, needs its own exact approval. Never enrich by the needs_input label. Finish deferred address checks on returned emails and rerun event_list_prep.
4. For a nonempty candidate list, require event_scrub_leads scrub and standalone audit-clean-output PASS, then event_make_batches checks, with domain mismatches held.
   Invoke `policy.tooling.scripts.event_scrub_leads` and `policy.tooling.scripts.event_make_batches` per their interfaces, the scrubber and shared prep "Enrichment".
   Keep Website, all source rows and every exclusion, quarantine, hold and batch count reconciled. Invoke `policy.tooling.scripts.event_list_prep` on reviewed evidence.
5. Check shared prep "No enrollment" after prep, declined enrichment and each helper. With no recipients and no enrichment remaining to propose or perform, return evidence to the coordinator.
   Skip audits of nonexistent clean files and remaining batching. Otherwise pass the viable list and actual receipts to Sequence Plan, without loading its contract as evidence.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | Candidates needing enrichment, exact operation, count, estimated credits and possible Apollo CRM sync | Approve the first C spend or skip |
| 3 | Each remaining C operation and estimated credits, waterfall separately, with CRM sync disclosed | Approve that spend or skip, never inherited from another operation |

Use the displayed C label grammar in shared prep "Enrichment". No enrichment approval authorizes enrollment.

## Audit

| Check | Pass Condition |
|---|---|
| Prep | Every source row reconciles to a normalized contact or reported duplicate. All guard reads complete, named-account scope fixed, exclusions have reasons |
| Credits | Sole-exclusion enrichment_candidates only. Exact spend approved, waterfall separately. Catch-all provenance is explicit, unknown remains held |
| Hygiene | For a nonempty candidate list, scrub and standalone audit both PASS. Batch counts reconcile, Website retained, missing fields and domain mismatches held unless explicitly resolved |
| No enrollment | No recipients and no remaining enrichment returns to coordinator without empty-file audits, E approval or Apollo enrollment writes |
| Handoff | Viable list includes full receipts, exact contacts and account linkage, scrub/audit reports, batches and retained Pipeline list |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Prepared list | Current Prospecting run thread and sandbox, enrichment only after approval | Original and reviewed rows, guards, C approvals, enrichment/helper receipts, chunks, batches, exclusions and holds |
| Viable handoff | Current run thread and sandbox | Actual scoped evidence for `workspaces/prospecting/workflows/event-sequence/02-sequence-plan/CONTEXT.md` |
| No-enrollment result | Coordinator in this run | Row reconciliation, evidence gaps, known enrichment CRM sync and retained Pipeline evidence, never an empty verified sequence |
