#!/usr/bin/env python3
"""Route a current Salesforce read for a named-account Research or Outreach run.

Usage: python3 workspaces/prospecting/scripts/prospect_account_route.py --receipt receipt.json [--core _core]
Receipt keys are account_exists (bool), account_id (str or null), owner_id (str or null),
and open_opportunity_ids (list of nonempty strings). Optional account_domain carries the verified Account domain for Outreach.
All reads must be complete and current.
Missing or ambiguous identity is not a completed no-match read. Stop and resolve it before calling.
Policy input requires prospecting.identity.sfdc_user_id. No ICP admission or Account writes.
Routes: absent Account -> outside_named_accounts, any open Opportunity -> active_deal,
Operator-owned Account -> scan, every other owner -> owned_elsewhere. Owner activity never allows claiming.
Exit 0 verdict JSON. Exit 2 unusable input with the common error envelope. Never authorizes a write.
"""
import argparse
import json
from pathlib import Path

import prospect_common

KEYS = {"account_exists", "account_id", "owner_id", "open_opportunity_ids"}


def route(receipt, policy):
    if not isinstance(receipt, dict) or not KEYS <= set(receipt) or set(receipt) - KEYS - {"account_domain"}:
        raise ValueError("Receipt needs account_exists, account_id, owner_id, open_opportunity_ids and only optional account_domain")
    if type(receipt["account_exists"]) is not bool:
        raise ValueError("account_exists must be a completed boolean read")
    opportunities = receipt["open_opportunity_ids"]
    if not isinstance(opportunities, list) or any(not isinstance(value, str) or not value.strip() for value in opportunities):
        raise ValueError("open_opportunity_ids must be a list of nonempty IDs from a complete read")
    if not receipt["account_exists"]:
        if opportunities or receipt["account_id"] not in (None, "") or receipt["owner_id"] not in (None, ""):
            raise ValueError("Absent Account cannot have Account, owner, or Opportunity evidence")
        return "outside_named_accounts"
    if any(not isinstance(receipt[key], str) or not receipt[key].strip() for key in ("account_id", "owner_id")):
        raise ValueError("Existing Account needs its verified ID and owner ID")
    owner = policy["identity"]["sfdc_user_id"]
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("Named-account owner must be configured")
    if opportunities:
        return "active_deal"
    return "scan" if receipt["owner_id"] == owner else "owned_elsewhere"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--core", type=Path, default=prospect_common.CORE)
    args = parser.parse_args(argv)
    try:
        receipt = json.loads(args.receipt.read_text())
        result = {"route": route(receipt, prospect_common.load_policy(args.core))}
    except prospect_common.INPUT_ERRORS as exc:
        print(prospect_common.error_json(exc))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
