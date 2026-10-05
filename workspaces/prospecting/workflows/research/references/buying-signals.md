# Buying signals

## Account and engagement

Account. Query Account by name and Website domain. Resolve one Id with OwnerId and Website, then query all open Opportunities under
`policy.prospecting.salesforce.open_opportunity`. Use `policy.tooling.scripts.prospect_account_route` for the current route.
Only an existing Account owned by `policy.prospecting.identity.sfdc_user_id` with route scan continues to public research.
Any open Opportunity routes active_deal to Pipeline. Every other owner routes owned_elsewhere. A completed no-match is outside_named_accounts. Never claim or transfer an Account.
Many matches or incomplete identity stop before source searches or fetches. Ask which Operator-owned Account Id to research. No unresolved-account research or Outreach recommendation.

Warm engagement. Query Tasks on the Account created inside `policy.prospecting.outreach.activity_lookback_days`. Drop Tasks owned by any id in
`policy.prospecting.scan.warm_engagement.ignored_owner_ids`. List distinct Owner.Name values other than Operator. These are other reps working the account. If any remaining Task has a Subject
starting case-insensitively with a value in `policy.prospecting.scan.warm_engagement.task_subject_markers` and an Owner meeting `policy.prospecting.scan.warm_engagement.task_owner`, stop and
report `warm_engaged`
with the matching Subjects, owners, and dates. Another rep has a live thread and cold outreach would collide with it.

## Aliases

`account_aliases` is every account-owned name a quote may be attributed to (brands, subsidiaries, named executives). Take them from the Account website or the first search results. List them in
the report. The user confirms they belong to the account before a bundle goes to outreach.

## Search

Search every discovery category in `workspaces/prospecting/references/signals.md` with the account name. Include public executive LinkedIn posts, careers, company announcements, and earnings
materials. Use the Where to look and Evidence to capture columns. Report inaccessible sources honestly. A snippet does not establish evidence. Keep the executed queries available for audit. The
routine report needs only coverage and material gaps. Retain useful discovery findings, including single substantive jobs and early executive commitments. Automated qualification still requires
the definition and freshness window in the document's Qualification section and frontmatter. Pick at most `policy.prospecting.scan.max_signals_per_account` candidate sources. Prefer the account's
own words, a named executive statement, a company action, or a mandate. Prefer evidence of the account using AI internally over evidence of the account selling AI.

## Qualification

Classify each finding (`active_initiative`, `early_indication`, `general_mention`) and its relevance (`employee_use`, `customer_product`, `unclear`) using the document. These describe each
finding, not the whole signal category. Select a qualification identifier only when its definition is met. Otherwise use `discovery_only`. A single substantive job is not a hiring cluster. Early,
general, API, or unclear findings stay in the report, not the employee-outreach bundle. Write one receipt per source with both classification and relevance (shape in the gate docstring) and run
`policy.tooling.scripts.prospect_evidence_gate --receipt <r.json> --page <page.txt>`. `evidence_subject` is the person or organization whose action the quote directly evidences.
`quote_speaker`
is `account` when the account or a named alias said or wrote the quote, `third_party` when a vendor or reporter paraphrased them. Set `published_date` to null only for a live first-party page
with no trustworthy date, and then set `event_date` to a date the page itself names for the event in the quote. A LinkedIn post URL dates itself. Leave `published_date` null and the gate reads
the date from the post id without `event_date`. A given date that disagrees with the id is unusable. An evergreen page with no dated event does not qualify. Never invent a date. The gate checks
the id, the date, and the speaker. Fit between quote and signal_type is your call.

## Verdict

Save each gate output to a file and run `policy.tooling.scripts.prospect_scan_verdict --route <current route> <outputs in report order>`.
Copy its `verdict` and `next` lines
verbatim. Qualification describes the source. Only route scan can recommend a conditional Outreach handoff. A named-account scan needs one qualified signal. A fit
objection goes on the item as `Rejected on fit,
<reason>`, never into the verdict.

## Report context

Report using the Report section of the stage reference. When the user named a person, state how directly each signal ties to that person and keep the search account-wide. When a page names the
quoted person's title, use the ICP persona tables to describe the evidenced responsibility, or report unresolved. No title matcher or fixed persona ID is required.

## Report

Keep the report concise, with source links, the decision, and material limitations. Detailed queries and rejected search results are optional audit detail.

```
**<Account> scan**

- Salesforce <Id or none>, owned by <name>, <active/inactive>. <No open Opportunity | Open Opportunity, stop>. <No other rep active inside the lookback | Other reps active inside the lookback. <names>>. Route is <scan / active_deal / warm_engaged / owned_elsewhere>.
- Warm engagement. <Subject, owner, date | omit the bullet when none>
- Aliases used. <list with roles>. Confirm before outreach.
- Ties to <person>. <direct / indirect / none>   (only when the user named a person)
- Quoted person. <name, title, responsibility <supported description | unresolved> | omit the bullet when no page names one>

<N> sources checked. <None usable | One qualified | ...>.

1. <Short headline, date; initiative stage, classification, relevance>. <One or two sentences of what happened and why it matters.> <Verbatim quote in double quotes when the source qualifies or nearly qualifies.> <Outcome and reason. Qualified | Rejected on fit, <reason> | Stale, <age> days against a <limit> day window | Undated, no dated event on the page | Discovery only, <reason; API next step if relevant> | Third-party paraphrase | Rejected, <reason>>. [<Source name>](<url>)
2. ...

Verdict. <prospect_scan_verdict.py verdict, verbatim> <One sentence on the next dated trigger, when one is known.>

Next. <prospect_scan_verdict.py next, verbatim | rescan after <event> when nothing qualified>.
```

Attach the gate bundle as a separate fenced json block for every qualified signal, not only the recommended signal, even when its item carries a fit objection.
Label each bundle with its report signal number. Operator chooses the signal and decides on any fit objection with its bundle in hand.
Add the Salesforce Account Id beside each bundle when the account resolved to one. Outreach will not draft without it.

## Batch mode

For a named-account list in one request. Same steps, rules, and gate as above, grouped so each read runs once per list. Read-only.

1. Select Buying signals and read its applicable contract Inputs once. Do not load Adoption inputs.
2. Salesforce in three reads for the whole list. Accounts by every name and every Website domain, Opportunities with AccountId in the matched ids where
`policy.prospecting.salesforce.open_opportunity` holds, and Tasks with AccountId in the matched ids inside `policy.prospecting.outreach.activity_lookback_days`. Split the rows by account and
apply "Account and engagement" to each. Only route scan continues. All other routes and unresolved identities stop before public research, with the appropriate owner or Pipeline handoff.
3. Declare aliases per account per "Aliases".
4. Send every continuing account's "Search" queries together, at most ten per `web_by_query` call, each hit tagged with its account.
Pick per account under `policy.prospecting.scan.max_signals_per_account`, then fetch all picks in one `content.fetch` batch.
5. Apply "Qualification" per source and "Verdict" per account. One receipt and one `prospect_evidence_gate.py` run per source, one `prospect_scan_verdict.py` run per account with its current route and
only its own outputs. Never pool
outputs across accounts.
6. Report one table, then the single-account Report block only for accounts with a gate-qualified item, fit-rejected included, each with its gate bundle. Every other account gets its table row
only.

```
**Signal scan, <N> accounts**

| Account | Salesforce | Route | Result |
|---|---|---|---|
| <Account> | <Id, owner / none / <n> matches>. <Other reps active, <names>, when any> | <route> | <Qualified, <tier> <type> / Gate qualified. Rejected on fit, <reason> / Nothing qualified. <reason> / Stopped, <route>> |
```

## Boundaries

- Drafting, wording, or sending any message. That is `signal-outreach`.
- Reading Gmail, Slack, Snowflake, or Example Product adoption data. Adoption is `signal-user-scan`.
- Any write to Salesforce, Gmail, or project files.
- Treating "no usable signal" as proof the account is not moving.
- Applying a rule not named in this stage contract, `policy.yaml`, or the taxonomy. Any rule cited in the report names its file.

## Sales authority

Use rules#approval and rules#write_protocol for each exact proposal, approval and native readback. Never treat a live policy mirror as independent approval.
An open Opportunity belongs to Pipeline. Re-read current owner, open Opportunities and duplicates before proposals and again before every approved write.
Never retry a failed or mismatched create blindly. Report the actual partial result and one corrective proposal for approval.
