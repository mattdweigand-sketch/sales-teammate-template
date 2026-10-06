---
cadence: one-off
reads: references/, _core/policy.yaml (prospecting, tooling, email_voice, template), _core/rules.md and current run evidence
writes: unsent Gmail draft after approval
next: Pipeline when an open Opportunity exists, otherwise Outputs handoff
---

# Outreach

Turns one qualified bundle into one Gmail draft (`policy.prospecting.outreach.max_drafts_per_run`). The bundle arrives as fenced JSON in the thread from a scan stage. This stage never finds
signals, never sends, and never writes to Salesforce. Product facts come from policy.template.
Wording follows `workspaces/prospecting/workflows/signal-prospecting/02-outreach/references/talk-track.md`.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Policy | `_core/policy.yaml` | prospecting.outreach, prospecting.identity, prospecting.user_scan, template | Set bundle age, verified recipient sources, suppression and draft limits |
| Reference | `workspaces/prospecting/workflows/signal-prospecting/02-outreach/references/talk-track.md` | Core messaging, applicable Match the angle row, Claim boundaries, supporting evidence only for claims used | Select supported product wording and keep claims within the chosen angle |
| Reference | `workspaces/prospecting/references/icp.md` | Relevant Target personas section | Connect the initiative to the recipient responsibility supported by sources |
| Tool | `workspaces/prospecting/workflows/signal-prospecting/02-outreach/scripts/prospect_outreach_gate.py` | Docstring and CLI | Check evidence age, recipient, suppression and the exact proposed draft |
| Tool | `workspaces/prospecting/scripts/prospect_account_route.py` | Docstring and route table | Recheck Account owner and open-deal routing before drafting |
| Tool | `workspaces/prospecting/scripts/prospect_readback_check.py` | Docstring and CLI | Compare approved fields with the complete native returned record or draft |
| External skill | draft-anti-slop | Advisory style review named in step 6 | Surface advisory cold-email style warnings without overriding approved wording |
| Working | Qualified bundle in this thread, recipient sources and current Salesforce/Gmail activity reads | No bundle reconstruction from memory or summaries | Bind this draft to its actual bundle, verified recipient and completed suppression reads |
| Reference | `workspaces/prospecting/workflows/signal-prospecting/02-outreach/references/execution.md` | Full file | Apply bundle intake, recipient checks, suppression and exact Gmail readback |
| Rules | `_core/rules.md` | rules#approval, rules#write_protocol, rules#absence_conclusions, rules#not_checked_means | Require exact approval and native readback, and separate unread evidence from absence |
| Rules | `_core/rules.md` | rules#email_body | Check customer draft wording and re-read linked security evidence before answering |
| Policy | `_core/policy.yaml` | email_voice, tooling | Shared draft review and tool paths |

## Process

1. Load the scoped Inputs.
2. Intake the same-thread fenced bundle for the signal Operator chooses using Intake. Confirm one current Operator-owned named Account and its scan route, refresh stale source evidence,
   never reconstruct missing fields. Any open
   Opportunity hands
evidence to Pipeline and stops prospecting.
3. Resolve the recipient and verified address using Recipient.
4. Complete and preserve all Salesforce and Gmail suppression reads using Activity.
5. Choose one supported messaging angle for the evidenced responsibility using Angle.
6. Draft and review the message using Draft. Run advisory style review.
7. Gate. Write the packet (shape in the script docstring) and run `policy.tooling.scripts.prospect_outreach_gate --packet <p.json>`.
Exit 1 means fix the named reason or stop. Never edit the packet to pass.
8. Run the Audit, then present the exact numbered proposal using Proposal and Report. Stop for approval.
9. After approval create only the approved Gmail draft and compare full native readback using Write and readback. Stop on mismatch. Recheck owner, open Opportunities and duplicates before writing
per rules#write_protocol.
10. Hand off. Say that `signal-followup` runs after Operator sends. Do not create a Task here.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 8 | Exact To, Subject, Body, recipient evidence, angle rationale and gate result | Approve these exact fields. Review meaning, recipient fit and claim support. Operator sends manually |

## Audit

| Check | Pass Condition |
|---|---|
| Evidence and fit | Source meaning, recipient responsibility and messaging connection are supported. No invented pain, budget or authority |
| Claims | Draft respects talk-track Claim boundaries and carries any material uncertainty |
| Gate | Required evidence/activity reads are complete and prospect_outreach_gate.py allows. Advisory style lint is reported |
| Ownership, before proposals and writes | Current owner is prospecting.identity.sfdc_user_id and complete open Opportunity reads pass. Any open deal routes to Pipeline |
| Scope | Respects policy.prospecting.approval.never. No run or customer material in Git. A failed read is not checked |
| Authority mirrors | policy.prospecting.approval.unattended_writes remains false and policy.prospecting.approval.readback_required remains true. Core rules own authority |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Exact proposal | Current thread | Numbered To, Subject and Body plus evidence and gate result |
| Approved draft | Gmail after approval | One draft with Id and exact readback. Operator sends manually |
| Proven send handoff | Current thread to workspaces/prospecting/workflows/signal-prospecting/03-followup/ | After Operator sends. No Salesforce Task in this stage |
| Pipeline handoff | Pipeline thread | Account and open Opportunity IDs with dated evidence. No prospecting writes |
