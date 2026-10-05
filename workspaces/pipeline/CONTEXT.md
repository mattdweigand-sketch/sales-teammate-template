# Pipeline routes

Enter through `workspaces/pipeline/AGENTS.md` for ownership and boundaries. Select one contract below, then only its applicable Inputs rows.
Triggers identify capabilities, not a sequence. Schedule values and sales behavior remain in the selected contract's canonical policy and rules.

## Task routing

| Task or event | Contract | Output and handoff | Human check |
|---|---|---|---|
| Named external call or call window | `workflows/sales-call-prep/CONTEXT.md` | Brief and CRM notes in the run thread. After the call, Pipeline logs the completed interaction | Read-only brief has no write approval step |
| Completed call or interaction | `workflows/interaction-sync/CONTEXT.md` | Approved Salesforce records feed pipeline-review. Unsent draft in Gmail for Operator | Review proposals before writes and draft creation |
| Daily completed-call sweep, sweep branch | `workflows/interaction-sync/CONTEXT.md` | Unlogged-call evidence and Task proposals to deal threads or Pipeline | Read-only sweep never approves logging |
| Daily watch or deal-thread reconciliation | `workflows/watch-sync/CONTEXT.md` | Numbered configuration and thread proposals to Pipeline | No changes in the run. Thread changes need Operator approval |
| Pipeline review or hygiene finding | `workflows/pipeline-review/CONTEXT.md` | Thread report and verified Salesforce corrections for Forecasting | Numbered or lettered approval per branch |
| Due, overdue, or undated Tasks | `workflows/task-triage-speed-run/CONTEXT.md` | Verified Salesforce queue and unsent Gmail drafts | Section walk and record approvals per contract |
| Pilot usage review or PDF request | `workflows/pilot-usage/CONTEXT.md` | Thread report or sandbox PDF, handed off per `rules#pilot_handoff` | Approve numbered PDF drafts before the build |
| Customer milestones and independent renewal notices, scheduled or one named Account | `workflows/customer-review/CONTEXT.md` | Short milestone assessment and numbered proposals in the run thread | Approve each record before writes and readback |
| Signed deal or close request | `workflows/close/CONTEXT.md` | Verified Salesforce records, receipt, and any approved Slack handoff | Approve each proposed record or external action |

## Handoffs

Salesforce suggestions from Deal Coaching enter the responsible workflow above for evidence review and Operator's approval. They never authorize a write by themselves.
Pipeline-review supplies verified Salesforce corrections to Forecasting. No receiving workflow loads another workflow's folder to consume a handoff.
Deal assessment routes to Deal Coaching. Forecast calls and pace tracking route to Forecasting through root `CONTEXT.md`.

## Shared resources

Load only the sections named by the selected contract's Inputs or rules.

| Path | Holds | Edited by |
|---|---|---|
| `references/org-lookup.md` | Field mappings and dated evidence behind `rules#org_lookup` | Operator, by hand |
| `references/pilot-usage-queries.md` | Read-only usage queries shared by pilot-usage and customer-review | Pipeline requirements, Systems implementation |
| `scripts/` | account_usage and gmail_contact_stats helpers shared by Pipeline workflows. Paths and interfaces stay in the repo-wide helper catalog | Operator, with tests |
