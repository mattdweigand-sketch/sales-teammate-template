---
cadence: [daily, one-off]
reads: _core/policy.yaml (salesforce, tooling, call_prep, momentum), _core/rules.md, references/, Calendar, Salesforce, Gmail, Momentum, org lookup, web
writes: nothing
next: interaction-sync after the call
---

# Sales Call Prep

Brief Operator before one named external call or every external call in a window. Read-only per `rules#read_only_skills`. Salesforce is the record; everything else is evidence.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `salesforce`, `tooling`, `call_prep`, `momentum` blocks | Windows, limits, call types, and the helper registry |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#read_only_skills`, `rules#not_checked_means`, `rules#absence_conclusions` | Run start, no writes, and evidence limits |
| Core rules | `_core/rules.md` | `rules#calendar_search`, `rules#momentum`, `rules#org_lookup`, `rules#call_type` | How each source is read and typed |
| Reference | `references/collect.md` | The section named in each of steps 2 to 7 | Queries and searches per source |
| Reference | `references/brief-formats.md` | Full file at step 9, using "Single call" or "Multi-call window" | Brief layout and sourcing |
| Reference | `references/daily.md` | Full file, scheduled daily run only | Today's window, runtime credential recovery, and full-summary audio |
| Per-run evidence | Calendar, Salesforce, Gmail, Momentum, org lookup, and web results saved in the sandbox | The calls in this request | Facts for the brief |

## Process

1. Start per `rules#run_start`.
   Scheduled daily runs use `references/daily.md` for today's local multi-call window and delivery. One-off briefs retain their requested scope.
2. Resolve the calls per `references/collect.md` "Resolve the calls".
3. Read Salesforce per `references/collect.md` "Salesforce".
4. Read Gmail per `references/collect.md` "Gmail".
5. Search prior calls per `references/collect.md` "Prior calls".
6. Check the Example Product footprint per `references/collect.md` "Example Product footprint".
7. Research the company and attendees per `references/collect.md` "Public research".
8. Set call type and discovery gaps per `rules#call_type`.
9. Write the brief per `references/brief-formats.md`, single-call or multi-call. Return the brief itself, not a source list with commentary.
   Daily runs then deliver full-summary audio per `references/daily.md`. An audio failure never withholds the written brief.

## Checkpoints

None. This read-only workflow prepares a brief without customer-system writes or an approval pause.

## Audit

| Check | Pass Condition |
|---|---|
| Sourcing, before step 9 output | Every fact carries a source or link. Every inference starts with `Hypothesis:` and is not restated as fact later |
| Failed sources, before step 9 output | Each unread or errored source appears as `<source> not checked: <error>` per `rules#not_checked_means` |
| Footprint, before step 9 output | Org fields appear under their returned names. A 404 or error reads `Org status unverified for <email>: <response>` |
| Research, before step 9 output | At most `policy.call_prep.research_sources_max` dated sources per company. Undated items are dropped |
| No writes, throughout | No Salesforce, Gmail, Calendar, or warehouse write. Record problems appear only under `CRM notes` |
| Daily audio | All written sections are narrated, playback and ending are verified, or the failure is reported alongside the written summary |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Call brief | Run thread | `references/brief-formats.md` "Single call" or "Multi-call window", for Operator before the call. After the call, interaction-sync reads the completed interaction as its evidence |
| CRM notes | Inside the brief | Record problems with links, not fixed here |
| Saved results | Sandbox | Query and search outputs, never Project Files |
| Daily audio | Run thread attachment, source files in sandbox | One playable downloadable MP3 with the original written brief |
