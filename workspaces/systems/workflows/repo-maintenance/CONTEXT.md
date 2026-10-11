---
cadence: one-off
reads: _core/CONVENTIONS.md, _core/rules.md, scoped request, approved wording, affected repo files and consumers, Git revision, tests, PR and deployment evidence
writes: repository branch and PR, authorized merge and deployment, after approval
next: agent-configuration for required pointer updates after deployment, otherwise Systems receipt with a necessary requesting-domain handoff only
---

# Repo Maintenance

Implement a scoped technical change while preserving domain ownership and existing approval boundaries. Run evidence stays outside the repo.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Authoring | `_core/CONVENTIONS.md` | "Navigation and loading", "Folder ownership", "Review boundaries", "Tests and maintenance", "Repo write boundaries" | Architecture, approval, and validation |
| Deployment | `_core/CONVENTIONS.md` | "Deployment communication" | Canonical receipt and necessary handoff, never broadcast guidance |
| Handoff rule | `_core/rules.md` | `rules#handoff_delivery` | Necessary domain handoff delivery result and visible failure |
| Request | Operator or requesting domain thread | Concrete outcome, scope, evidence, constraints, and exact approved policy, rule, or criteria wording | Authorized intent |
| Repository | Durable checkout and Git remote | Current revision, affected files, consumers, references, helper paths, and tests | Recovery and dependencies |
| Per-run evidence | PR, deployment settings, thread, and sandbox | Review feedback, tests, merge authorization, deployed revision, required pointers | Release gates and verification |

## Process

1. Establish a durable checkout, current revision, clean task-owned branch, and recovery point. Inspect the scoped request and applicable approval evidence.
2. Inventory affected files and consumers. Read only their relevant sections. Identify missing domain or policy decisions before dependent edits.
3. Resolve missing decisions per `_core/CONVENTIONS.md` "Review boundaries". Reuse exact wording approval already supplied by the domain or Operator.
4. Implement the authorized change. Update affected references, paths, and meaningful regression tests without changing unrelated sales behavior.
5. Validate per `_core/CONVENTIONS.md` "Tests and maintenance". Prepare a reviewable PR with scope, exact diff, approval evidence, results, and pending deployment actions.
6. Check the existing merge and deployment authorization per `_core/CONVENTIONS.md` "Review boundaries". Honor explicit holds and require a passing full local test run on the PR head.
7. Perform only the authorized merge and deployment. Verify the remote revision and deployed files. Hand required pointer updates to agent-configuration after the files exist.
8. Record the PR, tests, approval basis, deployed revision, verified pointers and pending actions per `_core/CONVENTIONS.md` "Deployment communication".

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | Missing domain decisions or exact policy, rule, or criteria wording approval | Operator supplies only the decision or approval not already authorized |
| 5 | Reviewable PR, tests, and applicable merge or deployment approval evidence | Existing standing or task-specific authorization governs, ask only if it is missing |

## Audit

| Check | Pass Condition |
|---|---|
| Scope, before step 4 | Every behavior or wording change has the required domain authority, and shared facts keep one home |
| Validation, before step 6 | Required tests and reference checks pass, or failures are reported and release remains pending |
| Release, before step 7 | The full local test run passes on the PR head and the exact merge or deployment is authorized, with no explicit hold |
| Verification, before receipt | Deployed revision and required pointer readbacks are verified or explicitly pending or not checked |
| Boundaries, throughout | No customer-system writes, no invented sales decisions, and no run evidence or customer material in Git |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Reviewable diff and PR | Task-owned repository branch and GitHub PR, after approval of the scoped change | Scope, tests, exact approved wording, and release state |
| Authorized deployment | Repository or deployment target, after approval | Verified revision and any required agent-configuration handoff |
| Evidence and receipt | Systems thread, supporting files in sandbox | Tests, approval links, revision, pointers and pending actions, with necessary handoff per "Deployment communication" |
