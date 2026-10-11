# Capturing process judgment

## Select a task

An unselected nomination is a suggestion until Operator selects the task.
Capture one recurring task that Operator wants to improve. Establish the intended outcome, audience, existing workflow owner, and one recent example with its original inputs and final result.
Reuse prior answers and selected evidence. Ask only for missing details, one or two focused questions at a time. Keep the conversation in the thread where Operator invokes capture.
If Operator has not selected a task, offer a few relevant choices without treating a suggestion as his preference. No task or usable example means needs-input, not an invented walkthrough.
Inspect only the named sections of the owning workflow needed to understand this task. Record the revision and relevant current guidance with the proposed diff.
Use Operator-selected material and the existing access boundaries. Report unavailable source material and its effect on capture rather than claiming to have read it.

## Walk through decisions

Have Operator walk through the actual work from its inputs to the accepted result. Start with what made the result usable, then ask at the points where a choice mattered.

- What did you notice, and why did it matter for this person or task?
- Which evidence did you trust, leave out, or treat as uncertain?
- What alternatives did you consider, and why did you choose this one?
- What would make you choose differently or stop for another person's decision?
- What would make this result unacceptable, even if all steps were followed?

Use edits and rejected results to locate decisions. An edit shows what changed, not why. Ask for Operator's reason instead of inferring a motive or a stable preference from a correction.
Keep three kinds of material distinct in the working notes.

| Material | Treatment |
|---|---|
| Operator's explicit explanation | Retain his words or a faithful paraphrase with a message link or artifact section |
| Observed choice or result | Describe what happened with its source, without assigning an unstated reason |
| Proposed interpretation | Label it an unconfirmed hypothesis and ask Operator before using it as his judgment |

Preserve the original situation and uncertainty. Separate case facts from potential reusable rules. One accepted example does not establish a universal preference.
Flag contradictions with current rules or between Operator's explanations. Present the exact conflict for resolution before preparing an active wording change.

## Working guide

Draft the smallest guide another run could use. Keep it proposed until the exact reusable wording is approved. Draft in the existing thread.
Save the record once Operator confirms it, per "Capture file".

| Part | Contents |
|---|---|
| When to use it | Task, audience, intended outcome, and scope exclusions |
| Inputs | Required evidence, relevant canonical sections, and what missing information prevents |
| Sequence | The few steps needed to reach a usable result |
| Decisions | For each choice, the signal, action, reason or tradeoff, exception, and source of Operator's explanation |
| Acceptance | What Operator would accept or reject, with checks that can be applied to a new result |
| Examples | Selected accepted and rejected passages with annotations, case context, and source links |
| Open questions | Unconfirmed hypotheses, conflicts, missing reasons, and untested situations |
| Intended home | Owning workspace, exact proposed reference file and section, and any affected consumers |

Write decisions as conditional guidance. Identify what evidence triggers a choice, what to do, why it helps the intended outcome, and what changes the choice.
Do not fill missing reasons with plausible sales advice. A hypothesis remains outside the proposed active rules until Operator confirms it.
Examples and customer facts support private capture. Only generalized guidance free of customer material is eligible for a repo diff.
Choose the narrowest existing owner. Extend that workflow's reference unless another actual consumer needs the same rule. Shared policy and rules keep their current canonical homes.
Systems owns this capture method. Domain criteria stay with the owning workflow and Operator, even when Systems drafts or implements the change.

## Try another case

Use a second relevant case with its normal inputs, preferably one where a deciding signal differs. Name context differences and unavailable evidence before applying the proposed guide.
Produce a read-only trial result and show which decisions led to it. No trial sends messages, edits customer systems, or runs a live write branch of the owning workflow.
Ask Operator whether he would use the result and what he would change and why. Acceptance of this result is not approval to publish the guide or perform customer-system writes.
Compare the first and second cases for missing explanations and substantive corrections. Refine the specific decision that failed rather than adding general instructions after every edit.
If a change affects an earlier accepted case, revisit that case too. Keep stable judgment distinct from a case exception and retain unresolved contradictions for Operator.
If a second case or Operator's review is unavailable, return a proposed guide marked untested with the missing check. Do not claim tested usefulness, saved time or better performance.
Operator's confirmation shows faithful capture. Only reviewed trial results show usefulness. Do not claim saved time or better performance without them.
Static navigation checks and fictional trials establish only the properties exercised.

## Review and handoff

Present the exact sanitized wording diff, intended canonical file and section, affected consumers, source links, resolved conflicts, and trial limits for Operator's review.
Use native approval evidence tied to that wording. A draft filename, accepted trial result, or instruction to capture a process does not approve a rule change.
Reuse a matching exact approval already supplied. Changed or contested wording stays proposed until the missing decision is resolved under the existing owning workflow's authority.
After approval, send the repo-maintenance request to the Systems thread per `_core/CONVENTIONS.md` "Handoffs and state" for destination and transport.
Include the exact approved diff, domain requirements, evidence links, current baseline revision, and Operator's native approval link, whichever thread ran the capture.
Include the capture file update to applied in the same request.
Capture itself makes no repo writes.
Repo-maintenance implements and tests under its contract and the existing merge and deployment authority. This handoff grants no new sales permissions or schedules.
Keep walkthroughs, real examples, corrections, and approval history in the thread or sandbox. Git receives only the generalized capture file, never code or test fixtures.
Later runs use the deployed canonical reference through their own contracts. This workflow does not become a second owner of the captured domain rules.

## Capture file

Each confirmed capture has one file at `workspaces/systems/captures/<workflow>-<task>.md`. Systems repo-maintenance commits it. Capture itself makes no repo writes.
Repo-maintenance commits each change Operator has reviewed, including reasons, exceptions, corrections, test results and status, batched per session. There is no fixed number of commits.
Unconfirmed material stays in the thread.
Statuses are `confirmed`, `applied` and `retired`, each with an ISO date in YYYY-MM-DD format.
`confirmed` means Operator confirmed that the record states his reasoning faithfully. It may be untested.
`applied` means approved wording is live in the owning workflow. Its Status line carries the PR link or the merge-commit link.
Each applied decision has an `Applied in:` sub-line naming the backticked repo file and section, plus any difference between captured wording and applied wording.
`retired` carries its reason.
Use these labeled lines and lists, in this order.

| Label | Contents |
|---|---|
| `Task` | The recurring task, in one line |
| `Owner` | Owning workspace and workflow |
| `Status` | `confirmed`, `applied` or `retired`, with ISO date, PR or merge-commit link when applied and reason when retired |
| `Reasons` | Operator's stated reasons, generalized |
| `Decisions` | For each choice, signal, action, reason, exception and intended home |
| `Second case` | One line on the trial result and Operator's review, or `untested` with the missing check |
| `Open questions` | Unconfirmed hypotheses, conflicts and untested situations |
| `Evidence` | Thread links only |

Remove customer and person names, deal values, email bodies, quotes and transcript text before sending. If removal leaves a decision unclear, keep it in the thread and list it under `Open questions`.
Approved rules live only in their owning workflow file. A record is history, never authority, and never overrides or substitutes for the owning file.
Routing exclusions mean no other workflow is told to read records as input. They do not block access.
Retire a file only through repo-maintenance after Operator agrees. Keep it with status `retired` and the reason.

## Method source

The method adapts the practical judgment-capture idea in [Jake Van Clief's video](https://www.youtube.com/watch?v=7Ds2ZJD37KY).
It asks for deciding evidence and reasons alongside steps, then checks another case with human review. The video's efficiency claims are not validation of this workflow.
