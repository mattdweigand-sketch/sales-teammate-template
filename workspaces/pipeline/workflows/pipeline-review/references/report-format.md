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

Use `routed` only for deal-context findings, with `kind: deal_context`, `deal`, `name`, `thread_url`, a one-line `reason` and `delivery`. One row per Opportunity, never Task findings.
Set `delivery.command` to `mail_send` and `delivery.status` to `delivered` or `failed`, from the actual send result. Retired `session_send` is rejected. A missing delivery record fails rendering.
The routed section lists Account, deal-thread link, reason, and command for delivered rows only. Failed deliveries appear under needs-input with the attempted command.
Count both separately from local flagged deals, recommendations, questions, and withheld entries. Include them in reviewed, never in `deals` or local approval labels.
Keep actual send receipts in the sandbox. The delivery record is not approval. Failed delivery never counts as routed or no-trigger and never suppresses a notification.

## Triage findings

Use read-only `triage` rows for extra Operator-owned Tasks, date mismatches and current-action gaps, even when a deal-context row is routed for the same Opportunity.
Each row has `deal`, `name`, a one-line `reason` and `triage_next_step: true`, native `triage_owned_task` or `triage_task_gap: true`. No `changes` or `delivery`. Findings never carry approval
labels or send requests.
Future Tasks never enter these triage findings. They can remain field-only ownership markers, without a Task proposal or delivery to triage.
Show `Triage owns Task <Id>` or `Triage owns the Task gap`. Gap markers are findings, not proof of complete reads.

## Approval boundary

A flag is a review finding, not automatically a proposed write. A clear recommendation holds only exact, evidence-supported changes.
Put `no action derivable`, unresolved contradictions, unsupported field values, and any change that rests on an unknown in **Needs your input** as a question, outside the approval batch.
A disclaimer never makes unsupported evidence sufficient. Do not invent a history note to make a flagged record approvable.
A deal may have one clear recommendation and a separate question; hold only the uncertain change and keep the supported one numbered.

## Next steps display

`next_step.current` and `next_step_current` show exact existing text as read-only context. `next_step.proposed` is always null. No proposed_full or history payload.
HTML entities and paragraph or break tags decode for display only. Never rewrite Salesforce history to match the display.
Next-step findings use `triage_next_step: true` and `Triage owns the next step`, not a clear recommendation, question option or letter.

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

Units are distinct. Open deals is the all-stage Collect count. Reviewed includes `policy.pipeline.stages` and `policy.pipeline.early_stages` on every weekly or requested run.
Flagged is unique triggered deals.
Not checked is per `rules#not_checked_means`. Clear recommendations are numbered blocks, one deal each. Questions are Q labels. Records written counts verified record writes.

Reviewed = flagged + routed + no trigger + not checked. Each flagged deal has a recommendation, question, withheld entry or triage finding. Mixed findings never double-count a deal.
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

Every weekly or requested run loads these sections and its early-stage qualification inputs. Pilot report input stays Friday-only under `rules#pilot_handoff`.
Rollup: count and Amount by stage and ForecastCategory, this quarter versus later. Delta since the previous Friday from OpportunityFieldHistory: new, stage moves, CloseDate moves, closed.
Record proposals per `workspaces/pipeline/workflows/pipeline-review/references/proposals.md` "Friday", lettered in order, one record each.
Add friday.qualification as the full reviewed early-stage list, empty when none qualify for this scope. Each row carries deal, name, stage, action, and summary.
Actions are closed_lost, triage, or needs_input. A triage row has a matching read-only triage finding.
A closed_lost row has last_buyer_activity, evidence_complete, and upcoming_event, or operator_stated_no with quote and date, or lost_path_size below.
Any row supporting an Amount letter also carries missing_amount true. Amount letters carry buyer_confirmed true after review of buyer evidence.
List unknowns as existing Q-labeled questions, not silent findings. The renderer prints a Qualification section capped at ten rows and the full reviewed count.
Its guard rejects upward early-stage moves and Closed Lost without a supported reviewed basis. The list is evidence review, never approval.
Every StageName letter is checked against its current source stage in report and receipt modes. Closed Won and early-stage upward moves fail with or without a qualification row.
For the lost-path size basis in proposals.md "Every run", lost_path_size carries reason (`buyer_deferral` or `departed_sponsor`), from_stage (`S2` through `S5`), and evidence_complete true.
It also carries buyer_step_within_three_months false, employees (native Account.NumberOfEmployees, integer or null), and description (exact native Opportunity Description, string or null).
Review the trigger under `rules#stage_move` and the prior backward move for an existing S1 before setting these facts. Never infer them from S1 or missing retrieval.
A blank native count can use operator_employee_count with value (integer), quote and ISO date for Operator's dated answer. Keep employees blank rather than claiming his answer is Salesforce data.
A size-floor StageName letter carries the same lost_path_size as its qualification row when present. An unsupported destination or unknown input blocks that proposal.
The helper checks fact shape, the numeric floor and marker shape, not buyer intent, complete retrieval, historical reason or authenticity.
A size-floor exception Description letter carries operator_size_exception with Operator's quote and ISO decision date, mode prepend, the exact current baseline and the exact new dated line.
Only the marker in proposals.md "Every run" is allowed in that Description letter. No overwrite, duplicate marker, other Description change or inferred approval is accepted.

## Notification

The helper's notification mode prints whether to send, the status, and the payload.

- Every authorized scheduled run: always one in-app notification. `ready for approval` when coverage and the run are complete, no question is open, and proposals exist. `complete` when those checks
  pass with no proposals.
  Otherwise `incomplete`, naming the coverage gap, failed step, or needed input.

Send the printed payload unchanged, only in an authorized scheduled run.
