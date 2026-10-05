# Onboarding

Instantiate a separate reusable Sales workspace from this template. Setup remains local and preserves template files.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Persistent choices | `questionnaire.md`, `questions.json`, `answers.example.json` | Remaining setup questions only | One-pass configuration |
| Adapter schema | `adapter-schema.json` and `adapters.md` | Needed fields, tables, prerequisites and verification | Compatible integrations |
| Tools | `_core/scripts/onboard.py` | setup, questions, check | Validate and copy without overwrites |

## Process

1. Use supplied persistent choices. Ask remaining questions from questionnaire.md together. Keep per-run inputs at workflow entry.
2. Save the answer file outside Git. Choose an absent external destination and an external artifact directory. Use demo mode for fictional data.
3. Run setup with the prepared Python. It validates before copying, applies canonical values and mappings, and creates all 18 skill pointers.
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

## Commands

Use Python 3.12 with the packages from _core/requirements.txt. From the template checkout

```bash
python -B _core/scripts/onboard.py setup --answers /absolute/answers.json --destination /absolute/new-sales-workspace
python -B _core/scripts/onboard.py check --workspace /absolute/new-sales-workspace
```

For interactive one-pass setup, omit --answers. To inspect the unconfigured template, use check --allow-template.
