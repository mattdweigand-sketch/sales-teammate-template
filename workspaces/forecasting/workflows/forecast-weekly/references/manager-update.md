# Friday manager update

## Scope and inputs

Run only the manager-update branch, following `policy.forecast.manager_update`. This procedure does not configure the automation.
Load `forecast.manager_update` and `forecast.amount_field` from `_core/policy.yaml`.
Load `rules#absence_conclusions` and `rules#not_checked_means` from `_core/rules.md`.
Use `_core/thread-locators.md` "Teammate thread lookup" for verified Forecasting and Pipeline thread reads.
If available, use `draft-anti-slop` for advisory Slack voice review. Report unavailable style review.
Never block or skip a draft because of this style review.
Use the manager DM and runtime identities supplied by the automation. Missing or conflicting destinations stay not checked.
Never send Slack or email. No Salesforce writes. Do not run the forecast, tracking or deck-write branch.

## Existing draft

Read the manager DM's current drafts before creating anything.
If a draft already exists in that DM, report it instead of overwriting. Return its draft text and the DM link, then stop.
If draft lookup is unavailable or incomplete, do not create a replacement. Report the not-checked result under the loaded evidence rules.

## Current sources

Record the current week and run time in the schedule's timezone. Read only the following sources.

- Read this week's forecast report in the Forecasting thread, including later turns through the run time.
  Use the latest call in that thread, since Operator may revise the first posted number in later turns.
  For change vs last week, compare to the prior week's forecast report. Missing prior history is not a zero baseline.
- Read Salesforce Opportunities owned by Operator changed this week. Resolve Operator's owner identity from the current Salesforce user.
  Use LastModifiedDate for the changed-this-week window, with complete pagination. Read amounts from `policy.forecast.amount_field`.
  Current Salesforce values alone do not prove an old-to-new change. Describe moves only when the source evidence supports them.
- Read deal-thread status messages in the Pipeline thread for this week. Keep their source links with the working evidence.

Amounts come from current source reports, never a dated automation value.
Calculate change only between the latest reported call and the prior week's reported call. Do not construct a new forecast from Salesforce.
An unread source or incomplete timestamp window stays not checked per the loaded rules. Do not invent a call, comparison, deal move or ask to fill a gap.
Report missing evidence with the result and keep unsupported claims out of the candidate.

## Draft and result

Draft five bullets or fewer covering forecast call and change vs last week, key deal moves, deals at risk, and asks for help.
Keep it terse, fact-led and in Operator's voice, with no colons inside sentences, no em dashes, no semicolons and no emojis.
Recheck that the manager DM has no existing draft immediately before creation. Apply "Existing draft" if that changed or the check fails.
Use `slack_send_message_draft` in that DM only. The draft stays unsent.
Reply with the draft text and the DM link. Claim draft creation only when the native result confirms it, otherwise report the actual error.
