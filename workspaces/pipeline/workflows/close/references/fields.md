# Fields read and checked at close

Query all of them at the Resolve step on the Opportunity, its Account, line items, and Contact Roles.
Also read the Account's other Opportunities (`StageName`, `Type`, `Subscription_Start_Date__c`, `Subscription_Cancel_Date__c`) and the Account's `Parent_Account_Related_List__c`.
Sources: A = signed agreement, R = existing record, S = system (admin tool, NetSuite, DocuSign, Ironclad). A field with source S is never typed by hand.

## Opportunity terms (preflight)

| Field | Source | Expected |
|---|---|---|
| `Type` | A | `policy.close.terms_default.type`; Renewal or Existing Business on path 5 |
| `Deal_Type__c` | A | agreement value from the live picklist; `policy.close.paid_pilot.deal_type` selects path 4 |
| `Customer_Type__c` | A | agreement value; stop values are owned by `policy.close.customer_type_stop` |
| `Subscription_Type__c` | A | `policy.close.terms_default.subscription_type` |
| `Subscription_Billing_Interval__c` | A | `policy.close.terms_default.billing_interval` unless the preflight records a Deal Desk approval or the user's confirmation |
| `Billing_Terms__c` | A | `policy.close.terms_default.billing_terms` unless the agreement says otherwise |
| `Contract_Term__c` | A | `policy.close.terms_default.contract_term_months`; pilots per `policy.close.paid_pilot.contract_term` |
| `Subscription_Start_Date__c`, `Subscription_Cancel_Date__c` | A | contract start and end. Never reset after signature |
| `Trial_Expiration_Date__c` | A | per `policy.pipeline.conditional_fields` |
| `Admin_Email__c`, `Admin_Invite_Tier__c` | A | the admin email resolved per `references/evidence.md` "Admin email and org status", and the named tier or `policy.close.setup_trial.tier_default`. A stored email that differs from the resolved one is a contradiction |
| `Pricebook2Id` | R | per `policy.close.price_books` for the path |
| `Amount`, `Total_Contract_Value__c`, `Credits_Purchased__c` | R | formulas from line items |
| `Contract_Status__c` | A | Signed |
| `Purchase_Order_Number__c`, `Special_Terms__c` | A | when the agreement carries them |
| `LeadSource` | R | must be set (`policy.salesforce.validation_rules`) |

## Preflight outcomes

Compare each term field above to the agreement. Three outcomes, listed by field:

- Matches: no proposal.
- Blank, value in the agreement or on the record: proposal.
- Blank, no source: ask. A validation failure is never permission to invent a value.

A record value that contradicts the agreement is reported, and the proposal moves the record to the agreement, never the reverse.
A billing interval other than `policy.close.terms_default.billing_interval` needs a Deal Desk approval link from `policy.close.deal_desk_channel` or the user's confirmation, quoted.
Show the pilot's actual charge next to its annualized Amount per `policy.close.price_books`.

## Contact Roles (Resolve, proposal C)

`SELECT ContactId, Contact.Name, Contact.Email, Role, IsPrimary FROM OpportunityContactRole WHERE OpportunityId = '<Id>'`, and describe `OpportunityContactRole.Role` for the live picklist.
Roles are evidence for C only; the admin email comes from `workspaces/pipeline/workflows/close/references/evidence.md`, never from a Role.

## Setup trial (proposal A0)

Fields per `policy.close.setup_trial.payload` and `.restore_after`. Capture the latter before A0; proposal R restores only those fields in a separate approved Opportunity update.
Read at verify: `Sync_Free_Trial_to_ADMIN__c`, `Admin_Last_Sync_Time__c`, `ADMIN_Error_Message__c`, `Admin_Org_Subscription_Id__c`, `Account.Admin_Organization_UUID__c`.

## Line items (preflight)

`SELECT Product2.Name, Quantity, UnitPrice, ListPrice, Discount, TotalPrice FROM OpportunityLineItem WHERE OpportunityId = '<Id>'`. Required at Closed Won. Check seats and credits equal the agreement.
Credits per `policy.close.credits`. Line items are edited by hand in Salesforce, not proposed here. A mismatch or missing line item is needs-input naming who fixes it, Deal Desk or Operator, and
holds A.

## Win fields (proposal A)

`Closed_Won_Notes__c` (why we won), `Use_Cases__c` (what they will do), `Next_Steps__c` (onboarding entry).

## Account (proposal B)

Written: `Billing_Email__c`, `Billing_Point_of_Contact__c` (Contact), `Org_UUID__c`, `Admin_Organization_UUID__c`, `Became_a_Customer_On__c`, `Customer_Type__c`.
Read for path selection only: `Customer_Status__c`, `Parent_Account_Related_List__c`, `Primary_Organization__c`.

## Signature

Fields behind `policy.close.signature_evidence`: `Paid_Contract_Signed__c`, `Ironclad_Contract_Signed__c`, `ironclad_Contract_Signed_Date__c`, `Signed_Contract_URL__c`, `Contract_Status__c`.

## Downstream status

| Item | Field | verified when |
|---|---|---|
| NetSuite subscription | `Netsuite_Sync_Status__c`, `Netsuite_Subscription_ID__c`, `Netsuite_Error_Message__c`, `Bypass_Netsuite_Sync__c` | SUCCESS with an ID. FAILED = blocked, quote the message. Bypass true = `not applicable`, say so |
| Admin org subscription | `Admin_Org_Subscription_Id__c`, `ADMIN_Error_Message__c`, `Admin_Last_Sync_Time__c`, `Sync_Subscription_to_ADMIN__c` | ID present. Error text = blocked |
| Org linked to Account | `Account.Admin_Organization_UUID__c`, `Account.Org_UUID__c` | both set and equal, or ops confirms the intended linkage |
| Stripe cancelled (self-serve path) | none | ops owner reply in the handoff thread |
| Invoice issued | none | ops owner reply or NetSuite evidence the user supplies |
