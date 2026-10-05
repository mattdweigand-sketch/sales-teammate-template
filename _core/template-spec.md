# Sales Teammate Template build specification

Approved scope is a new generalized template, local and GitHub repositories, complete onboarding, and a scratch simulation of every workflow.
The source checkout is unchanged. The template has independent Git history. Source revision is `c8387f37bcf43cd82bf517a7da8f457927763da2` with 170 tracked files.

## Audience and destination

A sales operator adapting the system to their company, territory, product, and connected tools.
Durable local home is a sales-teammate-template checkout under the operator's repository folder. GitHub name is sales-teammate-template, private by default.
Git and the verified GitHub revision provide recovery. Scratch and run evidence remain outside both repositories.

## Map and ownership

| Area | Owns | Handoffs |
|---|---|---|
| Prospecting | Signals, adoption, unsent outreach, follow-up, event sequences | Qualified evidence to Outreach, proven sends to Follow-up, open deals to Pipeline |
| Pipeline | Prep, interaction sync, watch proposals, hygiene, triage, usage, customers, close | Reviewed CRM state to Forecasting, approved configuration to Systems |
| Deal Coaching | Call, deal, pre-meeting and criteria branches | CRM suggestions to Pipeline, approved criteria diffs to Systems |
| Forecasting | Forecast, pace and forward coverage | Read-only reports and approved learning diffs to Systems |
| Systems | Repository, configuration and health maintenance | Implements authorized domain changes and verifies actual deployment |
| Shared core | Policy, shared rules, helpers, onboarding, simulator and tests | One canonical owner per value and rule |

Preserve five workspaces, 18 named routes and 17 contracts. Keep external Salesforce, Gmail draft, thread and sandbox handoffs.
No invented sequential stages. Named workflows load their contract and scoped Inputs. Onboarding and maintenance do not become routine sales context.

## Generalization

Copy tracked text only. Exclude the source Git history and all five collateral files including binary PDF and video.
Replace personal identity, owner IDs, tenant URLs, Slack IDs, sender addresses, company domains, note initials, quota history and seller-specific claims.
Demo examples use reserved domains and explicitly fictional IDs. Replace proprietary font dependencies with licensed bundled fonts.
Keep runtime adapter commands identifiable as platform-specific. CRM custom fields and warehouse schemas are sample compatibility interfaces.
Document their mapping and verification requirements before live use. No credentials or real customer data belong in template answers or fixtures.
Default automatic date moves, unattended writes, merges and schedule activation are disabled. Existing exact approval and readback gates remain.

## Onboarding

A company questionnaire and guided integration interview cover persistent settings and all 21 external and local surfaces. Required questions have no fictional defaults.
Every integration needs configure, defer or not_used with the declared settings or a reason. Credential values stay in the runtime secret store. There is no mode choice.
A saved JSON answer file maps each answer to canonical policy or product references. The agent collects actual settings and saves the file outside both workspaces.
Identity, timezone, internal domains, CRM URL, notes, product messaging, ICP, quarterly targets, warehouse, operation routing and adapter mappings are configurable.
Configuration creates a fresh workspace at an absent external destination, excludes Git history, preserves the source template, and commits no customer material.
Validate all answers before copying. Reject unknown answers, invalid types, paths, identity conflicts and invalid mappings without partial destinations.
Repeat setup refuses overwrites. Normal setup derives configured state and rejects reserved identity and CRM domains.
All 21 live integration checks remain pending. Deferred capabilities hold their dependent operations.
Only the scratch rehearsal opts into simulation with fictional answers stored under `_core/tests/fixtures/onboarding/`. Check distinguishes these internal states.
Generate portable skill pointers for all named routes. Pointers do not install agents, grant permissions or activate schedules.

## Verification

1. Source baseline passes its supported Python suite before copying.
2. Run one onboarding and research-to-outreach representative task, repair observed defects, then expand the rehearsal.
3. Configure scratch workspaces with demo and alternative company/timezone/CRM-field answers. Check source bytes remain unchanged.
4. Simulate all 18 names and every material branch through local connector doubles. Trace actual contract Inputs and handoffs.
5. Exercise positive, denial, no-approval, stale-evidence, ownership, duplicates, incomplete retrieval and mismatched readback cases where applicable.
6. Execute real deterministic helpers and the full inherited suite. Build the two-page pilot PDF and inspect both rendered pages.
7. Check routes, policy references, source-data leakage, local links, whitespace, placeholders and scratch output boundaries.
8. Commit and push a fresh main branch. Verify GitHub main equals local HEAD and GitHub CI passes. Mark the GitHub repository as a template.

The release report lists actual counts, scratch evidence and the deployed revision. A local simulation proves only the tested mechanics and cases.
Live CRM, mail, warehouse, runtime permissions, notification delivery and activated automations remain unverified until checked in the adopter's environment.

## Deliverables

The complete sanitized repository, this specification, onboarding questionnaire and CLI, typed company answer schema, product and ICP guidance, adapter guide,
portable skill pointers, fictional test fixtures, deterministic workflow rehearsal, regression tests, scratch report and verified GitHub publication.
Build and simulation are already authorized by the request. Runtime external writes still require the selected workflow's exact approval.
