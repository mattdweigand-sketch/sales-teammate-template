# Setup trial (proposal A0) and restoration (proposal R)

Use A0 only when the Account lacks an org UUID and an existing org cannot be linked. Values live in `policy.close.setup_trial`.
The Opportunity update fires its `flow_name`, which calls ADMIN, creates the org, writes `Admin_Org_Subscription_Id__c` and `Account.Admin_Organization_UUID__c`,
stamps `Admin_Last_Sync_Time__c`, and resets the checkbox.
`Org_UUID__c` stays blank until B copies the verified UUID. ADMIN emails the admin an invite; disclose these effects before approval.

## Before proposing A0

1. Use the admin email resolved per `workspaces/pipeline/workflows/close/references/evidence.md`, never `Admin_Email__c` as stored and never an address in `policy.tooling.internal_domains`.
2. Inspect the org lookup from `workspaces/pipeline/workflows/close/references/evidence.md` "Admin email and org status".
   An existing customer-owned enterprise org uses B-first linkage; a verified self-serve org selects path 2. Neither needs A0.
   Unknown membership or billing type, including an inconclusive 404, needs clarification before provisioning; do not infer a cancellation request from membership.
3. Fresh-read and capture every `policy.close.setup_trial.restore_after` field. Show the exact current-to-new value for every A0 payload field, with resolved dates, tier, and email.
   State that it creates an org and sends an admin invite. Approval applies only to this displayed Opportunity update and those stated effects.

## Apply and verify A0

Write once per `rules#write_protocol`.
Poll the setup-trial fields in `workspaces/pipeline/workflows/close/references/fields.md` using `policy.close.setup_trial.poll` until `success_fields` hold;
call it blocked only after the last read.
A polling timeout does not prove ADMIN has stopped; report downstream status as unresolved. A reset checkbox and sync time prove that the flow ran, not that provisioning succeeded.
Never retry the same payload more than once, and never retry without a new displayed approval.

On `user_already_in_org`, inspect the returned system org and classify it before proposing B or path 2; do not automatically select self-serve.
For other errors or timeout, quote the error/status, hold A, and propose the appropriate D. These outcomes still require the restoration review below.

## Independent restoration R

After every terminal attempt (success, failure, or polling timeout), fresh-read the Opportunity and compare only `policy.close.setup_trial.restore_after` fields
with the captured pre-A0 values and agreement.
Present R immediately, even if A is declined, skipped, or blocked. If A0 was never applied, verify no temporary change occurred and say no restoration is needed.

For each differing temporary field, show its live value and its evidenced agreement value, or its captured pre-A0 value when the agreement is silent.
Preserve a concurrent change: flag any value that differs from both the applied A0 payload and the intended restore target, and resolve it before proposing an overwrite.
If the captured value or agreement is unavailable, ask; never invent a restore value.

R is one independently approved Opportunity update, limited to those named fields.
Apply with a fresh read and readback per `rules#write_protocol`; approval of A0, A, B, or a Slack handoff does not approve R. No differences means a verified no-change result.
If R is skipped or fails, report the exact remaining temporary values and owner/action; do not claim recovery or completion.

Restoring Salesforce fields does not prove an org, subscription, invite, or other downstream effect was reversed. Report those effects separately from system evidence or an ops owner's reply.
Resolve outstanding temporary terms and verify org linkage before proposing Closed Won.
