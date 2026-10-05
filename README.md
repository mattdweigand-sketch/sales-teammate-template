# Sales Teammate Template

A reusable sales agent system with five workspaces, 18 named workflows, one-pass onboarding and fictional examples.
Salesforce holds records. Gmail, Calendar and transcripts provide evidence. Exact approval and native readback govern external writes.

The template ships unconfigured. Onboarding makes a separate copy with your settings and leaves this template reusable.
The [build specification](_core/template-spec.md) defines scope and acceptance. The [adapter guide](_core/onboarding/adapters.md) explains live prerequisites and mapping.

## Get started

Open this repository with a coding agent that can read files and run local commands. Give it this request.

```text
Help me set up this Sales Teammate template.
Read AGENTS.md and _core/onboarding/CONTEXT.md.
Ask whether I want a fictional demo or a workspace for my company.
Collect the remaining setup answers together and explain unfamiliar fields.
Create a separate workspace folder, prepare Python, and run setup and check.
Keep my answers and run outputs outside the template and the new workspace.
Show me the result and the remaining steps before live use.
```

Choose **demo** to explore the workflows with fictional settings. Choose **configured** to supply your company, identity, product, sales targets and integration mappings.
The agent uses the [questionnaire](_core/onboarding/questionnaire.md) and saves the answers for setup. You do not need to edit JSON by hand.

You receive a separate folder containing the five workspace definitions, your settings and 18 workflow pointer files.
A successful local check reports 18 routes and an empty errors list. It reports `external_ready` as false because this check only validates local setup.

For live use, follow the [adapter guide](_core/onboarding/adapters.md) to verify connections and load the workflows in your agent runtime.
Creating actual teammates and enabling schedules are separate deployment steps. The included runtime instructions target Perplexity Computer.

If you prefer terminal setup, the [onboarding guide](_core/onboarding/CONTEXT.md#terminal-demo) provides a runnable demo and explains each step.

## Workspaces

| Workspace | Responsibility |
|---|---|
| [Prospecting](workspaces/prospecting/CONTEXT.md) | Named-account signals, privacy-safe adoption, unsent outreach, proven-send follow-up and approved event campaigns |
| [Pipeline](workspaces/pipeline/CONTEXT.md) | Meeting prep, interaction sync, watches, hygiene, triage, pilot usage, customer milestones and closing |
| [Deal Coaching](workspaces/deal-coaching/CONTEXT.md) | Read-only call, deal and pre-meeting coaching and reviewed criteria proposals |
| [Forecasting](workspaces/forecasting/CONTEXT.md) | Evidence-backed forecast, pace and forward coverage |
| [Systems](workspaces/systems/CONTEXT.md) | Authorized repository and configuration changes and read-only health review |

Root AGENTS.md routes all names directly to scoped contracts. CONTEXT.md routes broader requests to their workspace.
Shared policy and rules have one home in _core. Workflow-only references stay with their owner.
Run artifacts, customer material and credentials stay outside Git. All example data is fictional. Source-company collateral and Git history are excluded.

## Verification

For maintainers, run these commands from the template checkout after preparing the Python environment in the onboarding guide.
The rehearsal folder must not already exist.

```bash
PYTHONDONTWRITEBYTECODE=1 "$HOME/.local/share/sales-teammate/venv/bin/python" -B -m unittest discover -s _core/tests
"$HOME/.local/share/sales-teammate/venv/bin/python" -B _core/scripts/rehearse.py --scratch "$HOME/sales-workspaces/rehearsal"
```

The rehearsal configures a scratch workspace, follows every named route and material branch, executes helpers and local connector doubles, and writes its report outside Git.
Local simulation proves the tested mechanics. Live authentication, CRM schemas, mail delivery, warehouse results, runtime permissions and schedules need actual verification.

## Repo map

```text
sales-teammate-template/
├── AGENTS.md
├── CONTEXT.md
├── README.md
├── workspaces/             Five responsibility boundaries and scoped workflow contracts
├── _core/
│   ├── onboarding/         Questionnaire, example answers, adapter schema and guide
│   ├── assets/fonts/       Licensed bundled PDF fonts
│   ├── scripts/            Shared helpers, onboarding and rehearsal
│   ├── policy.yaml         Demo settings and helper registry
│   ├── rules.md            Canonical approval, evidence and write rules
│   ├── template-spec.md    Build specification
│   ├── NOTICE.md           Provenance and retained notices
│   └── tests/              Synthetic regression tests
└── .github/                CI
```

See [maintenance conventions](_core/CONVENTIONS.md) and [notices](_core/NOTICE.md) for ownership and provenance.
