# Call coaching

## Collect calls

Use the requested call or window. For a scheduled run, review external calls since the previous scheduled call-review slot through run start, including intervening weekend days.
Resolve the Account and Opportunity from Salesforce and the completed calls from Calendar. Use attendee addresses as well as Account names per `rules#calendar_search`.
Retrieve each target call's Momentum transcript per `rules#momentum` and `policy.momentum`. Verify the meeting identity before evaluating it.
If a transcript is missing or outside the supported lookback, name the call as not checked. A meeting title never establishes what was said.
Read relevant Gmail threads, Salesforce fields and Contact Roles, and deal-thread context only for the calls selected. Keep conflicting sources visible with their dates.

## Call checks

- Outcome. Did the call end with a dated next step owned by the buyer?
- Discovery. Which MEDDICC elements moved, with timestamps? Which openings were available but not explored?
- Pain depth. Did the rep ask for a before and after number and who else feels the pain?
- Talk balance. Use speaker timing to calculate rep talk share. Flag discovery calls above `policy.coach.rep_talk_share_flag_percent` percent. Without timing, report unknown.
- Objections. List each objection, its handling, and any overstated boundary against the available written position.
- Demo discipline. Did the demo map to the buyer's stated workflow or only show features?
- Multithreading. Did the rep ask to meet the economic buyer or other stakeholders?
- One improvement. Give one specific thing to do differently on the next call, with a suggested question Operator can use.
