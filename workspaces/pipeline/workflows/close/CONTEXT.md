---
cadence: one-off
reads: _core/policy.yaml (salesforce, tooling, pipeline, close), _core/rules.md, references/, Salesforce, org lookup, Slack
writes: Salesforce Opportunity, Account, Contact Role, Task records and one Slack post, on approval
next: none, downstream status is verified in step 9
---

# Close

One signed Opportunity in, Closed Won verified, downstream done or handed off with a named owner. Salesforce is the record; the signed agreement is the authority for terms.

## Inputs

| Source | File/Location | Section/Scope | Why |
|---|---|---|---|
| Core policy | `_core/policy.yaml` | `salesforce`, `tooling`, `pipeline`, `close` blocks | Evidence types, terms, paths, setup trial, and ops channel |
| Core rules | `_core/rules.md` | `rules#run_start`, `rules#approval`, `rules#write_protocol`, `rules#note_prefix`, `rules#next_steps`, `rules#next_steps_format` | Run start, approval, and writes |
| Core rules | `_core/rules.md` | `rules#org_lookup`, `rules#stage_move` | Org status and stage ownership |
| Reference | `references/fields.md` | Full file at step 2 | Fields read, expected, and verified throughout the run |
| Reference | `references/evidence.md` | "Signature evidence" at step 3; "Admin email and org status" at step 4 | What proves signature and org ownership |
| Reference | `references/paths.md` | Opening and the selected path at step 4; "Handoff template (proposal D)" when D applies | Path selection and the ops post |
| Reference | `references/proposals.md` | "Labels" at step 6; "Apply" at step 8 | Proposal payloads A0, R, and A to E |
| Reference | `references/setup-trial.md` | Full file, only when A0 applies or after any A0 attempt | Provisioning and restoration R |
| Org skill | `configured-crm-guide` | Only when a Salesforce validation message needs interpreting | Validation rule meaning |
| Per-run evidence | The signed agreement, Salesforce reads, org lookup results, and ops channel search saved in the sandbox | This Opportunity and Account | Terms, status, and prior handoffs |

## Process

1. Start per `rules#run_start`.
2. Resolve `/close <Opportunity URL or Id>`; no Opportunity means ask. Read every field in `references/fields.md`.
3. Check signature evidence per `references/evidence.md` "Signature evidence". Without it, stop and say `No signature evidence.`
4. Resolve the admin email and org status per `references/evidence.md`, then select one path per `references/paths.md`.
5. Preflight every term field per `references/fields.md` "Preflight outcomes".
6. Propose per `references/proposals.md` "Labels", reading `references/setup-trial.md` for A0 and R.
7. Wait. Each proposal applies on `approved <label>` per `rules#approval`; `skip` is an answer. Apply only after a proposal's dependencies hold.
8. Apply per `references/proposals.md` "Apply" and `rules#write_protocol`.
9. Verify downstream per `references/fields.md` "Downstream status". Report each item as `verified`, `pending`, `blocked` with the error text, or `not applicable`.
10. Close with one header line (Closed Won date, proposals applied, then each skipped or needs-input label named per `rules#approval`),
    then one line per downstream item with its status and the owner of anything pending.

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 4 | A missing signature date, unverified org status, a missing admin email, or a stop `Customer_Type__c` | The missing fact, or how to proceed, before any write |
| 6 | Labeled proposals with current and new values, including A0 effects and any R | `approved <label>` per proposal, or `skip` |

## Audit

| Check | Pass Condition |
|---|---|
| Signature, before step 6 | One quoted item from `policy.close.signature_evidence` and a separately established signature date. Never today or the planned CloseDate |
| Org status, before step 6 | Every decision that depends on org status rests on a verified `rules#org_lookup` result. A 404 or error prints `Org status unverified for <email>: <response>` and blocks it |
| Preflight, before step 6 | Every term field matches the agreement, has a proposal, or is asked. A record never overrides the agreement. A non-default billing interval has a quoted Deal Desk link or user confirmation |
| A0 and R, before step 6 and after every A0 attempt | A0 is proposed only when no existing org can be linked, with its effects shown. R is presented after every terminal A0 attempt and approved on its own |
| Closed Won hold, before applying A | Org linkage is verified and outstanding temporary terms are resolved |
| Handoff dedupe, before proposing and before posting D | `policy.close.ops_channel` was searched. An open post with the same reason means `reuse existing`, never a second post or an edit |
| Downstream, at step 9 | Stripe cancellation, invoice issued, and org linkage are verified only by a system field or an ops owner's reply. Nothing is inferred |
| Scope, throughout | No Closed Lost (route to `pipeline-review`), no free trial outside A0, no org UUID resolved by name, and a verified Closed Won is never reopened or undone |

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Proposed changes | Run thread | Labeled A0, R, and A to E, current value to new value |
| Salesforce updates | Opportunity, Account, Contact Role, and Task records, after approval only | The approved payload, read back per `rules#write_protocol` |
| Slack handoff post | `policy.close.ops_channel`, after approval only | `references/paths.md` "Handoff template (proposal D)", for the named ops owners |
| Close summary | Run thread | Step 10 header line and one line per downstream item for Operator, with named owners for pending work |
| Saved results | Sandbox | Query, lookup, and search outputs, never Project Files |
