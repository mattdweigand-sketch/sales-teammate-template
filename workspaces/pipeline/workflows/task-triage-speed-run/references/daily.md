# Daily run

Scheduled and typed runs use the same triage approval and evidence gates. No reply writes nothing.

## Morning pass

- Collect all due, overdue and undated Tasks and current-action gaps per `references/collect.md`. Future Tasks serve only the pre-create duplicate check, never decisions, holds or counts.
- Read recent Gmail, Calendar, Slack and Momentum per `rules#momentum` for matching completed actions and quoted buyer dates. Unread sources are not checked, never evidence of completion.
- Use complete saved project pages and bounded Account searches with `deal_thread_match`. Read every matched deal thread's recent context yourself, read-only, with no message or wait.
  Include those Tasks in this one triage message, including eligible follow-up drafts. Never send email. Deal context never receives a Task proposal.
  `local` follows the local or unthreaded Opportunity branch; `needs_input` or `incomplete` holds that record. Never omit a held Task or claim a thread was read when it was not.
- Without action evidence, keep the Task due or overdue and prepare its action. Only a quoted buyer date or moved meeting can support a date proposal.
- Prepare full Task follow-up drafts, including deal accounts, without creating them. Verified creation after approval can qualify the displayed pair. The next Task first checks whether it was sent.

## Meeting preparation

This section loads only on an explicit typed request such as "prep tasks". Scheduled Morning pass and delivery inputs stay as today.
Unrequested prep is not applicable, not a not-checked result, and not a notification trigger. The existing Task approval and duplicate check stay.

- Read `triage` settings from `pipeline` for `meeting_lookahead_business_days` and `prep_lead_business_days`. If unavailable, report meeting preparation not checked without inventing defaults.
- Search external meetings in that business-day window on Operator's open Opportunities per `rules#calendar_search`, identifying external attendees with `policy.tooling.internal_domains`.
- Future prep Tasks serve only the pre-create duplicate check. Name an exact-action existing Task instead of creating a duplicate, never use its date to change the proposed lead or hold triage.
- If none exists, propose a Task due that lead before the meeting, with verified Opportunity, Contact, Subject and exact fields. Past prep dates or ambiguous links need input.
- Recheck duplicates before its own explicit record approval after the main pass. This creates a missing prep Task, never moves an existing Task or proves an action happened.

## Approval and delivery

- Group every due Task in one message and wait for Operator's one main-pass approval. No automatic writes. CRM corrections and new meeting-prep Tasks retain their existing separate record approvals.
- After approved writes, post the combined run receipt to Operator before deal receipts per `references/writes.md` "Writes" receipt instructions.
- Report verified results, blockers, remaining approvals and failed reads. Report undelivered receipts in a follow-up line per the same instructions.
- Only complete reads showing no due or overdue Tasks, no gap, next-step or prep proposals, no prioritized actions and no incomplete evidence qualify for the quiet one-line receipt and `pplx
  automation suppress-run-notification`.
