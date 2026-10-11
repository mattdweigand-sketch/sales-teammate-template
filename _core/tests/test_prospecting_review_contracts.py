"""Guard the Prospecting evidence boundaries clarified by the hostile review."""
from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
PROSPECTING = ROOT / "workspaces/prospecting"
SIGNAL = PROSPECTING / "workflows/signal-prospecting"
EVENT = PROSPECTING / "workflows/event-sequence"


class ProspectingReviewContracts(unittest.TestCase):
    def test_warm_engagement_policy_recognizes_outbound_sync_replies(self):
        policy = yaml.safe_load((ROOT / "_core/policy.yaml").read_text())
        markers = policy["prospecting"]["scan"]["warm_engagement"]["task_subject_markers"]
        prefixes = tuple(marker.casefold() for marker in markers)
        for subject in (
            "Re: Synthetic enterprise demo",
            "Email: << Re: Synthetic enterprise demo",
            "Email: >> Re: Synthetic enterprise demo",
            "email: >> re: Synthetic enterprise demo",
        ):
            with self.subTest(subject=subject):
                self.assertTrue(subject.casefold().startswith(prefixes))
        self.assertFalse("Email: >> Synthetic first outreach".casefold().startswith(prefixes))

    def test_enrichment_scope_prose_admits_existing_outreach_owner_candidates(self):
        prep = (EVENT / "references/prep.md").read_text()
        conventions = (ROOT / "_core/CONVENTIONS.md").read_text()
        sequential = conventions.split("## Sequential workspaces\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn(
            "Only helper enrichment_candidates inside the configured named-account or outreach-owner scope "
            "whose only exclusion is unverified_email enter enrichment.",
            prep,
        )
        self.assertIn(
            "Prospecting has two direct workflows, Signal Prospecting and coordinated Event Sequence. "
            "Signal Prospecting is limited to Operator-owned Salesforce Accounts. "
            "Event Sequence also admits the configured outreach-owner scope for Operator's named lists.",
            " ".join(sequential.split()),
        )
        self.assertIn("Wait for that spend's explicit approval", prep)
        self.assertIn("Label each spend C1, C2", prep)
        self.assertIn("the final enrollment approval never authorizes enrichment", prep)

    def test_buying_signals_names_real_taxonomy_sections_and_frontmatter(self):
        contract = (SIGNAL / "01-research/CONTEXT.md").read_text()
        taxonomy = (PROSPECTING / "references/signals.md").read_text()
        row = "\n".join(line for line in contract.splitlines() if "/references/signals.md`" in line)
        self.assertIn("Frontmatter tiers", row)
        scopes = re.findall(r'"([^"]+)"', row)
        self.assertEqual(scopes, [
            "Signals to look for", "Interpret the evidence", "Identify configured product relevance",
            "Check whether the initiative is current", "Record and use findings",
            "Qualification for automated stages",
        ])
        for scope in scopes:
            self.assertIn(f"## {scope}\n", taxonomy)
        self.assertNotIn("Verified configured product adoption", row)

    def test_missing_account_uses_cross_owner_supersets_and_exact_match_filter(self):
        prep = (EVENT / "references/prep.md").read_text()
        self.assertIn("Fetch cross-owner Account candidates with `Website LIKE '%<host>%'`", prep)
        self.assertIn("Contact candidates with `Email LIKE '%@<domain>'` as supersets only", prep)
        self.assertIn("Follow all pages of both reads", prep)
        self.assertIn("A wildcard hit never counts as a match", prep)
        self.assertIn("Keep only exact normalized Website host or exact Contact email-domain matches", prep)
        self.assertIn("both completed cross-owner superset fetches with zero exact matches", prep)
        self.assertIn("If either fetch fails or is incomplete, keep the row needs-input", prep)
        self.assertIn("never to identify the recipient Contact", prep)
        self.assertNotIn("never LIKE wildcards", prep)

    def test_owner_only_apollo_evidence_stays_unknown(self):
        prep = (EVENT / "references/prep.md").read_text()
        self.assertIn("An Apollo crm_owner_id alone does not prove a CRM link or its absence", prep)
        self.assertIn("keep apollo_crm_linked unknown", prep)
        self.assertIn("Never map an absent crm_id to false while owner evidence is present", prep)

    def test_followup_accepts_matt_supplied_historical_labels_without_session_reads(self):
        contract = (SIGNAL / "03-followup/CONTEXT.md").read_text()
        execution = (SIGNAL / "03-followup/references/execution.md").read_text()
        self.assertIn("Operator-supplied historical labels in this thread", contract)
        self.assertIn("Operator may supply those historical labels here when the outreach ran elsewhere", execution)
        self.assertIn("Do not read another session or infer labels from the sent body", execution)
        self.assertIn("A send whose computed due date is before today is blocked", execution)

    def test_followup_states_contact_identity_stop(self):
        execution = (SIGNAL / "03-followup/references/execution.md").read_text()
        self.assertIn("Missing or ambiguous Accounts or Contacts stop", execution)
        self.assertIn("Creating a Contact or an Event", execution)

    def test_outreach_pipeline_handoff_is_one_readable_instruction(self):
        contract = (SIGNAL / "02-outreach/CONTEXT.md").read_text()
        self.assertIn("Any open Opportunity hands evidence to Pipeline and stops prospecting.", contract)

    def test_standalone_scrub_audit_is_not_called_an_independent_classifier(self):
        paths = [
            EVENT / "01-list-prep/CONTEXT.md",
            EVENT / "01-list-prep/references/scrubber.md",
            EVENT / "references/prep.md",
        ]
        for path in paths:
            with self.subTest(path=path):
                source = path.read_text()
                self.assertNotIn("independent", source)
                self.assertIn("audit", source)
        scrubber = paths[1].read_text()
        self.assertIn("Both audits use the same classifier", scrubber)
        self.assertIn("Keep both required PASS reports", scrubber)

    def test_blocked_campaigns_show_fallback_names_saved_source_timestamp_and_failure(self):
        readback = (EVENT / "references/readback.md").read_text()
        self.assertIn("Attempt the live read on every run.", readback)
        self.assertIn("When campaigns_show is blocked on this run,", readback)
        self.assertIn("The readback receipt names that saved source, `apollo_sequences_create` or `apollo_sequences_update`, its response timestamp, "
                      "and the quoted current-read failure", readback)
        self.assertNotIn("The exact proposal then names", readback)
        self.assertIn("Never assume live access is unavailable on a later run.", readback)

    def test_dormant_adoption_section_left_the_buying_signal_taxonomy(self):
        taxonomy = (PROSPECTING / "references/signals.md").read_text()
        self.assertNotIn("## Verified configured product adoption", taxonomy)
        self.assertNotIn("Paid individual adoption", taxonomy)
        self.assertIn("- id: paid_individuals_present", taxonomy)
        adoption = (SIGNAL / "01-research/references/adoption.md").read_text()
        self.assertIn("Inferring a champion's identity, personal payment, unsanctioned use, or company disapproval from adoption facts.", adoption)
        self.assertIn("Public mentions never substitute for the warehouse check.", adoption)

    def test_read_only_research_does_not_repeat_inactive_write_instructions(self):
        for name in ("buying-signals.md", "adoption.md"):
            source = (SIGNAL / "01-research/references" / name).read_text()
            with self.subTest(name=name):
                self.assertNotIn("## Sales authority", source)
                self.assertIn("## Boundaries", source)
                self.assertNotIn("Never retry a failed or mismatched create", source)


if __name__ == "__main__":
    unittest.main()
