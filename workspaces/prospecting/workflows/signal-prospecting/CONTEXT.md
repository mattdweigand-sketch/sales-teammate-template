# Signal Prospecting

Named-account prospecting from signals or permitted adoption evidence through approved unsent outreach and proven-send follow-up.
This overview routes broad requests only. Named skills enter their stage contract directly and load only its applicable Inputs.

## Pipeline

| Stage | Trigger | Output | Human check | Contract route |
|---|---|---|---|---|
| Research | Named account or adoption question | Qualified public bundle or permitted adoption report | Resolve identity, confirm aliases or review the adoption claim before handoff | `01-research/CONTEXT.md` |
| Outreach | Qualified bundle and resolved named Account | One approved unsent Gmail draft | Approve exact message. Operator sends manually | `02-outreach/CONTEXT.md` |
| Follow-up | Native proof of a matching Gmail send | One approved Task with native readback | Approve exact Task fields | `03-followup/CONTEXT.md` |

## Entry and handoffs

Select the stage from the request and available evidence. Direct entry requires the receiving contract's evidence.
Both Research branches run independently and write no customer records. Research never progresses automatically to drafting.
Outreach uses the actual qualified bundle Operator chooses. Operator sends manually before Follow-up, which requires native proof of the matching send.
Current Account ownership defines the named-account list. Open Opportunities hand evidence to Pipeline. Another seller's Account routes to that owner.
A warm conversation stops cold outreach. Discovery and account claiming remain retired. Every external write keeps its exact approval and native readback.
Artifacts stay in the Prospecting thread, sandbox, Salesforce or Gmail. This overview adds no skill, runtime step or mandatory read.

## Shared resources

Load only the sections named by the receiving stage's Inputs.

| Path | Holds | Edited by |
|---|---|---|
| `../../references/icp.md`, `../../references/signals.md` | Shared persona guidance and signal taxonomy. Outreach owns its private talk track | Operator, by hand |
| `../../scripts/` | Helpers shared by the Signal stages. Paths and interfaces stay in the repo-wide helper catalog | Operator, with tests |
