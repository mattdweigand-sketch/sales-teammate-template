# Adoption

## Account resolution

Query Account by Id or Name. Record Id, Name, Website, OwnerId, and open Opportunities per `policy.prospecting.salesforce.open_opportunity`.
Use the `policy.tooling.scripts.prospect_account_route` route table. Only `scan` continues to the warehouse lookup.
One existing Account must be owned by `policy.prospecting.identity.sfdc_user_id`. Missing Accounts are outside_named_accounts. Other owners are owned_elsewhere. Open deals go to Pipeline.
Ambiguous identity stops. Ask for the Operator-owned Account Id before continuing. Never discover or claim another Account.

## Query

Derive the verified Account domain before lookup. Stop when it is in `policy.tooling.internal_domains`. Internal domains are never adoption targets.
Run `policy.tooling.scripts.prospect_adoption_lookup` through the Snowflake connector, read-only, async, warehouse `policy.prospecting.warehouse.name`.
Bind the Account Id, the domain, and `date_pt` (today minus `policy.prospecting.warehouse.data_lag_days`) in header order. Fetch the one result row only after status is success.

## Bundle

Build the bundle with exactly the keys in `policy.prospecting.user_scan.bundle_keys`. Split comma lists into arrays, empty string to `[]`. Cast `mapped_org_count` to int. Set `adoption` to one
value from `policy.prospecting.user_scan.adoption_values` by the rule noted beside that key. Save to a file.

## Handoff

An `individuals_only` bundle can use the existing warehouse outreach path. An `org_adopted` bundle is optional context alongside a qualified web signal, not a standalone outreach signal.
`none_found` supplies no adoption claim. Clean is not approval to draft or contact anyone.

## Report

````
Account: <name> | Salesforce: <Id> | Owner: <name, active/inactive> | Route: scan / active_deal / owned_elsewhere / outside_named_accounts
Domain: <domain> | Data through: <date>
Adoption: org_adopted / individuals_only / none_found
  Org subscription mapped to this Account: yes/no (<service types>, <platforms>) or none
  Paid individual subscribers at <domain>: yes/no
Privacy check: clean
```json
<bundle>
```
none_found: no mapped org and no paid individuals on the data date. Not proof of absence. The org may be mapped to a duplicate Account.
Next: individuals_only may go to signal-outreach; org_adopted needs a qualified web signal; none_found adds no claim.
````

## Boundaries

- Any field in `policy.prospecting.warehouse.forbidden`. Not in the report, not in chat, not roughly.
- Editing the query to add columns. Change the policy and the check first, in a separate approved edit.
- Any write to Salesforce, Snowflake, Gmail, or project files.
- Drafting or wording a message. That is `signal-outreach`.

## Sales authority

Use rules#approval and rules#write_protocol for each exact proposal, approval and native readback. Never treat a live policy mirror as independent approval.
An open Opportunity belongs to Pipeline. Re-read current owner, open Opportunities and duplicates before proposals and again before every approved write.
Never retry a failed or mismatched create blindly. Report the actual partial result and one corrective proposal for approval.
