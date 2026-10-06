# Prospecting

Own Signal Prospecting and Event Sequence for named accounts.
Signal Prospecting has Research, Outreach and Follow-up stages. Event Sequence coordinates List Prep, Sequence Plan and Launch.
Read `workspaces/prospecting/CONTEXT.md` for routing, or go directly to the named skill's contract in root AGENTS.md.

## Boundaries

Named accounts are existing Salesforce Accounts whose OwnerId is `policy.prospecting.identity.sfdc_user_id`. Resolve one current Account before research or outreach.
For Signal, missing, ambiguous, house-owned, inactive other-owner, and other seller Accounts are outside scope. Never discover new accounts, create Accounts, or change Account ownership.
For research, outreach, and follow-up, any open Opportunity belongs to Pipeline. Stop prospecting writes and hand evidence to Pipeline, regardless of Opportunity owner.
Event Sequence uses the same named-account scope.
For an event list Operator names, rows marked with Operator as outreach owner are in scope when the Salesforce Account is unassigned or missing. Other sellers' Accounts stay out.
Unassigned means the Account owner is in `prospecting.event.outreach_owner_scope.house_owner_ids`.
Missing means a completed lookup found no Account and `prospecting.event.outreach_owner_scope.include_missing_account` is true.
Other list overrides cannot expand it. Open-Opportunity contacts still go to Pipeline under the event contract.
Read ownership and open Opportunities completely before proposing and immediately before every approved write.
Reuse core approval, write protocol, email voice, and draft rules. Never send email except an approved Apollo event sequence under `rules#event_sequence`.
Never create an Opportunity or change its stage, amount, or next step. Event-sequence writes no Salesforce records.
Live helpers retain their checks. An allow verdict is never approval or authorization. Read only the selected contract's Inputs.
Keep customer evidence, packets, drafts, and receipts in the Prospecting thread or sandbox, never Git. Systems owns repo and configuration deployment.
Authoring and maintenance guidance stays in `_core/CONVENTIONS.md`, not the operational skill body.
