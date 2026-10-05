---
cadence: one-off
reads: common CRM inputs, _core/policy.yaml (prospecting, tooling, template), _core/rules.md and only the selected Buying signals or Adoption inputs
writes: nothing
next: Pipeline for an open Opportunity, Account owner for owned_elsewhere, otherwise conditional Outreach handoff
---

# Research

Read-only research with two branches. `signal-scan` selects Buying signals. `signal-user-scan` selects Adoption.
Select the branch before loading branch-specific Inputs. A report is not permission to draft, contact or write.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Common policy | `_core/policy.yaml` | prospecting.identity, prospecting.salesforce, tooling, template.icp | Resolve identity, ownership and registered tools |
| Common rules | `_core/rules.md` | rules#approval, rules#write_protocol, rules#absence_conclusions, rules#not_checked_means | Preserve authority and distinguish failed reads from absence |
| Common tool | `workspaces/prospecting/scripts/prospect_account_route.py` | Docstring and route table | Route current CRM ownership and open Opportunities |
| Common working | Current Salesforce Account and open Opportunity reads | Named Account/Id, complete current matches | Resolve the buying entity and Pipeline ownership |
| Buying signals policy | `_core/policy.yaml` | prospecting.scan, prospecting.outreach | Source limits, warm-engagement markers and activity window |
| Buying signals reference | `workspaces/prospecting/references/signals.md` | Discovery, interpretation and qualification | Apply live source and freshness definitions |
| Buying signals reference | `workspaces/prospecting/references/icp.md` | Target personas | Interpret evidenced responsibility |
| Buying signals reference | `workspaces/prospecting/workflows/research/references/buying-signals.md` | Full file except Batch mode, load Batch mode only for lists | Aliases, fit objections, per-account evidence and report |
| Buying signals tools | `workspaces/prospecting/scripts/prospect_evidence_gate.py`, `workspaces/prospecting/workflows/research/scripts/prospect_scan_verdict.py` | Docstrings and CLI | Prove quotes and render an ownership-aware next step |
| Buying signals working | Fetched public pages and current Account Tasks | This run, fetched text in sandbox | Source proof and warm-engagement checks |
| Adoption policy | `_core/policy.yaml` | prospecting.user_scan, prospecting.warehouse | Privacy schema and snapshot date |
| Adoption reference | `workspaces/prospecting/workflows/research/references/adoption.md` | Account resolution, Query, Bundle, Handoff, Report, Boundaries | Fixed query and limited claims |
| Adoption tool | `workspaces/prospecting/workflows/research/scripts/adoption_lookup.sql` | Header bindings and full query for one Account | Permitted organization and individual-adoption facts |
| Adoption tool | `workspaces/prospecting/scripts/prospect_privacy_check.py` | Docstring and CLI for account bundles | Reject extra fields and personal or activity data |
| Adoption working | Snowflake native status, fixed-query bindings and permitted result | Current run, completed snapshot only | Preserve query and result provenance |

## Process

1. Select Buying signals or Adoption and load only common and selected branch Inputs.
2. Resolve one current Account owned by prospecting.identity.sfdc_user_id and all open Opportunities before any source fetch or warehouse lookup. Missing or ambiguous identity stops.
   Apply `policy.tooling.scripts.prospect_account_route` to the current complete CRM receipt.
   Any open Opportunity hands evidence to Pipeline and stops. Every other owner reports owned_elsewhere and routes to that owner. No Account match is outside_named_accounts.
3. Buying signals checks Account and engagement, including ignored integration Tasks. Warm engagement stops cold outreach. Declare aliases, search every category and report access gaps.
4. Buying signals fetches sources in full, classifies findings and runs `policy.tooling.scripts.prospect_evidence_gate` using Qualification.
   Keep nonqualifying evidence and fit objections in the report.
5. Buying signals runs `policy.tooling.scripts.prospect_scan_verdict` with the current route and only this Account's outputs. Copy verdict and next verbatim.
   Batch mode never pools evidence across accounts.
6. Adoption resolves ambiguous identity before lookup, derives the domain and stops on internal domains.
   Run `policy.tooling.scripts.prospect_adoption_lookup` using Query. Fetch after native success.
7. Adoption builds the exact account bundle and passes `policy.tooling.scripts.prospect_privacy_check`. Never report forbidden data. A failed check stops.
8. Render the selected report and run the Audit. Before a requested Outreach handoff, confirm aliases and decide fit for Buying signals, or review the permitted claim for Adoption.
9. Hand off only an eligible qualified bundle on request. Adoption org_adopted is optional context beside a qualified web signal.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | Ambiguous Account matches before research | Choose a Operator-owned Account Id. Unambiguous named-account research continues |
| 8 | Aliases and fit objections, or permitted adoption claim, before Outreach handoff | Confirm identity and fit or review claim. Drafting still needs exact approval |

## Audit

| Check | Pass Condition |
|---|---|
| Branch | Only common and selected branch Inputs loaded. No warehouse in Buying signals |
| Evidence | Completed native reads and required helpers pass. Source meaning, dates and privacy limits preserved |
| Ownership | One current Operator-owned Account before research. Open Opportunities go to Pipeline. Other ownership goes to owner. Warm engagement prevents cold outreach |
| Scope | No external writes or send. Core rules own authority. A clean or qualified result is not approval |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Branch report and checked bundle | Current thread and sandbox | Public verdict or permitted adoption report, per branch reference |
| Eligible Outreach handoff | Current thread to workspaces/prospecting/workflows/outreach/ on request | Fenced JSON after the branch's identity, fit and claim review |
| Pipeline or owner handoff | Owning thread | Current Account, Opportunity or owner IDs with dated evidence. No Prospecting writes |
