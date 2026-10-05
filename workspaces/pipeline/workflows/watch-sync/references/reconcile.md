# Watch reconciliation

## Read

1. Query all open Opportunities owned by `policy.prospecting.identity.sfdc_user_id` in S1 and `policy.pipeline.stages`.
   Retrieve Account, StageName, CloseDate, Contact Roles, and Customer_Point_of_Contact__c, resolving every contact's email domain.
   Ignore `policy.tooling.generic_email_domains` and list those contacts separately. Missing email or unresolved contact is not checked.
2. Discover the three active-deal buyer-email automations from the current project's approved configuration inventory.
   Read each with `pplx automation get`, including every `from_address contains` filter. Use live IDs, never repo-stored IDs.
3. Read the account-name condition in the four shared-channel watches for deal desk, GRC help, enterprise security questions, and legal hub.
   Use the same approved inventory to resolve live IDs. Compare only open Opportunities in `policy.pipeline.stages`. One account change applies to all four.
   A missing, ambiguous, unreadable, or incomplete inventory means the affected comparison is not checked. Do not guess a consumer.
4. For every Account with an open Opportunity in `policy.pipeline.stages`, search current project sessions by Account name with `pplx project sessions list --search`.
   Match the exact `<Account> deal` title. Also inventory all such deal threads to identify Accounts with no open in-scope Opportunity.
5. Read Operator's explicit retained-thread exceptions from approved source-thread or configuration evidence.
   If that list cannot be read completely, do not propose any archive. Report the missing exception evidence.

## Compare and route

- Compare deduplicated contact domains from S1 and the pipeline stages against each buyer-email watch's live filters. Show domains to add or drop with Opportunity evidence.
- Compare deduplicated Account names from the pipeline stages only against all four shared-channel watches. Show each add or drop once, applying to all four.
- Propose one deal thread for each Account without an exact match. Show Opportunity Id, stage, and CloseDate. Ambiguous thread matches need input.
- Propose archiving an existing deal thread only when complete CRM reads show no open in-scope Opportunity and it is not explicitly retained by Operator.
- Number thread proposals after the domain and account proposals. Label the group `Deal threads, needs Operator approval`.
- Post one line per proposal in the run thread and send the same list with `pplx automation notify-source --message`.
  Pipeline handles configuration proposals under its existing authorization. Thread changes are not applied on receipt.
- If no actionable differences remain, give one line and suppress the run notification. Report not-checked reads rather than claiming a clean sync.
- Keep current automation IDs, customer names, contacts, and retained-thread lists in the sandbox or requesting thread, not the repository.
