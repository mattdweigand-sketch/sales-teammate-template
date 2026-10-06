# Prospecting routes

Enter through `workspaces/prospecting/AGENTS.md` for ownership and boundaries. Select one workflow and only the applicable contract Inputs.
Every workflow is limited to existing Salesforce Accounts owned by `policy.prospecting.identity.sfdc_user_id`. Current Salesforce ownership defines the named-account list.
Resolve one Account before research, outreach, or enrollment. Missing or ambiguous identity stops. Other-owner and house-owned Accounts are outside scope.

## Task routing

| Task or event | Contract | Output and handoff | Human check |
|---|---|---|---|
| Signals, adoption, outreach or proven send | `workflows/signal-prospecting/CONTEXT.md` | Qualified evidence, approved unsent draft or proven-send Task | Research claim review, exact draft or Task approval. Operator sends manually |
| Named-account event contacts or `event-sequence` | `workflows/event-sequence/CONTEXT.md` | Approved Apollo sequence or no-enrollment receipt, Pipeline handoff | Separate enrichment spends, then exact list, copy, mailbox and schedule |

Named skills use the direct root AGENTS.md routes. A broad request uses its workflow's Pipeline table to select a stage.
An open Opportunity routes to Pipeline. Another seller's Account routes to that owner. A warm conversation stops cold outreach.
Discovery and account claiming are retired. Research only queries adoption for a resolved named Account. No territory-discovery query or weekly discovery run remains.
Artifacts stay in the Prospecting thread, sandbox, Salesforce or Gmail. Every external write retains its exact approval and native readback.

## Shared resources

Load only the sections named by the selected contract's Inputs. Workflow-shared resources stay with their workflow and stage-private resources stay with their stage.

| Path | Holds | Edited by |
|---|---|---|
| `references/icp.md`, `references/signals.md` | Shared persona guidance and signal taxonomy. Outreach owns its private talk track | Operator, by hand |
| `scripts/` | Helpers shared by Research, Outreach and Follow-up. Paths and interfaces stay in the repo-wide helper catalog | Operator, with tests |
