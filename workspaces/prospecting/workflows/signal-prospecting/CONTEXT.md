# Signal Prospecting

Research existing Operator-owned Accounts, prepare reviewed unsent outreach, then create follow-up Tasks only after a proven send.
This overview routes broad requests. Named skills go directly to their stage and load only its applicable Inputs.

## Pipeline

| Stage | Trigger | Output | Human check | Contract route |
|---|---|---|---|---|
| Research | Named account or adoption question | Qualified public bundle or permitted adoption report | Resolve identity, confirm aliases or review the adoption claim before handoff | `01-research/CONTEXT.md` |
| Outreach | Qualified bundle and resolved named Account | One approved unsent Gmail draft | Approve exact message. Operator sends manually | `02-outreach/CONTEXT.md` |
| Follow-up | Native proof of a matching Gmail send | One approved Task with native readback | Approve exact Task fields | `03-followup/CONTEXT.md` |

## Entry and handoffs

Direct entry is allowed with the receiving contract's required evidence. Both Research branches run independently and write no customer records.
Research does not automatically draft outreach. Operator chooses the bundle. Operator sends the approved draft manually before Follow-up can begin.
An open Opportunity routes to Pipeline. Another seller's Account routes to that owner. A warm conversation stops cold outreach.
Artifacts remain in their existing thread, sandbox, Salesforce or Gmail locations. Every external write retains its exact approval and native readback.

## Shared resources

Workspace references and helpers remain under `workspaces/prospecting/references/` and `workspaces/prospecting/scripts/`.
Each stage owns its private references and helpers. Read only its declared sections. No Event Sequence or sibling-stage Inputs are loaded for a named Signal skill.
