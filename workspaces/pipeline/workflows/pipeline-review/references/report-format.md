# Report format

`policy.tooling.scripts.pipeline_render` owns the exact presentation of the report, each question, write receipts, the close, and the notification,
including headings, counts wording, empty-section text, and the approval line.
This file owns what goes into the run file the helper reads. Never hand-write or edit rendered text; correct the run file and render again.
Post the rendered report once in the final chat answer for manual and scheduled runs. Arguments are in the helper's `--help`; its promise is in `_core/scripts/interfaces.md` "Interfaces".

## Run file

One reviewed run file per run, in the sandbox, never in Project Files. Its keys are in the helper's docstring.
It holds the run identity, counts, flagged deals, clear recommendations, questions, Friday additions, each label's status, and each write outcome.
It is the run's label record, not approval; approval is Operator's reply in the thread per `rules#approval`. If it is lost, rebuild it from the thread before continuing.

## Routed to deal threads

Use `routed` for records owned by active deal threads, one row per Opportunity with `deal`, `name`, `thread_url`, and a one-line `reason`.
The section lists Account, deal-thread link, and reason. Count routed records separately from local flagged deals, recommendations, questions, and withheld entries.
Include routed records in reviewed, never in `deals` or local approval labels. A failed delivery is needs-input, recorded in run gaps, never claimed as delivered.
Keep the transport and successful-send receipt in the sandbox. The list records ownership and destination, not approval or proof of delivery.

## Top 3 actions today

On the weekday branch, add `today_actions` to the existing run file, empty when there are no supported candidates. Friday output stays unchanged.
Use only reviewed deals in `policy.pipeline.stages` and evidence already collected from Salesforce, Gmail, Calendar, and Slack. Do not add searches, writes, or state files for this section.
Candidate evidence must still match the kind's sources below. Slack does not turn a message into a Gmail `buyer_reply` candidate.
Include deals with a relevant meeting or due action even when they have no hygiene trigger. Keep flagged-deal counts and proposal labels unchanged.
Each candidate has `deal` as its Opportunity ID, `name`, `kind`, `date` in YYYY-MM-DD, a one-line `reason`, and `evidence` using the existing Evidence schema below.
Copy its Salesforce size under the exact field named by `policy.forecast.amount_field`. Null, empty, or absent ranks as blank. Zero is set. Never fall back to Amount when ARR is blank.

- `buyer_reply` uses Gmail evidence of a buyer request needing Operator and the message date. Set `reply_reviewed` true only after reviewing the already retrieved thread in both directions.
  Say that a reply is needed in the retrieved thread. A missing reply in a partial search is not proof of no reply anywhere. Do not rank an outbound message or an answered request.
- `meeting` uses a Salesforce Event or Calendar event scheduled today or tomorrow in the run timezone. Use its start date and explain what Operator needs to prepare or attend.
- `due` uses an open Salesforce Task or the current next step due today or overdue. Use the action deadline, never the note entry date or a proposed replacement date.
- `date_at_risk` uses the existing hygiene finding and Salesforce CloseDate. Explain the date risk without inventing buyer intent.

The renderer ranks those kinds in the order above, then earlier dates, `policy.forecast.amount_field` descending with blanks last, deal names, IDs, and reasons.
It keeps the highest-ranked reason per deal and shows at most three deals.
Top 3 may name a routed deal, marked "in deal thread", without a local proposal.
It excludes withheld deals and deals affected by coverage gaps. An incomplete process or a coverage gap with unknown scope leaves the section empty.
Gmail and Calendar IDs resolve against the saved results and their dates must match the candidate date. Salesforce dates and action meaning require review against the saved records.
Write one short reason per deal with no semicolons, em dashes, or colons. The section uses Priority labels for reading order. Only the proposal labels below it can approve writes.

## Approval boundary

A flag is a review finding, not automatically a proposed write. A clear recommendation holds only exact, evidence-supported changes.
Put `no action derivable`, unresolved contradictions, unsupported field values, and any change that rests on an unknown in **Needs your input** as a question, outside the approval batch.
A disclaimer never makes unsupported evidence sufficient. Do not invent a history note to make a flagged record approvable.
A deal may have one clear recommendation and a separate question; hold only the uncertain change and keep the supported one numbered.

## Next steps display

Every deal block shows three sections: Current next steps, Recommended next steps, and Evidence.
For a next-step-only change, set the exact current first entry and the exact proposed next-step sentence, not the unchanged history twice.
The write payload still retains all history per `rules#next_steps_format`. When proposing a history change, or when Operator asks for the full field, set the complete current and proposed fields
instead.
Preserve wording, punctuation, dates, and line order. Never replace exact text with an action summary or Unchanged. An empty current field renders as Empty.

Include any proposed new history entry within the proposed field, not a separate History section. The proposed sentence is the actual Salesforce write per `policy.pipeline.note_next_line`.
Distinguish the action's due date from the entry's written date and CloseDate. Follow `rules#next_steps_review` when the checker cannot resolve a date or owner.
When a fresh Salesforce read supersedes an earlier draft, mark the old label superseded and cite the evidence for the new one.

Current field text is shown with HTML entities decoded and paragraph and break tags as new lines, for reading only.
Existing Salesforce history is never rewritten to match, and approved write text stays exact.

## Evidence

Calendar start and end times prove scheduling, not attendance or outcomes. Never describe an upcoming or ongoing event as held.
If the only evidence is a calendar entry, say `scheduled` or `elapsed, attendance unverified`; event-only `new_activity` is a display finding and never a write basis.
Completion evidence is a completed call Task, a transcript, the user's confirmation, or a sent message that did what the Task asked.
For a Task that waits on the buyer, a received message that delivers what it waited for is also completion evidence.
A Task subject supports its title, direction, activity date, and contact only, not a summary of the email body.

Each evidence item names its source, sender or contact when known, and the supported fact.
Gmail and Calendar items carry `source_id`, the returned email_id or event_id. Gmail items also carry `quote`, copied verbatim from the saved body.
The quote must support the fact. Read the full body before quoting, never the snippet.
The helper resolves each ID against the saved results and fills the date, subject or title, and link from that record.
It rejects an unknown ID, a missing or unmatched quote, and any hand-written date, title, or link on these items.
Other items name their date and record title. Never construct or invent a link.
Slack items use source `Slack` with `date`, `who`, `title`, `link`, and `fact` copied or supported by the saved message. The link is its returned permalink and the date is its message date.
Use the freshest dated evidence across Salesforce, Gmail, Calendar, and Slack for each supported fact. Older legal-status wording never overrides a newer buyer status.
A retrieved-set statement such as no reply retrieved is not proof that none exists (`rules#absence_conclusions`).
The helper prints the retrieved-set limitation once in each section that shows Gmail, Calendar, or Slack evidence.

Use the checker's Account-and-Opportunity activity scope for last touch. Show the source record for each trigger and proposed factual addition.
On Friday, an accepted pilot report (`rules#pilot_handoff`) is cited as evidence with source `Pilot report`, its source reference, its window from start to `data_through`, and its stated limits.
If sources disagree with the checker, withhold the affected proposal and identify the discrepancy.

## Counts

Units are distinct. Open deals is the all-stage Collect count. Reviewed includes `policy.pipeline.stages`, plus `policy.pipeline.early_stages` on Friday. Flagged is unique triggered deals.
Not checked is per `rules#not_checked_means`. Clear recommendations are numbered blocks, one deal each. Questions are Q labels. Records written counts verified record writes.

Identities the helper checks: reviewed = flagged + routed + no trigger + not checked, and every flagged deal has a clear recommendation, a question, or a withheld entry.
A deal may have both, so clear recommendations plus questions can exceed flagged. At Close, open equals the Collect count.

## Coverage

Save the `coverage_check --json` output for this run and scope, and pass that same file to the report and the notification.
After evidence changes or a gap is repaired, rerun coverage, save it, and render again.
When coverage or the run is incomplete, or a deal is withheld, the helper prints one status line under the counts naming the withheld deals.
The checker's summary lines, each once, a count of per-file diagnostics, withheld reasons, and run gaps go in a closing Coverage section.
Withhold every flagged deal in the checker's `affected` list, or every flagged deal when it is null, with its reason. The helper enforces this.
Keep the full checker receipts, including per-file lines, in the sandbox.
Slack is an added evidence source, not a required coverage gate. Missing Slack users or evidence are Slack not checked for that contact per `rules#not_checked_means`.
Use the optional `run.slack_coverage_notes` list, one entry per deal with `deal`, `name`, `contacts`, and `reason`. `contacts` groups that deal's affected contact names in one list.
The helper prints one compact Slack not checked line per deal in Coverage. These notes do not affect status, counts, withholding, or notification.
Never change the saved checker output to add Slack notes. Missing identities or empty Slack results never set `run.process_status` to `incomplete` or withhold a proposal by themselves.
For a Slack limit, withhold only a buyer-status or commitment change when a search errored or was incomplete for a contact on that deal with a verified Slack user.
Put that change in Needs your input with the limitation in its context and no write option until the search is repaired. Preserve unrelated changes on the same deal and other deals.
Split mixed proposals before assigning labels. Do not add the deal to `withheld` for Slack alone, since that field withholds every change on the deal.
Positive Slack facts remain usable and win when fresher. Missing Slack evidence does not invalidate supported Salesforce, Gmail, or Calendar facts.
The Salesforce, Gmail, and Calendar checker does not verify Slack coverage. Its existing affected-deal withholding and incomplete-run behavior stay unchanged.
Preserve `rules#absence_conclusions` for empty or partial retrieved sets. Slack limits alone do not make the run incomplete or change the deal-level not-checked count.
A clean render never makes an incomplete run ready.

## Friday additions

Rollup: count and Amount by stage and ForecastCategory, this quarter versus later. Delta since the previous Friday from OpportunityFieldHistory: new, stage moves, CloseDate moves, closed.
Record proposals per `workspaces/pipeline/workflows/pipeline-review/references/proposals.md` "Friday", lettered in order, one record each.
Add friday.qualification as the full reviewed early-stage list, empty when none qualify for this scope. Each row carries deal, name, stage, action, and summary.
Actions are closed_lost, next_step, or needs_input. A next_step row has next_step_date. A closed_lost row has last_buyer_activity, evidence_complete, and upcoming_event.
Any row supporting an Amount letter also carries missing_amount true. Amount letters carry buyer_confirmed true after review of buyer evidence.
List unknowns as existing Q-labeled questions, not silent findings. The renderer prints a Qualification section capped at ten rows and the full reviewed count.
Its guard rejects upward early-stage moves and Closed Lost without reviewed silence. The list is evidence review, never approval.

## Notification

The helper's notification mode prints whether to send, the status, and the payload.

- Weekday: silent when there are no clear recommendations, no questions, and coverage and the run are complete.
  Otherwise one in-app line with the counts and the run link, led by the status line when coverage or the run is incomplete.
- Friday: always one in-app notification. `ready for approval` when coverage and the run are complete, no question is open, and proposals exist. `complete` when those checks pass with no proposals.
  Otherwise `incomplete`, naming the coverage gap, failed step, or needed input.

Send the printed payload unchanged, only in an authorized scheduled run.
