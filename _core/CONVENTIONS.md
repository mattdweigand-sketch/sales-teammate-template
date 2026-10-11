# Sales workspace conventions

Canonical architecture, folder ownership, authoring, and maintenance guidance for this repo. Sales operating rules stay in `_core/rules.md` and values stay in `_core/policy.yaml`.

## Navigation and loading

`AGENTS.md` gives workspace identity, boundaries and routing. A named skill goes directly to its stage, coordinator or standalone contract, bypassing routing overviews and sibling stages.
Root `CONTEXT.md` maps tasks and events to owning workspaces. Workspace AGENTS.md defines role and boundaries, and workspace CONTEXT.md routes workflows, triggers, outputs, and human checks.
Read workspace entry files explicitly for task routing. Named skills retain direct root AGENTS.md routes to contracts, without relying on automatic discovery of nested instructions.
An execution contract controls the run through its Inputs, Process, Checkpoints, Audit and Outputs. Signal Prospecting's parent CONTEXT.md only routes broad requests to stages.
Event Sequence's saved skill enters its coordinator. It loads a stage only when entered, never the union of descendant Inputs. Stages run in the same agent session.
Read only the Inputs rows for the selected branch, including named reference sections, helper interfaces, policy blocks, rule anchors, and per-run evidence.
Use an explicit Full file scope only when the whole reference applies. Sales runs never load another workflow's folder.
Systems maintenance may inspect the affected files and consumers named by its scoped request. That access does not run or assume ownership of another domain's workflow.
Contracts route. Definitions, queries, formats, and examples live in references. No run needs to load these authoring conventions first.
Keep reference dependencies one-way. A workflow cites shared material without making that material load the workflow in return. Handoff routes name consumers without loading their contracts.

## Terms

| Term | Means |
|---|---|
| Workspace | An agent's ownership boundary under `workspaces/`, with AGENTS.md for its role and CONTEXT.md for workflow routing |
| Workflow | An owning task under a workspace's workflows/. It has a standalone contract, a routing overview or an executable coordinator with numbered stages. Research aliases select one stage's branches |
| Stage | A numbered execution contract directly under its owning workflow, representing an actual evidence handoff. No extra stages layer |
| Overview | A small broad-task workflow router without execution frontmatter. It is not a saved skill, runtime step or required pre-read |
| Coordinator | An execution contract with a Pipeline table that enters stages conditionally. Event Sequence is the saved-skill coordinator |
| Contract | The folder's `CONTEXT.md`, which names what to load and do. It is the workflow's skill body, at most 80 lines |
| Core | `_core/`, for repo-wide policy, rules, registries and resources shared across workspaces, plus the workflow template and every test |
| Reference | A file in a workspace or workflow's `references/`, read only through its contract's Inputs table and only the named sections. At most 200 lines |
| Helper | A deterministic script keyed in `policy.tooling.scripts` |

## Folder ownership

Workspace and direct workflow folders use descriptive names. Numbered stages live directly under their owning workflow. Legacy numeric workspace or direct workflow prefixes remain prohibited.

| Path | Holds |
|---|---|
| `README.md` | Reader overview, workspace map, and navigation |
| `AGENTS.md` | Identity, essential boundaries, and entry routing |
| `CONTEXT.md` | Task and event routes, outputs, and handoffs |
| `workspaces/<workspace>/` | Prospecting, Pipeline, Deal Coaching, Forecasting, or Systems, each with AGENTS.md, CONTEXT.md, and owned workflows |
| `workspaces/<workspace>/references/` | Canonical references shared by that workspace's workflows, with bounded Inputs in each consuming contract |
| `workspaces/<workspace>/scripts/` | Deterministic helpers shared by that workspace's workflows, keyed in the repo-wide helper registry |
| `workspaces/<workspace>/workflows/<workflow>/` | Standalone contract, grouped-stage overview or executable coordinator, with resources at their narrowest shared scope |
| `workspaces/<workspace>/workflows/<workflow>/<numbered-stage>/` | Stage contract and private resources. Shared workflow resources stay at the workflow level |
| `workspaces/prospecting/workflows/event-sequence/` | Event coordinator, three stage contracts, shared prep/sequence/readback references and the shared list helper |
| `_core/` | Shared policy, rules, collateral, helpers, conventions, the workflow template, and tests. `_core/CONTEXT.md` lists resources and their editors |
| `workspaces/systems/captures/` | Method in `workspaces/systems/workflows/process-capture/references/capture.md` "Capture file". Never customer names, email bodies, quotes or transcripts. Committed by Systems repo-maintenance |
| `.github/` | Template CI runs Python 3.12 tests and the scratch rehearsal. Preserve pinned actions, licensed dependencies and required checks |

Only process-capture and system-review read capture records as input. This routing does not block access or make records authoritative.
Share at the narrowest scope. Stage-private resources live in the stage. Resources shared by stages stay at the workflow level. Workspace-wide resources stay beside workflows.
A shared workflow reference lives in workflow-level references/ beside stage contracts. It needs same-workflow stage or coordinator Inputs with resolved paths and exact valid quoted headings.
Prose, Process, Audit, Outputs, comments and bare Inputs paths do not establish shared-reference coverage. Standalone-owned and stage-private references retain their existing scopes.
Resources shared across workspaces live in `_core/`. Repo-wide policy, rules, helper registries, templates and tests retain their canonical homes there.
One home per fact. Values live in policy once, rules in `_core/rules.md` or the owning workflow once, and other files cite them. Skill descriptions live only in library frontmatter.
Coach criteria remain in that workflow's references unless another workflow actually needs the same criteria.
Domain agents own requirements, evidence, and proposals. Systems maintains the implementation across workspaces and shared core, then tests, ships when authorized, and verifies deployment.
Systems never sets sales policy, coach scores, forecasts, or CRM values. Shared material has one canonical home at its owning scope, under its existing wording authority.
Numbered stages represent actual evidence handoffs, not a branch or calculation alone. Pipeline review summaries must match the existing contracts without adding approval pauses.

## Handoffs and state

This is the Perplexity adaptation of ICM output-folder handoffs. Each contract names an actual artifact, its location, the existing human review point, and its consumer when one exists.
Salesforce records, chat threads, Gmail drafts, and sandbox artifacts are the handoff surfaces. No repo output folders, state files, or orchestration layer replace them.
The capture files in `workspaces/systems/captures/` are the one exception.
An output stays in its declared location. A receiving workflow reads that source under its own Inputs and approval rules rather than loading the producer's folder.
Pipeline review hands verified Salesforce records to forecasting. A pilot report follows `rules#pilot_handoff`, including its existing acceptance checks.
Forecast tracking keeps pace reports and weekly snapshots in the run thread. At quarter end, Operator-approved bucket edits go to Systems repo-maintenance for a repo PR.
Coach assessment produces a report for Operator. Criteria refresh produces exact proposed wording for Operator's approval, then a repository PR handled by Systems repo-maintenance.
Domain handoffs carry a concrete requested outcome, evidence, exact proposed diff where applicable, and approval evidence. Systems findings route to repo-maintenance or agent-configuration for
repair.
Resolve the configured Systems destination through `_core/thread-locators.md`. Send once with `pplx tm mail send <session id> "<message>"` and keep its actual native result.
The merged PR updates the canonical criteria references for later runs. Lessons and approval history stay in the Coach thread, not in repo files.
The `next` header and Outputs table must agree about conditional consumers. A report for Operator can be terminal even when another branch has a PR handoff.
Stage handoffs carry reviewed evidence, not sibling-contract loading. Pipeline tables name triggers, outputs, human checks and relative contract routes.
Event stage handoffs retain one immutable run_start and actual native receipts in the current thread and sandbox, without persistent state files or automatic replanning loops.
Factory material is stable across runs in `_core/` and `workspaces/`. Product material is new each run and stays outside the repo.
Proposals live in threads, drafts in Gmail, records in Salesforce, and PDFs and saved query results in the sandbox. Read run status from those locations, never from files here.

## Review boundaries

Expose the existing human checkpoints before CRM writes, Gmail draft creation, PDF production, and criteria changes. Keep each workflow's current approval grammar and scope.
Each checkpoint names the completed unit Operator reviews and the decision needed before the following action. Retrieval and calculation do not acquire new approval pauses.
Read-only reports can run straight through. Audits name an unambiguous pass condition before the relevant output or action.
Sales writes continue to follow `rules#approval` and `rules#write_protocol`. The authoring structure does not grant approval or weaken any gate.
For repo changes, Operator approves wording changes in `_core/rules.md` and `_core/policy.yaml` first. Domain criteria changes retain their workflow's exact wording approval.
The adopter's verified standing or task-specific approval defines merge authority. Require the full local test run and applicable CI on the PR head. The template grants no standing merge approval.
Explicit task-specific holds override that standing rule.
An implementation request alone does not authorize every later merge or deployment. Use the existing standing or task-specific approval, without requesting an approval already given.
Material schedule, permission, or agent behavior changes need the existing user approval. Approved path-only configuration changes need no repeat approval after their target files are deployed.
Collateral is attached only where the contract allows it and Operator approves. Pipeline review, task triage, and forecasting never load collateral or draft product wording.

## Cadence and library pointers

Cadence is metadata in each contract and in the automations. Schedule values stay in policy and scheduled behavior follows `rules#scheduled_runs`.
Pipeline review uses its weekly schedule with the same rollup on requested runs. Forecasting follows it on Friday and reads corrected records, per `policy.pipeline.schedule` and
`policy.forecast.schedule`.
Coach branch schedules stay in `policy.coach.schedule`. Authoring a contract or changing documentation does not activate or change an automation.
The saved project skill is frontmatter plus a pointer to its execution contract, and stops if that file is missing. Signal skills point directly to stages, not their overview.
Event Sequence's pointer stays at the coordinator. Internal stages add no saved skills or schedules. Launch consumes only the exact E proposal's native approval in this same run thread.
Editing a skill means editing its workflow folder. Touch the library pointer only to change its name, description, connectors, or contract path.
Contract frontmatter carries `cadence`, `reads`, `writes`, and `next`, consistent with Inputs and Outputs. The workflow template is a starter, not a skill.

## Deployment communication

Publish shared changes in the canonical repo and one deployment receipt in Systems. Notify the requesting domain once only for a necessary handoff.
Never enumerate or wake every deal thread to broadcast common repo guidance. Do not retry obsolete undelivered guidance notices. Real Account evidence routing stays unchanged.
Writers acquire current instructions through `rules#repo_currency`, not message receipt. Required Project pointers stay thin and name the canonical rule rather than copying its wording.

## Adding a workflow

1. Copy `_core/templates/workflow-context-template.md` to `workspaces/<workspace>/workflows/<skill>/CONTEXT.md` and fill its frontmatter and contract sections.
   A sequential handoff belongs in the owning workflow's pipeline table. Standalone workflows retain execution contracts, Signal keeps an overview, and Event keeps an executable coordinator.
   Keep definitions, queries, formats, and examples in references. Add reference or script folders only when needed.
   Keep Checkpoints for every workflow. When it runs straight through, state `None.` plus the reason, with no approval pause.
   When a stage consumes an existing exact approval, use `None.` with that reason. Missing, cross-thread or changed authority stops under the existing proposal rules, never a new blanket permission.
2. Add a saved skill's direct route in root `AGENTS.md`, workspace workflow route and test ownership. A skill may target a numbered stage. Overviews do not add saved skills.
   Create an approved library pointer at deployment with the same name and contract path. A move updates routes, helpers, root discovery, imports, and tests before switching pointers after merge.
3. Register any helper in `policy.tooling.scripts`, add its row to `_core/scripts/CONTEXT.md` "Helpers" and its interface to `_core/scripts/interfaces.md`, and add `_core/tests/test_<helper>.py`.
4. Run the tests and validate navigation from a fresh context before submitting.

## Tests and maintenance

Prepare and activate the environment per `_core/scripts/interfaces.md` "Running".
Run from the repo root with `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s _core/tests` in that active environment. All must pass before submit.
Run the full local suite and scratch rehearsal on the final PR head. Wait for required GitHub CI before the authorized merge. Record the tested revision and verify the published remote SHA.
`_core/tests/test_skill_contracts.py` checks layout and resolves policy keys, rule anchors, paths, scripts, and registry entries.
`_core/tests/test_icm_contracts.py` checks contract sections, line limits, scoped references, routing, and handoffs. Update references and tests together without weakening checks.
Keep every CONTEXT.md at most 80 lines and references at most 200. Execution stages retain strict contract shape; routing overviews have explicit roles. Prose caps are 200 and table rows 300.
Use plain language. New prose has no semicolons, em dashes, or colons inside sentences.
For a navigation change, start at `AGENTS.md` in a fresh context and record the entry, bounded Inputs, output location, review boundary, and downstream handoff.
Report what was verified structurally and what was not exercised through live connectors or schedules. Maintain canonical references rather than copying old run outputs as templates.

## Repo write boundaries

- Root holds `README.md`, `AGENTS.md`, `CONTEXT.md`, `.gitignore`, `.github/`, `_core/`, and `workspaces/` only. Other writes need Operator's explicit yes and a named path.
- Run scratch and saved tool output stay in the sandbox. Deliverables are shared from the sandbox, never moved here.
- No customer names, email bodies, transcripts, private approval receipts or run state in Git. Generalized process records may enter only `workspaces/systems/captures/` through approved maintenance.

## Sequential workspaces

Prospecting has two direct workflows, Signal Prospecting and coordinated Event Sequence.
Signal Prospecting is limited to Operator-owned Salesforce Accounts.
Event Sequence also admits the configured outreach-owner scope for Operator's named lists.
Signal Prospecting groups 01-research, 02-outreach and 03-followup directly under its overview. Root skill routes name each stage and both Research aliases explicitly.
The workflow pipeline declares handoffs. Broad Signal tasks use the overview, named Signal skills bypass it. Event Sequence enters its coordinator and selected stage with every existing gate.
Research owns the read-only account adoption query. No discovery stage, account claiming, territory-discovery query, or discovery schedule remains.
Workspace references and helpers live beside workflows when they serve only that workspace. Every consumer names bounded Inputs. Workflow-only resources stay in the owning workflow folder.

## Platform limits

These source adapter observations require current adopter verification before deployment. Read actual settings and report unavailable evidence rather than assuming a command succeeded.

1. Automation edit scope. Edits, pauses, and deletes worked in direct Operator turns. Agent Mail turns and automation wakes failed with `RUN_AUTOMATION_SCOPE_VIOLATION`.
   Use the automation screen outside a direct Operator turn.
2. Automation delivery. `pplx automation edit` cannot change delivery. Recreate the automation instead, only after approval.
3. Dedicated threads. A dedicated automation thread needs a schedule. Connector events use new threads.
4. Worker messaging. Workers cannot message other sessions. Hand the receipt to the owning teammate for session delivery.
5. Teammate instructions. `pplx tm new --description` did not save. The Edit teammate Description field holds standing instructions. Role is the short title. Readback can lag seconds.
6. Credential injection. Credentials inject only for literal top-level `pplx` commands, not sourced scripts or loops.
7. Slack watch coverage. Slack watches miss app and bot messages. Watches on Operator's DMs never fire.
8. Session tools. The supported included adapter uses native session tools for reads. Send once with `pplx tm mail send <session id> "<message>"` and record delivery or failure.
   Use `session_list` for Account searches and `session_download_content` for thread reads. Unavailable or failed reads are not checked, never inferred. Project session listing is unchanged.
9. Retire a replaced Teammate by rewriting its Description to read-only before archiving. Pause, never delete, an automation while any affected run thread holds known unapproved proposals.
