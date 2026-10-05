import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "_core"
SCRIPTS = ROOT / "workspaces/prospecting/scripts"
sys.path.insert(0, str(SCRIPTS))
import prospect_common  # noqa: E402
import prospect_privacy_check  # noqa: E402

CLEAN = {
    "account_name": "Acme",
    "salesforce_account_id": "001000000000001AAA",
    "account_domain": "example.com",
    "data_through_date": "2026-09-20",
    "mapped_org_count": 1,
    "org_subscribed": True,
    "org_paying": True,
    "org_service_types": ["SELF_SERVE"],
    "org_platforms": ["stripe"],
    "paid_individuals_exist": True,
    "adoption": "org_adopted",
}


def run(bundle, raw=None, extra_args=()):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bundle.json"
        p.write_text(raw if raw is not None else json.dumps(bundle))
        r = subprocess.run([sys.executable, str(SCRIPTS / "prospect_privacy_check.py"), "--bundle", str(p), *extra_args],
                           capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)


class PrivacyCheckTests(unittest.TestCase):
    def test_policy_keys_load(self):
        us = prospect_common.load_policy(CORE)["user_scan"]
        self.assertEqual(set(us["bundle_keys"]), set(CLEAN))
        self.assertEqual(us["adoption_values"], ["org_adopted", "individuals_only", "none_found"])

    def test_clean_bundle_exits_0(self):
        code, out = run(CLEAN)
        self.assertEqual((code, out["verdict"]), (0, "clean"))

    def test_core_flag_accepted(self):
        code, out = run(CLEAN, extra_args=("--core", str(CORE)))
        self.assertEqual((code, out["verdict"]), (0, "clean"))

    def test_extra_key_blocked(self):
        code, out = run({**CLEAN, "user_count": 12})
        self.assertEqual(code, 1)
        self.assertIn("forbidden key: user_count", out["problems"])

    def test_missing_key_blocked(self):
        b = dict(CLEAN); del b["adoption"]
        code, out = run(b)
        self.assertEqual(code, 1)
        self.assertIn("missing key: adoption", out["problems"])

    def test_email_in_string_blocked(self):
        code, out = run({**CLEAN, "account_name": "jane.doe@example.com"})
        self.assertEqual(code, 1)
        self.assertIn("email address in account_name", out["problems"])

    def test_email_in_list_blocked(self):
        code, out = run({**CLEAN, "org_platforms": ["bob@example.com"]})
        self.assertEqual(code, 1)

    def test_timestamp_blocked(self):
        code, out = run({**CLEAN, "adoption": "org_adopted 2026-09-20 14:02"})
        self.assertEqual(code, 1)
        self.assertIn("timestamp in adoption", out["problems"])

    def test_dict_inside_list_blocked(self):
        smuggled = [{"email": "bob@example.com", "last_active": "2026-09-20T14:02"}]
        code, out = run({**CLEAN, "org_service_types": smuggled, "org_platforms": [42]})
        self.assertEqual(code, 1)
        self.assertIn("non-scalar element in org_service_types", out["problems"])
        self.assertNotIn("non-scalar element in org_platforms", out["problems"])

    def test_nested_list_blocked(self):
        code, out = run({**CLEAN, "org_platforms": [["stripe"]]})
        self.assertEqual(code, 1)
        self.assertIn("non-scalar element in org_platforms", out["problems"])

    def test_bool_where_int_expected_blocked(self):
        code, out = run({**CLEAN, "mapped_org_count": True})
        self.assertEqual(code, 1)

    def test_wrong_type_blocked(self):
        code, out = run({**CLEAN, "org_paying": "yes"})
        self.assertEqual(code, 1)
        self.assertIn("wrong type for org_paying: expected bool", out["problems"])

    def test_adoption_outside_values_blocked(self):
        code, out = run({**CLEAN, "adoption": "whatever"})
        self.assertEqual(code, 1)
        self.assertIn("adoption not in policy user_scan.adoption_values: 'whatever'", out["problems"])

    def test_adoption_rule_mismatch_blocked(self):
        code, out = run({**CLEAN, "adoption": "individuals_only"})
        self.assertEqual(code, 1)
        self.assertIn("adoption individuals_only does not follow the rule, booleans give org_adopted", out["problems"])
        code, out = run({**CLEAN, "org_subscribed": False, "org_paying": False, "adoption": "none_found"})
        self.assertEqual(code, 1)
        self.assertIn("adoption none_found does not follow the rule, booleans give individuals_only", out["problems"])

    def test_adoption_rule_match_passes(self):
        code, _ = run({**CLEAN, "org_subscribed": False, "org_paying": False, "adoption": "individuals_only"})
        self.assertEqual(code, 0)
        code, _ = run({**CLEAN, "org_subscribed": False, "org_paying": False, "paid_individuals_exist": False,
                       "org_service_types": [], "org_platforms": [], "mapped_org_count": 0, "adoption": "none_found"})
        self.assertEqual(code, 0)

    def test_expected_adoption_needs_booleans(self):
        self.assertIsNone(prospect_privacy_check.expected_adoption({"org_subscribed": "yes", "paid_individuals_exist": True}))
        self.assertEqual(prospect_privacy_check.expected_adoption({"org_subscribed": True, "paid_individuals_exist": False}), "org_adopted")

    def test_bad_json_exits_2(self):
        code, out = run(None, raw="{not json")
        self.assertEqual((code, out["verdict"]), (2, "error"))

    def test_non_object_bundle_exits_2(self):
        code, out = run(["a", "list"])
        self.assertEqual((code, out["verdict"]), (2, "error"))


if __name__ == "__main__":
    unittest.main()
