# Runtime adapters and live setup

This template preserves the source system's Salesforce, Gmail, Calendar, transcript, Slack, Apollo and Snowflake interfaces.
Runtime `pplx` commands target Perplexity Computer. Another environment needs equivalent tools and the same exact approval and readback behavior.
Example Product is a fictional seller product. It is separate from the agent runtime.

## Local prerequisites

Python 3.12, PyYAML and pypdf. Install _core/requirements.txt in an environment outside the repository.
PDF production also needs headless Chromium. Licensed DejaVu fonts are bundled with hashes, so no proprietary font service or download is needed.
For page inspection use pdftoppm or another PDF rasterizer and inspect both pages. Missing optional audio or PDF tooling is a prerequisite gap.
Helpers run from any working directory with explicit saved-evidence paths and the documented policy options.

## Mapping

questions.json owns the flat answer schema. adapter-schema.json lists every sample CRM custom field and warehouse table consumed by the copied interfaces.
crm_field_map and warehouse_table_map map sample names to verified actual names. A one-pass replacement updates policy, helpers and references in the configured copy.
No source files or generic test fixtures are rewritten. Identity mappings are the default. They do not prove the actual environment provides that schema.
The amount_field answer selects the canonical forecast revenue field. Map sample stages, picklist values and close flows through an approved policy change when your sales process differs.
The sample close integration describes an org provisioning interface. Its flow, success/error fields, product names and price books require verification or an explicit adapter replacement.
Read back your actual price books, currency, ARR semantics, products, billing terms, signature fields, provisioning payload and permissions before running close.
The sample usage interface measures billed contexts and credit cents. Adapters must retain those semantics or revise the contract and compute helpers together with meaningful tests.
warehouse_timezone describes persisted warehouse dates. Operator timezone governs due dates and scheduled runs. Do not relabel stored dates without an adapter conversion.

## Verify before live use

| Surface | Required actual readback |
|---|---|
| Salesforce | Current-user ID and email match, Account ownership, complete queries, Opportunity and Task describe, stages, validation and configured fields |
| Gmail and Calendar | Operator mailbox and calendar, draft permissions, cursor semantics and retrieval limits. No send authority except approved event campaign |
| Transcript | Available org transcript skill, supported windows, meeting identity and Account binding |
| Warehouse | Schema and result columns match, read-only grants, timezone, snapshot dates and complete terminal query pages |
| Apollo | Verified sender, sequence templates, exact approved contacts/copy/schedule and stop-on-reply readback |
| Slack | Correct channel and user IDs, readable evidence and intended handoff destination |
| Runtime | Load each generated pointer through the supported skill mechanism and prove the exact contract and declared Inputs were read |
| Schedules | Operator reviews times and timezone, permissions and delivery. Creation needs authorization, then actual setting readback |

Onboarding leaves external_ready false and lists these checks in the configured receipt. File presence, sample IDs and passing local tests prove none of them.
Document actual verified settings and approval evidence in the runtime thread or external sandbox. Keep customer material and credentials outside Git.

## Release and maintenance

The template ships unconfigured with fictional examples. Local demo mode is suitable for the rehearsal.
The release CI runs the full regression suite and scratch rehearsal. New adopters should repeat the rehearsal after changing schema, policy or helpers.
Systems owns implementation. Domain owners and the operator retain product, policy, criteria and forecast decisions. Source standing merge permissions never transfer.
