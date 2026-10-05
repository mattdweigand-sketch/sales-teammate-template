# Deal Coaching

Own deal-coach and assess deal or call evidence. Call preparation, post-call logging, and CRM execution belong to Pipeline.

## Entry

Read `workspaces/deal-coaching/CONTEXT.md` to select a deal-coach branch. Load only that contract's applicable Inputs rows and named reference sections.
Root AGENTS.md provides direct named-skill routes, so execution does not depend on automatic discovery of this file.

## Boundaries and handoffs

Customer systems remain read-only per `rules#read_only_skills`. Salesforce suggestions and record problems are notes for Operator, never writes by Coaching.
Route call preparation to Pipeline's sales-call-prep through root `AGENTS.md`.
Route completed-interaction suggestions to Pipeline's interaction-sync, hygiene findings to pipeline-review, Task work to task-triage-speed-run, and signed-deal work to close.
The responsible Pipeline workflow checks evidence, obtains Operator's approval, and reads back any approved write. Coaching notes do not bypass those gates.
Coaching reports, lessons, and criteria proposals stay in the Coach thread. Source material stays in its systems or the sandbox.
For criteria refresh, Operator approves exact numbered wording in the Coach thread. The Systems repo-maintenance carries the approved diff and evidence into a repo PR.
Authoring guidance lives in `_core/CONVENTIONS.md`. No customer data, snapshots, or lessons files enter the repo.
