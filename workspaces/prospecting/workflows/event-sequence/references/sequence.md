# Event sequence

## Copy and timing

Use `policy.prospecting.event.steps`, `policy.prospecting.event.step_gap_days`, and `policy.prospecting.event.last_touch_before_event_days` as defaults.
Default touches are emails followed by a LinkedIn task. The task creates manual work, not an automated LinkedIn message.
Anchor the final touch to the first attendance date minus the configured last-touch days. Work backwards by the configured gap for each preceding step.
Build the sequence in Apollo interval mode on a named sending schedule, not exact datetimes. Email 1 waits 0 days from enrollment and later steps wait the configured gap.
Show each step's expected local send date and window with timezone, not just relative offsets. The exact schedule is chosen and approved by Operator, never inferred from the sandbox timezone.
Resolve and display the sending schedule ID along with its name. An approved name alone cannot authorize enrollment.
If any touch is in the past or the event dates conflict, stop for an exact revised schedule. Do not send immediately or compress gaps without approval.
Draft every subject, full email body, and LinkedIn task instruction using `policy.email_voice` and the event ask. Never invent a relationship, attendance, or recipient fact.
Apply advisory `policy.prospecting.outreach.lint`. Disclose lint flags without treating them as sending permission.
Show the resolved mailbox ID, address, provider and verified Apollo user ownership from `apollo_email_accounts_index`. A default mailbox remains a proposal until approved.
Default selection uses exactly one default after filtering to Operator's resolved Apollo user, never the team's defaults. Keep user and mailbox IDs in run-time evidence, not Git.

## Approval

Present one complete enrollment proposal in the Prospecting thread. Include these items before asking for one explicit approval.
Label it E1. Edits or changed evidence use the next unused E label. Accept only its displayed label or `approved <label>` under `rules#approval`.

- Event name, Operator's attendance dates, location, and ask.
- Original rows, normalized contacts, duplicates, proposed enrollments, needs-input rows, and exclusion counts.
- Count outreach-owner rows with no Account and disclose that Apollo's CRM sync may create Salesforce Contacts for them.
- Exact contacts and emails to enroll, with every exclusion and its reason. Include each named per-list override and the approval evidence for it.
- The bounded reply-check summary from `references/prep.md` "Salesforce and reply checks", with window, query shapes, contacts checked, replies found, holds, and the retrieval limit.
  Attach the saved receipt file to the E1 thread message, not a sandbox-path link.
- Exact subject and full body for every email, and the full LinkedIn task instruction. Include all personalization or rendered variants, not an unspecified template.
- Each step's include_signature boolean. Approve false for bodies that already end with a sign-off.
- Every step's local send date and time, timezone, gap, schedule window, and first-send time.
- Sending mailbox ID and address, schedule ID and name, sequence target, stop-on-reply setting, and the enrollment and scheduled-message counts expected on readback.
- Enrichment receipts and spend approvals, scrub PASS, audit PASS, batch reconciliation, and all held domain mismatches.
- Apollo existing-contact identity holds and reasons, active_sequence evidence including prior same-event enrollment in every status, and event_app_invite matches or no invite export checked.
- Apollo's CRM sync may create or update Salesforce Contacts from approved enrollment. The workflow itself makes no direct Salesforce writes. Include this in E1 and every revised E proposal.

Ask Operator to approve the exact contact list, sequence copy, sending mailbox, and schedule under `rules#event_sequence`, or edit or skip.
State the displayed E label as the response that approves this complete snapshot. `skip` declines it.
Named-account scope, including the outreach-owner rule, cannot be overridden. Operator may override other named exclusions for a named contact in this list.
Display that override with the exact recipient, reason, copy, mailbox, and schedule.
Edits or changed evidence require a new exact proposal except the narrowing-only reply recheck in "Enrollment". Unanswered, skipped, needs-input, and unapproved contacts never enter enrollment.
Do not rely on a past campaign's approval, mailbox defaults, helper labels, or a generic approval of the event idea.
Apollo add-to-sequence sends real email and cannot be undone once sent. Say so before the approval question. Never create drafts in Gmail as a substitute sending route.

## Enrollment

Immediately before writing, re-read Account ownership and open Opportunities for every approved contact, with complete pages.
Existing Accounts still owned by `policy.prospecting.identity.sfdc_user_id` can enroll. Approved outreach-owner rows also qualify only while their Account remains house-owned or missing under policy.
No revised proposal or other list override expands that scope. Repeat the completed missing-Account lookup, never assume yesterday's absence still holds.
If either changes, those guard reads fail, or recipient identity, copy, mailbox, or schedule differs, stop and present a revised exact proposal. No silent scope expansion or inherited override.
Re-run the bounded reply check per `references/prep.md` "Salesforce and reply checks" from the saved window end through the recheck time, inclusive, for each approved Contact.
Keep sender-only inbound searches, separate sent searches, full thread reads, timestamp classification, and complete cursors. Incomplete reply evidence holds that Contact, not the entire list.
Update `replies_checked` from the recheck, never reuse the earlier true marker. Any incomplete recheck sets it false or unknown before rerunning the helper.
Merge the recheck with saved reply evidence, retaining the newest substantive reply. Save the current recheck time with an explicit offset.
Re-run `policy.tooling.scripts.event_list_prep` on the same saved reviewed rows in their original order, with `--as-of` set to that recheck time, never the old run start.
For a newer reply, do not carry a prior recent_reply override forward. Drop approved Contacts newly labeled `recent_reply` and hold Contacts whose reply recheck is incomplete.
Intersect the remaining eligible Contacts with the exact approved recipient snapshot. Enroll the rest without re-approval under `rules#event_sequence`, never add or replace a Contact.
Preserve the approved copy, mailbox, schedule, and other explicit overrides. The reply recheck only narrows the list and authorizes no enrichment or other writes.
Save and attach the recheck receipt with its window, query shapes, contacts checked, replies found, dropped Contacts, holds, and each reason. Report it in the final receipt.
If no recipients remain, skip every Apollo call and close through `references/readback.md` "Handoff and close", with zero enrollment and the drops and holds.
Only after Operator approves the original snapshot perform these operations on its remaining Contacts under `rules#write_protocol`.

1. `apollo_contacts_bulk_create` for only approved contacts. Reuse returned existing contacts when supported, and reconcile every approved recipient to its exact Apollo Contact ID.
   A returned identity mismatch stops enrollment for a revised proposal, never silently accept a different or personal email or another owner's CRM link.
   A house-owner CRM link on an outreach-owner row is not another owner's link.
2. `apollo_sequences_create` for one sequence, or `apollo_sequences_update` only on the exact existing sequence Operator approved. Set the approved copy, steps, mailbox, schedule, and stop on reply.
   Set each touch's include_signature to its step's approved boolean. Approve false when the body already ends with a sign-off, so Apollo does not append another signature.
   Save the full create or update response in the sandbox, including native steps, touches, and templates with subject and body, for copy readback.
   Never substitute the approved proposal for returned native copy evidence.
   Before step 3, compare the saved response with the approved snapshot using `references/readback.md` "Readback" copy rules.
   Compare steps, touches, subject and body templates, merge variables, schedule and stop on reply. Normalize only the HTML Apollo sanitizes and require exact merge variables.
   If the response has no templates, stop before step 3 and ask Operator. Never enroll copy that has not been compared.
   Any mismatch or unexplained difference stops before step 3 with one fix proposal. Never call add_contact_ids or approve on unmatched copy.
   Run `policy.tooling.scripts.event_launch_check` after create/update and before add_contact_ids on the exact saved E snapshot and fresh event_list_prep recheck output.
   Supply the saved bulk-create contacts, native sequence response and exact planned enrollment payload. Retain the result outside Git.
   Approved recipients carry row_id and email. Approved steps carry subject, body and a required include_signature boolean.
   Require send_email_from_email_account_id, stop_on_reply and emailer_schedule_id in the snapshot. A missing approved include_signature is a ValueError.
   Include schedule_settings with mode interval and step_waits for every step. Native contacts carry id and email. Check the mailbox only in the planned enrollment payload.
   Accept the confirmed bare result or saved wrapper with tool, result, connector and structure. Read result unchanged, never reshape it by hand or guess aliases.
   The result has emailer_campaign plus sideloaded emailer_steps, emailer_touches and emailer_templates arrays. Steps carry id, emailer_campaign_id, position, type, wait_time and wait_mode.
   Touches carry id, emailer_step_id, emailer_template_id, type and include_signature. Templates carry id, subject and body_html. Join the native IDs and order steps by position.
   Compare every native touch's include_signature with its approved step's boolean. A mismatch is FAIL with no enrollment payload.
   Every step must link to emailer_campaign.id. Dangling or duplicate IDs, ambiguous positions and a step without required copy produce STOP.
   Compare mark_finished_if_reply with approved stop_on_reply and emailer_schedule_id with the approved schedule ID. Require sequence_by_exact_daytime false for interval mode.
   Compare each ordered step's wait_time with its approved wait and require wait_mode day. If campaign and sideloaded step lists both exist, IDs, waits and modes must agree or FAIL.
   Copy may match raw or after conservative HTML-to-text normalization. Extracted merge variables and URLs must still match exactly in count and order.
   Record matched after HTML normalization when used, including native html/head/body wrappers. Never substitute approved copy for native evidence.
   Missing documented fields or an unrecognized structure produce STOP with the missing list and no payload. Stop and ask Operator, just as for missing templates.
   Only PASS returns an enrollment payload. FAIL stops with one fix proposal. Only fields outside the connector schema remain not_checked without blocking enrollment.
   The payload carries only id, emailer_campaign_id, contact_ids and send_email_from_email_account_id. Both campaign identifiers must equal emailer_campaign.id. Any other key is FAIL.
   A saved wrapper or inner response carrying truncated, error, isError or authenticated false is STOP before unwrapping. isError false, error null and truncated false are not failures.
3. `apollo_emailer_campaigns_add_contact_ids` with only the approved Contact IDs and that approved sequence. This is the real-send boundary, not a harmless list upload.
   Use only the unchanged PASS payload from event_launch_check. Never rebuild it after the comparison.
4. `apollo_emailer_campaigns_approve` for only the campaign and recipients in that approval.

Save each response outside Git and read back per `references/readback.md` "Readback". Unsupported fields or tool capabilities stay needs-input, never guessed payloads.
If a call times out or returns an ambiguous response, read the native state before any retry. Never blindly reenroll or repeat a send-affecting call.
Any partial result stops later calls until the known state is reconciled. Report one exact fix proposal, without sending fixes automatically.
