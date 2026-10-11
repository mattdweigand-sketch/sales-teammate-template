---
cadence: one-off
reads: >-
  _core/CONVENTIONS.md, _core/rules.md, references/, workspaces/systems/captures/, Operator's selected task and examples,
  scoped owning workflow sections, the thread where Operator invokes capture and sandbox
writes: nothing
next: Systems repo-maintenance for the confirmed capture file and its reviewed updates, and for wording only with Operator's exact approval and the owning domain's requirements
---

# Process Capture

Help Operator explain the judgment behind one recurring task, then try a short guide on another case. Systems facilitates capture while Operator and the owning domain retain decisions.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Ownership | `_core/CONVENTIONS.md` | "Folder ownership", "Handoffs and state", "Review boundaries", "Repo write boundaries" | Canonical homes and existing authority |
| Handoff rule | `_core/rules.md` | `rules#handoff_delivery` | Approved Systems request delivery result and visible failure |
| Reference | `references/capture.md` | "Select a task", "Walk through decisions", "Working guide", "Try another case", "Review and handoff", "Capture file" | Conversation, evidence, review, and the repo record |
| Capture files | `workspaces/systems/captures/` | Only the selected task's file, if one exists | Prior status, decisions, and open questions |
| Operator's request | the thread where Operator invokes capture | One task, intended outcome and audience, selected example, constraints, and prior answers | Actual scope and judgment |
| Current guidance | Selected owning workflow files | Only named contract or reference sections affected by this task | Compare current behavior and identify conflicts |
| Examples | Operator-selected thread messages or sandbox artifacts | Original inputs, accepted or rejected result, edits, and source locations for selected cases | Observe choices in context |

Do not load unrelated customer material or other workflows. Reading scoped target guidance does not execute its workflow or authorize its writes.

## Process

1. Select one task, owner, intended use, and recent example per `references/capture.md` "Select a task". Reuse supplied answers and report missing inputs.
2. Walk through the actual example with Operator per `references/capture.md` "Walk through decisions". Keep stated judgment, observed choices, and hypotheses distinct.
3. Draft a short proposed guide per `references/capture.md` "Working guide". Identify conflicts with current guidance without changing it.
   Send the record to repo-maintenance when Operator confirms it and after each reviewed change per `references/capture.md` "Capture file".
4. Try another case per `references/capture.md` "Try another case". Ask Operator to review the result, refine from his reasons, and state what remains untested.
5. Present the exact proposed reusable wording and its owning file and section per `references/capture.md` "Review and handoff". Reuse matching approval already supplied.
6. Return the guide and remaining questions. Only an approved wording diff goes to Systems repo-maintenance with domain requirements, native approval evidence, and the capture file set to applied.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 3 | Generalized record of reasons, decisions, exceptions, and open questions | Operator confirms that it states his reasoning faithfully or corrects it |
| 4 | Second-case result, applied decisions, corrections, and limits | Operator accepts or explains what to change and why |
| 5 | Exact reusable wording, conflicts, intended home, and supporting evidence | Operator approves that wording for the existing repo-maintenance handoff or keeps it proposed |

## Audit

| Check | Pass Condition |
|---|---|
| Evidence, before step 3 | Each judgment has Operator's words or an explicit unconfirmed hypothesis with its source location |
| Usefulness, before step 5 | The guide states deciding signals, tradeoffs, exceptions, and acceptance checks, with second-case feedback or an explicit untested limit |
| Authority, before step 6 | Handoff includes the exact approved diff and native approval link, resolves contested wording, and preserves domain ownership |
| Boundaries, throughout | No direct repo or customer-system writes and no new schedules or agents. Git receives only the generalized capture file through repo-maintenance, never customer examples |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Proposed process guide | the thread where Operator invokes capture | Short guide with evidence, hypotheses, conflicts, examples, and open questions per "Working guide" |
| Walkthrough and trial evidence | the thread where Operator invokes capture, supporting artifacts in sandbox | Selected source locations, corrections and reasons, and actual review status |
| Capture file | `workspaces/systems/captures/<workflow>-<task>.md` through Systems repo-maintenance | Generalized record and reviewed updates per `references/capture.md` "Capture file" |
| Approved wording handoff | Systems thread per `_core/CONVENTIONS.md` "Handoffs and state" | Repo-maintenance request with exact sanitized diff, owning file and section, domain requirements, and Operator's native approval link, only when approved |
