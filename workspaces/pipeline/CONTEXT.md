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
| Weekly pipeline review or requested review | `workflows/pipeline-review/CONTEXT.md` | Thread report and verified Salesforce corrections for Forecasting | Numbered or lettered approval in the weekly pass |
| `next step <Account> <action> by <date>`, in any project thread | `workflows/task-triage-speed-run/CONTEXT.md` | One fresh next-step and Task row | One row approval, or one date question |
| Due, overdue, or undated Tasks | `workflows/task-triage-speed-run/CONTEXT.md` | Verified Salesforce queue and unsent Gmail drafts | Section walk and record approvals per contract |
| Pilot usage review or PDF request | `workflows/pilot-usage/CONTEXT.md` | Thread report or sandbox PDF, handed off per `rules#pilot_handoff` | Approve numbered PDF drafts before the build |
| Customer milestones, scheduled or one named Account | `workflows/customer-review/CONTEXT.md` | Short milestone assessment and numbered proposals in the run thread | Approve each record before writes and readback |
| Signed deal or close request | `workflows/close/CONTEXT.md` | Verified Salesforce records, receipt, and any approved Slack handoff | Approve each proposed record or external action |
| Closed Won downstream Task evidence from a deal thread | `workflows/close/CONTEXT.md` | In a standalone Pipeline run, `/close <OpportunityId>` for downstream verification and initial proposal E | Handoff is evidence only. Existing Close approval gates apply |

## Internal ask poll

For internal-ask nudges, including a scheduled poll-mode run, load `references/internal-asks.md`, Full file, and only the inputs it names.
Cadence stays in `policy.pipeline.schedule.ask_nudges`. Output is an unsent Slack draft or an answered-ask summary, with per-task results in the run thread.
This workspace procedure handles Teammate internal-ask tasks, not Salesforce Tasks. It adds no skill or automation configuration.

## Handoffs

Salesforce suggestions from Deal Coaching enter the responsible workflow above for evidence review and Operator's approval. They never authorize a write by themselves.
Pipeline-review supplies verified Salesforce corrections to Forecasting. No receiving workflow loads another workflow's folder to consume a handoff.
Deal assessment routes to Deal Coaching. Forecast calls and pace tracking route to Forecasting through root `CONTEXT.md`.

Inbound handoffs are evidence under `rules#handoff_delivery`. Each row names the receiving contract and its existing approval scope. No row adds a pause or approval.

| Inbound source | Receiving contract | Existing approval scope |
|---|---|---|
| Forecasting CloseDate and Next Step corrections | `workflows/pipeline-review/CONTEXT.md` for CloseDate. `workflows/task-triage-speed-run/CONTEXT.md` one-deal mechanics for Next Step and its Task | Evidence only. Pipeline makes its own fresh proposal. Operator approves the letter or row here |
| Deal Coaching Salesforce suggestions | The responsible workflow above, interaction-sync, pipeline-review, task-triage-speed-run or close | One-line evidence note. Operator approves the receiving contract's proposal before any write |
| Event-sequence open-Opportunity contacts and signal active-deal evidence | The Opportunity's deal thread, under `rules#task_date_coordination` deal-thread lines | Evidence only. Deal-thread writes need Operator's typed command and label approval there. No prospecting write |
| Customer-review recommended actions on an open Opportunity | The active deal thread first, otherwise `workflows/pipeline-review/CONTEXT.md` hygiene | Read-only advice. No new Opportunity. Writes keep the receiving contract's approval |
| Interaction-sync sweep unlogged calls | Deal thread when available, otherwise `workflows/interaction-sync/CONTEXT.md` single-call steps | Receiving never approves logging. Operator approves each record before writes |
| Watch-sync numbered proposals | buyer-email watch domain and channel-watch Account-list add or drop only under the adopter's verified approval, one line per change, read back | Deal-thread create or archive need Operator's approval. Never applied on receipt. Receipt grants no approval |

Watch-sync row. Handle approved changes in a permitted execution context. A scope failure stays pending for an authorized direct turn. Claim applied only after native settings readback.

## Shared resources

Load only the sections named by the selected contract's Inputs or rules.

| Path | Holds | Edited by |
|---|---|---|
| `references/org-lookup.md` | Field mappings and dated evidence behind `rules#org_lookup` | Operator, by hand |
| `references/pilot-usage-queries.md` | Read-only usage queries shared by pilot-usage and customer-review | Pipeline requirements, Systems implementation |
| `references/triggers.md`, `references/deal-activity-reads.md` | Shared trigger definitions and native deal-activity reads | Pipeline requirements, Systems implementation |
| `references/watches.md` | Buyer-email and shared-channel watch procedure. Each prompt selects one section. Runtime IDs, admission lists and exceptions stay in live settings | Pipeline requirements, Systems implementation |
| `scripts/` | account_usage, deal_thread_match, gmail_contact_stats, task_reschedule_check and top_actions helpers shared by Pipeline workflows. Paths and interfaces stay in the repo-wide helper catalog | Operator, with tests |
