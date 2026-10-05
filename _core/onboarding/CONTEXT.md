# Onboarding

Create a separate Sales workspace from this template. Setup remains local and preserves template files.
For guided setup, use the request in the root README with a coding agent that can read this repository and execute commands.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Persistent choices | `questionnaire.md`, `questions.json` | Remaining company setup questions only | One-pass configuration |
| Adapter schema | `adapter-schema.json` and `adapters.md` | Needed fields, tables, prerequisites and verification | Compatible integrations |
| Tools | `_core/scripts/onboard.py` | setup, questions, check | Validate and copy without overwrites |

## Process

1. Collect remaining company questions from questionnaire.md together. Reuse supplied settings and explain unfamiliar IDs and mappings. Keep per-run inputs at workflow entry.
2. Save personal answers outside both folders. Choose a destination folder that does not exist and a separate folder for run outputs. Use the operator's actual settings.
3. Prepare Python 3.12 and _core/requirements.txt outside both folders. Run setup to validate answers, copy the template, apply settings and create all 18 workflow pointers.
4. Run check against the new destination. The mode must be configured and all routes and helpers must resolve.
5. Follow adapters.md for actual tool verification and deployment. Review product evidence, schema, schedules and approval rules with the operator.

## Checkpoints

None for local setup because the requested copy is reversible. Actual agent creation, permissions and schedule activation need the operator's concrete deployment authorization.
Review derived product wording and note style with the operator before buyer use. Do not treat sample wording as approved company facts.

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
| Setup receipt | `_core/onboarding/status.json` in the configured workspace | Configured state and pending live verification |

## Terminal setup

This optional path creates your company workspace at `~/sales-workspaces/company`. Open a terminal in the template checkout first.
Python 3.12 must be available as `python3.12`. If it is missing, ask your coding agent to prepare the required Python runtime before continuing.
The Python environment holds the packages needed by the setup tool and helpers. It lives under your home folder, outside the repository.

```bash
python3.12 -m venv "$HOME/.local/share/sales-teammate/venv"
"$HOME/.local/share/sales-teammate/venv/bin/python" -m pip install -r _core/requirements.txt
```

Run setup and answer the company questions. The destination must not already exist. The setup tool creates the parent folder if needed.

```bash
"$HOME/.local/share/sales-teammate/venv/bin/python" -B _core/scripts/onboard.py setup --destination "$HOME/sales-workspaces/company"
"$HOME/.local/share/sales-teammate/venv/bin/python" -B _core/scripts/onboard.py check --workspace "$HOME/sales-workspaces/company"
```

Success reports `mode` as `configured`, `routes` as `18` and `errors` as `[]`. `external_ready` remains `false` because no live connections were checked.
Setup creates local configuration and pointer files. It does not create teammates in Perplexity Computer or activate schedules.

To reuse saved answers, pass the external JSON file path with `--answers`. Setup derives the configured state, so the answer file has no mode field.
The terminal questionnaire requires JSON for list and mapping answers. Guided setup is easier when those formats are unfamiliar.
Use `check --allow-template` only to inspect this unconfigured template. Follow adapters.md to verify and deploy a configured workspace.
