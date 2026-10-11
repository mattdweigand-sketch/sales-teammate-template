# Collect

Read at the Collect step. Save each query result in the sandbox. Deduplicate SELECT fields before querying.
For Gmail pagination, use only the exact cursor returned by that same search. Continue until no `next_cursor` and retain all pages. Salesforce queries must also be complete.
Page one call at a time. Print only date, sender, subject, and snippet per message. The saved page stays whole.
Resume from the last `next_cursor`, never page one. Retry a failed page once with the same cursor, then record a gap per item 5.
`<userId>` comes from `rules#run_start`.

1. Opportunities. Record the original open count.
   List all current project sessions with `pplx project sessions list <project> --limit <L> --offset <O>`, starting at 0 and advancing by L until a short page.
   Save each unchanged raw list bound to its requested offset in `pages` entries with `offset` and `sessions`, plus `limit`, `project_uuid`, and `accounts`.
   Each Account input has `account_id` and `account_name`. Run `deal_thread_match --input <sandbox.json>` and keep its output, owner session id, and link.
   The helper matches exact normalized names after legal suffix removal, using only titles ending in " deal". Do not filter the project listing with `--search` or guess a match.
   For every Account, including listed matches, call `session_list` with type `computer`, search `"<account_name> deal"` and limit `100`. A listing alone never proves absence or uniqueness.
   Save raw JSON in `account_searches` by account_id (null on failure or unavailable tool). Rerun the helper before routing or proposals. Missing search evidence never establishes an owner or local.
   Missing, failed, malformed or at-limit searches hold that Account only. Same-project exact matches merge by context_uuid with the listing. Ambiguity and collisions still hold.
   `owner` routes evidence to the deal thread. `local` keeps the existing review path. `needs_input` or `incomplete` holds proposals on the affected record.
   Load shared `workspaces/pipeline/references/deal-activity-reads.md` "Opportunities" for the native fields and owned-open query.
2. Tasks, Events, and Contacts for those deals. Use the shared "Activity" native templates, fully paged, retaining undated open Tasks for review.
   Account domains come from external Contact emails, excluding `policy.tooling.internal_domains` and `policy.tooling.generic_email_domains`.
   Use a verified Contact ID for Task linkage; a name alone is insufficient.
3. Run `policy.tooling.scripts.hygiene_check <opps> --tasks <tasks> --events <events> --as-of <run start with local offset> --json`.
   Its source receipts own mechanical triggers, last touch, and field checks. Event-only `new_activity` is displayed as elapsed, attendance unverified, never a write basis.
   `task_gap` is a trigger for triage, not a Task create here. Review `milestone_task_candidates` per `rules#followup_task` before treating a later Task as an extra current-action Task.
   Identify all Operator-owned open sales Tasks by OwnerId equal to the run user per `rules#task_date_coordination`. Save native Task state and `run.user_id` for the renderer.
   Split extra Tasks, date mismatches and absent current-action Tasks into read-only `triage` rows. Route only deal-context findings to deal threads, even when the same deal has both.
   For a triage-only finding, keep the flagged deal in `deals` with its read-only `triage` row, never invent a `routed` deal-context row or approval label.
   Never propose any Task or next-step change. Missing or unreadable owner evidence holds that finding as needs-input.
   Future Tasks stay outside `triage` findings. They may name a field-only ownership boundary, never a triage item or deal-thread Task proposal.
4. Gmail and Calendar, every weekly or requested run, including early stages. Use shared `workspaces/pipeline/references/deal-activity-reads.md` "Account-domain Gmail" for every Account thread.
   Read Slack even for deals not flagged by Gmail or Salesforce. The freshest dated evidence across Gmail, Calendar, Salesforce, and Slack wins.
   Search Calendar by Account name over `policy.tooling.calendar_lookback_days` through `policy.tooling.calendar_lookahead_days`, per `rules#calendar_search`.
   These Account reads cover any inbox scan. Query field history since the previous weekly review:
     ```sql
     SELECT OpportunityId, Opportunity.Name, Opportunity.Account.Name, Field, OldValue, NewValue, CreatedDate
     FROM OpportunityFieldHistory
     WHERE Opportunity.OwnerId = '<userId>' AND CreatedDate > <previous Friday run start> AND Field IN ('created', 'StageName', 'CloseDate')
     ```
   For owned S1 deals, also page all StageName history without a date cutoff to establish a prior S2+ backward move. History alone does not establish its lost-path reason.
   Review that reason against dated retrieved buyer evidence and existing notes. Missing history or evidence is unknown, not proof of a lost path.
     ```sql
     SELECT OpportunityId, Field, OldValue, NewValue, CreatedDate FROM OpportunityFieldHistory
     WHERE OpportunityId IN (<owned S1 ids>) AND Field = 'StageName' ORDER BY CreatedDate
     ```
5. Coverage. `policy.tooling.scripts.coverage_check --scope pipeline --since <run start with local offset> --json`.
   Save the output in the sandbox; the report and notification both render from that file. Rerun and save again after evidence changes or a gap is repaired.
   Reconcile any unmatched or domain-unverified Salesforce Event before proposing on its Account; zero Account-name results cannot pass this check.
   Search its Subject or sweep the date range, splitting below `policy.tooling.calendar_result_cap`, match attendee domains, save results, and rerun per `rules#calendar_search`.
   Exit 1 means not ready: finish missing checks and rerun.
   If a gap cannot be resolved, label the report incomplete, disclose it, and withhold affected proposals. Do not silently exclude test-looking records or invent domains.
6. `not checked` per `rules#not_checked_means`. Whether the user's last message was answered, and the newest message, are bounded by `rules#absence_conclusions`.
   Preserve errors and reconciliation evidence. Subjects alone support metadata-only notes, not email-body conclusions.
7. Friday only, when Operator supplies a `pilot-usage` report in this thread. Take the `AccountId` from the item 1 Opportunity the report links or Operator names, never by matching a name.
   Run `SELECT Id, Name, Admin_Organization_UUID__c, Org_UUID__c FROM Account WHERE Id = '<AccountId>'` and save the result.
   No linked or named Opportunity in item 1, or no Account row returned, makes the report needs-input. This read feeds only the `rules#pilot_handoff` identity check.
   It reads no warehouse data and approves no write.

## Slack


For every in-scope deal, use its named buyer contacts from Contact Roles and `Customer_Point_of_Contact__c`.
Resolve that field to a verified Contact and email from saved Salesforce records. Read the Contact by ID when needed. An unclear identity or missing email is Slack not checked, never a name guess.
Deduplicate contacts per deal. Do not replace the named buyers with every Account contact.

Follow `_core/slack-evidence.md` "Search" and "Limits" for every selected contact.

- Slack is an added evidence source, not a required coverage gate. No Slack user or no Slack evidence means Slack not checked for that contact, listed in Coverage.
  Group contacts in one compact line per deal using `run.slack_coverage_notes` per `references/report-format.md` "Coverage".
  Missing identities and empty Slack results never set `run.process_status` to `incomplete` or withhold a proposal by themselves. They do not add to the deal-level not-checked count.
- Withhold a buyer-status or commitment change for a Slack limit only when a search errored or was incomplete for a contact on that deal with a verified Slack user.
  List the limitation in that proposal's section. Put the affected change in Needs your input with no write option until that search is repaired.
  Keep unrelated changes on the same deal and proposals on other deals eligible. Do not put the whole deal in `withheld` because of a Slack limit.
  If a row mixes status and unrelated changes, separate them before assigning proposal labels. Slack limits alone do not make the run incomplete.
- Positive Slack facts stay usable and win when fresher. Missing Slack evidence does not invalidate supported Salesforce, Gmail, or Calendar facts.
  Keep the Salesforce, Gmail, and Calendar checker behavior and its saved output unchanged. Slack notes do not repair or bypass its required checks.
