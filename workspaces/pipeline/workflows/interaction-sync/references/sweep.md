# Daily call sweep

## Release gate

Read the deployed `rules#momentum` before enumeration. Its approved sweep exception must permit host or attendee enumeration and reading every window.
If that exception is absent, stop with `Sweep not checked, shared Momentum exception pending approval`. Do not execute an Account-free search under the old rule.
The exception is proposed separately in the held policy PR. This contract grants no new shared-rule authority.
The `momentum` policy block must also supply `sweep` settings with `page_size` and `window_hours`. Missing settings stop enumeration as not checked.

## Find every call

- Use the previous business day in `policy.momentum.display_tz`, skipping weekends. Match `policy.momentum.attendee_email` as host or attendee.
- Load the org call-transcript skill for endpoint, authentication, and response shape. Use authorized runtime credentials, never a stored handle from the repo.
- The page parameter repeats results. Set `pageSize` from `page_size` and window hours from `window_hours` in the sweep settings.
  Recursively split any window returning the page-size cap until each window is below the cap.
  Keep each request within `policy.momentum.window_days`, read every window, and deduplicate by meeting Id. Do not stop at the first match.
  If a capped window cannot be split further or any retrieval fails, that interval is not checked. Never claim all calls are logged from incomplete retrieval.
- Keep completed external calls with at least one attendee outside `policy.tooling.internal_domains`. A scheduled event alone proves no completed call.
- Before using each transcript, verify start date and attendee emails against the Calendar event per `rules#calendar_search`.
  Reject contradictory transcript date cues, including scheduling the supposed call date as a future meeting.
  List a mismatch or unreadable identity evidence as `identity unverified` with the reason. Propose no Task edits from that transcript.

## Check and route

1. Query all of Operator's Salesforce Tasks created since the call date, with Description and the relevant record links.
   Description cannot be filtered in SOQL. Check locally that its first line exactly matches `policy.salesforce.call_marker` with this meeting Id.
   A match means logged. A failed or incomplete Task read means not checked, never unlogged.
2. For a verified unlogged call, resolve its Account and Opportunity. Ambiguity needs input rather than guessed Task linkage.
   Read transcript next steps and open Tasks on that Opportunity. Draft completion, buyer-stated date move, or new follow-up proposals only.
3. Find the current project's deal thread by Account name with `pplx project sessions list --search`.
   If one is verified, send it with `pplx session send` the meeting marker, title, date, and Task proposals.
   On confirmed failure with no delivery, retry once with `pplx tm mail send <deal-thread session id>`. Record which command delivered. Never claim delivery without a successful send.
  An ambiguous send needs native reconciliation or stays needs-input. Never blindly retry a missing or delayed response.
  Keep the verified destination session ID, link and successful native delivery receipt in the run evidence. Report the exact blocker when delivery is unresolved.
   Failed or ambiguous routing stays needs-input.
   Request the interaction-sync skill for this meeting and its lettered proposals there. Explicitly say no writes until Operator approves.
   Otherwise use `pplx automation notify-source --message` with the same evidence for Pipeline. If routing is unavailable, report it, never claim delivery.
4. Reply with one line per unlogged or identity-unverified call, naming Account, title, time, and destination or blocker.
   If complete reads show every call logged or no calls, reply in one line and run `pplx automation suppress-run-notification`.
   No Salesforce or Gmail writes, no automatic logging, and no approval transferred from the sweep.
