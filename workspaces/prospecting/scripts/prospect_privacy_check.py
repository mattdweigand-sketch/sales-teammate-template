#!/usr/bin/env python3
"""Privacy check for the signal-user-scan adoption bundle.

Usage: python3 prospect_privacy_check.py --bundle <bundle.json> [--core _core]

Policy input requires prospecting.user_scan.bundle_keys (allowed keys and types)
and prospecting.user_scan.adoption_values.
Fails when the bundle has a key outside the list, a missing key, a value of the wrong type, a list element
that is not a string, bool, int, or null, any string (top level or inside a list) that looks like an email
address or a person's activity timestamp, an adoption value outside adoption_values, or an adoption value
that does not follow the rule. org_adopted when org_subscribed, individuals_only when only
paid_individuals_exist, else none_found.
It checks shape, email addresses and timestamps. It cannot recognize a person's name inside a category list; the
query's fixed columns are the control for that. Prints the verdict JSON to stdout.

Exit codes: 0 clean, 1 blocked, 2 usage or input error, {"verdict": "error", "reason": ...}.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import prospect_common

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
TYPES = {"str": str, "bool": bool, "int": int, "list": list}


def expected_adoption(bundle):
    """The adoption value the three booleans imply. None when they are not all booleans."""
    subscribed, paid = bundle.get("org_subscribed"), bundle.get("paid_individuals_exist")
    if not isinstance(subscribed, bool) or not isinstance(paid, bool):
        return None
    if subscribed:
        return "org_adopted"
    return "individuals_only" if paid else "none_found"


def scan_text(key, value, problems):
    """Every element is a string, bool, int, or null. Strings are scanned wherever they sit."""
    for t in value if isinstance(value, list) else [value]:
        if isinstance(t, str):
            if EMAIL_RE.search(t):
                problems.append(f"email address in {key}")
            if TIMESTAMP_RE.search(t):
                problems.append(f"timestamp in {key}")
        elif t is not None and not isinstance(t, (bool, int)):
            problems.append(f"non-scalar element in {key}")


def check(bundle, allowed, adoption_values):
    problems = []
    for k in bundle:
        if k not in allowed:
            problems.append(f"forbidden key: {k}")
    for k, typ in allowed.items():
        if k not in bundle:
            problems.append(f"missing key: {k}")
        elif not isinstance(bundle[k], TYPES[typ]) or (typ == "int" and isinstance(bundle[k], bool)):
            problems.append(f"wrong type for {k}: expected {typ}")
    for k, v in bundle.items():
        scan_text(k, v, problems)
    adoption = bundle.get("adoption")
    if "adoption" in bundle and adoption not in adoption_values:
        problems.append(f"adoption not in policy user_scan.adoption_values: {adoption!r}")
    expected = expected_adoption(bundle)
    if expected is not None and adoption in adoption_values and adoption != expected:
        problems.append(f"adoption {adoption} does not follow the rule, booleans give {expected}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--core", default=str(prospect_common.CORE))
    a = ap.parse_args()
    try:
        bundle = json.loads(Path(a.bundle).read_text())
        us = prospect_common.load_policy(Path(a.core))["user_scan"]
        allowed, adoption_values = us["bundle_keys"], list(us["adoption_values"])
        if not isinstance(allowed, dict) or not allowed or not isinstance(bundle, dict):
            raise ValueError("policy has no user_scan.bundle_keys mapping or bundle is not an object")
        problems = check(bundle, allowed, adoption_values)
    except prospect_common.INPUT_ERRORS as e:
        print(prospect_common.error_json(e))
        return 2
    print(json.dumps({"verdict": "clean" if not problems else "blocked", "problems": problems}, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
