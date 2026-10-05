# Proposals

Read at the Propose step, and "Apply" again after approval. Labeled, one record per approval, current value to new value.
Each proposal applies on `approved <label>` per `rules#approval`; use separate labels when several Contact Roles are missing.

## Labels

- **A0. Setup trial.** Closed Won requires an Account org UUID. Use an existing verified org through B when available; A0 applies only when no existing org is established and provisioning is needed.
  Read `workspaces/pipeline/workflows/close/references/setup-trial.md`. One Opportunity update per `policy.close.setup_trial`; display all resolved changes and the org-create/admin-invite effects.
  Declined or failed: hold A and propose the appropriate D. An inconclusive precheck is not permission to provision.
- **R. Restore temporary fields.** After every terminal A0 attempt, including failure, timeout, or success followed by a skipped close,
  fresh-read and independently propose restoration per `workspaces/pipeline/workflows/close/references/setup-trial.md`.
  Approval of A or B does not approve R. If nothing differs, show the verified no-change result; unresolved effects remain visible.
- **A. Closed Won update.** One Opportunity update carrying:
  - `StageName` Closed Won and `CloseDate` = the evidenced signature date from `workspaces/pipeline/workflows/close/references/evidence.md` "Signature evidence".
  - `Closed_Won_Notes__c` and `Use_Cases__c`, each a new line per `rules#note_prefix`, between `policy.close.win_note_min_chars` and `policy.close.win_note_max_chars`
    (`policy.salesforce.validation_rules`), quoting the buyer where possible.
  - The remaining approved term changes from the preflight.
  - `Next_Steps__c` per `rules#next_steps_format` with the onboarding action.

  Never `NextStep`. When `StageName` is already Closed Won, say `Closed Won on <CloseDate>` and A carries only the remaining fields.
  Hold a Closed Won change until the org linkage verifies and outstanding temporary terms are resolved. Restoration is R, not part of A.
- **B. Account.** When linking before A, the displayed B proposal contains only `Org_UUID__c` and `Admin_Organization_UUID__c` from the verified system result; no commercial or customer-date fields.
  After A readback (or verification that the Opportunity is already Closed Won), separately propose any remaining `Billing_Email__c`, `Billing_Point_of_Contact__c`,
  `Customer_Type__c`, and blank `Became_a_Customer_On__c` from the evidenced signature date or verified Closed Won CloseDate.
  Never use a planned CloseDate as a customer date. Use distinct labels and approvals when B is split; each update is still one Account record.
- **C. Contact Roles.** Only a missing sales role that is evidenced for a named Contact and exists in the `Role` picklist read at the Resolve step.
  Admin or signer status establishes no sales role by itself, and no Admin or Signer picklist value exists. With no evidenced valid role missing, C proposes nothing.
- **D. Slack handoff.** Only when the path or a downstream status in `policy.close.handoff_when` calls for it.
  Before proposing, search `policy.close.ops_channel` for an existing post naming this Opportunity.
  An existing post with the same handoff reason and an open thread means show its link and disposition `reuse existing` and propose no new post.
  A completed thread or a different reason allows a new post that links the earlier one. Never edit an existing post.
  Exact text per the template in `workspaces/pipeline/workflows/close/references/paths.md`, to `policy.close.ops_channel`, mentioning `policy.close.ops_owners`.
  Re-run the search immediately before posting; approval may be hours old.
- **E. Follow-up Task.** Only when D was posted or a downstream status is pending.
  First query `SELECT Id, Subject, ActivityDate, Status FROM Task WHERE WhatId = '<OppId>' AND IsClosed = false`.
  An open Task awaiting the same downstream item is reused or rescheduled by Id, never duplicated.
  Otherwise propose a Task due today plus `policy.close.followup_days`, Subject naming the downstream item awaited,
  linked to the Opportunity and to the Contact whose email is the resolved admin email, else the primary Contact Role.

Then wait. `skip` is an answer; if A is skipped after A0, still present R and record its disposition. Approvals may arrive in any order, but apply only after each proposal's dependencies hold.
D's first line reads the live `StageName`.

## Apply

Writes per `rules#write_protocol`. A verified Closed Won is never reopened or undone by this skill.
