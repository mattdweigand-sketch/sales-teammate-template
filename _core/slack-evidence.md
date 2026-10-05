# Slack evidence

Read only the scoped sections named by the selected contract. Save identities, searches, and receipts in the sandbox.

## Search

Use verified Salesforce Contact emails for the selected deal or Task contacts. Deduplicate by Contact. Never guess identity from a name.
- Use the `slack_direct` connector and `slack_search_users` with the Contact's email as `query`. Accept only an exact email match, paging through all returned cursors.
  No Slack user means that contact is `not checked` for Slack per `rules#not_checked_means`. Ambiguous matches, unread results, and tool errors also remain not checked.
  A Slack user is verified only after an exact Contact email match. A failed identity lookup does not establish a verified Slack user.
- Compute the window from run start minus `policy.tooling.slack_lookback_days` through run start in the run timezone, then convert both bounds to Unix epoch seconds.
  Call `slack_search_public_and_private` with those bounds as string `after` and `before` parameters, `content_types="messages"`, `include_bots=false`, and `include_context=true`.
  Keep date words and date filters out of `query`. Check returned message `ts` values against the numeric bounds.
- Search DMs and group DMs with `query="with:<@SlackUserId>"` and `channel_types="im,mpim"`.
  Search shared channels with `query="from:<@SlackUserId>"` and `channel_types="public_channel,private_channel"`.
  Keep only verified Slack Connect channels and messages about that deal. Verify shared-channel context from the returned results or state the gap.
  Read the returned context before using a message as evidence, including relevant replies in either direction. Exclude bot messages from evidence and context.
- Page each search using only its own returned cursor until none remains. Save all search inputs, pages, and identity results in the sandbox.
  Retry a failed page once with the same cursor. Preserve the error and mark any unresolved page or context gap per `rules#not_checked_means`.
- DM and private-channel search is approved for scheduled runs with no per-run consent pause. This is read-only. Never post or react.
- Cite each used message by its returned permalink and date, with the sender and supported fact. Never construct a permalink.
  Apply `rules#absence_conclusions` to Slack retrieval completeness. A fully paged retrieved set is not full history, and absence is not evidence.
  State the limitation in each affected report section. No results, no Slack user, and incomplete retrieval never prove buyer silence or no status change.

## Limits

Slack adds positive evidence, not a required coverage gate. No user or no results means Slack not checked, never buyer silence.
Missing identities or empty results alone never make a run incomplete or withhold a proposal. Disclose the limitation.
Withhold only a buyer-status or commitment change when a verified user's search errored or was incomplete. Separate unrelated changes and keep them eligible.
Read fresher positive Slack facts alongside Salesforce, Gmail, and Calendar. Slack does not repair or bypass their required checks.

## Reply receipts

For task triage, classify the full returned message and relevant context. A substantive reply answers, asks, commits, or reports a buyer fact.
A bot, acknowledgement-only reaction, or automated notice is not a substantive reply. Do not infer a reply from a snippet or Task note.
Save reviewed substantive replies as a JSON list for `gmail_contact_stats --slack-replies <reviewed.json>`. Each receipt has these fields.

| Field | Meaning |
|---|---|
| `contact_email` | Exact verified Salesforce Contact email matched to the Slack sender |
| `ts` | Returned Unix message timestamp, no later than run start |
| `permalink` | Returned message permalink, never constructed |
| `verified_identity` | `true` only after the exact identity match |
| `substantive` | `true` only after reading and classifying the full reply |
| `is_bot` | `false` for a buyer reply |

The helper reports a positive veto when a qualifying Slack reply is at or after the last sent email. A false veto is not evidence of no reply or automatic approval.
No receipt or Slack retrieval gap never substitutes for either required Gmail reply check. Recheck Slack evidence immediately before an automatic date write.
