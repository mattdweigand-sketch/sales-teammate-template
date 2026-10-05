---
cadence: daily
reads: _core/policy.yaml (prospecting, pipeline, tooling), _core/rules.md, references/, Salesforce, live automations, project deal threads, approved retained-thread evidence
writes: nothing
next: Pipeline receives configuration proposals, Operator approves deal-thread changes
---

# Watch Sync

Reconcile active-deal buyer-email watches, shared-channel account watches, and deal threads. Propose only. A scheduled run cannot edit other automations.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `prospecting.identity.sfdc_user_id`, `pipeline.stages`, `tooling.generic_email_domains` | Owner, shared-channel stages, and excluded domains |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#scheduled_runs`, `rules#not_checked_means`, `rules#absence_conclusions`, `rules#approval` | Run context, evidence limits, and approval |
| Reference | `references/reconcile.md` | "Read", "Compare and route" | Queries, comparison, retained-thread exceptions, and delivery |
| Per-run evidence | Current project automations, deal threads, and Operator's approved retained-thread list | Live identifiers, complete settings, and explicit exceptions only | Keep customer names and identifiers outside Git |

## Process

1. Start per `rules#run_start`. Read Salesforce and the live consumers per `references/reconcile.md` "Read".
2. Compare domains, account lists, and deal threads per "Compare and route". Missing settings or exception evidence are not checked, never inferred empty.
3. Number each add or drop with its Opportunity evidence. Append deal-thread proposals under `Deal threads, needs Operator approval`.
4. Post here and route the same numbered proposals with `pplx automation notify-source --message` to Pipeline. A receipt is not approval for a thread change.
5. If nothing differs and no thread change is needed, reply in one line and run `pplx automation suppress-run-notification`.

## Checkpoints

None. This workflow reads and routes proposals only. The receiver applies its existing authorization and configuration gates.

## Audit

| Check | Pass Condition |
|---|---|
| Scope | No automation edit, thread create or archive, Salesforce, Gmail, or Slack write |
| Evidence | All expected consumers and relevant records were read completely, or their comparison is explicitly not checked |
| Retained threads | Operator's explicit retained-thread exceptions are read from approved run evidence and excluded from archive proposals |
| Handoff | Thread changes are labeled for Operator approval and are never applied on receipt |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Configuration proposals | Run thread and Pipeline source thread | Numbered domain and account additions or removals with Opportunity links |
| Deal-thread proposals | Same handoff, after configuration proposals | Account, Opportunity Id, stage, CloseDate, and Operator approval label |
| Saved settings and exceptions | Sandbox | Complete live evidence, never in Git |
