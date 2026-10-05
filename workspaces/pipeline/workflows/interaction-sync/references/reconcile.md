# Find, extract, and reconcile

Read at the Find, Extract, and Reconcile steps. Save every result in the sandbox.

## Find the interaction

- Resolve the Account from the named request or Calendar attendees before searching Momentum. Use its Salesforce Id when available.
- Stop and ask when the Account is ambiguous: two or more Accounts share the name, the Momentum `salesforceAccountId` differs from the linked Opportunity's `AccountId`,
  or the matched Contact sits on a placeholder or unrelated Account. State the candidates with Ids and propose nothing for that call until the user picks one.
- Named call or "log this call": search Momentum per `rules#momentum`.
- For a Momentum transcript, before Extract, compare the meeting's start date and attendee emails with the Calendar event for this call. They must match.
- Check the transcript for date cues that contradict that date, including scheduling that same date as a future meeting
  or describing the call as a first meeting when an earlier one is logged.
- A mismatch or an identity check that cannot be completed makes the run needs-input. State the reason and propose nothing derived from that transcript.
- No recording: find the Calendar meeting per `rules#calendar_search`, say `No transcript found.`, and build the log from what the user tells you plus the event description.
  Keep the event's stable ID. With neither a Calendar event ID nor a Momentum meeting ID, ask before proposing a call Task or claiming duplicate detection.
- Record source type, stable meeting or event ID, date, start and end, and attendees with emails.
  The source marker is `policy.salesforce.call_marker` when a Momentum ID exists, else `policy.salesforce.calendar_call_marker` with the Calendar event ID. Never invent or leave an empty marker.

## Extract

From the transcript, with speaker attribution:
- Buyer-stated facts as short quotes, at most `policy.interaction.max_buyer_quotes`: cost, incumbents, decision process, named stakeholders, timeline, requirements.
- Commitments by each side, with any dates spoken.
- Pricing or seat figures, each marked `buyer_confirmed` or `operator_stated`.

## Reconcile

1. Contacts by attendee email, then name: `SELECT Id, Name, Email, Title, AccountId FROM Contact WHERE Email IN (<emails>)`.
   Unmatched external attendees become Contact-create proposals on the Account of the matched attendees' domain. No match at all: ask for the Account.
2. Account and open Opportunities. Several open: ask which one before proposing. None: say so and propose nothing on the Opportunity; creation is the user's call.
3. Opportunity Contact Roles for each matched attendee. Missing roles become proposals.
4. Open Tasks, each marked tied to this call or unrelated:
   ```sql
   SELECT Id, Subject, ActivityDate, Description, WhoId, WhatId, Status FROM Task
   WHERE IsClosed = false AND (WhatId IN ('<OppId>', '<AccountId>') OR WhoId IN (<ContactIds>))
   ```
5. Duplicate check:
   ```sql
   SELECT Id, Subject, ActivityDate, TaskSubtype, Description FROM Task
   WHERE (WhatId IN ('<OppId>', '<AccountId>') OR WhoId IN (<ContactIds>)) AND ActivityDate = <call date>
   ```
   Read Subject and Description for the exact source marker from "Find the interaction". When Momentum is available check its marker;
   when Calendar metadata is also available check that marker too before logging a formerly unrecorded meeting.
   A hit means the call is already logged: report it, skip proposal A, and limit B, C, and F to what that Task and the existing Next line do not already carry.
6. Newest thread: `search_email` on the external attendees' addresses, newest first, following every returned cursor. Newest is bounded by `rules#absence_conclusions`.
   Record its `thread_id` for proposal D; none means D starts a new thread.
7. Call type per `rules#call_type`, then its `policy.call_prep.expected_information` items now answered, partially answered, or still open.
