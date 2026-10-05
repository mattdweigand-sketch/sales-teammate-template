# Pilot usage report

Plain text. One block for the named pilot. Record links use `policy.salesforce.record_url`.

```
# Pilot usage · <M/D/YY>

## <Account> · <stage> · $<amount> · trial ends <M/D> (<d> days) · <link>
Roster seats <n> as of <data_through> · active in last <window_days> days <active> (<pct>%) · active in last 7 days <l7> (<pct>%)
Weekly active (week starting): <M/D> <n> · <M/D> <n> · ...   (first and last week marked `partial, <d> days` when shorter than 7; omit when query 1b returns fewer than two rows)
Top users: <email> <n> · <email> <n> · ... (up to `policy.pilot_usage.top_users`)
Idle seats (<n>): <email>, <email>, ...      (or `none`)
Feature mix by query mode: Computer <pct>% · Search <pct>% · Chat <pct>% · Other <pct>%. Models: <model> <n>, <model> <n>.   (query 2 mode share; the query 1 daily Computer share counts differently and may differ, print it only in the query-2 fallback)
Use cases (<sample size> most recent queries, <d> day(s), <u> of <active> active users; up to `policy.pilot_usage.use_case_themes_max` themes):
1. <theme> (<n>). "<example>"
2. ...
Operator's next step (Next_Steps__c first entry): <entry with its date>
Handoff (`rules#pilot_handoff`): source <this run thread> · org <org id> · window <start>–<data_through> (<window_days> days) · limits: warehouse counts for this org and window only; <any section not available>

<Account> reported · report. Nothing written.
```

Rules. No `Trial_Expiration_Date__c` prints `trial end not set`.
Zero query-1 rows prints `No roster rows returned as of <data_through>; current provisioning unverified` and omits the other lines through Use cases.
Percentages rounded to whole numbers, each with its window named. Emails as stored. `L7` and `active in last 7 days` mean `l7_query_count > 0` on data_through.
For weekly trend, count only days inside the resolved report window. A mid-week start makes the first week partial, just as a mid-week end makes the last week partial.
An erroring or timed-out query prints `<section>: not available, <Snowflake message>` in place of that section only.
Exception: when query 2 fails, Feature mix prints the Computer share from query 1 marked `(from activity table)` and omits Models.
