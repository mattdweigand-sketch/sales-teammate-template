# Event list preparation

## Intake

Accept a file, sheet, or paste of any size. Save the original and a working CSV or JSON list in the sandbox, never Git.
Confirm the event name, the dates Operator attends, location, and exact ask. Missing details are needs-input, not guessed.
Optional sending mailbox and schedule come from Operator. Otherwise read `apollo_email_accounts_index` and select its `default: true` account.
No default or multiple defaults is needs-input. Selecting a mailbox is not approval to use it.
Run `policy.tooling.scripts.event_list_prep <input.csv|input.json> --as-of <local-offset timestamp> --output <reviewed.json>`.
It normalizes names, email, company, and website, deduplicates, and labels missing guard evidence as needs-input. It performs no network calls or writes to customer systems.
Preserve source row IDs and duplicate reasons. A row with no usable email is still retained for possible enrichment. No list-size cap applies.

## Salesforce and reply checks

Read Salesforce for every contact and Account, with all pages retained. Resolve Contacts by exact email or a verified supplied ID, never name-only guessing.
Missing email may use verified contact or Account IDs and reviewed account-domain evidence. Unclear identity stays needs-input until resolved.
Read Account `Id, OwnerId, Website` and associated Contact `Id, Email, AccountId`. Record a completed no-match search explicitly, not as a tool gap.
Fetch complete candidate Accounts under exact OwnerId or verified AccountId filters, never LIKE wildcards.
Normalize Website and input hosts by removing scheme, www, and path, then compare exact hosts.
Match the normalized Website host or exact Contact email domain. Do not collapse subdomains to a root domain. Review any subdomain alias explicitly, with its evidence, before matching.
Read Opportunities for each resolved Account using `policy.prospecting.salesforce.open_opportunity`, regardless of Opportunity owner.
An existing Account owned by `policy.prospecting.identity.sfdc_user_id` is eligible.
Event lists Operator names also admit rows marked with Operator as outreach owner when the Account is unassigned or missing.
Unassigned means its owner is in `policy.prospecting.event.outreach_owner_scope.house_owner_ids`.
Missing means a completed lookup found no Account and `policy.prospecting.event.outreach_owner_scope.include_missing_account` is true.
Other sellers' Accounts, including inactive other owners, and unflagged house-owned or missing-Account rows are outside_named_accounts.
Ambiguous identity or an incomplete lookup stays needs-input. No other list override can expand it.
The run names the outreach-owner column and Operator's value from the list Operator named. A missing or ambiguous column is needs-input, never an inferred outreach owner.
Retain that column in saved reviewed rows. Pass `--outreach-owner-column <column>` and `--outreach-owner-value <Operator's value>` on every helper run, including launch rechecks.
An existing CRM link to a configured house owner is allowed only for a row qualified as outreach_owner. Named-account rows retain the existing hold.
Before E1 run `apollo_contacts_search` by each exact email, following all cursors and reading contact data.
Record a complete no-match explicitly and resolve duplicate Apollo matches before proceeding.
Hold an existing Apollo contact with a different or personal email, or a CRM link owned by another seller. Personal domains use `policy.tooling.generic_email_domains`. Show each hold reason in E1.
Set apollo_contacts_checked only after email, CRM linkage and owner, and active-sequence data are complete per contact. Unknown active_sequence stays needs-input, never assume false.
Match Operator's event invite export, such as Grip, by exact contact email. If supplied, require a complete match check per contact. If no export is supplied, E1 says none was checked.
active_sequence and event_app_invite are named, overridable per-list exclusions. An override never completes their missing evidence or expands outside_named_accounts.
Use the bounded reply check allowed by `rules#absence_conclusions`, with the verified Contact address and Operator's mailbox from `rules#run_start`.
The window runs from run start minus `policy.prospecting.event.recent_reply_days` through run start, inclusive. Save both endpoints with explicit offsets.
Run a targeted inbound search by that exact Contact sender address over the window in Operator's mailbox, without a recipient restriction. Keep a separate sent search from Operator to that Contact.
Use inbound `from:<Contact address>` and sent `from:<Operator address> to:<Contact address>`, with date filters covering the window. Run each Contact separately, never grouped searches.
Use exact email addresses and date filters covering both endpoint dates, then classify actual timestamps within the window. Never substitute a domain-only search.
Follow every returned cursor and read all returned message bodies and every message in each returned Gmail thread. Deduplicate messages by native ID.
Exclude notices, bots, and out-of-office mail from substantive replies. Save the newest retrieved substantive inbound timestamp within the window.
Set `replies_checked=true` only after both searches and all returned thread reads finish without errors, timeouts, unread bodies, or incomplete pagination.
Otherwise leave it false or unknown and hold the row as needs-input. Neither an override nor a null timestamp completes the check.
Save the queries, window, pages, thread IDs, and reviewed classifications in the sandbox. Set `last_reply_at=null` only when the completed check retrieved no substantive reply.
Report "bounded reply check completed, no substantive reply retrieved" with its window when applicable. Relevance-ordered search does not establish complete Gmail history.
Show that retrieval limit in the enrollment proposal. The check supports the E1 enrollment proposal and its pre-enrollment recheck only, never approval to spend or enroll.
Save a reply-check receipt with window endpoints, exact query shapes, contacts checked, substantive replies found, holds and reasons, cursor completion, and thread-read evidence.
Attach that saved receipt file to the E1 thread message. Do not substitute a sandbox-path link for an attachment.
Read-only Salesforce queries may use `policy.salesforce` values. The workflow makes no direct Salesforce writes. Apollo's CRM sync may create or update Salesforce Contacts after approved operations.
Run the list helper again with reviewed guard evidence. Assign enroll or one exclusion from `policy.prospecting.event.exclude`, with its reason.
Incomplete identity, ownership, Opportunity, Apollo, invite, or reply evidence stays needs-input, never enroll. The helper checks mechanics, not the truth of connector evidence.
Keep every open-Opportunity contact in the Pipeline handoff list, even when Operator explicitly overrides that exclusion for this list.
Show outside_named_accounts and recent replies as exclusions. Account scope cannot be overridden. Operator may explicitly override other named exclusions for a named contact in this list only.
An override never completes missing evidence, creates a reusable approval, or overrides a missing or malformed recipient address.

## Enrichment

Only helper enrichment_candidates on resolved Operator-owned Accounts whose only exclusion is unverified_email enter enrichment.
Use `policy.prospecting.event.enrich` and `policy.prospecting.event.enrich_order`.
Never select enrichment by the needs_input label, and never enrich outside_named_accounts or contacts with other exclusions. Resolve missing guard evidence read-only first.
For a row with no usable email, only the exact-email Apollo existing-contact/active-sequence, supplied invite-export matching and reply checks may wait for the returned address.
Account identity and owner, open-deal, name, duplicate and any existing-Apollo-contact conflict checks must pass first. The row stays needs_input until its email-dependent checks complete.
Before every credit spend show the exact candidates, operation, count, available balance, estimated credits, and the source of that estimate. Unknown cost stays needs-input.
Wait for that spend's explicit approval. One operation's approval never covers another, and the final enrollment approval never authorizes enrichment.
Label each spend C1, C2, and so on within this run. Accept only its displayed label or `approved <label>` under `rules#approval`. Edits need a new label and exact proposal.
Every C proposal states that Apollo's CRM sync may create or update Salesforce Contacts from approved enrichment. The workflow itself makes no direct Salesforce writes.
1. Call `apollo_people_bulk_match` without waterfall on the approved candidates. Preserve each returned verification status and domain catch-all evidence.
2. For candidates with no verified email after step 1, propose a separate waterfall search and spend. Only after approval call `apollo_people_bulk_match` with `run_waterfall_email=true`.
On the address enrichment returns, run the exact-email Apollo existing-contact/active-sequence, supplied invite-export and reply checks per "Salesforce and reply checks".
Do not reuse checks from a missing or different address. Rerun the helper before E1. Incomplete results stay needs-input and cannot enroll. Known-email enrichment still requires all checks complete.
If a waterfall email lacks a catch-all flag, use only a same-run Apollo match flag for the same exact email domain. Preserve immutable run_start, match run_start, match email, flag, and native source.
Record the inherited flag source in the helper output and saved receipt. No same-run same-domain flag means unknown and held, not a guessed non-catch-all value or another spend.
Verified means Apollo `verified` on a non-catch-all domain, with `catchall_domain` false.
Unknown catch-all evidence, any error, empty result, or out-of-credits response is unverified. Never infer verified status from a plausible email or scrub PASS.
Keep catch-all addresses excluded under event policy unless Operator explicitly overrides them for this list. Domain mismatches stay held for review.
After reviewing enrichment results, rerun event_list_prep. Export only eligible rows with `First Name, Last Name, Email, Company Name, Website` to sandbox CSV.
Run `policy.tooling.scripts.event_scrub_leads scrub <eligible.csv> --output-dir <fresh-dir> --clean-column-profile full` per `01-list-prep/references/scrubber.md` "Run".
Then independently run `policy.tooling.scripts.event_scrub_leads audit-clean-output <fresh-dir/clean_chunks> --report <audit.json>`.
Both reports must say PASS. Scrubbing is hygiene, not verification, approval, or enrollment. Preserve every removed or quarantined row and reason in the proposal.
Run `policy.tooling.scripts.event_make_batches <clean_chunks> --code <event-code> --output-dir <fresh-batches-dir>`.
Use full-column clean chunks so Website remains available for the batch domain check. Review `batches_report.json` and `domain_mismatch.csv` when present.
Every missing name or email, duplicate, excluded row, domain mismatch, or quarantine must reconcile to the approved list. Never silently lose a row.
Keep mismatches held unless Operator explicitly resolves or overrides the named address. An approved domain override uses the helper's `--allow` file, limited to those exact emails.

## No enrollment

Check after prep, declined enrichment, scrubbing, and batch holds. If no eligible recipients remain and no enrichment remains to propose or perform,
return the reconciled no-enrollment result to the Event Sequence coordinator.
Reconcile every input row to a duplicate, exclusion, hold, or removed row with its reason. Keep evidence gaps as needs-input and preserve the open-Opportunity handoff list.
Skip the remaining enrichment, audit of nonexistent clean files, batching, copy, enrollment approval, and Apollo writes. Never call an empty export a verified sequence.
The coordinator completes `references/readback.md` "Handoff and close" and reports closed with no enrollment, zero enrolled, no sends, exclusions, holds, and actual handoff delivery status.

## Helper evidence

`event_list_prep` accepts a reviewed JSON list or CSV with these canonical fields. Title-case intake names such as First Name and Email are also accepted.

| Field | Evidence |
|---|---|
| `first_name`, `last_name`, `email`, `company`, `website`, `contact_id` | Intake values and exact verified identity when available |
| `account_checked`, `account_id`, `account_owner_id` | Complete Salesforce Account read or explicit completed no-match |
| `opportunities_checked`, `open_opportunity` | Complete read under the configured open-Opportunity filter, including no Account match |
| `replies_checked`, `last_reply_at` | Both bounded searches and returned thread reads completed per "Salesforce and reply checks", with newest retrieved substantive reply or explicit null |
| `email_provider`, `email_status`, `catchall_domain` | Native Apollo verification status and explicit domain flag. |
| `email_operation`, `run_start` | Apollo match or waterfall operation and immutable run-start timestamp, retained through reply rechecks |
| `apollo_match_email`, `apollo_match_catchall_domain`, `apollo_match_run_start` | Saved same-run match email, explicit flag, and run identity for same-domain waterfall fallback |
| `apollo_contacts_checked`, `apollo_contact_id`, `apollo_contact_email` | Complete per-contact Apollo search and exact existing identity, or explicit completed no-match |
| `apollo_crm_linked`, `apollo_crm_owner_id` | Complete existing-contact CRM linkage and linked record owner, or explicit no link |
| `active_sequence` | True or false from complete Apollo contact data, unknown stays needs-input |
| `event_app_invite_export_supplied`, `event_app_invite_checked`, `event_app_invite` | Export availability and complete exact-email match, or no export supplied with no match claimed |

Boolean fields accept true/false JSON booleans or true/false CSV strings. Unknown values are not checked. Reply timestamps need an explicit offset and cannot be in the future.
Use `--overrides <overrides.json>` for a JSON object from normalized row ID to the exact exclusion names Operator overrode for this list. outside_named_accounts is never allowed.
The output preserves matched exclusions and reasons, applied overrides, source row IDs, enrollment labels, enrichment_candidates, catchall_source, event_app_invite_status, and Pipeline handoffs.
Eligible outreach-owner rows have `scope: outreach_owner`. The output records the selected column and value. Every other eligibility and approval gate still applies.
These outputs are proposals. No helper knows whether Operator approved a real write, and none can authorize enrollment.
