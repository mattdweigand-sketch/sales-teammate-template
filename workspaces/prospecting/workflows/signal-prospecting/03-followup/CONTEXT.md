---
cadence: one-off
reads: references/, _core/policy.yaml (prospecting, tooling, salesforce), _core/rules.md and current run evidence
writes: Salesforce Task after approval
next: Pipeline when an open Opportunity exists, otherwise Outputs handoff
---

# Follow-up

One proven send becomes one open Salesforce Task (`policy.prospecting.followup.max_tasks_per_run`). The completed Email Task is never created here, the Gmail sync owns it. Manual only
(`rules#approval`).

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Policy | `_core/policy.yaml` | prospecting.identity, prospecting.followup | Set due-date rules and exact Task fields for the proven send |
| Tool | `workspaces/prospecting/workflows/signal-prospecting/03-followup/scripts/prospect_followup_gate.py` | Docstring and CLI | Validate the proven send identity and reject duplicate follow-up Tasks |
| Tool | `workspaces/prospecting/scripts/prospect_readback_check.py` | Docstring and CLI | Compare approved fields with the complete native returned record or draft |
| Working | Live Gmail sent-mail proof, Salesforce Account, Contact and Task reads, outreach verdict in this thread | Historical labels as approved at send time | Tie the Task to a native sent message and its historical approved signal |
| Reference | `workspaces/prospecting/workflows/signal-prospecting/03-followup/references/execution.md` | Full file | Link sent proof, existing Tasks and exact approval to one follow-up write |
| Rules | `_core/rules.md` | rules#approval, rules#write_protocol, rules#note_prefix, rules#absence_conclusions, rules#not_checked_means | Require exact approval and native readback, and separate unread evidence from absence |
| Policy | `_core/policy.yaml` | tooling | Registered helper paths |
| Policy | `_core/policy.yaml` | prospecting.salesforce, salesforce.note_prefix | Fresh open Opportunity reads and canonical Description prefix |

## Process

1. Load the scoped Inputs.
2. Establish a matching live Gmail send using Send proof. A draft or memory does not qualify. Any open Opportunity hands evidence to Pipeline and stops prospecting.
3. Resolve the current Operator-owned named Account, Contact and existing Tasks using Salesforce reads. Query all open Opportunities on the Account. Any open deal routes to Pipeline.
4. Build the same-thread signal packet and run the follow-up gate using Packet and gate. A block ends the run.
5. Run the Audit and present the exact Task using Proposal and Report. Stop for approval.
6. After approval create the approved Task and compare all fields with native readback using Write and readback. Stop on mismatch. Recheck owner, open Opportunities and duplicates before writing
per rules#write_protocol.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 5 | Exact Task fields tied to the proven send | Approve these fields. A changed field, recipient or sent message requires a new proposal |

## Audit

| Check | Pass Condition |
|---|---|
| Send and task | Live send proof matches the requested action and prospect_followup_gate.py allows the exact proposed Task |
| Ownership, before proposals and writes | Current owner is prospecting.identity.sfdc_user_id and complete open Opportunity reads pass. Any open deal routes to Pipeline |
| Scope | No send or Opportunity write. No run or customer material in Git. A failed read is not checked |
| Authority mirrors | policy.prospecting.approval.unattended_writes remains false and policy.prospecting.approval.readback_required remains true. Core rules own authority |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Exact Task proposal | Current thread | Report with the gate Task tied to the proven send |
| Approved Task | Salesforce after approval | One Task read back by Id. Final output, no further stage |
| Pipeline handoff | Pipeline thread | Account and open Opportunity IDs with dated evidence. No prospecting writes |
