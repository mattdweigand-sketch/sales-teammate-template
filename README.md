# Sales Teammate Template

Sales Teammate is a set of AI assistants that help with everyday sales work.
They prepare for customer meetings, keep deal records up to date, forecast revenue, and recommend next steps.

This template holds the instructions, shared rules, and tools those assistants use.
Onboarding adapts them to your company, product, sales process, and connected tools.

## Setup

1. Open this repository with your AI agent.
2. Ask it to **set up Sales Teammate for your company**.
3. Answer the onboarding questions. Your agent creates a separate workspace with your settings.

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

Prospecting works only on existing Salesforce Accounts owned by the user. Research, Outreach, Follow-up, and Event Sequence each have a direct workflow folder.
The Prospecting context explains their handoffs. Named skills go directly to their contracts through root `AGENTS.md`.
