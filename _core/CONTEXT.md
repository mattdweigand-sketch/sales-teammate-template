# _core, the factory

Stable across sales runs. Holds repo-wide policy, rules, registries, cross-workspace resources, the workflow template and every test. Workspace-only resources stay with their owner.
Operator and the domain agents own sales requirements and proposals. Operator retains the wording authority shown below. Systems implements authorized changes through repo-maintenance, with tests
and a PR.
Systems owns technical maintenance, deployment verification, and configuration. It does not set sales policy, coach scores, forecasts, or CRM values.

| Item | Holds | Edited by |
|---|---|---|
| `CONVENTIONS.md` | Architecture, ownership, authoring, maintenance, and tests. Read when changing the repo, not as a routine run prerequisite. | Operator, with tests |
| `policy.yaml` | Values: thresholds, dates, IDs, field lists, templates, script keys. Workflows read the blocks their contract names at run start and cite `policy.<key>`. | Operator, by hand |
| `rules.md` | Shared operating rules two or more workflows follow, plus the permission exceptions `auto_date_move` and `event_sequence`, one anchor each. Contracts cite `rules#<anchor>`. Any other rule one workflow follows lives in that workflow's folder. | Operator, by hand |
| `slack-evidence.md` | Shared read-only Slack collection and reviewed reply receipts for pipeline-review, forecast-weekly, and task triage. | Pipeline and Forecasting requirements, Systems implementation |
| `collateral/` | Example Product-authored sales materials a workflow may attach after approval. Files are named `<topic>-<type>-<YYYY-MM>.<ext>`; the date is the last content check. Never customer material. | Operator, by hand |
| `scripts/` | Cross-workspace helpers and the repo-wide helper catalog. Workspace and workflow helpers stay with their owner. Paths are keyed in `policy.tooling.scripts`, with interfaces in `scripts/interfaces.md`. | Operator, with tests |
| `templates/` | `templates/workflow-context-template.md`, the starter for a new workflow contract, with the Inputs, Process, Checkpoints, Audit, and Outputs sections. Not a skill. | Operator, by hand |
| `tests/` | Every test, for core and workflow helpers and for the repo's layout and references. | Operator, with tests |

Workspace resource maps and editors live in `workspaces/prospecting/CONTEXT.md` and `workspaces/pipeline/CONTEXT.md`.

Onboarding resources live in `_core/onboarding/CONTEXT.md`. The build specification is `_core/template-spec.md`. Assets and notices are maintained by Systems.
