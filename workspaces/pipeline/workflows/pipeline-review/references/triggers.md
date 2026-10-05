# Triggers

Read at the Flag step. Names match `policy.pipeline.triggers`.

`hygiene_check` emits every trigger it can compute from Salesforce; the run adds `new_activity` from mail and calendar. One proposal per flagged deal.
- `next_passed`: the next-step action's due date is before today, not the entry's written date.
- `new_activity`: an inbound buyer email (Task Subject `policy.pipeline.inbound_subject_prefix`, or inbox mail from the Account domain) or a held meeting, dated after the newest note.
  An elapsed calendar event is not a held meeting; display it as `elapsed, attendance unverified` and never use it as a write basis.
- `blank_field`: a required or conditional field is blank, or the current next-step entry is missing, malformed, or has an unresolved due date.
- `date_at_risk`: CloseDate is past, or within `policy.pipeline.close_warning_days` while StageName is below `policy.pipeline.date_at_risk_below_stage`.
- `stale`: no Task or Event within `policy.pipeline.stale_days`, no upcoming Event, and the next-step due date has passed or is missing. A live next step is not stale.
  An unresolved next-step date requires review before a stale-based write.
- `task_gap`: the current-action Task count or date fails `rules#followup_task`; later scheduled-Event milestone candidates still need action and linkage review before retention.

Friday only, `hygiene_check` also checks `policy.pipeline.early_stages` against `policy.pipeline.early_required_fields` and marks review_scope qualification.
S1 Amount missing or zero emits blank_field with Amount in blank_fields. S0 does not inherit S2 required fields. Other days keep the ordinary hygiene scope.
Qualification reviews every early-stage deal, not only flagged ones. A mechanical stale or last-activity receipt is not proof of buyer silence.
