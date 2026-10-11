# Proposals

Read at preparation, "Questions" during the walk and "Apply" after approval. Record every label, exact change and outcome in the sandbox run file.

## Every run

Keep Task and next-step findings in the read-only `triage` list. Label them `Triage owns the next step`, `Triage owns Task <Id>` or `Triage owns the Task gap`.
No Task or next-step change, approval label or delivery command belongs to those rows. They never route to deal threads and are not a handoff request.
For a deal-thread-owned Opportunity, route only stage, close date, Amount and required-field findings with evidence and recommended fixes. Propose nothing on that record here.
Send once with `pplx tm mail send <deal-thread session id> "<message>"`. Never wait, sleep or poll.
Run every `pplx` command as its own top-level line, never inside a script, function, loop or conditional, so its credentials apply.
Save actual transport and delivery outcome in `routed`. A failed or ambiguous send is needs-input, never claimed delivered or counted as no trigger.
For local deals, numbered clear recommendations contain only evidence-supported blank required or conditional fields. No Next_Steps__c payload or Task change is accepted.
CloseDate, StageName, Closed Lost and Amount remain lettered record proposals, one record per letter. `all` covers displayed numbered blocks only, never questions or letters.
Every flagged deal has a supported proposal, question, withheld row or read-only triage finding. No-trigger deals are counted, not listed in ordinary hygiene.

Review the lost path in `rules#stage_move` on every weekly or requested run. Use the linked Salesforce Account's `NumberOfEmployees` and the exact native Opportunity `Description`.
At or above `policy.pipeline.worth_growing_min_employees`, propose S1 and keep open, or leave an existing S1 unchanged. Below it, propose Closed Lost unless a size-floor exception is recorded.
A blank or unreadable count asks Operator. Propose neither S1 nor Closed Lost for that lost path until his dated count answer or a filled native count supports the choice. Never treat blank as zero.
Apply this same size test to an existing S1 only with positive history of an S2+ backward move for the lost path. Newly qualifying S1 deals that never moved back are unaffected.
Missing history or reason evidence is unknown and holds only the dependent size-floor proposal. A stage label or Operator's outbound follow-up never proves that history or buyer agreement.
For Operator's one-deal exception, prepare a lettered Opportunity Description proposal with `mode: prepend`, the exact current baseline, and his dated instruction in `operator_size_exception`.
The new line is `policy.salesforce.note_prefix` plus `Size floor exception, kept open by Operator M/D/YY`, using his decision date. Preserve all existing text under `rules#note_prefix`.
Honor that dated marker in fresh native Description and propose no size-floor Closed Lost. Do not add it again when present.
Missing retrieval or ambiguous Description holds the dependent size proposal.
The marker does not defeat an independent buyer no, Operator's stated no or reviewed-silence basis. All marker and stage writes retain letter approval, fresh-read and readback gates.
Every size-floor StageName letter and qualifying Closed Lost row carries reviewed `lost_path_size` per `references/report-format.md` "Friday additions". The helper does not judge buyer intent.

## Questions

Labels Q1, Q2 in report order. After the numbered blocks are applied, skipped, or deferred, walk the open questions one at a time with the helper's question mode.

- Each question carries brief factual context and evidence, one precise question, two or three options where useful, and the exact record and field changes for each write option.
  An option with no changes is a factual answer. Option labels are Q1-a, Q1-b; `skip` defers the question to the Close list.
- Selecting an option with changes approves exactly those changes. Apply them without a second confirmation.
- A factual answer, free text, or edit becomes a new option with the next unused letter and its exact changes, then waits for approval. Mark any option it replaces superseded.
- Read back every write before rendering the next question.
- Never reuse a label for a different or revised proposal in the run. A revised block takes the next unused number and the old one is marked superseded. Approval never transfers to a new label.

## Friday

Apply "Every run" routing on every weekly or requested run. Keep rollup, delta and lettered record proposals, one record each:
- CloseDate per `rules#close_date_basis`.
- StageName per `rules#stage_move`. Closed Lost requires reviewed silence for `policy.pipeline.closed_lost_silence_days` with no upcoming Event, a stated buyer no, Operator's stated no,
  or the reviewed lost-path size basis in "Every run".
- Amount only from a buyer-confirmed or user-supplied figure.
One record and field appear in one proposal only. A numbered blank-field block can get a different letter, such as a CloseDate move.

## Friday qualification

Review every owned open deal in `policy.pipeline.early_stages` once per weekly or requested run. Keep findings in friday.qualification and the existing approval labels.
For S1 with a blank Amount under `policy.pipeline.early_required_fields`, propose Amount only from buyer evidence and set buyer_confirmed true on that letter after review.
ARR__c is a non-editable formula equal to Amount and zero when Amount is null, verified October 3, 2026. Propose Amount, never ARR__c.
If no buyer-supported figure exists, ask a Q-labeled question rather than copying a seat wish, user-supplied estimate, or an inferred amount.
Reviewed buyer silence for `policy.pipeline.closed_lost_silence_days` with no upcoming Event supports Closed Lost.
The reviewed lost-path size basis in "Every run" also supports Closed Lost for a previously moved-back S1.
Operator's stated no in the run thread also supports Closed Lost. Quote his words and date in operator_stated_no. Newer buyer activity does not defeat it.
Record the last dated buyer activity, evidence_complete true only after the relevant reads and reconciliation, and upcoming_event false only after the fresh Event read.
Missing dates, partial searches, outbound follow-ups, and elapsed meetings never establish buyer silence. Positive newer buyer activity defeats an older silence conclusion.
Otherwise record its next-step finding in `triage` with `triage_next_step: true`, labeled `Triage owns the next step`. No next-step or Task proposal.
Never propose moving an early stage up. Amount and Closed Lost changes stay Friday letters with fresh reads, approval, and readback. Next-step findings stay read-only.
Keep the full qualification list in the sandbox run file. The report shows at most ten rows plus the total reviewed count.

## Pilot report input

Friday only, when Operator supplies a `pilot-usage` report in this run's thread, per `rules#pilot_handoff`.
Accept it per `rules#pilot_handoff`: confirm its Account and org id against the Account read in `workspaces/pipeline/workflows/pipeline-review/references/collect.md` item 7,
then use its figures as evidence for that Account only.
It can support a lettered record proposal above, such as StageName per `rules#stage_move` or a required field, that quotes the figures with their window and limits.
A missing handoff field or an identity mismatch goes to Needs your input. The report is record-proposal evidence, not a trigger, and it never authorizes a write or widens this run's reads.

## Apply

Write only approved Opportunity fields per `rules#write_protocol`, one record at a time. Fresh-read every changed record and read each write back.
Record every outcome in the run file. Never repeat a verified write. A partial block names successes and each failed or dependent unapplied field.
Render the helper receipt. Re-query written Opportunities and shared native Activity reads.
Per `rules#run_start`, record a fresh local-offset time for the pipeline-review post-write `hygiene_check` and use it as `--as-of` on those re-queried records.
The Collect files predate the writes and cannot verify them.
Next-step and Task flags remain read-only triage findings, never failed field verification or a claim this workflow repaired them.
