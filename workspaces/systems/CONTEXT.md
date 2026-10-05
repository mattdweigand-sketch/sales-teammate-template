# Systems routes

Enter through `workspaces/systems/AGENTS.md` for role and boundaries. Select one contract, then load only its bounded Inputs and affected evidence.

## Task routing

| Task or event | Contract | Output and handoff | Human check |
|---|---|---|---|
| Scoped repo request or approved domain criteria diff | `workflows/repo-maintenance/CONTEXT.md` | Reviewable PR, tests, authorized deployed revision, pending actions | Missing domain decisions and applicable merge authorization |
| Approved pointer or configuration change | `workflows/agent-configuration/CONTEXT.md` | Verified settings and before/after receipt, or not-checked items | Existing approval for material changes, no repeat path-only approval |
| Friday Review or typed health or eval request | `workflows/system-review/CONTEXT.md` | Systems scorecard, ranked improvement tasks, and top-five backlog | Task recording needs no pause. Repairs and policy decisions follow their own approvals |

## Handoffs

Pipeline, Forecasting, and Deal Coaching retain domain decisions. Systems takes their concrete requested outcome, evidence, and required exact wording approvals into the selected contract.
Repo-maintenance verifies deployed revisions before any required agent-configuration handoff. Configuration reads back actual settings and checks the deployed route.
System-review findings never authorize repairs. State the owner, proposed fix, and verification criteria, then route the finding without applying it.
All reports and execution evidence stay in the Systems thread or sandbox. `_core/` holds repo-wide resources. Workspace-only shared resources stay with their owner.
