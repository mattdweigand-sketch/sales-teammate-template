"""Resolve exactly one owned, unexpired pilot from saved Salesforce records."""
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from account_usage import resolve_org


def resolve_pilot(records, owner_id, as_of, opportunity_id=None, account_id=None, account_name=None):
    if not isinstance(owner_id, str) or not owner_id:
        raise ValueError("current Salesforce user id required")
    moment = datetime.fromisoformat(as_of)
    if moment.utcoffset() is None:
        raise ValueError("as-of needs the local offset")
    today = moment.astimezone(ZoneInfo("America/Los_Angeles")).date()
    if sum(bool(value) for value in (opportunity_id, account_id, account_name)) != 1:
        raise ValueError("supply one Opportunity Id or Account selector")
    if not isinstance(records, list):
        raise ValueError("input must be a complete Salesforce record list")
    matches = []
    for record in records:
        account = record.get("Account") or {}
        if opportunity_id and record.get("Id") != opportunity_id:
            continue
        if account_id and record.get("AccountId") != account_id:
            continue
        if account_name and not account.get("Name", "").casefold().startswith(account_name.casefold()):
            continue
        if record.get("OwnerId") != owner_id:
            continue
        closed, won = record.get("IsClosed"), record.get("IsWon")
        if not isinstance(closed, bool) or not isinstance(won, bool):
            raise ValueError("IsClosed and IsWon must be Salesforce booleans")
        end = record.get("Trial_Expiration_Date__c")
        expiration = date.fromisoformat(end) if end else None
        paid = record.get("Deal_Type__c") == "Paid Trial"
        if expiration and expiration < today:
            continue
        if closed:
            eligible = won and paid and expiration is not None
        else:
            eligible = paid or expiration is not None
        if eligible:
            matches.append(record)
    if len(matches) != 1:
        raise ValueError("multiple eligible pilots, ask which Opportunity Id" if matches else "no eligible pilot")
    selected = matches[0]
    return {"opportunity": selected, "org_uuid": resolve_org(selected["Account"]), "today": today.isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--as-of", required=True)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--opportunity-id")
    selector.add_argument("--account-id")
    selector.add_argument("--account-name")
    arguments = parser.parse_args()
    try:
        result = resolve_pilot(json.loads(arguments.input.read_text()), arguments.owner_id, arguments.as_of,
                               arguments.opportunity_id, arguments.account_id, arguments.account_name)
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({"valid": False, "error": str(error)}))
        return 2
    print(json.dumps({"valid": True, **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
