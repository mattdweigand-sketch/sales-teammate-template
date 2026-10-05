# Close paths

Use `policy.close.path_order`; first match wins. One path per run. State the selecting fact before proposing.
Commercial terms still come from the signed agreement. Whenever `Deal_Type__c` is `policy.close.paid_pilot.deal_type`, use `policy.close.paid_pilot` and its price book
even if self-serve or multi-org selected the path.
Values live in `policy.close`.

For an existing enterprise org with verified customer ownership but missing Account UUIDs, propose B first using the system UUID; after readback, continue the applicable commercial path without A0.
A `Customer_Type__c` in `policy.close.customer_type_stop` has no established close flow: stop and ask before any write.

## Path 1. New annual enterprise contract

Selects when no other path matches. Terms per `policy.close.terms_default`, price book `policy.close.price_books.annual`.
DocuSign completion sets Closed Won automatically; when `StageName` is already Closed Won, proposal A carries only the remaining fields.
Missing Account UUID: link an existing verified enterprise org through B first, or use A0 when provisioning is needed (`workspaces/pipeline/workflows/close/references/setup-trial.md`).
Handoff per `policy.close.handoff_when`.

## Path 2. Self-serve org converting to enterprise

Selects only when `rules#org_lookup` classifies the org as self-serve and establishes customer ownership; a UUID or membership alone is insufficient. The self-serve billing stays live until ops acts.
Proposal B sets `Org_UUID__c` and `Admin_Organization_UUID__c` from the system result and may precede A.
Proposal D asks ops to activate the enterprise subscription on that org and cancel the verified self-serve billing. Handoff required.

## Path 3. Multi-org customer

Selects when the Account or its parent has an org UUID and this deal is another org.
One Account per org UUID; several orgs use child Accounts under one parent through `Parent_Account_Related_List__c`, one Opportunity each.
This run closes one Opportunity; list the sibling Opportunities and their state. Handoff required.

## Path 4. Paid pilot

Selects when `Deal_Type__c` is `policy.close.paid_pilot.deal_type`. Terms per `policy.close.paid_pilot`. An annual-term record with a heavy discount is a mismatch, not a pilot; report it.

## Path 5. Renewal or expansion

Selects when the Account has a prior Closed Won Opportunity with an active subscription and this deal extends or grows it. `Type` is Renewal or Existing Business.
B only fills blanks, including verified enterprise-org linkage before A when missing; membership does not select the self-serve path.
Handoff per `policy.close.handoff_when` or when the org or plan changes.

## Handoff template (proposal D)

```
<Account> is <StageName>, <path name>.
Opportunity: <link>
Org: <UUID or "none on the Account">
Admin: <email>
Terms: <seats>, <term>, <billing interval>, start <date>
Ask: <one sentence, what ops must do>
<mentions from policy.close.ops_owners>
```
