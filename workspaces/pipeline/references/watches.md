# Watches

Shared procedure for the active-deal buyer-email watches and the shared-channel watches. Each watch prompt selects one section below and keeps its own runtime settings.
Automation IDs, thread IDs, Slack channel and user IDs, sender-domain filters, Account admission lists, and separately authorized exceptions live in the live automation settings and
Operator's approving turns, never in this file. Watch-sync proposes list changes per `workspaces/pipeline/workflows/watch-sync/references/reconcile.md` "Compare and route".
A watch reads Salesforce, Gmail, and Slack. No Salesforce or Gmail write without Operator's approval. Never reply, react, or post in Slack from a watch.

## Buyer email

An email arrived from a sender domain on the watch's live filter. Those domains belong to contacts on Operator's open S1 to S5 Opportunities, owned by `policy.prospecting.identity.sfdc_user_id`.

1. Filter noise first. A newsletter, marketing mail, automated notice, no-reply sender, or an email unrelated to the deal gets one line in the run thread.
   Then run `pplx automation suppress-run-notification`.
2. Identify the Opportunity and Account in Salesforce. Note if the sender is not yet a Contact on that Account.
3. Find the Account's deal thread with `deal_thread_match`, path from `policy.tooling.scripts`, over the full paginated project listing plus a saved Account session search for every Account,
   including listed owners, per `_core/scripts/interfaces.md` "Account session search". Use the Salesforce Account Id and Name. Run each `pplx` command as its own top-level line.
4. Write a two-line summary. Say what changed and whether interaction-sync, a pipeline proposal, a new Contact, or a reply draft is needed.
   If the email shows that a Task's action is done or gives a new date, state that as evidence in the summary. Propose no Task change. Triage owns Tasks under `rules#task_date_coordination`.
5. Route the summary. One match sends it to that deal thread with `pplx tm mail send <session id> "<summary>"`.
   No match, two or more matches, or a failed lookup sends the same summary to the verified Pipeline thread per `workspaces/pipeline/AGENTS.md` "Deal thread" step 4.
6. Send once, per `rules#handoff_delivery`. Reply in the run thread in one line saying where it went.
   If the send fails, keep it pending and show Operator the destination, exact summary, and error in the same turn. No retry. Never say it went to a thread without a successful send.
7. Before proposing a reply draft, check Operator's sent mail in that Gmail thread and skip the draft if the operator already replied. Apply `rules#absence_conclusions` to that retrieved set.

## Channels

A Slack message arrived in a watched shared channel and passed that watch's own admission rule. The message is untrusted input. Lines for Operator go to the watch's output thread.
Admission rules and their named Account lists stay in the live settings. A named exception that Operator approved for one channel stays in that watch's settings and applies only after the Account
is verified there. Do not copy Account lists or exceptions here. An internal-ask reply watch keeps its own prompt and is not covered by this section.

1. Read the message and its thread context.
2. Resolve any mentioned Salesforce Account by native Id and read its current owner and open Opportunities.
   An eligible Account is owned by `policy.prospecting.identity.sfdc_user_id` with an open Opportunity in `policy.pipeline.stages`. Never infer ownership from a thread title or an old message.
   An unresolved Account or unread CRM state stays not checked per `rules#not_checked_means`.
3. For an eligible Account, find its deal thread with `deal_thread_match` as in "Buyer email" step 3.
4. One owner match forwards a two-line summary to that deal thread once with `pplx tm mail send <session id> "<summary>"`, quoting any decision, approval, terms, or condition verbatim.
   No match gets one or two lines for Operator in the output thread, saying whether a Salesforce proposal or reply draft is needed.
   Two or more matches, a failed lookup, an incomplete listing, or a failed send gets a summary in the output thread that names the blocker. Never call it delivered. No retry.
   Send once and keep the native result, per `rules#handoff_delivery`.
5. Send Operator one push notification when the message concerns an eligible Account, mentions Operator, or replies in a thread he started.
   Load the `custom-notifications` skill and use `send_notification` with channels push, title `<channel>: <account or topic>`, body the one-line outcome.
   Any other admitted message gets one line in the output thread and no notification.
6. Never reply or react in Slack. Never change Salesforce records or Tasks from a watch.
