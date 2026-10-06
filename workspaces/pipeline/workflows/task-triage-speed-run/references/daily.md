# Scheduled triage

## Evidence and routing

- Run the existing triage contract for Operator's due and overdue Tasks, applying `references/grouping.md` "Pipeline ownership" and retaining undated-Task coverage.
- Before proposing, read Gmail sent mail, Calendar, and Momentum per `rules#momentum` for completed actions and buyer-stated dates.
  Propose completion when Operator already handled the action, or the date the buyer actually stated. An unread source is not checked, never proof of completion.
- Search current project deal threads by Account name with `pplx project sessions list --search`.
  Send matched Tasks and evidence with `pplx session send` to the verified deal thread instead of proposing them in the scheduled run.
  On confirmed failure with no delivery, retry once with `pplx tm mail send <deal-thread session id>`. Record which command delivered. Never claim delivery without a successful send.
An ambiguous send needs native reconciliation or stays needs-input. Never blindly retry a missing or delayed response.
  Mark those rows routed, not completed. Do not auto-move or otherwise write them here. Failed or ambiguous routing is needs-input.
- Show draft text only. Create Gmail drafts only after approval. Apply the ownership order in `references/grouping.md` "Pipeline ownership".

## Meeting preparation

- Read `triage` settings from the `pipeline` policy block for `meeting_lookahead_business_days` and `prep_lead_business_days`.
  If unavailable, report meeting preparation not checked and continue the existing Task pass. Never invent timing defaults.
- Read Calendar for external meetings within the configured business-day lookahead on Operator's open Opportunities, per `rules#calendar_search`.
  Determine external attendees with `policy.tooling.internal_domains`. Scheduling alone does not establish completed action.
- Read open prep Tasks on each Opportunity. An adequate prep Task is due at least the configured business-day lead before the meeting.
- For each meeting without one, propose a Task due that lead before it. The Subject names the asset to prepare and WhoId links the verified primary Contact.
  Show the exact Opportunity, Contact, date, and proposed fields. Missing Contact, ambiguous linkage, or a past prep date needs input, not a guessed record.
  Recheck duplicates before any approved create. Treat the create as its own explicit record approval after the main pass, never as an automatic date move.

## Approval and delivery

- Apply only qualifying next-business-day moves under `rules#auto_date_move`, with complete readback and the label `Auto-moved`.
- Group all other local proposals and wait for Operator in this run thread. Apply only approved items with readback. No reply writes nothing else.
- Report routed rows and prep proposals separately from the due-Task pass. No email is sent.
- If complete reads show no due or overdue Tasks and no prep proposals, reply in one line and run `pplx automation suppress-run-notification`.
  Do not suppress actionable proposals or incomplete-source warnings merely because the initial Task queue is empty.
