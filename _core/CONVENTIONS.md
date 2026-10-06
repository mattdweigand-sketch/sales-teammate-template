# Sales workspace conventions

Canonical architecture, folder ownership, authoring, and maintenance guidance for this repo. Sales operating rules stay in `_core/rules.md` and values stay in `_core/policy.yaml`.

## Navigation and loading

`AGENTS.md` gives workspace identity, essential boundaries, and entry routing. A named skill goes directly to its workflow contract.
Root `CONTEXT.md` maps tasks and events to owning workspaces. Workspace AGENTS.md defines role and boundaries, and workspace CONTEXT.md routes workflows, triggers, outputs, and human checks.
Read workspace entry files explicitly for task routing. Named skills retain direct root AGENTS.md routes to contracts, without relying on automatic discovery of nested instructions.
A workflow has a standalone contract or a routing parent with stage contracts. Execution contracts use Inputs, Process, Checkpoints, Audit and Outputs.
The Signal Prospecting parent is an overview. Named Signal skills go directly to their stages. The Event Sequence parent is an executable coordinator.
Coordinators load a stage only when entered and never preload the union of stage Inputs.
Read only the Inputs rows for the selected branch, including named reference sections, helper interfaces, policy blocks, rule anchors, and per-run evidence.
Use an explicit Full file scope only when the whole reference applies. Sales runs never load another workflow's folder.
Systems maintenance may inspect the affected files and consumers named by its scoped request. That access does not run or assume ownership of another domain's workflow.
Contracts route. Definitions, queries, formats, and examples live in references. No run needs to load these authoring conventions first.
Keep reference dependencies one-way. A workflow cites shared material without making that material load the workflow in return. Handoff routes name consumers without loading their contracts.

## Terms

| Term | Means |
|---|---|
| Workspace | An agent's ownership boundary under `workspaces/`, with AGENTS.md for its role and CONTEXT.md for workflow routing |
| Workflow | An owned task under `workflows/`, with a standalone contract or an overview or coordinator routing its actual stages |
| Stage | One sequential responsibility with a bounded execution contract and declared evidence handoff. Research aliases share one stage |
| Contract | The folder's `CONTEXT.md`, which names what to load and do. It is the workflow's skill body, at most 80 lines |
| Core | `_core/`, for repo-wide policy, rules, registries and resources shared across workspaces, plus the workflow template and every test |
| Reference | A file in a workspace or workflow's `references/`, read only through its contract's Inputs table and only the named sections. At most 200 lines |
| Helper | A deterministic script keyed in `policy.tooling.scripts` |

## Folder ownership

Workspace and workflow folders use descriptive names. Number nested stage folders where actual handoffs have an order. Direct workspace and workflow names keep no numeric prefixes.

| Path | Holds |
|---|---|
| `README.md` | Reader overview, workspace map, and navigation |
| `AGENTS.md` | Identity, essential boundaries, and entry routing |
| `CONTEXT.md` | Task and event routes, outputs, and handoffs |
| `workspaces/<workspace>/` | Prospecting, Pipeline, Deal Coaching, Forecasting, or Systems, each with AGENTS.md, CONTEXT.md, and owned workflows |
| `workspaces/<workspace>/references/` | Canonical references shared by that workspace's workflows, with bounded Inputs in each consuming contract |
| `workspaces/<workspace>/scripts/` | Deterministic helpers shared by that workspace's workflows, keyed in the repo-wide helper registry |
| `workspaces/<workspace>/workflows/<skill>/` | One contract with its own references and scripts where needed. Named aliases can select branches of one contract |
| `workspaces/<workspace>/workflows/<workflow>/<NN-stage>/` | An ordered stage contract, with private references and helpers only when needed |
| `workspaces/prospecting/workflows/signal-prospecting/` | Small Signal routing overview and three stages. Named skills bypass the overview |
| `workspaces/prospecting/workflows/event-sequence/` | Event coordinator, three stages and references or helpers shared by those stages |
| `_core/` | Shared policy, rules, collateral, helpers, conventions, onboarding, assets, specification and tests. `_core/CONTEXT.md` lists resources and their editors |
| `.github/` | Repository automation such as the tests workflow |

Share at the narrowest scope. Private stage dependencies stay with the stage. References and helpers used by several stages stay at their workflow parent.
Each shared reference has at least one same-workflow contract Inputs consumer with its resolved path and exact valid section headings. Mentions elsewhere do not count.
Dependencies shared by workflows in one workspace retain that workspace's references/ or scripts/ home.
Resources shared across workspaces live in `_core/`. Repo-wide policy, rules, helper registries, templates and tests retain their canonical homes there.
One home per fact. Values live in policy once, rules in `_core/rules.md` or the owning workflow once, and other files cite them. Skill descriptions live only in library frontmatter.
Coach criteria remain in that workflow's references unless another workflow actually needs the same criteria.
Domain agents own requirements, evidence, and proposals. Systems maintains the implementation across workspaces and shared core, then tests, ships when authorized, and verifies deployment.
Systems never sets sales policy, coach scores, forecasts, or CRM values. Shared material has one canonical home at its owning scope, under its existing wording authority.
Add stages for distinct sequential responsibilities and evidence handoffs. Preserve existing human reviews without adding pauses. A branch or calculation alone does not justify a stage.

## Handoffs and state

This is the runtime adaptation of ICM output-folder handoffs. Each contract names an actual artifact, its location, the existing human review point, and its consumer when one exists.
Salesforce records, chat threads, Gmail drafts, and sandbox artifacts are the handoff surfaces. No repo output folders, state files, or orchestration layer replace them.
An output stays in its declared location. A receiving workflow reads that source under its own Inputs and approval rules rather than loading the producer's folder.
Pipeline review hands verified Salesforce records to forecasting. A pilot report follows `rules#pilot_handoff`, including its existing acceptance checks.
Forecast tracking keeps pace reports and weekly snapshots in the run thread. At quarter end, Operator-approved bucket edits go to Systems repo-maintenance for a repo PR.
Coach assessment produces a report for Operator. Criteria refresh produces exact proposed wording for Operator's approval, then a repository PR handled by Systems repo-maintenance.
Domain handoffs carry a concrete requested outcome, evidence, exact proposed diff where applicable, and approval evidence. Systems findings route to repo-maintenance or agent-configuration for
repair.
The merged PR updates the canonical criteria references for later runs. Lessons and approval history stay in the Coach thread, not in repo files.
The `next` header and Outputs table must agree about conditional consumers. A report for Operator can be terminal even when another branch has a PR handoff.
Factory material is stable across runs in `_core/` and `workspaces/`. Product material is new each run and stays outside the repo.
Proposals live in threads, drafts in Gmail, records in Salesforce, and PDFs and saved query results in the sandbox. Read run status from those locations, never from files here.

## Review boundaries

Expose the existing human checkpoints before CRM writes, Gmail draft creation, PDF production, and criteria changes. Keep each workflow's current approval grammar and scope.
Each checkpoint names the completed unit Operator reviews and the decision needed before the following action. Retrieval and calculation do not acquire new approval pauses.
Read-only reports can run straight through. Audits name an unambiguous pass condition before the relevant output or action.
Sales writes continue to follow `rules#approval` and `rules#write_protocol`. The authoring structure does not grant approval or weaken any gate.
For repo changes, Operator approves wording changes in `_core/rules.md` and `_core/policy.yaml` first. Domain criteria changes retain their workflow's exact wording approval.
Each merge and deployment requires authorization for the exact change. No standing source permission transfers to this template. Explicit task-specific holds override any approval.
An implementation request alone does not authorize every later merge or deployment. Use the existing standing or task-specific approval, without requesting an approval already given.
Material schedule, permission, or agent behavior changes need the existing user approval. Approved path-only configuration changes need no repeat approval after their target files are deployed.
Collateral is attached only where the contract allows it and Operator approves. Pipeline review, task triage, and forecasting never load collateral or draft product wording.

## Cadence and library pointers

Cadence is metadata in each contract and in the automations. Schedule values stay in policy and scheduled behavior follows `rules#scheduled_runs`.
Pipeline review runs each weekday with its Friday rollup. Forecasting follows it on Friday and reads corrected records, per `policy.pipeline.schedule` and `policy.forecast.schedule`.
Coach branch schedules stay in `policy.coach.schedule`. Authoring a contract or changing documentation does not activate or change an automation.
The saved project skill is frontmatter plus a pointer to its workflow contract, and stops if that file is missing. The contract is the skill body.
Editing a skill means editing its workflow folder. Touch the library pointer only to change its name, description, connectors, or contract path.
Execution and coordinator frontmatter carries `cadence`, `reads`, `writes` and `next`, consistent with Inputs and Outputs. Routing overviews have no execution frontmatter.
Launch consumes Sequence Plan's exact same-thread E approval and stops on material change. Consuming approval adds no repeat pause. The workflow template is a starter, not a skill.

## Adding a workflow

1. Copy `_core/templates/workflow-context-template.md` to `workspaces/<workspace>/workflows/<skill>/CONTEXT.md` and fill its frontmatter and contract sections.
   A stage contract belongs under its ordered stage folder. Its handoff belongs in the workflow parent's Pipeline table. Workspace routes name the workflow parent.
   Keep definitions, queries, formats, and examples in references. Add reference or script folders only when needed.
   Keep Checkpoints for every workflow. When it runs straight through, state `None.` plus the reason, with no approval pause.
2. Add its direct route in root `AGENTS.md`, task route in the owner's CONTEXT.md, and owner in `SKILLS` in `_core/tests/test_skill_contracts.py`. Root CONTEXT.md routes workspaces.
   Create an approved library pointer at deployment with the same name and contract path. A move updates routes, helpers, root discovery, imports, and tests before switching pointers after merge.
3. Register any helper in `policy.tooling.scripts`, add its row to `_core/scripts/CONTEXT.md` "Helpers" and its interface to `_core/scripts/interfaces.md`, and add `_core/tests/test_<helper>.py`.
4. Run the tests and validate navigation from a fresh context before submitting.

## Tests and maintenance

Prepare and activate the environment per `_core/scripts/interfaces.md` "Running".
Run from the repo root with `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s _core/tests` in that active environment. All must pass before submit.
`_core/tests/test_skill_contracts.py` checks layout and resolves policy keys, rule anchors, paths, scripts, and registry entries.
`_core/tests/test_icm_contracts.py` checks contract sections, line limits, scoped references, routing, and handoffs. Update references and tests together without weakening checks.
Keep contracts at most 80 lines and references at most 200. Markdown prose lines are at most 200 characters and table rows at most 300, with code fences exempt.
Use plain language. New prose has no semicolons, em dashes, or colons inside sentences.
For a navigation change, start at `AGENTS.md` in a fresh context and record the entry, bounded Inputs, output location, review boundary, and downstream handoff.
Report what was verified structurally and what was not exercised through live connectors or schedules. Maintain canonical references rather than copying old run outputs as templates.

## Repo write boundaries

- Root holds `README.md`, `AGENTS.md`, `CONTEXT.md`, `.gitignore`, `.github/`, `_core/`, and `workspaces/` only. Other writes need Operator's explicit yes and a named path.
- Run scratch and saved tool output stay in the sandbox. Deliverables are shared from the sandbox, never moved here.
- No real customer material or run records enter Git. Clearly fictional fixtures and onboarding examples are allowed.

## Sequential workspaces

Prospecting has Signal Prospecting and Event Sequence as direct workflow folders, all limited to Operator-owned Salesforce Accounts.
Signal Prospecting routes Research, Outreach and Follow-up. Event Sequence coordinates List Prep, Sequence Plan and Launch.
Each parent's Pipeline table names triggers, outputs, reviews and stage routes. Root named skill routes remain direct and keep both Research aliases explicit.
Research owns the read-only account adoption query. No discovery stage, account claiming, territory-discovery query, or discovery schedule remains.
Workspace references and helpers live beside workflows when they serve only that workspace. Every consumer names bounded Inputs. Workflow-only resources stay in the owning workflow folder.

## Platform limits

These observations came from the source Perplexity runtime. Verify them in the adopter environment before using them to constrain deployment proposals.
Read actual settings and report unavailable evidence rather than assuming a command succeeded.

1. Automation edit scope. Edits, pauses, and deletes worked in direct Operator turns. Agent Mail turns and automation wakes failed with `RUN_AUTOMATION_SCOPE_VIOLATION`.
   Use the automation screen outside a direct Operator turn.
2. Automation delivery. `pplx automation edit` cannot change delivery. Recreate the automation instead, only after approval.
3. Dedicated threads. A dedicated automation thread needs a schedule. Connector events use new threads.
4. Worker messaging. Workers cannot message other sessions. Hand the receipt to the owning teammate for session delivery.
5. Teammate instructions. `pplx tm new --description` did not save. The Edit teammate Description field holds standing instructions. Role is the short title. Readback can lag seconds.
6. Credential injection. Credentials inject only for literal top-level `pplx` commands, not sourced scripts or loops.
7. Slack watch coverage. Slack watches miss app and bot messages. Watches on Operator's DMs never fire.
8. Session send. Verify the included Perplexity adapter's session delivery and teammate mail in the adopter environment.
   Try session send once, then teammate mail once only on confirmed no delivery. Reconcile ambiguous outcomes before retrying and record the successful transport.
