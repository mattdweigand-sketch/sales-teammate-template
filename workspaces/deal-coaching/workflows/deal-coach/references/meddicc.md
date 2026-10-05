# MEDDICC

## Evidence scores

Score evidence rather than the rep's belief. Each score needs a source reference. Unread or missing sources leave the element unknown rather than proving a zero.
Use zero when the reviewed evidence establishes that the element is absent. Keep the retrieval limitation beside the score when only part of the history was available.

| Element | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| Metrics | None | Buyer interest without a number. Contract value, purchased credits, and product usage stay at 1 until tied to a buyer-stated workflow result | Buyer-stated before and after for one workflow | Buyer-owned number tied to a business outcome and agreed as the pilot success test |
| Economic Buyer | Unknown in reviewed evidence | Named by someone else | Met or emailed directly | Stated the budget, decision rule, and what they need to see |
| Decision Criteria | Unknown in reviewed evidence | Generic criteria such as security and price | Written buyer list | Buyer ranked criteria and scored the product against named alternatives |
| Decision Process | Unknown in reviewed evidence | Rep's guess | Buyer described the steps | Dated steps with owners, including security, legal, and procurement |
| Paper Process | Unknown in reviewed evidence | Procurement expected to handle it | Paper owner named and whose paper known | Redline path, signer, PO or billing route, and target date confirmed |
| Identify Pain | None | Nice to have | Named pain with a current workaround | Pain with a cost, an owner who feels it, and a trigger for why now |
| Champion | None | Friendly contact | Coach who shares internal information | Has power, sells internally in the rep's absence, and has been tested with an ask |
| Competition | Unknown in reviewed evidence | Assumed | Named alternative, including build or do nothing | Known reasons to choose each option and the wedge against it |

## Stage gates

Use the deal's current Salesforce stage and the matching entry in `policy.coach.stage_gate_minimums`. The `pain` key maps to Identify Pain.
Flag each element below its minimum and cite the evidence needed to close the gap. Unknown elements make the gate unverified, never passed.
For S4, the Metrics standard requires a written pilot success test. These gates guide coaching and do not authorize Salesforce stage changes.
