"""Shared Salesforce organization identity and report-mode usage counts."""
import argparse
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


def resolve_org(account):
    admin = account.get("Admin_Organization_UUID__c")
    legacy = account.get("Org_UUID__c")
    if admin and legacy and admin != legacy:
        raise ValueError(f"org ids differ: Admin_Organization_UUID__c={admin}, Org_UUID__c={legacy}")
    if not (admin or legacy):
        raise ValueError("org id missing in Salesforce")
    return admin or legacy


def count_value(value):
    if value is None:
        return Decimal(0)
    if isinstance(value, bool):
        raise ValueError("usage counts must be nonnegative numbers")
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("usage counts must be nonnegative numbers") from error
    if not number.is_finite() or number < 0:
        raise ValueError("usage counts must be nonnegative numbers")
    return number


def summarize_usage(evidence):
    org_uuid = resolve_org(evidence["Account"])
    if evidence.get("org_uuid") != org_uuid:
        raise ValueError("usage org does not match Salesforce Account")
    data_through = date.fromisoformat(evidence["data_through"]).isoformat()
    rows = evidence["rows"]
    if not isinstance(rows, list):
        raise ValueError("roster rows must be a complete list")
    seen = set()
    active = last_seven = 0
    for row in rows:
        if not {"user_email", "window_queries", "l7_queries"} <= row.keys():
            raise ValueError("roster activity fields missing")
        email = row.get("user_email")
        if not isinstance(email, str) or not email:
            raise ValueError("roster user_email missing")
        normalized = email.casefold()
        if normalized in seen:
            raise ValueError("duplicate roster user_email")
        seen.add(normalized)
        active += count_value(row.get("window_queries")) > 0
        last_seven += count_value(row.get("l7_queries")) > 0
    billed = evidence.get("billed_seats")
    if billed is not None:
        number = count_value(billed)
        if number != number.to_integral_value():
            raise ValueError("billed_seats must be a whole number")
        billed = int(number)
    return {"org_uuid": org_uuid, "data_through": data_through,
            "billed_seats": billed, "roster_seats": len(rows),
            "active_users": active, "active_last_seven_days": last_seven}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        result = summarize_usage(json.loads(arguments.input.read_text()))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({"valid": False, "error": str(error)}))
        return 2
    print(json.dumps({"valid": True, **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
