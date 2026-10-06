---
cadence: one-off
reads: _core/policy.yaml (prospecting, salesforce, tooling), _core/rules.md, references/, event list, Salesforce, Gmail, Apollo
writes: approved Apollo enrichment with CRM sync disclosed, no direct Salesforce writes
next: Sequence Plan with viable prepared evidence, otherwise coordinator for early close
---

# List Prep

Prepare one event list under Operator's named-account scope. Helpers do not authorize enrichment or enrollment.
Keep this run's immutable run_start. Enrichment spend never grants enrollment approval.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `prospecting.event`, `prospecting.identity`, `prospecting.salesforce`, `prospecting.approval`, `salesforce`, `tooling` | Scope, exclusions and helpers |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#event_sequence`, `rules#approval`, `rules#write_protocol`, `rules#absence_conclusions`, `rules#not_checked_means` | Existing permission and evidence limits |
| Helper | `_core/scripts/interfaces.md` | "Interfaces", event_list_prep, event_scrub_leads, event_make_batches rows | Reviewed preparation and deterministic hygiene |
| Reference | `../references/prep.md` | "Intake", "Salesforce and reply checks" | Complete current guard reads |
| Reference | `../references/prep.md` | "Enrichment", "No enrollment", "Helper evidence" | Separately approved credits and reconciled results |
| Reference | `references/scrubber.md` | "Run", "Output Contract", "Operator Checklist", "Fail-Closed Model" | Full-column scrub and independent audit |
| Per-run evidence | Prospecting thread and sandbox | Original rows, event details, per-list overrides, complete native reads, C approvals and current receipts | Evidence for this list, never Git |

## Process

1. Intake per `../references/prep.md` "Intake", including the list, event, attendance dates, location and ask.
2. Prep read-only per `../references/prep.md` "Salesforce and reply checks". Complete exact Account matching, Apollo identity, active-sequence, invite-export and reply checks.
   With no usable email, defer only exact-email checks until enrichment returns an address. Complete them and rerun the helper before E1. Unchecked rows stay needs_input.
   Exclude every Account outside Operator's named accounts. Missing evidence stays needs-input.
3. Enrich only helper enrichment_candidates whose sole exclusion is unverified_email per `../references/prep.md` "Enrichment".
   Each C proposal discloses Apollo CRM sync and requires separate exact count and estimated-credit approval. Waterfall has its own approval.
4. Run `policy.tooling.scripts.event_list_prep` on reviewed evidence per `../references/prep.md` "Helper evidence".
   Check after prep and each helper. If no recipients and no enrichment remain, follow `../references/prep.md` "No enrollment" and return the result to the coordinator.
5. For a nonempty candidate list, run `policy.tooling.scripts.event_scrub_leads` scrub and audit-clean-output per `references/scrubber.md` "Run".
   Both reports must say PASS. Then run `policy.tooling.scripts.event_make_batches`, retain Website, reconcile counts and hold domain mismatches.
6. Return the viable prepared list and complete receipts to Sequence Plan, or return no-enrollment evidence and the Pipeline list to the coordinator. Do not load either receiving contract here.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | Candidates needing enrichment, operation, count and estimated credits | Approve the first exact C spend or skip |
| 3 | Each remaining C operation and credit estimate, including CRM-sync disclosure | Approve that spend or skip, never inherited from another operation |

## Audit

| Check | Pass Condition |
|---|---|
| Prep, before output | Every source row reconciles to one normalized contact or reported duplicate. Guard reads complete, Accounts belong to Operator, exclusions have reasons and overrides cannot expand scope |
| Credits, before each spend | Operator approved that exact count and estimated credit spend. Waterfall search has its own approval |
| Hygiene, before output | For a nonempty candidate list, scrub and independent audit both PASS. Batch counts reconcile, missing fields and domain mismatches remain held unless explicitly resolved |
| No enrollment | No recipients and no remaining enrichment return to the coordinator without an audit of nonexistent files or Apollo enrollment writes |
| Scope, throughout | No direct Salesforce writes or enrollment. Separate exact C approvals with Apollo CRM-sync disclosure. Helper labels never grant permission |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Enrichment results | Apollo and sandbox, after approval only | Each exact C operation, native status, credit use and disclosed CRM-sync outcome |
| Prepared list | Prospecting thread and sandbox | Reviewed rows, exclusions, holds, guard and C receipts, scrub audits and reconciled batches for Sequence Plan |
| No-recipient result | Prospecting thread and sandbox | Every row reconciled, remaining enrichment status and Pipeline list for coordinator close |
