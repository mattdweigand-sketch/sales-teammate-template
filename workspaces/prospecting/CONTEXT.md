# Prospecting routes

Enter through `workspaces/prospecting/AGENTS.md` for ownership and boundaries. Select one contract and only its applicable Inputs.
Every workflow is limited to existing Salesforce Accounts owned by `policy.prospecting.identity.sfdc_user_id`. Current Salesforce ownership defines the named-account list.
Resolve one Account before research, outreach, or enrollment. Missing or ambiguous identity stops. Other-owner and house-owned Accounts are outside scope.

## Task routing

| Task or event | Contract | Output and handoff | Human check |
|---|---|---|---|
| Buying signals or `signal-scan` | `workflows/research/CONTEXT.md` | Public-source verdict and qualified bundle for a named account | Confirm aliases and decide fit before outreach handoff |
| Adoption or `signal-user-scan` | `workflows/research/CONTEXT.md` | Privacy-checked named-account adoption report | Resolve ambiguous identity and review the adoption claim before handoff |
| Qualified bundle or `signal-outreach` | `workflows/outreach/CONTEXT.md` | Exact proposal and approved unsent Gmail draft | Approve To, Subject and Body. Operator sends manually |
| Proven Gmail send or `signal-followup` | `workflows/followup/CONTEXT.md` | Exact Task proposal tied to native send | Approve exact Task fields and associations |
| Named-account event contacts or `event-sequence` | `workflows/event-sequence/CONTEXT.md` | One Apollo sequence and Pipeline handoff | Approve each enrichment spend, then exact list, copy, mailbox, and schedule |

## Pipeline

| Stage | Trigger | Output | Human check | Contract route |
|---|---|---|---|---|
| Research | Named account or adoption question | Qualified public bundle or permitted adoption report | Resolve identity, confirm aliases or review the adoption claim before handoff | `workflows/research/CONTEXT.md` |
| Outreach | Qualified bundle and resolved named Account | One approved unsent Gmail draft | Approve exact message. Operator sends manually | `workflows/outreach/CONTEXT.md` |
| Follow-up | Native proof of a matching Gmail send | One approved Task with native readback | Approve exact Task fields | `workflows/followup/CONTEXT.md` |

Direct entry is allowed with the receiving contract's required evidence. Both Research branches run independently and write no customer records.
Event Sequence is a complete workflow beside Research, Outreach, and Follow-up. It uses the same named accounts, with its own list, spend, and enrollment review.
An open Opportunity routes to Pipeline. Another seller's Account routes to that owner. A warm conversation stops cold outreach.
Discovery and account claiming are retired. Research only queries adoption for a resolved named Account. No territory-discovery query or weekly discovery run remains.
Artifacts stay in the Prospecting thread, sandbox, Salesforce or Gmail. Every external write retains its exact approval and native readback.

## Shared resources

Load only the sections named by the selected contract's Inputs.

| Path | Holds | Edited by |
|---|---|---|
| `references/icp.md`, `references/signals.md` | Shared persona guidance and signal taxonomy. Outreach owns its private talk track | Operator, by hand |
| `scripts/` | Helpers shared by Research, Outreach and Follow-up. Paths and interfaces stay in the repo-wide helper catalog | Operator, with tests |
