---
cadence: <daily | weekly | monthly | one-off, or a list such as [monthly, one-off]>
reads: _core/policy.yaml (<blocks>), _core/rules.md, references/, <systems>
writes: <records and systems, on approval, or nothing>
next: <consumer and handoff condition, or none>
---

# <Workflow name>

Template, not a skill. Never run it for a request. To add a workflow, follow "Adding a workflow" in `_core/CONVENTIONS.md`.
Replace this paragraph with one or two sentences naming the question the workflow answers.
Use this execution shape for a standalone workflow or numbered stage. A small routing overview has no execution frontmatter and adds no saved skill.
An Event coordinator keeps this shape plus Pipeline, loading a stage only when entered. Consuming an existing exact approval adds no repeat pause.
Keep the finished file at most 80 lines. Definitions, queries, formats, and examples go in `references/`, at most 200 lines each.

## Inputs

<!-- Place under the owning workflow, directly for standalone execution or in a numbered stage. Root named-skill routes reach execution; broad routes may use an overview. -->
<!-- Shared parent references require resolved paths and exact quoted headings in Inputs. Private references may keep Full file. Never load sibling contracts as evidence. -->
<!-- Name exact files, policy blocks, rule anchors, and quoted reference sections. Say which branch loads each row. Persistent references first, per-run evidence last. -->

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `<block>` blocks | <values this workflow reads> |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#approval`, `rules#write_protocol` | Run start, approval, and writes |
| Reference | `references/<file>.md` | "<Heading>" at step <n> | <what it defines> |
| Per-run evidence | <saved results in the sandbox> | <this run's scope> | <what the evidence establishes> |

## Process

<!-- Short numbered steps. Each routes to the reference that holds the detail. -->
<!-- In a stage, consume only the selected Inputs and handoff evidence, not sibling contracts or the parent's union of resources. -->
<!-- Validate an inherited exact approval against its native message and proposal scope before any write. A label or file never supplies authority. -->

1. Start per `rules#run_start`.
2. <Collect per `references/<file>.md` "<Heading>".>
3. <Propose per `references/<file>.md` "<Heading>".>
4. Wait per `rules#approval`. <This workflow's approval grammar.>
5. Apply only approved changes per `rules#write_protocol`. For a read-only workflow, delete this step and cite `rules#read_only_skills`.
6. Close. <Counts that must reconcile.> Name each skipped or needs-input item per `rules#approval`.

## Checkpoints

<!-- Keep this section. Use existing approval points, or state None. plus the reason when the workflow runs straight through with no approval pause. -->
<!-- If this stage consumes an existing exact approval, state None. and name that approval and its evidence. Missing or changed authority stops under the current proposal rules. -->

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
<!-- Stage outputs name the actual receiving stage and evidence. A handoff is not automatic progression or permission for a customer-system write. -->
<!-- Carry the exact approved snapshot and native approval evidence when the next stage consumes that approval. Keep original run identity and actual receipt status. -->

| Artifact | Location | Format |
|---|---|---|
| <Report or brief> | Run thread | <reference layout and intended reader> |
| <Approved writes> | <system>, after approval only | Read back per `rules#write_protocol`, then <conditional consumer or no downstream workflow> |
| Saved results | Sandbox | Query and helper outputs, never Project Files |
