# Next steps

Read at proposal preparation, including one-deal mode. Core ownership and write limits stay in `rules#task_date_coordination` and `rules#followup_task`.

## Draft

Next-step entries follow `rules#next_steps` and `rules#next_steps_format`. Apply `rules#next_steps_review` before date-based proposals.
Build each next-step proposal from the newest message in either direction plus the next scheduled Event, never from Task dates alone.
When Operator's last message is unanswered in the retrieved thread, propose the wait and a re-follow-up date only when that exact sent message fulfilled the stored action.
Quote and link the action evidence. Otherwise retain the stored action and show its blocker, never infer completion from an unrelated outbound.
When the buyer's last message names a date, meeting, or ask, the proposal carries it.
Every clause traces to Salesforce, Gmail, Calendar, or Slack evidence. No inferred buyer intent. Preserve `rules#absence_conclusions` for retrieved-set limits.
Only the deal's current-action Task pairs with Next_Steps__c. Contact-only, meeting-prep and retained later milestone Tasks never pair or change the next step.
Show the exact new first entry and matching current-action Task in one row.
Triage may add one `policy.pipeline.note_history_line` when new inbound buyer evidence arrived after the newest note. Display that supported history note in the same row.

## Findings

Use the saved native `hygiene_check` results and shared `workspaces/pipeline/references/triggers.md` definitions, with reviewed Gmail and Calendar additions.
Review `next_passed`, missing or REVIEW next steps, `stale`, `task_gap` and buyer-email `new_activity` once per deal, merging with its current-action Task row.
Friday adds early-stage next-step review per `references/collect.md` "Friday early stages". Automatic task_gap creates stay in `policy.pipeline.stages`, not early stages.
Required-field and CloseDate checks remain weekly on Friday by Operator's decision, not daily triage findings. Keep other Opportunity fields outside this workflow's writes.
A mechanical flag is not proof the action happened or the buyer is silent.
For a held meeting dated after the newest next-step entry with no verified call Task or source marker, show `Call needs logging` and route to interaction-sync.
Propose no next step for that deal until logging is verified.
An older unlogged held call is a separate `Call needs logging` finding, not a blocker.
Scheduling or elapsed Events alone cannot establish a held call. Missing evidence becomes a blocker, not an invented action.

## One deal

For `next step <Account> <action> by <date>`, typed in any project thread, resolve the Account and exactly one open Opportunity in `policy.pipeline.stages` or `policy.pipeline.early_stages`.
With none or several, ask which Opportunity and propose nothing. With no date, ask once and propose nothing. Read the typed source turn and its native link.
Fresh-read `Next_Steps__c` and all related open Tasks on the selected Opportunity and Account. Use shared deal-activity reads and the normal duplicate and ownership gates.
Prepare one row with the new entry, matching new Task, and old current-action Task completion only when the new action replaces it. Keep action equivalence explicit.
Manual forms are new action plus date, same action with a new date, or done plus the next action and date. All three propose the exact next-step and current-action Task pair.
Never touch non-current Tasks or retained milestones. Name an existing exact-action Task instead of creating a duplicate. A done row names its replacement action and date.
Source permission comes only from `rules#task_date_coordination`, recording Operator's typed command, never buyer evidence.
For date moves, run existing `task_reschedule_check` proposal and prewrite phases on unchanged native snapshots and the displayed payload. It checks mechanics, not source intent.
Keep writer=triage and use manual_one_deal per the helper interface for the selected current-action Task, including a future date. Save its command provenance baseline unchanged for prewrite.
Scheduled triage never sets that option. All native identity, completeness, duplicate, stale-payload, approval and readback gates stay in force.
One row approval covers only displayed changes. Apply `references/writes.md` and read every write back. No typed command is itself write approval.
