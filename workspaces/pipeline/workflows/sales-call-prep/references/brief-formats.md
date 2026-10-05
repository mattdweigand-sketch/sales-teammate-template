# Brief formats

Plain text, numbered or bulleted, no tables. Every fact carries a source in parentheses or a link. Anything inferred starts with `Hypothesis:` and is never restated as fact in a later section.
A source that failed is written as `<source> not checked: <error>` per `rules#not_checked_means`.

## Single call

```
# Call brief: <Company> · <External attendee(s)>

**Meeting:** <title>, <day date>, <start to end TZ>, <duration>. (<calendar link>)
**Attendees:** <external names, titles, emails>; <internal names>.
**Call type:** <intro | discovery | demo | proposal | customer> because <one clause of evidence>.

## Bottom line
Two to four sentences. Where the deal stands, what this call must accomplish, the main risk.

## Prior context
- Bullets, newest first, from Salesforce and Gmail. Each ends with its source: (Salesforce Task <date>), (Salesforce Event <date>), (Gmail <date>).
- Include what Operator promised and what the buyer asked for.

## Who is on the call
- <Name>, <title>, <tenure>. One line on their remit. (<source>)
- Repeat per external attendee.

## What the business does
- Three to five bullets. Business lines, scale, current-year strategy signals, AI or data moves, incumbent tools. Each with a dated link.

## Example Product footprint
One line per external email: org name, service type, billing status, billed seats, members, or `Org status unverified for <email>: <response>` (`rules#org_lookup`).

## Where to open
- Two or three bullets. Facts first, then `Hypothesis:` lines.

## Discovery gaps
- One bullet per item in `policy.call_prep.expected_information[type]` not established, written as `<item>: not established`.

## Prior calls
Skip this section if none. Otherwise date, attendees, two to five short buyer quotes, commitments, open questions (Momentum <date>). If the search failed, one line: `Prior call transcripts not checked: <error>`.

## CRM notes
Skip this section if none. One bullet per record problem flagged in `workspaces/pipeline/workflows/sales-call-prep/references/collect.md` "Salesforce" item 5, with the record link.

Say "log this call" after the meeting and I will hand off to interaction-sync.
```

Target length: 300 to 450 words for an intro, up to 600 for a proposal or customer call.

## Multi-call window

```
# <Window> call prep

<N> external calls <on date | from date to date>. Times <TZ>. For a multi-day window, add a `### <Day, date>` heading before each day's calls. One sentence naming the calls that need the most care and why.

## <time> · <Company>
- **Who and business.** <attendee, title>. <One sentence on the business.> (<link>)
- **Prior context.** <what has happened, stage, amount, close date, last touch>. (<Salesforce link>)
- **Opening focus.** <one sentence>.
- **Risk.** <one sentence>.
- **Discovery gaps.** <comma-separated items not established>.
- **CRM notes.** <record problems with links, or omit the line>.

Repeat per call in time order.

Say "log this call" after any of these meetings and I will hand off to interaction-sync.
```

Target length: 90 to 130 words per call. If a call needs the single format, say so and offer it.
