"""Current named-account routing, incomplete reads, and sandbox CLI behavior."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "workspaces/prospecting/scripts"
sys.path.insert(0, str(SCRIPTS))
import prospect_account_route as router

POLICY = {"identity": {"sfdc_user_id": "synthetic-operator"}}
RECEIPT = {"account_exists": True, "account_id": "synthetic-account", "owner_id": "synthetic-operator", "open_opportunity_ids": []}


class NamedAccountRoute(unittest.TestCase):
    def test_only_configured_owner_can_research(self):
        for owner, expected in (("synthetic-operator", "scan"), ("synthetic-other", "owned_elsewhere"),
                                ("synthetic-house", "owned_elsewhere"), ("synthetic-inactive", "owned_elsewhere")):
            with self.subTest(owner=owner):
                self.assertEqual(router.route(dict(RECEIPT, owner_id=owner), POLICY), expected)

    def test_open_opportunity_always_hands_to_pipeline_regardless_of_owner(self):
        for owner in ("synthetic-operator", "synthetic-other", "synthetic-house"):
            self.assertEqual(router.route(dict(RECEIPT, owner_id=owner, open_opportunity_ids=["synthetic-opp"]), POLICY), "active_deal")

    def test_completed_no_match_never_proposes_account_creation(self):
        receipt = dict(RECEIPT, account_exists=False, account_id=None, owner_id=None)
        self.assertEqual(router.route(receipt, POLICY), "outside_named_accounts")

    def test_missing_unknown_and_contradictory_reads_are_unusable(self):
        invalid = [None, [], {}, dict(RECEIPT, account_exists=None), dict(RECEIPT, account_exists="true"),
                   dict(RECEIPT, owner_id=""), dict(RECEIPT, account_id=None), dict(RECEIPT, account_id=[]),
                   dict(RECEIPT, open_opportunity_ids=None), dict(RECEIPT, open_opportunity_ids=[""]),
                   dict(RECEIPT, open_opportunity_ids=[None]), dict(RECEIPT, account_exists=False),
                   dict(RECEIPT, account_exists=False, account_id=None, owner_id=None, open_opportunity_ids=["synthetic-opp"])]
        missing = copy.deepcopy(RECEIPT)
        del missing["owner_id"]
        invalid.append(missing)
        for receipt in invalid:
            with self.subTest(receipt=receipt), self.assertRaises(ValueError):
                router.route(receipt, POLICY)

    def test_legacy_claim_inputs_are_rejected(self):
        for extra in ("headcount", "signals", "owner_is_active", "claimable"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                router.route(dict(RECEIPT, **{extra: None}), POLICY)

    def test_owner_change_and_empty_configuration_cannot_allow_scan(self):
        self.assertEqual(router.route(RECEIPT, {"identity": {"sfdc_user_id": "synthetic-new-owner"}}), "owned_elsewhere")
        with self.assertRaises(ValueError):
            router.route(RECEIPT, {"identity": {"sfdc_user_id": ""}})

    def test_cli_loads_adjacent_policy_from_sandbox_and_errors_without_tracebacks(self):
        with tempfile.TemporaryDirectory() as folder:
            sandbox = Path(folder)
            receipt = sandbox / "receipt.json"
            known = dict(RECEIPT, owner_id="005000000000001AAA")
            for value, code, expected in ((known, 0, {"route": "scan"}), ({}, 2, None), (None, 2, None)):
                receipt.write_text(json.dumps(value))
                result = subprocess.run([sys.executable, str(SCRIPTS / "prospect_account_route.py"), "--receipt", str(receipt)],
                                        cwd=sandbox, capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                self.assertEqual(result.stderr, "")
                output = json.loads(result.stdout)
                self.assertEqual(output, expected) if expected else self.assertEqual(output["verdict"], "error")
