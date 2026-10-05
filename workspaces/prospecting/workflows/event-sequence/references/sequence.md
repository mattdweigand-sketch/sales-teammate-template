# Event sequence

## Copy and timing

Use `policy.prospecting.event.steps`, `policy.prospecting.event.step_gap_days`, and `policy.prospecting.event.last_touch_before_event_days` as defaults.
Default touches are emails followed by a LinkedIn task. The task creates manual work, not an automated LinkedIn message.
Anchor the final touch to the first attendance date minus the configured last-touch days. Work backwards by the configured gap for each preceding step.
Show every absolute local date and time with timezone, not just relative offsets. The exact schedule is chosen and approved by Operator, never inferred from the sandbox timezone.
If any touch is in the past or the event dates conflict, stop for an exact revised schedule. Do not send immediately or compress gaps without approval.
Draft every subject, full email body, and LinkedIn task instruction using `policy.email_voice` and the event ask. Never invent a relationship, attendance, or recipient fact.
Apply advisory `policy.prospecting.outreach.lint`. Disclose lint flags without treating them as sending permission.
Show the resolved mailbox ID, address, and provider from `apollo_email_accounts_index`. A default mailbox remains a proposal until approved.

## Approval

Present one complete enrollment proposal in the Prospecting thread. Include these items before asking for one explicit approval.
Label it E1. Edits or changed evidence use the next unused E label. Accept only its displayed label or `approved <label>` under `rules#approval`.

- Event name, Operator's attendance dates, location, and ask.
- Original rows, normalized contacts, duplicates, proposed enrollments, needs-input rows, and exclusion counts.
- Exact contacts and emails to enroll, with every exclusion and its reason. Include each named per-list override and the approval evidence for it.
- The bounded reply-check summary from `references/prep.md` "Salesforce and reply checks", with window, query shapes, contacts checked, replies found, holds, and the retrieval limit.
  Attach the saved receipt file to the E1 thread message, not a sandbox-path link.
- Exact subject and full body for every email, and the full LinkedIn task instruction. Include all personalization or rendered variants, not an unspecified template.
- Every step's local send date and time, timezone, gap, schedule window, and first-send time.
- Sending mailbox ID and address, sequence target, stop-on-reply setting, and the enrollment and scheduled-message counts expected on readback.
- Enrichment receipts and spend approvals, scrub PASS, audit PASS, batch reconciliation, and all held domain mismatches.
- Apollo existing-contact identity holds and reasons, active_sequence evidence, and event_app_invite matches or the explicit statement that no invite export was checked.
- Apollo's CRM sync may create or update Salesforce Contacts from approved enrollment. The workflow itself makes no direct Salesforce writes. Include this in E1 and every revised E proposal.

Ask Operator to approve the exact contact list, sequence copy, sending mailbox, and schedule under `rules#event_sequence`, or edit or skip.
State the displayed E label as the response that approves this complete snapshot. `skip` declines it.
Named-account scope cannot be overridden. Operator may override other named exclusions for a named contact in this list.
Display that override with the exact recipient, reason, copy, mailbox, and schedule.
Edits or changed evidence require a new exact proposal except the narrowing-only reply recheck in "Enrollment". Unanswered, skipped, needs-input, and unapproved contacts never enter enrollment.
Do not rely on a past campaign's approval, mailbox defaults, helper labels, or a generic approval of the event idea.
Apollo add-to-sequence sends real email and cannot be undone once sent. Say so before the approval question. Never create drafts in Gmail as a substitute sending route.

## Enrollment

Immediately before writing, re-read Account ownership and open Opportunities for every approved contact, with complete pages.
Only existing Accounts still owned by `policy.prospecting.identity.sfdc_user_id` can enroll. No revised proposal or list override expands that scope.
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
2. `apollo_sequences_create` for one sequence, or `apollo_sequences_update` only on the exact existing sequence Operator approved. Set the approved copy, steps, mailbox, schedule, and stop on reply.
   Save the full create or update response in the sandbox, including native steps, touches, and templates with subject and body, for copy readback.
   Never substitute the approved proposal for returned native copy evidence.
   Before step 3, compare the saved response with the approved snapshot using `references/readback.md` "Readback" copy rules.
   Compare steps, touches, subject and body templates, merge variables, schedule and stop on reply. Normalize only the HTML Apollo sanitizes and require exact merge variables.
   If the response has no templates, stop before step 3 and ask Operator. Never enroll copy that has not been compared.
   Any mismatch or unexplained difference stops before step 3 with one fix proposal. Never call add_contact_ids or approve on unmatched copy.
3. `apollo_emailer_campaigns_add_contact_ids` with only the approved Contact IDs and that approved sequence. This is the real-send boundary, not a harmless list upload.
4. `apollo_emailer_campaigns_approve` for only the campaign and recipients in that approval.

Save each response outside Git and read back per `references/readback.md` "Readback". Unsupported fields or tool capabilities stay needs-input, never guessed payloads.
If a call times out or returns an ambiguous response, read the native state before any retry. Never blindly reenroll or repeat a send-affecting call.
Any partial result stops later calls until the known state is reconciled. Report one exact fix proposal, without sending fixes automatically.
