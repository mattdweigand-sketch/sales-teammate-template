# Signature and org evidence

Read at the Signature and Path steps.

## Signature evidence

Closed Won needs one item from `policy.close.signature_evidence`, quoted. A call, verbal yes, booking form, or sent order form never counts.
Without it stop and say `No signature evidence.` Establish the actual signature date separately: use `ironclad_Contract_Signed_Date__c` when supported, else the date in the quoted evidence.
A true flag, URL, or statement that the deal is signed does not establish its date. Ask for the missing date before proposing a CloseDate change; never substitute today or the planned CloseDate.

## Admin email and org status

Resolve the admin email from the signed agreement text, else from the address the user explicitly designates, else ask.
Never take it from `Admin_Email__c` or a Contact Role; the stored field is compared to this resolved value in the preflight like every other term field.
Run `policy.tooling.org_lookup_tool` on the resolved email per `rules#org_lookup`. Distinguish a verified self-serve org, a verified enterprise org, and unverified status.
Membership alone never proves self-serve billing. Unverified status needs clarification before provisioning or selecting a self-serve cancellation handoff.
