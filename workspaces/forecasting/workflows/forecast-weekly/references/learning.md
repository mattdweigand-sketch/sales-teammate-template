# Forecast learning

## Quarter-end review

At quarter end, use the forecast thread's dated weekly calls and reviewed bucket snapshots for that quarter. Identify each snapshot and the call Operator actually made.
Read final owner-scoped Salesforce records for those Opportunity Ids, including deals whose CloseDate moved out of the quarter, plus all wins in the quarter.
Compare each recorded commit, upside, excluded, and pull-in decision with its actual closed outcome and CloseDate. Missing snapshots or final reads remain unknown.
For the called number and actual booked total, use `policy.tooling.scripts.forecast_math` in its existing forecast mode with the snapshot's quarter and policy amount field.
Use the stored reviewed snapshot for the historical call and final IsWon in-quarter records as booked with empty deals and pull_ins for the actual total. Do not recalculate totals in prose.
Report each number and the deal-level differences. Distinguish incorrect timing, a missed blocker, and insufficient evidence from a later outcome that could not have been known.
Propose numbered edits only when evidence supports an improvement to `references/buckets.md`. Name the heading and exact current and proposed wording, evidence, and counterexamples.
Use the bucket reference loaded for this quarter-end branch. Generalize the lesson before proposing repo text, with no customer names, quotes, or snapshots in the diff.

## Approval and delivery

Operator approves specific numbered wording changes in the forecast thread. Approval covers only the displayed text. Revised wording needs another approval.
Send the approved diff, evidence links, and approval link to Systems repo-maintenance for a tested repo PR under the existing repository approval process.
The receiving contract is `workspaces/systems/workflows/repo-maintenance/CONTEXT.md`. Route the handoff without loading or executing it during tracking.
The tracking branch writes no CRM records and edits or merges no repo files. The merged PR updates the canonical bucket criteria for later runs.
Keep calls, outcomes, proposals, approvals, and PR links in the forecast thread. Never add state files or lessons files to the repo.
