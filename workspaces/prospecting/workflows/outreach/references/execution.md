# Outreach execution

## Intake

Take the fenced JSON bundle for the signal Operator chooses from the thread, not automatically the recommended signal. If the choice is unclear, ask before drafting.
A web bundle must carry `gate`, `quote`, `source_url`, `published_date`, `date_basis`, `checked_at`, `account_domain`, `classification: active_initiative`, and
`relevance: employee_use`. Bundles missing those fields need a new scan. Do not invent them to pass a gate. No bundle, no draft. Do not reconstruct one from memory or a summary. Re-fetch the
source page when `checked_at` is older than `policy.prospecting.outreach.bundle_checked_max_age_hours`.

Account. No draft without one resolved Salesforce Account Id that routes `scan` on a current read, owned by `policy.prospecting.identity.sfdc_user_id`. Query the Account by Id (OwnerId,
Owner.IsActive, open Opportunities per `policy.prospecting.salesforce.open_opportunity`) and apply the `policy.tooling.scripts.prospect_account_route` route table.
Zero or many matches,
or any route other than `scan` stops. Prior evidence never overrides current ownership. Include that complete current Account receipt and its verified account_domain in the outreach gate packet.
The bundle must match this domain.

Adoption. An adoption sentence needs a privacy-checked `signal-user-scan` bundle from this thread and states only that bundle's `policy.prospecting.user_scan.statements` fact, per the talk-track
Claim boundaries. Without one, leave the sentence out. For a `paid_individuals_present` draft, wrap that bundle and use the wrapper as the bundle.

```
{signal_type: paid_individuals_present, published_date: <data_through_date>, checked_at: <now, ISO with offset>,
 quote: <policy.prospecting.user_scan.statements[adoption]>, date_basis: warehouse, account_domain: <account_domain>,
 account_name: <account_name>, adoption_bundle: <the privacy-checked bundle>}
```

## Recipient

Prefer the person named in the signal. Sources in `policy.prospecting.outreach.recipient_sources` order. Query Salesforce Contacts on the Account with Email and Id. A Salesforce recipient needs
its Contact Id. Search Gmail for prior threads with the person, then Apollo. If Operator explicitly supplies the address here, record `Operator supplied in this conversation`. Never guess an
address or
relabel its source.

## Activity

Read Salesforce Tasks and Events on the Account and Contact inside `policy.prospecting.outreach.activity_lookback_days`, including date, target, and each Task's status and subtype. Search Gmail
`in:sent to:<address>` for the same window. Both completed reads go into the packet unfiltered. Missing or failed reads stop. They are not empty results. Preserve unknown targets so the gate can
suppress conservatively.

## Angle

Choose one messaging angle from `workspaces/prospecting/workflows/outreach/references/talk-track.md` for the verified initiative and recipient's evidenced responsibility. State the
persona/responsibility in ordinary language and give one sentence explaining the connection. Titles are search aids, not proof of ownership or authority. If responsibility is unknown,
research it or ask Operator. Do not
fabricate a rationale.

## Draft

Follow `policy.prospecting.outreach.draft_shape`. Use the Core messaging and Match the angle sections selectively. Preserve the document's Claim boundaries. Consult its supporting evidence only
for claims actually used. Do not infer pain, budget, tool dissatisfaction, or buying authority. When the bundle carries `third_party_paraphrase`, credit the observation to the outlet that
reported it, not to the person it describes. Keep benchmark statistics, customer names, and unsupported numerical claims out of the first message. Review source meaning, recipient fit, claim
support and limitations before proposing. The packet's `talk_track` is `{angle, persona, pick_reason}` in ordinary language. It records judgment, not proof that judgment is correct. Load
`draft-anti-slop` and run `policy.prospecting.outreach.lint` for advisory style review. Style warnings never block. Report unavailable lint.

## Proposal

Show exact To, Subject, Body, recipient source and title, signal type, verified responsibility, chosen angle, rationale, and the gate verdict. Number it. Stop and wait.

## Write and readback

On approval create the one Gmail draft. Read it back by draft id (rules#write_protocol).
Compare the complete returned `to`, `subject`, and `body` with the exact approved values using
`policy.tooling.scripts.prospect_readback_check --gmail --expected <approved.json> --actual <readback.json>`.
Preserve any returned CC/BCC fields.
The checker rejects added recipients. Use returned
field values, never reconstruct them from the proposal. Missing full readback or a mismatch stops. Report it without repairing or repeating the write.

## Report

```
Bundle: <account> | Salesforce <Account Id>, route scan | <signal_type> | <published_date or observed current> | source checked <checked_at date>
Recipient: <name>, <title> | <email> | source: <policy source>
Activity: <n> Salesforce rows, <n> Gmail sent, last touch <date or none>
Responsibility: <verified role> | Angle: <plain-language messaging angle>
Pick reason: <one sentence>
Gate: allow / block (<reasons>) | Lint: <advisory warnings, none, or unavailable>

Proposal 1. Gmail draft
To: <email>
Subject: <subject>
<body>

Limits: <material inference, uncertainty, or unresolved style issue; omit when none>
```

## Boundaries

- Sending email, replying, or forwarding. Ever (rules#approval).
- A recipient address that is guessed, pattern-built, or from a source not in policy.prospecting.
- Unsupported product claims or wording that exceeds the talk track's Claim boundaries. An angle label or passing gate does not establish claim support.
- Any Salesforce write. Follow-up Tasks belong to `signal-followup`.
- Ledgers or files written to the project. Gmail is the record of what was drafted.

## Sales authority

Use rules#approval and rules#write_protocol for each exact proposal, approval and native readback. Never treat a live policy mirror as independent approval.
An open Opportunity belongs to Pipeline. Re-read current owner, open Opportunities and duplicates before proposals and again before every approved write.
Canonical draft, body and voice rules apply with policy.email_voice. A conflicting rule holds the proposal for Operator.
Never retry a failed or mismatched create blindly. Report the actual partial result and one corrective proposal for approval.
