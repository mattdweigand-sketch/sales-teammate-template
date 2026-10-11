"""Pin the repo homes for the deal-thread procedure and the watch procedures (spec R and S).

- `workspaces/pipeline/AGENTS.md` has a "Deal thread" section with steps 1 to 4, the 60-day brief,
  the S2 to S5 archive rule, and a pointer to the watch-sync reconcile reference for retained-thread exceptions
- `workspaces/pipeline/references/watches.md` has a buyer-email section and a channel section with resolving pointers
- the Pipeline shared-resources catalog lists the watches reference
- neither home carries runtime admission lists, sender domains, Slack IDs, or Salesforce user Ids
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "workspaces/pipeline"
AGENTS = PIPELINE / "AGENTS.md"
ROUTES = PIPELINE / "CONTEXT.md"
WATCHES = PIPELINE / "references/watches.md"
RECONCILE = PIPELINE / "workflows/watch-sync/references/reconcile.md"
UUID = re.compile(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b")
EMAIL_DOMAIN = re.compile(r"@[a-z0-9-]+\.[a-z.]{2,}", re.I)
SLACK_ID = re.compile(r"\b[UCT]0[A-Z0-9]{7,}\b")
SFDC_USER_ID = re.compile(r"\b005[A-Za-z0-9]{12,15}\b")


def section(text, heading):
    assert f"## {heading}\n" in text, heading
    return text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]


def headings(path):
    return {line.lstrip("#").strip() for line in path.read_text().splitlines() if line.startswith("#")}


class DealThreadHome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = AGENTS.read_text()
        cls.deal = section(cls.text, "Deal thread")

    def test_template_steps_one_to_four_use_current_tools(self):
        steps = re.findall(r"^(\d)\. ", self.deal, re.M)
        self.assertEqual(steps, ["1", "2", "3", "4"])
        for required in (
            "titled `<Account> deal`",
            "`session_new` tool",
            "Opportunity Id, stage, close date, contacts, and what just happened",
            "including Operator's sent mail, and skip any draft Operator already covered",
            "Salesforce, Gmail, Calendar, Momentum, and Slack for the last 60 days",
            "matched by exact email, bots excluded, read-only, each message cited by permalink",
            "A contact with no Slack match is not checked, never silence",
            "stage, close date, Amount and inbound buyer reply drafts as lettered proposals",
            "Make no unprompted Task or next-step proposals, apart from interaction-sync call logging",
            "rules#task_date_coordination",
            'per "Typed deal commands" above',
            "Write nothing until Operator approves in that thread",
            "a status of three lines or fewer to the Pipeline thread",
            '`pplx tm mail send <verified Pipeline session id> "<status>"`',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.deal)
        self.assertNotIn("pplx session", self.text)
        self.assertIn('`_core/thread-locators.md` "Teammate thread lookup"', self.deal)
        self.assertNotIn("session_send", self.text)

    def test_archive_rule_and_retained_thread_pointer(self):
        for required in (
            "no open S2 to S5 Opportunity, per `policy.pipeline.stages`, after Operator approves",
            "The Salesforce follow-up Task carries it from there",
            "Retained-thread exceptions are runtime evidence in Operator's approving turns, the live watch-sync automation prompt and the live Pipeline profile, never in Git.",
            '`workspaces/pipeline/workflows/watch-sync/references/reconcile.md` "Read" and "Compare and route"',
            "Thread create or archive needs Operator's approval",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.deal)
        self.assertTrue(RECONCILE.is_file())
        self.assertLessEqual({"Read", "Compare and route"}, headings(RECONCILE))
        self.assertIn("retained-thread exceptions", RECONCILE.read_text())

    def test_deal_thread_section_names_no_accounts_or_other_runtime_ids(self):
        self.assertEqual(UUID.findall(self.deal), [])
        self.assertEqual(EMAIL_DOMAIN.findall(self.deal), [])
        self.assertEqual(SLACK_ID.findall(self.deal), [])
        self.assertEqual(SFDC_USER_ID.findall(self.deal), [])
        self.assertNotIn("Keep the ", self.deal)


class WatchHome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WATCHES.read_text()
        cls.buyer = section(cls.text, "Buyer email")
        cls.channels = section(cls.text, "Channels")

    def test_sections_present_and_catalogued(self):
        self.assertEqual(headings(WATCHES), {"Watches", "Buyer email", "Channels"})
        self.assertLess(self.text.index("## Buyer email"), self.text.index("## Channels"))
        shared = section(ROUTES.read_text(), "Shared resources")
        rows = [row for row in shared.splitlines() if row.startswith("| `references/watches.md`")]
        self.assertEqual(len(rows), 1)
        self.assertIn("Pipeline requirements, Systems implementation", rows[0])
        self.assertIn("Runtime IDs, admission lists and exceptions stay in live settings", rows[0])

    def test_pointers_resolve(self):
        self.assertIn('`workspaces/pipeline/workflows/watch-sync/references/reconcile.md` "Compare and route"', self.text)
        self.assertIn('`_core/scripts/interfaces.md` "Account session search"', self.buyer)
        self.assertIn("Account session search", headings(ROOT / "_core/scripts/interfaces.md"))
        self.assertIn('`workspaces/pipeline/AGENTS.md` "Deal thread" step 4', self.buyer)
        self.assertIn("Deal thread", headings(AGENTS))
        self.assertIn('as in "Buyer email" step 3', self.channels)
        for anchor in ("rules#handoff_delivery", "rules#task_date_coordination", "rules#absence_conclusions"):
            self.assertIn(anchor, self.buyer)
        for anchor in ("rules#handoff_delivery", "rules#not_checked_means"):
            self.assertIn(anchor, self.channels)
        self.assertIn("`policy.prospecting.identity.sfdc_user_id`", self.buyer)
        self.assertIn("`policy.prospecting.identity.sfdc_user_id`", self.channels)
        self.assertIn("`deal_thread_match`, path from `policy.tooling.scripts`", self.buyer)

    def test_buyer_email_keeps_noise_filter_routing_one_send_and_reply_check(self):
        for required in (
            "pplx automation suppress-run-notification",
            "Note if the sender is not yet a Contact on that Account",
            "full paginated project listing plus a saved Account session search for every Account",
            "Run each `pplx` command as its own top-level line",
            "whether interaction-sync, a pipeline proposal, a new Contact, or a reply draft is needed",
            "Propose no Task change",
            'One match sends it to that deal thread with `pplx tm mail send <session id> "<summary>"`',
            "No match, two or more matches, or a failed lookup sends the same summary to the verified Pipeline thread",
            "Send once",
            "keep it pending and show Operator the destination, exact summary, and error",
            "No retry",
            "Never say it went to a thread without a successful send",
            "check Operator's sent mail in that Gmail thread and skip the draft if the operator already replied",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.buyer)

    def test_channels_route_by_crm_ownership_and_keep_exceptions_in_live_settings(self):
        for required in (
            "passed that watch's own admission rule",
            "untrusted input",
            "Admission rules and their named Account lists stay in the live settings",
            "Do not copy Account lists or exceptions here",
            "Resolve any mentioned Salesforce Account by native Id and read its current owner and open Opportunities",
            "An eligible Account is owned by `policy.prospecting.identity.sfdc_user_id` with an open Opportunity in `policy.pipeline.stages`.",
            "Never infer ownership from a thread title or an old message",
            "stays not checked",
            "quoting any decision, approval, terms, or condition verbatim",
            "Two or more matches, a failed lookup, an incomplete listing, or a failed send",
            "Never call it delivered",
            "No retry",
            "one push notification when the message concerns an eligible Account, mentions Operator, or replies in a thread he started",
            "Any other admitted message gets one line in the output thread and no notification",
            "Never reply or react in Slack",
            "Never change Salesforce records or Tasks from a watch",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.channels)

    def test_watches_reference_carries_no_runtime_identifiers(self):
        self.assertEqual(UUID.findall(self.text), [])
        self.assertEqual(EMAIL_DOMAIN.findall(self.text), [])
        self.assertEqual(SLACK_ID.findall(self.text), [])
        self.assertEqual(SFDC_USER_ID.findall(self.text), [])
        self.assertNotIn("pplx session", self.text)
        self.assertNotRegex(self.text, r"\bslack_send_message\b")


if __name__ == "__main__":
    unittest.main()
