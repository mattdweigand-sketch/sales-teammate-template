# Event sequence receipt

## Readback

Use the full saved `apollo_sequences_create` or `apollo_sequences_update` response for the exact approved sequence as native copy evidence.
Use its stored steps, touches, and templates with subject and body.
Use the confirmed sideloaded emailer_steps, emailer_touches and emailer_templates joined by native IDs. Native template copy is subject and body_html, not a model-reshaped response.
Compare each touch's subject and body with the approved copy after normalizing only the HTML Apollo sanitizes.
Compare each native touch's include_signature with its approved step's required boolean. A mismatch is FAIL with no enrollment payload. Missing approved values are a ValueError.
Record the approved and native signature flags. Bodies already ending with a sign-off should use approved false, so Apollo does not append another signature.
Preserve text and links. Merge variables must match exactly. Unexplained differences stay partial.
Report the pre-enrollment comparison result against the approved snapshot, including steps, touches, subject/body templates, merge variables, schedule and stop on reply.
Include the saved event_launch_check PASS, FAIL or STOP, exact mismatches, missing fields, structure errors and full not_checked list in the receipt.
FAIL stops enrollment with one fix proposal. STOP for missing documented fields or unknown structure stops and asks Operator, with no enrollment payload.
Report mark_finished_if_reply, emailer_schedule_id, sequence_by_exact_daytime, wait_time and wait_mode comparisons. The planned payload supplies the mailbox check, not the native sequence.
Only fields outside the connector schema stay not_checked without blocking enrollment. They do not establish a verified native readback.
Missing templates stop before enrollment and require Operator's input. Never infer native copy or send without the completed comparison.
Read `apollo_emailer_campaigns_show` for the exact approved campaign and sequence when accessible. Compare native steps, mailbox, and schedule against Operator's approved snapshot.
On a permission error only, quote the error and use available Apollo campaign and message search tools with complete pages for counts, active state, stop on reply, and first send.
Attempt the live read on every run. When campaigns_show is blocked on this run, take steps and exact send times from the stored create or update response and compare them with approval.
The readback receipt names that saved source, `apollo_sequences_create` or `apollo_sequences_update`, its response timestamp, and the quoted current-read failure.
Never assume live access is unavailable on a later run.
Take the mailbox from the saved `apollo_emailer_campaigns_add_contact_ids` response if it returns each contact's sending account. After the first send, also check the sender on get_content results.
If neither shows the mailbox, use the accepted enrollment request's `send_email_from_email_account_id`, labeled "mailbox from accepted enrollment request".
That mailbox source counts as verified only when the enrollment call succeeded with no errors and the ID matches the approved mailbox. Missing sources or any mismatch stay partial.
Missing or mismatched fields stay partial.
Other errors never enable the permission-error search path. Never infer native copy from the approved proposal alone or a successful enrollment count.
Check the native stop-on-reply setting against `policy.prospecting.event.stop_on_reply`. A reply must finish that contact's sequence, not trigger workflow follow-up.
Read `apollo_emailer_messages_search` in list mode, paging all returned cursors for this campaign. Do not treat an incomplete result as a scheduled count.
Before the first send, check every scheduled message's `variant.subject` against the approved subject for its `touch_id`.
Complete pages and exact touch mapping are required. Any missing variants, unknown touches, or subject mismatches stay partial.
If any step has already sent at readback, use `apollo_emailer_messages_get_content` for each sent email.
Compare its subject and body with the approved copy using the same HTML normalization and exact merge-variable checks.
Otherwise state "first send pending, sent-content check not yet run". Never use get_content as evidence for unsent messages. Any missing sent content stays partial.
Reconcile the original approved recipient set as remaining approved Contacts plus reported drops and holds. Compare actual enrolled Contact IDs and email addresses with only the remaining set.
Report unexpected missing, duplicate, extra, or errored recipients explicitly. Documented reply drops and holds are not unexplained enrollment failures.
Reconcile scheduled-message counts to the approved steps, actual email steps, and remaining approved recipients. LinkedIn tasks are not email messages.
Report the native first-send date and time with timezone, sending mailbox, enrolled count versus approved count, and stop-on-reply setting.
Enrollment may already have sent real email. Say what native evidence proves sent versus scheduled, not that every email is unsent.
Readback is verified when the create or update response copy, scheduled subjects, counts, active state, stop on reply, and first send all match approval.
Matching steps, mailbox, schedule, recipient reconciliation, and sent-content checks when applicable are also required.
Only the matched pre-enrollment copy result plus complete native readback satisfies readback. The permission-error search path changes the read tools, never the copy gate.
Other gaps make the outcome partial.
Report native CRM push status from enrichment and enrollment responses or reads when available. If unavailable, say not checked. Never infer a successful Salesforce sync from enrollment counts.
For partial results show one exact fix proposal and wait for its approval. Never retry sends automatically, claim rollback of sent mail, or cover gaps with a successful count.

| Receipt field | Required detail |
|---|---|
| Scope | Event, source list, approved snapshot and link, no direct Salesforce writes, with Apollo CRM sync disclosed |
| Enrollment | Original approved, remaining after recheck, and actual recipient counts, exact set differences, and returned sequence/campaign references |
| Reply recheck | When run, window, query shapes, contacts checked, replies found, dropped Contacts and reasons, holds and reasons, and attached saved receipt file |
| Delivery | Mailbox, first send with timezone, exact steps, scheduled-message count, and any native sent evidence |
| Copy | Pre-enrollment comparison result, stored create/update steps, touches and templates, normalized-copy comparison, complete scheduled-subject checks, and sent-content results or first send pending, sent-content check not yet run |
| Launch check | event_launch_check result, exact mismatches, missing fields, structure errors, normalization notes and full not_checked list, with the unchanged PASS payload saved outside Git |
| Stop | Native stop-on-reply setting and evidence source |
| CRM sync | Native CRM push status when available, with its source, otherwise not checked |
| Holds | Every excluded or needs-input contact, duplicate, mismatch, failure, and applied per-list override |
| Status | Matched pre-enrollment copy and verified native readback, or partial with one exact proposed fix |

## Handoff and close

For the no-enrollment branch, skip Apollo calls and report zero enrolled with no sends. Use closed with no enrollment, never a verified sequence or a failed empty-file audit.
If a reply recheck ran, include its summary and exact dropped and held lists with reasons, including when it removed every approved Contact. Attach its saved receipt file to the thread message.
Otherwise close with the original exclusions, holds, and handoff evidence. State that the pre-enrollment recheck was not reached. Never run a recheck just to fill the receipt.
Include native CRM push status from any approved enrichment already run, when available, otherwise not checked, even with zero enrollment.
Send the open-Opportunity contact list to the Pipeline thread using configured authorized session delivery. Include the Prospecting source thread and native Contact, Account, and Opportunity links.
Include the open-Opportunity reason and any explicit per-list override without implying that enrollment authorizes Pipeline writes.
Workers do not directly message other sessions. When run by a worker, return the handoff to the owning Prospecting teammate for delivery and report that delivery is pending.
Never claim a delivered handoff without a native receipt. If delivery is unavailable, keep the exact list in the run thread and name the limitation.
Close with enrolled, excluded, held, failed, and handed-off counts and the receipt status. Customer lists, reports, and tool output remain in the thread or sandbox, never Git.
The workflow ends here. Apollo stops a contact on reply and Operator takes over. Do not run signal-followup, create Salesforce Tasks, monitor indefinitely, or send manual replies.
