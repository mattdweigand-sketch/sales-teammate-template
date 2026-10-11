# Drafts

Read while preparing every full draft for the main proposal, then when creating approved drafts.

Follow `policy.email_voice` and `rules#email_body`. Every follow-up continues the prior email read in `references/collect.md` "Gather evidence" item 6.
It names one specific claim, offer, or question from that email and moves it forward with one new fact or a sharper ask. `rules#email_body` decides when a timing or break-up note replaces the ask.
A question the prior email did not set up is not a follow-up. Write for a cold read. Restate the referenced point in plain words instead of pointing at it. Short sentences, one idea each.
If the ask is not clear in five seconds without the thread, rewrite. Reply in the existing thread when one exists. Pass `thread_id` only, not `reply_to_email_id`.
The draft tool rejects a reply whose recipients omit the parent's sender or any parent recipient, and the thread-only form avoids that rule while keeping the thread.
Gmail quotes the thread's newest message under the body.
If that message is from `policy.email_voice.computer_sender`, the quote carries internal notes, so flag the draft in the readout as `Quoted Computer note, delete before sending`.
Prepare the exact draft body and metadata before the main-pass approval question. Do not create it until its displayed row is approved.
Before creating an approved draft, refresh its Contact's Gmail reads and rerun `gmail_contact_stats --send-hold` with `--as-of` set to this check's current aware timestamp.
This hold-check timestamp does not reset run_start. A newly blocked or unread hold stops that draft and its contingent writes, never bypasses timing or reuses stale evidence.
An approved numbered draft row covers its displayed contingent completion and next Task.
Create and verify the draft, then read back any displayed next step, then verify or create/read back the matching Task before completing the old one, without another question.
After creating the approved batch, list drafts once and read each new draft back; confirm To, CC, Subject, and full body match the approved row.
Only a draft triage created after approval and verified by readback qualifies as action evidence. A failed or unverified draft gets no next-step, completion or next-Task write.
The next Task records the draft id and thread link and first checks whether that exact draft was sent. If not, flag `Draft not sent`, never a new follow-up.
Report `Draft ready` only for verified rows. Keep existing drafts as blockers rather than counting them as newly completed actions.
Deal Task follow-up drafts use this same path. Read the deal thread for context only, then prepare, approve, create and verify the draft here. Never delegate its proposal. Never send.
