# Sequencer Lead Scrub Process

This tool performs deterministic CSV hygiene after Apollo email verification and before batching for the approved sequence.
A scrub PASS does not prove email verification, authorize credit spending or approve enrollment. Keep eligibility and every approval in the event contract.

## Run

Use the prepared Python and registered helper notation in `_core/scripts/interfaces.md` "Running". Keep all files in the sandbox.

```bash
policy.tooling.scripts.event_scrub_leads \
  scrub \
  /path/to/raw.csv \
  --output-dir /path/to/output-folder \
  --chunk-size 25000 \
  --max-clean-chunk-mb 10 \
  --output-profile final \
  --clean-column-profile full
```

Then independently audit the clean chunks:

```bash
policy.tooling.scripts.event_scrub_leads \
  audit-clean-output \
  /path/to/output-folder/clean_chunks \
  --report /path/to/output-folder/audit_clean_output_report.json
```

The scrubber auto-detects email-finder columns and selects the farthest-right non-empty candidate per row. This supports waterfall outputs where later columns represent more recent or
preferred finder results. Use `--email-column "Column Name"` only when you need to force a specific source column.

## Output Contract

- `clean_chunks/clean_part_001.csv`, `clean_part_002.csv`, etc. Each file has at most 25,000 clean rows.
  After independent audit PASS, route full-column chunks to `policy.tooling.scripts.event_make_batches`.
- `removed_leads.csv` holds rows excluded from enrollment. In final mode, this includes internally removed and internally quarantined rows, with source and diagnostic columns.
- `output_manifest.json`: deterministic output proof with selected email columns, row counts, file sizes, and SHA256 hashes for clean chunks and removed rows.
- `audit_report.json`: machine-readable audit.
- `audit_report.md`: human-readable audit summary.

The workflow uses `--clean-column-profile full`. Full clean chunks retain source columns, including Website for batch domain checks, with selected email normalization and these diagnostic fields.
Removed rows retain source and diagnostic columns in both clean-column profiles.
Review mode puts quarantined rows in a separate `quarantine_leads.csv` with the same fields.

- `normalized_email`
- `local_part`
- `domain`
- `scrub_status`
- `reason_codes`
- `matched_rule_ids`
- `validator_votes`

The scrubber also adds:

- `raw_selected_email`
- `selected_email_column`

The default `--clean-column-profile upload` is a reduced clean-column profile, not this workflow's handoff. It includes only these fields, with normalized Email.

- `First Name`
- `Last Name`
- `Title`, when present
- `Company Name`
- one company website/domain column, when present
- `LinkedIn`, when present
- `Email`

The default `--max-clean-chunk-mb 10` also rolls to a new clean chunk before the current one exceeds the limit. `removed_leads.csv` may be larger because it is never enrolled.

## Operator Checklist

Before sending files forward:

1. Confirm `audit_report.md` says `Status: PASS`.
2. Confirm `audit_clean_output_report.json` says `"status": "PASS"` and has no failures.
3. Confirm `output_manifest.json` exists.
4. Confirm each `clean_chunks/*.csv` row count is 25,000 or fewer.
5. Confirm each `clean_chunks/*.csv` file size is less than 10 MB.
6. Route only full-column `clean_chunks/*.csv` to `policy.tooling.scripts.event_make_batches`. Retain Website and review every domain hold.
7. Keep removed and quarantined rows out of enrollment. Reconcile list counts and hold reasons before the exact Apollo enrollment approval.
8. Keep separate enrichment-credit approvals, Apollo verification, catch-all exclusions and domain checks. Clean output never overrides eligibility.

For repeatability checks, compare `output_manifest.json` between runs. With the same input file, rules version, command options, and script version, the manifest should match.

## Fail-Closed Model

The clean chunks are allowed only when every deterministic validator votes `CLEAN`.

If any validator votes `REMOVED`, the row goes to `removed_leads.csv`.
If no validator votes `REMOVED` but any validator votes `QUARANTINE`, the row is still treated as failed in final mode and goes to `removed_leads.csv`.

Use `--output-profile review` during rule tuning if a separate `quarantine_leads.csv` is useful. Do not use review mode for final handoff outputs.

After writing clean chunks, the script re-reads them and audits them from scratch. Any failure writes `failure_report.json` and exits non-zero.

## Updating Rules

Rules live in the adjacent `scripts/email_rules.json` within this workflow.

When adding a new risky pattern:

1. Add the rule to the relevant list.
2. Add or retain the source URL and retrieval date if the rule comes from a platform/policy source.
3. Re-run the scrubber against a fixture containing that pattern.
4. Confirm the pattern is removed or quarantined before using new clean chunks.

## Test

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest _core.tests.test_event_scrub_leads -v
```
