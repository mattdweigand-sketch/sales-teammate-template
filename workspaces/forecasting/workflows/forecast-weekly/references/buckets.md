# Buckets, pull-ins, and CRM proposals

Read at the Bucket step.

Interpret timing, activity, and blockers from the combined evidence, quoting the source.
For current-quarter deals, a buyer-stated delay past quarter end excludes the deal before either bucket is considered. Then test in order:

- Commit: S4 or S5, or S3 with a buyer-named signature/decision date inside the quarter. Activity within `policy.forecast.activity_days` from any allowed source.
  No open blocker without a named owner and date.
- Upside: S2 or S3 with `policy.forecast.amount_field` set. Activity within `policy.forecast.activity_days` from any allowed source.
- Excluded: everything else; name the failed condition and its source. A passed CRM CloseDate alone does not exclude; it becomes a proposal.

Pull-in candidates are next-quarter S2+ deals with `policy.forecast.amount_field` set, where the buyer confirmed reviewing a sent proposal/order form
or named a signature/decision date inside this quarter.
An Amount without ARR ranks as blank and does not meet either size gate. Never fall back to Amount.
No further stage gate or date window. They are ranked separately and never counted in the call or buffer.

Where fresher allowed evidence supports a CloseDate or Next Step fix, hand it to Pipeline with current value, proposed correction and source.
Use `rules#close_date_basis` and `rules#next_steps` to describe the evidence, not to authorize a Forecasting write. Pipeline owns the matching Task and its own approval.
Forecasting may propose Contact Email and ForecastCategoryName only. Never apply CloseDate or Next_Steps__c here, even if a reply asks to approve the handoff.
Propose `ForecastCategoryName` from `policy.forecast.forecast_category_map` only when it differs; excluded deals keep their category. Each proposal is one record per approval.
