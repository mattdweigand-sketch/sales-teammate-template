# Sales Teammate Template

Sales Teammate is a set of AI assistants that help with everyday sales work.
They prepare for customer meetings, keep deal records up to date, forecast revenue, and recommend next steps.

This template holds the instructions, shared rules, and tools those assistants use.
Onboarding adapts them to your company, product, sales process, and connected tools.

## Setup

1. Open this repository with your AI agent.
2. Ask it to **set up Sales Teammate for your company**.
3. Answer the company questions and review each system with your agent. It creates a separate workspace with your settings.

Onboarding covers every connector, MCP or API adapter, credential requirement, org skill, downstream system and local tool used by the source.
You can configure, defer or mark a system unused. Credentials go directly into your runtime secret store. Deferred dependencies keep their affected operations pending.
Setup leaves schedules inactive and live connection checks pending.

See [onboarding](_core/onboarding/CONTEXT.md) for setup details and the connection checks to complete before live use.

## Workspaces

| Workspace | Responsibility |
|---|---|
| [Prospecting](workspaces/prospecting/CONTEXT.md) | Researches named accounts, prepares approved unsent outreach, runs approved event sequences, and hands open deals to Pipeline. |
| [Pipeline](workspaces/pipeline/CONTEXT.md) | Prepares for customer meetings, keeps deal records current, organizes follow-up work, reviews customer trials, and helps finish signed deals. |
| [Deal Coaching](workspaces/deal-coaching/CONTEXT.md) | Reviews calls and deals, spots missing information or relationships, and suggests questions and next steps to improve the chance of winning. |
| [Forecasting](workspaces/forecasting/CONTEXT.md) | Estimates how much revenue deals are likely to bring in this quarter and tracks progress toward sales goals. |
| [Systems](workspaces/systems/CONTEXT.md) | Keeps the assistants' instructions and settings up to date, checks that they work as intended, and brings improvement ideas to the user. |

## Repo map

```text
sales-teammate-template/
├── README.md            Start here for an overview
├── AGENTS.md            Overall roles and where assistants find instructions
├── CONTEXT.md           Guide to which workspace handles each kind of request
├── workspaces/          Instructions grouped by the work each assistant does
│   ├── prospecting/
│   │   └── workflows/
│   │       ├── signal-prospecting/
│   │       │   ├── 01-research/
│   │       │   ├── 02-outreach/
│   │       │   └── 03-followup/
│   │       └── event-sequence/
│   │           ├── 01-list-prep/
│   │           ├── 02-sequence-plan/
│   │           └── 03-launch/
│   ├── pipeline/
│   ├── deal-coaching/
│   ├── forecasting/
│   └── systems/
├── _core/               Shared rules, resources, tools, templates, and tests
│   ├── onboarding/      Company setup questions and connection guide
│   ├── collateral/
│   ├── scripts/
│   ├── templates/
│   └── tests/
└── .github/             Automated checks for repository changes
```

## Where to start

Open a workspace above to see the jobs it handles. For guidance on changing the repo, see [how it is maintained](_core/CONVENTIONS.md).

Each workspace keeps its workflows together. Shared references and helpers used only within Prospecting or Pipeline live in that workspace's `references/` and `scripts/` folders.
Repo-wide resources, policy, rules, the helper catalog and tests live in `_core/`.

Signal Prospecting works only on existing Salesforce Accounts owned by the user and groups Research, Outreach and Follow-up.
Event Sequence may include explicitly marked house-owned or missing Accounts under optional configured policy. Both branches default off.
Event Sequence coordinates List Prep, Sequence Plan and Launch. Each stage loads only its scoped Inputs and preserves its approval and handoff gates.
The Prospecting context routes these two workflows. Named Signal skills go directly to their stages through root `AGENTS.md`. Event Sequence enters through its coordinator.

## Recent workflow improvements

Pipeline review uses weekly or requested reports. Task triage owns routine follow-up work and checks native state before approved date changes.
Forecasts preserve unknown evidence as Held rows. An optional shared Google Slides branch updates only the configured operator slide after exact approval.
Customer review uses first-win milestones. Legacy renewal receipts remain readable and do not create new renewal work.
Systems can run `process-capture` to test a reusable procedure on a second case. Only generalized approved capture records enter the repo.

## Configured deployment and upgrades

Onboarding creates a separate company workspace without Git or external activation. Review operating policy and configure the adopter deployment repository, remote and branch.
Publish those actual configured files through authorized repository maintenance before affected CRM, Gmail draft or Event writes.
Proposal snapshots bind the selected deployed instructions and target. Old snapshots require a fresh proposal. Fetch and native record reads do not form an atomic lock.

Existing adopters should port approved mechanisms into their own repository. Preserve tenant values, field/table maps, targets, product evidence, house-owner opt-ins and existing permissions.
Do not rerun onboarding over an existing workspace. Remove legacy auto_date_move settings and obsolete daily Pipeline or renewal schedules through separately authorized configuration.
Read-only runs, internal-ask polling and unsent manager drafts retain their selected contract scope. This template release does not activate any runtime integration or automation.

Existing run evidence with old actor fields needs a current reviewed proposal using `operator_*` and `operator_typed_command`. Never rewrite historical approval receipts to reuse them.
Revision snapshots use format 2 and bind the deployed repository, remote and branch. Rebuild affected proposals and 19 skill pointers against the configured deployment.
Legacy renewal entries are ignored and retained. Migration never automatically reschedules, completes or removes Salesforce Tasks.
Review the new integration choice and policy fields with the adopter. Keep optional Slides and the size floor disabled until their selected configuration is approved and verified.

Git rollback changes instructions. It does not reverse sent mail, campaign enrollment, provisioning or customer-system writes.
The responsible workflow reconciles each actual partial external state before any separately approved corrective action.
