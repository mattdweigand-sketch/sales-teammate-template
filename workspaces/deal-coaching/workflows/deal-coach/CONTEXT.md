---
cadence: {call-review: daily, pre-meeting: daily, deal-review: weekly, criteria-refresh: monthly}
reads: _core/policy.yaml (coach, momentum, tooling, forecast), _core/rules.md, references/, Salesforce, Momentum, Gmail, Calendar, deal threads
writes: nothing
next: Systems repo-maintenance for a repo PR after Operator approves criteria-refresh wording, otherwise reports for Operator
---

# Deal Coach

Find the evidence gap and the next move that improves a deal or call. Read-only per `rules#read_only_skills`.
Call review and pre-meeting coaching run weekdays, deal review weekly, and criteria refresh monthly per `policy.coach.schedule`.
Select one branch and load only its Inputs rows. These schedules describe the workflow and do not activate automations.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | All branches load `coach` | Schedule, gates, review count, and talk share flag |
| Core policy | `_core/policy.yaml` | Deal-review only: `forecast.amount_field` | ARR ranking field |
| Core policy | `_core/policy.yaml` | All branches load `momentum`, `tooling` | Transcript and Calendar retrieval limits |
| Core rules | `_core/rules.md` | All branches load `rules#run_start`, `rules#read_only_skills`, `rules#not_checked_means`, `rules#absence_conclusions` | Identity, scope, and evidence limits |
| Core rules | `_core/rules.md` | All branches load `rules#momentum` | Transcript retrieval |
| Core rules | `_core/rules.md` | Call-review, deal-review, pre-meeting load `rules#calendar_search` | Calendar retrieval |
| Reference | `references/report-format.md` | All branches load "Scope and evidence", "Output rules" | Branch selection, evidence, and voice |
| Reference | `references/meddicc.md` | Call-review, deal-review, pre-meeting load "Evidence scores", "Stage gates" | Evidence and current-stage gaps |
| Reference | `references/strategy.md` | Deal-review and pre-meeting load "Strategy questions" | Power, positioning, and next move |
| Reference | `references/risk-patterns.md` | Call-review, deal-review, pre-meeting load "Risk patterns" | Generalized risks and checks |
| Reference | `references/call-review.md` | Call-review loads "Collect calls", "Call checks" | Transcript scope and coaching |
| Reference | `references/report-format.md` | Call-review loads "Call review" | Call report layout |
| Reference | `references/report-format.md` | Deal-review loads "Deal review" | Deal selection and report layout |
| Per-run evidence | Coach thread and Salesforce | Deal-review loads previous gap records and all owned open Opportunities closing this quarter | Closed-gap comparison and open-gap count |
| Reference | `references/report-format.md` | Pre-meeting loads "Pre-meeting" | Meeting scope and questions |
| Reference | `references/report-format.md` | Criteria-refresh loads "Criteria refresh" | Monthly patterns and numbered edit proposals |
| Reference | `references/learning.md` | Criteria-refresh loads "Signals", "Monthly refresh", "Approval and delivery" | Evidence, proposals, and approved PR handoff |
| Reference | `references/meddicc.md` | Criteria-refresh only when targeted for an edit, "Evidence scores" or "Stage gates" | Exact current wording |
| Reference | `references/strategy.md` | Criteria-refresh only when targeted for an edit, "Strategy questions" | Exact current wording |
| Reference | `references/risk-patterns.md` | Criteria-refresh only when targeted for an edit, "Risk patterns" | Exact current wording |
| Reference | `references/call-review.md` | Criteria-refresh only when targeted for an edit, "Collect calls" or "Call checks" | Exact current wording |
| Reference | `references/report-format.md` | Criteria-refresh only when targeted for an edit, "Call review", "Deal review", or "Pre-meeting" | Exact current wording beyond sections already loaded |
| Per-run evidence | Salesforce, Momentum, Gmail, Calendar, and deal threads | Call-review and pre-meeting use selected deals and window. Deal-review includes selected reviews and all open S3 to S5 coverage | Current records and buyer evidence |
| Per-run evidence | Salesforce Contact Roles, Gmail, and Momentum | Deal-review covers every owned open S3 to S5 Opportunity, including outside the deal_review_count selection | Stakeholder roles and active contacts |
| Per-run evidence | Coach thread and linked deal threads | Criteria-refresh uses outcomes, prior coaching, Operator's reactions, and Friday system reviews since the last refresh | Learning evidence |
| Per-run evidence | Owned Opportunity call Tasks and Next_Steps__c, Momentum transcripts, and linked deal evidence | Criteria-refresh uses the previous calendar month, within supported source limits | Recurring objections, blockers, and product gaps |

## Process

1. Start per `rules#run_start`. Select the branch and scope per `references/report-format.md` "Scope and evidence".
2. Call-review collects per `references/call-review.md` "Collect calls" and evaluates "Call checks" against the routed evidence and risk criteria.
3. Deal-review follows `references/report-format.md` "Deal review", scoring per `references/meddicc.md` "Evidence scores" and "Stage gates" before strategy and risks.
4. Pre-meeting follows `references/report-format.md` "Pre-meeting", using evidence gaps, strategy, and risks to select questions for the buyer.
5. Criteria-refresh follows `references/learning.md` "Signals", "Monthly refresh", and "Approval and delivery" for Patterns and supported edits. Only edits need Operator's approval and a repo PR
handoff.
6. Post only the selected branch's output in the Coach thread per `references/report-format.md` "Output rules". Include evidence limits and confirm nothing written.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 5 | Numbered criteria edits with evidence in the Coach thread | Operator approves specific edits before Systems repo-maintenance prepares a repo PR |

## Audit

| Check | Pass Condition |
|---|---|
| Sourcing, before step 6 | Every claim and score cites a call timestamp, email date, Salesforce field, or thread link. Unsupported claims are unknown |
| Gates, before coaching output | Scores use the cited evidence and current-stage minimums in policy. Retrieval gaps stay unknown |
| Stakeholders, before deal-review output | Every owned open S3 to S5 deal has one coverage line, including unselected deals. Single-thread flags use active-contact evidence |
| Patterns, before criteria-refresh output | At most 10 patterns recur on two or more deals in the previous calendar month, each with accounts, dated evidence per deal, and a suggested owner |
| Branch loading, throughout | Only the selected branch's Inputs rows and named reference sections are loaded |
| Scope, throughout | No Salesforce, Gmail, Slack, or buyer writes. Salesforce suggestions go to the Pipeline thread as one-line notes for Operator to approve there |
| Learning, throughout | Lessons stay in the Coach thread. Approved reference edits go through Systems repo-maintenance as a repo PR. No state files enter the repo |
## Outputs

| Artifact | Location | Format |
|---|---|---|
| Coaching reports | Coach thread | Evidence and assessment for Operator in the selected "Call review", "Deal review", or "Pre-meeting" layout in `references/report-format.md` |
| Criteria edit proposals | Coach thread | "Criteria refresh" layout in `references/report-format.md` |
| Monthly patterns | Coach thread | Previous-month objections, blockers, and product gaps per `references/report-format.md` "Criteria refresh", even without supported criteria edits |
| Approved criteria handoff | Coach thread, to Systems repo-maintenance | Exact diff and Operator's approval link per `references/learning.md` "Approval and delivery". A merged repo PR updates the canonical references |
| Salesforce suggestions | Pipeline thread | One-line notes for Operator's approval per `references/report-format.md` "Output rules" |
