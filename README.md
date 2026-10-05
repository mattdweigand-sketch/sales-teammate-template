# Sales Teammate Template

A reusable sales agent system with five workspaces, 18 named workflows, one-pass onboarding and fictional examples.
Salesforce holds records. Gmail, Calendar and transcripts provide evidence. Exact approval and native readback govern external writes.

Start with [onboarding](_core/onboarding/CONTEXT.md). The template ships unconfigured. Local setup creates a separate demo or configured workspace.
The [build specification](_core/template-spec.md) defines scope and acceptance. The [adapter guide](_core/onboarding/adapters.md) explains live prerequisites and mapping.

## Quick start

Use Python 3.12. Keep environments, answers and run artifacts outside the repository.

```bash
python3.12 -m venv /absolute/sales-venv
/absolute/sales-venv/bin/python -m pip install -r _core/requirements.txt
cp _core/onboarding/answers.example.json /absolute/answers.json
# Edit the answer file once, then instantiate at an absent destination.
/absolute/sales-venv/bin/python -B _core/scripts/onboard.py setup --answers /absolute/answers.json --destination /absolute/my-sales-workspace
/absolute/sales-venv/bin/python -B _core/scripts/onboard.py check --workspace /absolute/my-sales-workspace
```

Omit --answers for the flat interactive questionnaire. Use demo mode for reserved domains and fictional IDs.
Configured mode saves actual setup values but does not verify connectors, install agents or activate automations. Follow the adapter guide before live use.

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

Run the regression suite in the prepared environment from the checkout.

```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s _core/tests
python -B _core/scripts/rehearse.py --scratch /absolute/absent-sales-rehearsal
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
