---
cadence: <daily | weekly | monthly | one-off, or a list such as [monthly, one-off]>
reads: _core/policy.yaml (<blocks>), _core/rules.md, references/, <systems>
writes: <records and systems, on approval, or nothing>
next: <consumer and handoff condition, or none>
---

# <Workflow name>

Template, not a skill. Never run it for a request. To add a workflow, follow "Adding a workflow" in `_core/CONVENTIONS.md`.
Replace this paragraph with one or two sentences naming the question the workflow answers.
Keep the finished file at most 80 lines. Definitions, queries, formats, and examples go in `references/`, at most 200 lines each.

## Inputs

<!-- Place a standalone contract under workflows/<skill>/ or a numbered stage under its workflow parent. Root named routes or the coordinator must reach it. -->
<!-- Name exact files, policy blocks, rule anchors, and quoted reference sections. Say which branch loads each row. Persistent references first, per-run evidence last. -->

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `<block>` blocks | <values this workflow reads> |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#approval`, `rules#write_protocol` | Run start, approval, and writes |
| Reference | `references/<file>.md` | "<Heading>" at step <n> | <what it defines> |
| Per-run evidence | <saved results in the sandbox> | <this run's scope> | <what the evidence establishes> |

## Process

<!-- Short numbered steps. Each routes to the reference that holds the detail. -->

1. Start per `rules#run_start`.
2. <Collect per `references/<file>.md` "<Heading>".>
3. <Propose per `references/<file>.md` "<Heading>".>
4. Wait per `rules#approval`. <This workflow's approval grammar.>
5. Apply only approved changes per `rules#write_protocol`. For a read-only workflow, delete this step and cite `rules#read_only_skills`.
6. Close. <Counts that must reconcile.> Name each skipped or needs-input item per `rules#approval`.

## Checkpoints

<!-- Keep existing approval points. A stage consuming exact prior approval uses None. plus its producer, same-thread approval evidence and stop-on-change reason. -->
<!-- Coordinator pipeline tables summarize delegated reviews. Routing overviews have no execution frontmatter or contract tables. -->

| After Step | Agent Presents | Human Decides |
|---|---|---|
| <n> | <what is shown> | <what Operator chooses> |

## Audit

<!-- Checks that run before the named output or action, each with an unambiguous pass condition. Name the helper when one owns the check. -->

| Check | Pass Condition |
|---|---|
| <Check>, before step <n> | <what passing looks like> |
| Scope, throughout | <actions this workflow never takes> |

## Outputs

<!-- Name each actual artifact, its location, and its consumer when one exists. Keep handoffs consistent with next and the existing Checkpoints. -->

| Artifact | Location | Format |
|---|---|---|
| <Report or brief> | Run thread | <reference layout and intended reader> |
| <Approved writes> | <system>, after approval only | Read back per `rules#write_protocol`, then <conditional consumer or no downstream workflow> |
| Saved results | Sandbox | Query and helper outputs, never Project Files |
