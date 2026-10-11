# Prospecting routes

Enter through `workspaces/prospecting/AGENTS.md` for ownership and boundaries. Select one contract and only its applicable Inputs.
Every workflow is limited to existing Salesforce Accounts owned by `policy.prospecting.identity.sfdc_user_id`. Current Salesforce ownership defines the named-account list.
Event Sequence also admits outreach-owner rows per `AGENTS.md`.
Resolve one Account before research or outreach. Event enrollment also follows that exception. Ambiguous identity stops. Other sellers' Accounts stay outside scope.

## Task routing

| Task or event | Contract | Output and handoff | Human check |
|---|---|---|---|
| Named-account signals, adoption, outreach or proven-send follow-up | `workflows/signal-prospecting/CONTEXT.md` | Qualified public bundle, permitted adoption report, unsent draft or Task | Resolve identity and review handoffs. Approve exact draft or Task fields |
| Named-account event contacts or `event-sequence` | `workflows/event-sequence/CONTEXT.md` | One Apollo sequence and Pipeline handoff | Approve each enrichment spend, then exact list, copy, mailbox, and schedule |

Signal Prospecting's overview selects Research, Outreach or Follow-up. Named Signal skills bypass it and enter their stage contract directly.
Direct entry is allowed with the receiving contract's required evidence. Both Research branches run independently and write no customer records.
Event Sequence's coordinator enters List Prep, Sequence Plan or Launch only with that stage's required evidence. It loads each stage only when entered, never their combined Inputs.
It uses the same named accounts, with separate C spends and exact same-thread E enrollment approval. Valid resumes retain the original run_start and approval scope.
An open Opportunity routes to Pipeline. Another seller's Account routes to that owner. A warm conversation stops cold outreach.
Discovery and account claiming are retired. Research only queries adoption for a resolved named Account. No territory-discovery query or weekly discovery run remains.
Artifacts stay in the Prospecting thread, sandbox, Salesforce or Gmail. Every external write retains its exact approval and native readback.

## Shared resources

Load only the sections named by the selected contract's Inputs.

| Path | Holds | Edited by |
|---|---|---|
| `references/icp.md`, `references/signals.md` | Shared persona guidance and signal taxonomy. Outreach owns its private talk track | Operator, by hand |
| `scripts/` | Helpers shared by Research, Outreach and Follow-up. Paths and interfaces stay in the repo-wide helper catalog | Operator, with tests |
