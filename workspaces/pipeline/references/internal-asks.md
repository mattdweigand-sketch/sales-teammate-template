# Internal ask nudges

## Scope and inputs

Run this procedure for the Internal ask poll in Pipeline, including a scheduled poll-mode run.
Cadence comes from `policy.pipeline.schedule.ask_nudges`. This procedure does not configure the automation.
Read that schedule and `policy.pipeline.internal_ask_nudge_business_days` from `_core/policy.yaml`.
Load `rules#handoff_delivery`, `rules#absence_conclusions` and `rules#not_checked_means` from `_core/rules.md`.
Use `_core/thread-locators.md` "Teammate thread lookup" for thread verification and history reads.
If available, use `draft-anti-slop` for advisory Slack voice review. Report unavailable style review.
Never block or skip a draft because of this style review.
Runtime destinations and colleague identities come from the task and automation, never from this file.
Never send Slack or email. No Salesforce writes. These are open Teammate tasks, not Salesforce Tasks.

## Poll and answers

1. Run `pplx tm tasks list` and select open tasks with label `internal-ask`. Read each task's sent time, named Slack location and related deal context.
2. Read the Slack DM or thread named by the task through the run time, including the colleague's reply after the named ask.
   Apply `rules#absence_conclusions` and `rules#not_checked_means` to unread or incomplete history. Do not infer silence from a failed read.
3. If the colleague replied, prepare a two-line summary of the reply for the related deal thread when one exists.
   Resolve and verify the destination per the thread lookup reference, then use `pplx tm mail send <deal-thread session id> "<summary>"` under `rules#handoff_delivery`.
   Use the verified related deal thread when one exists, otherwise summarize for Operator in the run thread.
   An unreadable or conflicting destination is not checked, not absent.
   After the local summary or successful handoff, mark the Teammate task done. A failed handoff leaves the task open and follows `rules#handoff_delivery`.

## Waiting and nudges

For a verified no-reply task, compare the run time with the sent time recorded in the task.
Use business days in the schedule's timezone and the interval from `policy.pipeline.internal_ask_nudge_business_days`.
Missing or ambiguous sent time is not checked and cannot qualify a nudge.
Inside the interval, leave the task open as waiting. After the interval, create an unsent nudge in that same DM or thread using `slack_send_message_draft`.
Before creating a nudge, retrieve existing drafts in the task's named DM or thread. If lookup is unavailable or incomplete, report not checked and create nothing.
Reuse or report a same-purpose unsent draft. Never create a second or overwrite it.
Write one or two sentences in Operator's voice, continuing the named ask, with no colons inside sentences, no em dashes and no semicolons.
Keep nudged tasks open. A draft is not a sent nudge or an answer.

## Run result

Reply with one line per task showing answered, nudge drafted, or waiting, with the native outcome.
Use not checked for missing evidence or an unsuccessful action, never a success label.
If every task is verified inside its nudge window, reply in one line and run `pplx automation suppress-run-notification`.
Never suppress a failed handoff or a not-checked task. An empty verified queue can be reported in one line without inventing an answered task.
