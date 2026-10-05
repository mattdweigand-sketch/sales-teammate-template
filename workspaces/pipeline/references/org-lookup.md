# Org lookup

Fields returned by `policy.tooling.org_lookup_tool` and what each proves. Cited by `rules#org_lookup`.
Add a dated observation when a lookup teaches something new. Change a mapping only after Operator confirms.

## Fields

| Field | Meaning and proof |
|---|---|
| `org_uuid` | The org id. Never resolved by name. Enterprise ownership needs it equal to the Account's `Org_UUID__c` and `Admin_Organization_UUID__c`. |
| `org_name` | As returned. |
| `org_service_type` | `WHITE_GLOVE` is an enterprise org. `SELF_SERVE` is a self-serve org. Any other or missing value is unverified until Operator confirms the mapping here. Never a product tier. |
| `user_role` | `ADMIN` on a customer address, with matching UUIDs or ops confirmation, evidences customer ownership of an enterprise org. Membership proves nothing about billing. |
| `billing_status` | As returned. |
| `billing_quantity` | Billed seats. Never merged with or substituted for `member_count`. |
| `member_count` | Members. Never merged with or substituted for `billing_quantity`. |
| `stripe_customer_email` | On a customer address, evidences customer ownership of a self-serve org, whichever member was looked up. Often null on enterprise orgs, where its absence proves nothing. |

## Observations

- 9/26/26 smoke runs on four Accounts. `org_service_type` returned `WHITE_GLOVE` for enterprise orgs and `SELF_SERVE` for self-serve orgs. No other values seen.
- 9/26/26 self-serve org. The looked-up address returned `user_role` MEMBER and `stripe_customer_email` matched a different Contact on the same Account.
  Basis for the Stripe-on-any-customer-address rule.
- 9/26/26 enterprise org with `stripe_customer_email` null. Basis for the rule that a null Stripe email on an enterprise org proves nothing.
- No explicit no-org response has been observed. HTTP 404 remains unverified status, not proof of no org.
