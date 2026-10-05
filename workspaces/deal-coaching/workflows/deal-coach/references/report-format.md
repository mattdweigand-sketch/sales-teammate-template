# Coaching reports

## Scope and evidence

Use Operator's requested branch. Otherwise use the matching slot in `policy.coach.schedule`. If the branch or deal is ambiguous, ask before collecting evidence.
Scope live reads to Operator's Opportunities using the owner resolved at run start. Resolve each deal's Account, Contacts, Contact Roles, current stage, next step, and relevant Tasks and Events.
For call-review and pre-meeting, read the selected deals' Gmail threads, Calendar events, Momentum transcripts, and deal threads within the stated window.
Deal-review reads that evidence for selected reviews and Contact Roles, Gmail, and Momentum for every owned open S3 to S5 deal's stakeholder coverage, including unselected deals.
Use `rules#calendar_search` with Account names and attendee addresses. Apply `rules#momentum` and `policy.momentum` to transcripts and prior-call windows.
For deal-review and pre-meeting, use the supported transcript lookback for recent communication and state its dates.
Keep current Salesforce fields and dated deal-thread evidence separately identified.
For criteria-refresh, read Coach-thread lessons and their linked deal evidence since the last refresh. If no prior refresh exists, review from the first Coach-thread report.
For monthly Patterns, also read owned Opportunity call Tasks and Next_Steps__c, Momentum transcripts, and linked evidence for the previous calendar month, within supported source limits.
Every claim cites a call timestamp, email date and thread, Salesforce record and field, or deal-thread link. Anything without evidence is unknown rather than inferred.
Separate unread sources from evidence of absence per `rules#not_checked_means` and `rules#absence_conclusions`. Do not claim a search proves complete history.

## Output rules

Lead with the single most important gap, then use short bullets. Plain language only, with no colons inside sentences, em dashes, or semicolons.
Coaching is for Operator only and lands in the Coach thread. Never post to Slack, email, Salesforce, or buyers.
Salesforce suggestions go to the Pipeline thread as a one-line note for Operator to approve there. Link the evidence and proposed field change without performing it.
Close with the reviewed scope, unknown or not-checked items, and `Nothing written`. Keep report content and lessons out of the repo.

## Call review

For each selected call, give the date and source link, the most important gap, then short bullets covering the call checks with timestamps.
Show MEDDICC changes supported by the call, the dated next step, any risk pattern, talk share or unknown, and one specific improvement for the next call.
Name calls without transcripts as not checked and give no content-based coaching for them.

## Deal review

Review Operator's named deals or select up to `policy.coach.deal_review_count` open Opportunities for the scheduled review.
Rank by `policy.forecast.amount_field` descending with blanks last, then nearest CloseDate, with Opportunity Id as a stable tie break. State the selection and any missing dates.
An Amount without ARR ranks as blank. Never fall back to Amount.
For each deal, lead with its largest gap. Present the score table first, strategy answers second, and one next best move last.

| Element | Score or unknown | Evidence | Stage gate gap |
|---|---|---|---|
| Each MEDDICC element | Evidence-backed level | Source and date or timestamp | Minimum from policy and missing evidence |

Answer every strategy question briefly and name the supported risk patterns. End with the single action this week and the person to involve.

Add one count line to the weekly deal review. `Gaps closed since last deal review <n>. Open gaps on deals closing this quarter <n>.`
A gap is a MEDDICC element scored below its `policy.coach.stage_gate_minimums` value for the deal's current stage. Label it by element, for example EB or PP.
Compare with the previous deal review in the Coach thread. Count distinct recorded gaps by Opportunity Id and gap label, not repeated mentions.
The closed count is unknown when the prior review has no baseline in this format.
Count a gap closed only when dated evidence resolves the previously reported gap. Unknown or unread evidence never proves closure.
For open gaps, apply this definition to all owned open Opportunities with CloseDate in the current quarter, including deals outside the selected review set.
If the baseline or current-quarter coverage is incomplete, mark the affected count unknown with its limit, never zero. Keep detail in Coach. Systems copies only the count line.

After the per-deal reviews, add a Stakeholder coverage section. Give one line for every owned open S3 to S5 Opportunity, including deals outside `policy.coach.deal_review_count`.
Each line names the economic buyer or signer, security or IT reviewer, and legal or procurement contact, each with Contact Roles, Gmail, or Momentum evidence, or marked missing.
Use dated buyer participation in Gmail or Momentum within the supported review window to identify active contacts. Contact Roles alone do not prove a contact is active.
Flag a deal as single-threaded when only one distinct active contact is evidenced, even when that person holds multiple roles. Unread evidence is not checked, not proof of missing roles or inactivity.
Suggest a Contact or Contact Role only when a named person has evidence. Send that suggestion as a one-line note to the Pipeline thread per "Output rules", never a write.

## Pre-meeting

Use the requested meeting, or external meetings between run start and the end of the next business day in the schedule's timezone that are on an open deal at S2 or later or are a demo or on-site.
Give the meeting time and link, the largest evidence gap, relevant MEDDICC gates, and supported risks.
Use the strategy questions to choose the questions most likely to close those gaps. End with the buyer-owned next step to seek and the stakeholder whose participation matters.
Questions are preparation for Operator, never buyer outreach drafts. Mark missing evidence and unconfirmed attendance explicitly.

## Criteria refresh

Show the review window and the main lesson, then a Patterns section for the previous calendar month per `references/learning.md` "Monthly refresh".
Cover objections, blockers, and product gaps seen on two or more distinct deals. Give at most 10 patterns, each with the accounts, one dated piece of evidence per deal, and a suggested owner.
The suggested owner is product, security, deal desk, or enablement. Pattern account names and buyer quotes stay in the Coach thread, never the repo.
Follow with supported numbered edits naming the target reference and heading, exact current and proposed wording, evidence, and expected coaching benefit.
List contradictions and unknowns beside the affected proposal. Ask Operator to approve specific numbers in the Coach thread only when criteria edits are proposed.
A scheduled refresh posts Patterns even when no criteria edit is supported. It posts nothing only when there are neither patterns nor supported edits.
For a typed request with neither patterns nor supported edits, report no patterns or proposed edits and the evidence limits.
Nothing is written to the repo by the coach.
