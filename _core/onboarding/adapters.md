# Runtime adapters and live setup

`integrations.json` is the complete setup inventory. It names each source dependency, its consuming workflows, authentication, settings and live checks.
The included commands target Perplexity Computer. Another runtime needs equivalent tools and the same approval, evidence and native readback behavior.
Seller product claims are separate from runtime capabilities.

## Guided interview

Walk through every entry in `integrations.json` with the operator. Explain what uses it, how to connect it, what authentication it needs and what readback proves it works.
Reuse supplied settings. Collect company choices together, then handle the remaining integration choices in small groups.
Choose `configure`, `defer` or `not_used` for every entry. Never silently skip a connector, MCP server, org skill or downstream system.
A deferred or unused surface holds its dependent operation. Other branches can proceed when their own dependencies and evidence are verified.
For example, deferred audio permits a written brief with the audio gap stated. Deferred provisioning holds close A0 and requires a supported linkage or operations route.
Deferred warehouse access holds Adoption and usage reads. A manual billing or signature evidence route still needs the corresponding reviewed close configuration.
`not_used` does not waive an existing contract requirement. If the selected workflow requires that capability, provide and verify an equivalent adapter or keep it blocked.

For a configured surface, record only these fields in `integration_setup`.

| Field | Meaning |
|---|---|
| `choice` | `configure` records intended configuration and keeps live verification pending |
| `transport` | `native`, `mcp`, `api`, `cli`, `manual` or `local` |
| `connection` | Actual connector, MCP server, API adapter, CLI or manual evidence route name |
| `auth` | `oauth`, `api_key`, `service_account`, `runtime` or `none`, never the secret value |
| `settings` | Exactly the non-secret fields declared for this surface in `integrations.json` |

Deferred and unused entries contain only `choice` and a concrete `reason`. There are no default integration answers.
The terminal setup tool asks this interview explicitly. `onboard.py integrations` prints the full inventory for guided setup.

## Complete system checklist

Use the detailed setup and verification text in the registry. This table is the interview order and the main configuration work.

| Surface | Configuration to walk through |
|---|---|
| Runtime | Project, deployment root, five teammates and threads, 18 skill pointers, org skills, project tasks/comments, session routing and saved-result paths |
| Credentials and MCP | Actual server or connector name, transport, endpoint or launch command, allowed tools, auth grant or key, secret store, scopes and rotation owner |
| Salesforce | Tenant and current user, ownership, standard objects, custom field maps and types, stages, picklists, validation, Contact Roles, formulas and CRM guide |
| Gmail | Operator mailbox, search and full-thread reads, attachments, drafts and readback, assistant sender address |
| Calendar | Calendar identity, shared calendars, local timezone, event IDs, attendees, search caps and window splitting |
| Momentum transcripts | Runtime `call-transcript-skill`, endpoint, key or token, curl/proxy behavior, response schema, Account binding, windows and sweep pages |
| Snowflake | Account, role, database, schema, warehouse, tables and columns, read-only grants, async polling, complete pages, dates, privacy and billing metrics |
| ADMIN lookup | `admin_support_team` or equivalent, actual lookup tool, email input, customer ownership, subscription status and error meanings |
| ADMIN provisioning | Deployed Salesforce flow and service identity, tier, payload, trial dates, success/error fields, invite effects, polling and restoration |
| Slack | Workspace, `slack_direct` or equivalent, exact user search, Slack Connect/DM access, complete pages, ops users and ops/deal-desk channels |
| Apollo | Account and key if needed, enrichment credits, waterfall, Contact ownership, verified sender, copy/templates, campaign tools, schedule and stop-on-reply |
| CRM sync | Gmail activity logging, Apollo Contact push, actual integration users such as Unify, Task markers, subtype, dedupe and native sync status |
| Event invites | Actual event app or manual export, complete scope and exact email matching. No export means no checked invite evidence |
| Billing | NetSuite or equivalent, CRM/ops evidence route, Stripe cancellation owner, invoices, currency, terms, price books, products, credits and pilot annualization |
| Signatures | DocuSign, Ironclad or equivalent, CRM or signed-document evidence, actual signed date and documented StageName side effects |
| Web research | Search and page retrieval tools or MCP/API, any required key, actual source text, URLs and dates |
| Audio | Media skill and speech guide, supported provider/voice, key if needed, chunk joining, MP3 playback and thread attachment |
| PDF and helpers | Python 3.12+, pinned packages, Chromium, rasterizer, bundled font hashes and external artifact paths |
| GitHub | Adopter repo and remotes, login or app access, default branch, required CI, deployment target, authorized merge and revision readback |
| Automations | Every schedule and watch, branch, owner, time, timezone, destination, delivery, duplicate checks, notifications and suppression |
| Collateral | Dated company-approved claims and limits, approved seller files, attachment access and review before buyer use |

The source has no checked-in MCP server configuration or reusable API credentials. Choose actual native connectors or configure an equivalent MCP/API adapter in the adopter runtime.
NetSuite, Stripe, DocuSign and Ironclad are downstream systems in the source close process. Its CRM and operations-evidence routes do not require direct provider API keys.
Unify contributes an integration User ID when present. The source does not call a Unify API. LinkedIn campaign touches create manual tasks and need no LinkedIn messaging connector.

## Credentials and connection setup

Authenticate each selected connection in the runtime's own connection screen or approved secret store. Guide the operator through the actual login or key provisioning there.
For an MCP server, inspect its real configuration and available tools. For a direct API, inspect its configured endpoint, auth method, rate limits and response adapter.
Check the intended account, project and tenant for each connection. Read tool permissions back from the actual runtime rather than inferring them from file paths.
Never ask the operator to paste a key, token, password, private key or credential handle into chat, JSON answers, policy, pointers, fixtures or Git.
The answer validator rejects credential-shaped keys, common token formats and credentials in URLs. This does not replace reviewing the answer file before saving it.
Record only connection metadata in setup. Keep live receipts, protected server configuration, secret references and approval evidence in the runtime thread or external sandbox.

## Schema and company policy

`questions.json` owns the company answer schema. `adapter-schema.json` lists every sample CRM custom field and warehouse table consumed by the template.
Map sample field and table names to actual names. Setup applies a single replacement pass to policy, helpers and references in the separate copy.
The revenue-field answer also maps `ARR__c` throughout that copy. Conflicting mappings fail before copying. Identity mappings remain unverified until actual describe succeeds.
Field API names alone are insufficient. Check object ownership, type, editability, formulas, record types, stages, enum values and validation behavior.
Review sample S0 through S5 stages, Paid Trial, customer types, subscription values, stage gates and terms with the operator. Adapt incompatible policy and helper logic through Systems.
Warehouse adapters also need compatible columns, joins, UUIDs and result envelopes. Table renaming does not repair incompatible semantics.
Review privacy-safe adoption projections separately from pilot/customer roster access. Configure billed-context grain and credit-cent semantics, or revise contract and helpers together.
Warehouse timezone governs persisted usage dates. Operator timezone governs local due dates and schedules. Verify conversions rather than relabeling data.
Configure the actual org lookup tool, assistant sender, integration User exclusions, provisioning flow and speech voice through the selected integration settings.
Setup places operational settings in their declared canonical policy targets. Stored integration choices retain only connection metadata and external review references.
Configure actual commercial terms, price-book names and list prices, credit products and units through Billing settings. The template's sample prices are not company prices.
Price-book and provisioning objects retain the compatible interface shape. A different interface requires a reviewed adapter change rather than invented payloads.
Do not trigger provisioning or sending to test setup. A0 can create an organization and send an invite. Verify those effects through metadata or separately authorized test evidence.

## Local prerequisites

Prepare Python 3.12 or later and `_core/requirements.txt` outside both folders. The [terminal setup](CONTEXT.md#terminal-setup) shows the manual path.
Pilot PDF production also needs headless Chromium. Use an installed compatible browser or install Playwright and its Chromium through the approved local package environment.
Install `pdftoppm` or another PDF rasterizer and inspect both pages after the scratch build. Verify bundled licensed DejaVu fonts and their hashes.
Audio needs the actual runtime media skill and speech guide. Joining needs FFmpeg or the skill's equivalent when the summary exceeds the provider input limit.
A missing local prerequisite stays pending. Local helpers use saved evidence and documented policy options. They do not authenticate or call customer systems.

## Thread delivery

The included Perplexity adapter verifies current-project thread identity and record linkage before routing evidence.
Try session send once. On confirmed no delivery, try teammate mail once. Record the native receipt and transport outside Git.
An ambiguous response needs native reconciliation, never a blind retry. Missing discovery or delivery capabilities hold the affected handoff.
Equivalent adapters use their verified transports and receipts. Local setup performs no test sends and creates no schedule.

## Deployment and live verification

Local setup produces company settings, all 18 portable pointers and a receipt listing all 21 integration choices. It sets `external_ready` to false.
For configured entries, `configure` means selected, never authenticated or verified. Deferred and unused entries keep their reasons and affected workflows visible.
Review every schedule in policy, including Coach branches, call prep, watch sync, sweep, triage, nudges, daily/Friday pipeline, customer review, forecast, pace and system review.
Include manager-update delivery, connector watches, dedicated thread requirements, worker messaging, notifications and suppression in the external deployment plan.
The copied schedule values are inactive proposals. Company timezone replacement is not approval of the times, permissions, recipients or delivery.
Complete all reversible preparation and present the exact agent, tool-permission, pointer and schedule plan for any deployment authorization still needed.
Create or activate only the authorized plan and read back actual settings. Test notification delivery only under that authorization.

Before each live branch, read its selected entries under `policy.template.integrations` and current verification receipts in the runtime thread or external sandbox.
Apply the registry's exact checks for each surface used by that branch. Deferred or unavailable mandatory capabilities hold the dependent operation.
Record identity, permissions, tools, schema compatibility, native readback and the evidence reference. Report blocked, not checked or not applicable honestly.
Keep live receipts outside Git. Local `check` reports pending live verification and never grants external readiness or write approval.
The selected workflow's approval, fresh-read and native readback gates still govern each external write after connection verification.
The template ships unconfigured. Only scratch rehearsal uses fictional connector doubles. The source company's accounts, keys, handles, merge permissions and active schedules never transfer.
