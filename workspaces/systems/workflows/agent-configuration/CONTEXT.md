---
cadence: one-off
reads: _core/CONVENTIONS.md, approved ownership, deployed contract paths, project-skill pointers, agent instructions, automation settings
writes: authorized project-skill pointers and agent or automation configuration, after approval
next: verified receipt to the requesting domain or repo-maintenance for missing deployed targets
---

# Agent Configuration

Align actual settings with approved ownership and deployed workflow contracts. Documentation alone creates no agent and activates no schedule.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Approval | `_core/CONVENTIONS.md` | "Review boundaries", "Cadence and library pointers" | Existing authority and deployment order |
| Request | Operator or requesting domain thread | Approved ownership, exact intended change, permission boundaries, and approval evidence | Scope and intent |
| Deployed repository | Verified revision and requested contract paths | Target existence, workspace role, workflow Inputs, outputs, and current boundaries | Correct destination |
| Per-run evidence | Live project-skill pointers, agent instructions, and automation settings | Only settings affected by this request, including existing matching schedules | Actual before state and duplicates |

## Process

1. Inventory the actual affected settings and current deployed revision. Save evidence in the sandbox. Missing access or unread settings remain not checked.
2. Compare approved ownership and intended targets with deployed files and actual settings. Identify missing targets, permission changes, and duplicate schedules.
3. Propose exact before and after pointer or configuration values, expected routing, and verification criteria. Name any material schedule, permission, or behavior change.
4. Apply only authorized changes after the referenced files are deployed, per `_core/CONVENTIONS.md` "Review boundaries". Approved path-only changes need no repeat approval.
5. Read back actual settings. Trace each route through the intended workspace and contract. Verify permissions, schedule uniqueness, and the requested behavior.
6. Return a deployment receipt with before and after targets, verified revision and settings, and blocked or not-checked items. Route missing repo targets to repo-maintenance.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 3 | Exact changes and any missing approval for material schedules, permissions, or behavior | Existing user approval governs, ask only for missing authorization |

## Audit

| Check | Pass Condition |
|---|---|
| Targets, before step 4 | Every referenced file exists at the verified deployed revision |
| Authority, before step 4 | The exact change is authorized and preserves the approved permission boundaries |
| Schedule, before and after step 4 | Existing matching automations are inventoried and the change creates no duplicate schedule |
| Readback, before receipt | Actual settings resolve to the correct workspace and workflow, or the gap is explicitly blocked or not checked |
| Scope, throughout | This design grants no authority to create Teammates, widen permissions, or activate automations. No customer-system writes |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Verified configuration | Project skills or agent and automation settings, after approval | Authorized values read back against deployed targets |
| Deployment receipt | Systems or requesting thread, evidence in sandbox | Exact before and after targets, revision, route check, and remaining actions |
| Pending changes | Systems thread or sandbox | Exact proposed settings, blocked or not-checked evidence, and required owner action |
