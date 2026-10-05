# Onboarding

Create a separate Sales workspace from this template. Setup remains local and preserves template files.
For guided setup, use the request in the root README with a coding agent that can read this repository and execute commands.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Persistent choices | `questionnaire.md`, `questions.json`, `answers.example.json` | Remaining setup questions only | One-pass configuration |
| Adapter schema | `adapter-schema.json` and `adapters.md` | Needed fields, tables, prerequisites and verification | Compatible integrations |
| Tools | `_core/scripts/onboard.py` | setup, questions, check | Validate and copy without overwrites |

## Process

1. Explain demo and configured mode, then collect remaining questions from questionnaire.md together. Explain unfamiliar IDs and mappings. Keep per-run inputs at workflow entry.
2. Save personal answers outside both folders. Choose a destination folder that does not exist and a separate folder for run outputs. Use demo mode for fictional data.
3. Prepare Python 3.12 and _core/requirements.txt outside both folders. Run setup to validate answers, copy the template, apply settings and create all 18 workflow pointers.
4. Run check against the new destination. The mode must be demo or configured and all routes and helpers must resolve.
5. Follow adapters.md for actual tool verification and deployment. Review product evidence, schema, schedules and approval rules with the operator.

## Checkpoints

None for local setup because the requested copy is reversible. Actual agent creation, permissions and schedule activation need the operator's concrete deployment authorization.
Review derived product wording and note style with the operator before buyer use. Do not treat demo wording as approved company facts.

## Audit

| Check | Pass Condition |
|---|---|
| Configuration | Typed answers are valid, canonical policy is updated and no required answer is unresolved |
| Copy | Source bytes stay unchanged, destination was absent and no source Git history or runtime data was copied |
| Routing | All 18 named skill pointers resolve their exact contract, including shared Research branch selectors |
| Readiness | Mode and pending live checks are explicit. Local setup never claims connector or schedule readiness |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Configured workspace | Operator-selected external destination | Entry maps, policy, product guidance, helpers and skill pointers |
| Setup receipt | `_core/onboarding/status.json` in the configured workspace | Demo or configured mode and pending verification |

## Terminal demo

This optional example creates a fictional workspace at `~/sales-workspaces/demo`. Open a terminal in the template checkout first.
Python 3.12 must be available as `python3.12`. If it is missing, ask your coding agent to prepare the required Python runtime before continuing.
The Python environment holds the packages needed by the setup tool and helpers. It lives under your home folder, outside the repository.

```bash
python3.12 -m venv "$HOME/.local/share/sales-teammate/venv"
"$HOME/.local/share/sales-teammate/venv/bin/python" -m pip install -r _core/requirements.txt
```

Run setup using the included fictional answers. The destination must not already exist. The setup tool creates the parent folder if needed.

```bash
"$HOME/.local/share/sales-teammate/venv/bin/python" -B _core/scripts/onboard.py setup --answers _core/onboarding/answers.example.json --destination "$HOME/sales-workspaces/demo"
"$HOME/.local/share/sales-teammate/venv/bin/python" -B _core/scripts/onboard.py check --workspace "$HOME/sales-workspaces/demo"
```

Success reports `mode` as `demo`, `routes` as `18` and `errors` as `[]`. `external_ready` remains `false` because no live connections were checked.
Setup creates local configuration and pointer files. It does not create teammates in Perplexity Computer or activate schedules.

For company setup, the guided agent collects actual values and saves a JSON answer file outside both folders. Pass its path with `--answers` and use a new destination.
Omitting `--answers` starts the terminal questionnaire. Its list and mapping answers require JSON, so guided setup is easier when those formats are unfamiliar.
Use `check --allow-template` only to inspect this unconfigured template. Follow adapters.md to verify and deploy a configured workspace.
