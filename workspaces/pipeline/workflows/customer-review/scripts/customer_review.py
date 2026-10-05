"""Read-only customer milestones and independent renewal notices from complete saved evidence.

Needs policy.pipeline.customer_review: schedule, milestone_months,
renewal_notice_days, expansion_type and expansion_stage. Scheduled --window-start is
the last scheduled receipt's as_of, never a platform completion flag. Without
it, use the previous policy occurrence. --carry-forward and --reviewed take
receipt-derived JSON lists; one Account selector runs on-demand, without
moving the scheduled window. --milestone-months explicitly reassesses a milestone.
usage_ready requires complete roster, weekly trend and feature mix for a due row.
Billed seats may be unknown. Buyer context never controls usage readiness.
"""
import argparse
import calendar
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from account_usage import count_value, resolve_org, summarize_usage


def calendar_months_after(anchor, months):
    if isinstance(months, bool) or not isinstance(months, int) or months <= 0:
        raise ValueError("milestone_months must contain positive integers")
    year, zero_month = divmod(anchor.year * 12 + anchor.month - 1 + months, 12)
    month = zero_month + 1
    return date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))


def local_moment(value, timezone):
    moment = datetime.fromisoformat(value)
    if moment.utcoffset() is None:
        raise ValueError("timestamps need a local offset")
    return moment.astimezone(timezone)


def schedule_occurrence(moment, schedule, direction, inclusive=False):
    weekdays = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
    scheduled_days = [weekdays.index(day) for day in schedule["days"]]
    week = schedule["week_of_month"]
    if isinstance(week, bool) or not isinstance(week, int) or not 1 <= week <= 5 or not scheduled_days:
        raise ValueError("schedule needs days and week_of_month from 1 to 5")
    clock = datetime.strptime(schedule["time"], "%H:%M").time()
    for offset in range(24):
        year, zero_month = divmod(moment.year * 12 + moment.month - 1 + direction * offset, 12)
        month = zero_month + 1
        first = date(year, month, 1)
        candidates = []
        for weekday in scheduled_days:
            day = 1 + (weekday - first.weekday()) % 7 + 7 * (week - 1)
            if day <= calendar.monthrange(year, month)[1]:
                candidate = datetime.combine(date(year, month, day), clock, moment.tzinfo)
                if (direction < 0 and (candidate < moment or inclusive and candidate == moment)) or (direction > 0 and candidate > moment):
                    candidates.append(candidate)
        if candidates:
            return max(candidates) if direction < 0 else min(candidates)
    raise ValueError("no policy schedule occurrence found")


def receipt_entries(entries, months, reviewed=False):
    if not isinstance(entries, list):
        raise ValueError("receipt entries must be a JSON list")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("account_id"), str) or not entry["account_id"]:
            raise ValueError("receipt entry needs account_id")
        count = entry.get("milestone_months")
        if not reviewed and count is None and entry.get("milestone_date") is None:
            result[(entry["account_id"], None, None)] = dict(entry)
            continue
        if isinstance(count, bool) or not isinstance(count, int) or count not in months:
            raise ValueError("receipt milestone_months must match policy")
        milestone_date = date.fromisoformat(entry["milestone_date"]).isoformat()
        if reviewed:
            timestamp = datetime.fromisoformat(entry["receipt_date"])
            if timestamp.utcoffset() is None:
                raise ValueError("reviewed receipt_date needs an offset")
        key = (entry["account_id"], count, milestone_date)
        if key not in result or reviewed and datetime.fromisoformat(entry["receipt_date"]) > datetime.fromisoformat(result[key]["receipt_date"]):
            result[key] = dict(entry)
    return result


def milestone_selection(anchor, months, moment, start, window, identifier, carried, reviewed, requested=None):
    milestones = []
    previous = anchor
    for count in months:
        milestone_date = calendar_months_after(anchor, count)
        milestones.append({"months": count, "date": milestone_date.isoformat(), "status": "not_due", "window": window,
                           "evidence_window": {"start": previous.isoformat(), "as_of": moment.isoformat()}})
        previous = milestone_date
    on_demand = start is None
    eligible, already = [], []
    for item in milestones:
        key = (identifier, item["months"], item["date"])
        midnight = datetime.combine(date.fromisoformat(item["date"]), datetime.min.time(), moment.tzinfo)
        if midnight <= moment and (on_demand or midnight > start or key in carried or (identifier, None, None) in carried):
            if key in reviewed and not on_demand:
                already.append(reviewed[key])
            eligible.append(item)
    if requested is not None:
        eligible = [item for item in eligible if item["months"] == requested]
        if not eligible:
            raise ValueError("requested milestone is not dated on or before today")
    if not eligible:
        future = [item for item in milestones if date.fromisoformat(item["date"]) > moment.date()]
        return (future[0] if future else milestones[-1]), [], already
    latest = eligible[-1]
    if on_demand or (identifier, latest["months"], latest["date"]) not in reviewed:
        latest["status"] = "due"
    else:
        latest["reason"] = "already reviewed"
    superseded = [] if on_demand else eligible[:-1]
    for item in superseded:
        item["status"] = "superseded"
    return latest, superseded, already


def review_customers(evidence, as_of, policy, window_start=None, account_id=None, account_name=None,
                     carry_forward=None, reviewed=None, milestone_months=None):
    settings = policy["pipeline"]["customer_review"]
    timezone = ZoneInfo(settings["schedule"]["tz"])
    moment = local_moment(as_of, timezone)
    today = moment.date()
    on_demand = account_id is not None or account_name is not None
    if account_id is not None and account_name is not None or on_demand and window_start is not None:
        raise ValueError("on-demand requires one Account selector and no --window-start")
    if milestone_months is not None and not on_demand:
        raise ValueError("explicit milestone reassessment requires a named Account")
    start = None
    if not on_demand:
        if window_start is not None:
            start = local_moment(window_start, timezone)
        else:
            nominal = schedule_occurrence(moment, settings["schedule"], -1, inclusive=True)
            start = schedule_occurrence(nominal, settings["schedule"], -1)
    if start is not None and start >= moment:
        raise ValueError("--window-start must be before --as-of")
    window = {"window_start": start.isoformat() if start else None, "as_of": moment.isoformat(),
              "source": "on_demand" if on_demand else "scheduled_receipt" if window_start is not None else "previous_policy_occurrence"}
    next_run = schedule_occurrence(moment, settings["schedule"], 1)
    months = settings["milestone_months"]
    if not isinstance(months, list) or not months:
        raise ValueError("milestone_months must be a nonempty list")
    for count in months:
        calendar_months_after(today, count)
    if months != sorted(set(months)) or milestone_months is not None and milestone_months not in months:
        raise ValueError("milestone_months must be unique, increasing policy values")
    carried = receipt_entries([] if carry_forward is None else carry_forward, months)
    reviewed_entries = receipt_entries([] if reviewed is None else reviewed, months, reviewed=True)
    if any(local_moment(entry["receipt_date"], timezone) > moment for entry in reviewed_entries.values()):
        raise ValueError("reviewed receipt_date cannot be in the future")
    if evidence.get("accounts_complete") is not True or evidence.get("opportunities_complete") is not True:
        raise ValueError("complete Account and Opportunity reads required")
    owner_id = evidence["owner_id"]
    if not isinstance(owner_id, str) or not owner_id:
        raise ValueError("current Salesforce user id required")
    accounts, opportunities = evidence["accounts"], evidence["opportunities"]
    if not isinstance(accounts, list) or not isinstance(opportunities, list):
        raise ValueError("Account and Opportunity records must be lists")
    by_account, seen, conflicts = {}, {}, {}
    for opportunity in opportunities:
        identifier = opportunity["Id"]
        if not isinstance(opportunity.get("IsClosed"), bool) or not isinstance(opportunity.get("IsWon"), bool):
            raise ValueError("IsClosed and IsWon must be Salesforce booleans")
        if identifier in seen:
            previous = seen[identifier]
            if previous == opportunity:
                raise ValueError("duplicate Opportunity Id")
            for owner_account in (previous["AccountId"], opportunity["AccountId"]):
                conflicts.setdefault(owner_account, []).append(f"{identifier}: conflicting Opportunity anchor evidence")
            continue
        seen[identifier] = opportunity
        by_account.setdefault(opportunity["AccountId"], []).append(opportunity)
    owned = []
    account_ids = set()
    for account in accounts:
        if account["Id"] in account_ids:
            raise ValueError("duplicate Account Id")
        account_ids.add(account["Id"])
        if account.get("OwnerId") == owner_id:
            owned.append(account)
    if on_demand:
        owned = [account for account in owned if account["Id"] == account_id] if account_id is not None else [
            account for account in owned if account["Name"] == account_name]
        if len(owned) != 1:
            raise ValueError("on-demand requires exactly one named owned Account")
    output, handled = [], set()
    not_due_count = subscription_date_needs_input_count = excluded_count = 0
    for account in owned:
        identifier = account["Id"]
        related = by_account.get(identifier, [])
        won = [record for record in related if record["IsClosed"] and record["IsWon"] and record.get("Deal_Type__c") != "Paid Trial"]
        carried_account = any(key[0] == identifier for key in carried)
        if not won and not on_demand and not carried_account:
            excluded_count += 1
            continue
        open_ids = sorted(record["Id"] for record in related if not record["IsClosed"])
        row = {"account_id": identifier, "account_name": account["Name"],
               "won_opportunity_ids": sorted(record["Id"] for record in won), "open_opportunity_ids": open_ids,
               "action_route": "pipeline_hygiene" if open_ids else "customer_review",
               "anchor": None, "anchor_evidence": [], "milestone": None, "superseded": [], "already_reviewed": [],
               "renewals": [], "usage": None, "usage_ready": False, "needs_input": list(conflicts.get(identifier, []))}
        dates = []
        if not won:
            row["needs_input"].append("first verified non-trial Closed Won anchor missing")
        for record in sorted(won, key=lambda item: item["Id"]):
            row["anchor_evidence"].append({"opportunity_id": record["Id"], "close_date": record.get("CloseDate")})
            try:
                if "Deal_Type__c" not in record:
                    raise ValueError("non-trial status unverified")
                closed = date.fromisoformat(record.get("CloseDate"))
                if closed > today:
                    raise ValueError("Closed Won CloseDate is in the future")
                dates.append((closed, record["Id"]))
            except (ValueError, TypeError):
                row["needs_input"].append(f"{record['Id']}: missing or invalid Closed Won CloseDate or non-trial status")
            end = record.get("Subscription_Cancel_Date__c")
            try:
                end_date = date.fromisoformat(end)
            except (ValueError, TypeError):
                row["needs_input"].append(f"{record['Id']}: Subscription End Date missing or invalid")
                continue
            notice = end_date - timedelta(days=settings["renewal_notice_days"])
            notice_moment = datetime.combine(notice, datetime.min.time(), timezone)
            eligible = on_demand or start < notice_moment <= moment or moment < notice_moment <= next_run
            status = "notice window passed" if notice < today else "proposal candidate" if eligible else "not_due"
            row["renewals"].append({"opportunity_id": record["Id"], "subscription_end_date": end_date.isoformat(),
                                    "notice_date": notice.isoformat(), "status": status, "in_review_window": eligible,
                                    "task_due_date": notice.isoformat() if eligible and notice >= today else None})
        if not conflicts.get(identifier) and len(dates) == len(won) and dates:
            earliest = min(closed for closed, opportunity_id in dates)
            row["anchor"] = {"date": earliest.isoformat(), "opportunity_ids": sorted(
                opportunity_id for closed, opportunity_id in dates if closed == earliest)}
            row["milestone"], row["superseded"], row["already_reviewed"] = milestone_selection(
                earliest, months, moment, start, window, identifier, carried, reviewed_entries, milestone_months)
            for count in months:
                key = (identifier, count, calendar_months_after(earliest, count).isoformat())
                if key in carried and date.fromisoformat(key[2]) <= today:
                    handled.add(key)
            if row["milestone"]["status"] == "due" or row["already_reviewed"]:
                handled.add((identifier, None, None))
        selected = (on_demand or carried_account or row["anchor"] is None or row["already_reviewed"] or row["superseded"]
                    or row["milestone"]["status"] == "due" or any(item["in_review_window"] for item in row["renewals"]))
        if not selected:
            not_due_count += 1
            subscription_date_needs_input_count += any("Subscription End Date" in reason for reason in row["needs_input"])
            continue
        try:
            row["org_uuid"] = resolve_org(account)
        except ValueError as error:
            row["needs_input"].append(str(error))
            output.append(row)
            continue
        if row["milestone"] and row["milestone"]["status"] == "due":
            usage = evidence.get("usage", {}).get(identifier)
            if usage is None:
                row["needs_input"].append("usage evidence missing")
            else:
                try:
                    if usage.get("complete") is not True:
                        raise ValueError("complete usage results required")
                    summary = summarize_usage({**usage, "Account": account})
                    if date.fromisoformat(summary["data_through"]) != today - timedelta(days=1):
                        raise ValueError("usage data_through must be yesterday for this review")
                    for key, fields in (("weekly_trend", {"week_start", "active_users", "queries"}),
                                        ("feature_mix", {"kind", "value", "queries", "users"})):
                        records = usage.get(key)
                        if not isinstance(records, list):
                            raise ValueError(f"complete {key} results required")
                        for record in records:
                            if not isinstance(record, dict) or not fields <= record.keys():
                                raise ValueError(f"{key} fields missing")
                            count_value(record["queries"])
                            if key == "weekly_trend":
                                date.fromisoformat(record["week_start"])
                                count_value(record["active_users"])
                            else:
                                if record["kind"] not in {"mode", "model"}:
                                    raise ValueError("feature_mix kind must be mode or model")
                                count_value(record["users"])
                        summary[key] = records
                    summary["idle_seats"] = summary["roster_seats"] - summary["active_users"]
                    row["usage"] = summary
                    row["usage_ready"] = True
                except (ValueError, KeyError, TypeError) as error:
                    row["needs_input"].append(str(error))
        output.append(row)
    outstanding = [{**entry, "reason": "held milestone not resolved against current owned Account and anchor"}
                   for key, entry in carried.items() if key not in handled] if not on_demand else []
    return {"as_of_date": today.isoformat(), "mode": "on_demand" if on_demand else "scheduled", "window": window,
            "accounts": output, "skipped": [], "not_due_count": not_due_count, "excluded_count": excluded_count,
            "subscription_date_needs_input_count": subscription_date_needs_input_count, "carry_forward_held": outstanding,
            "expansion_type": settings["expansion_type"], "expansion_stage": settings["expansion_stage"], "writes": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--window-start")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--account-id")
    selector.add_argument("--account-name")
    parser.add_argument("--milestone-months", type=int)
    parser.add_argument("--carry-forward", type=Path)
    parser.add_argument("--reviewed", type=Path)
    parser.add_argument("--policy", type=Path, default=ROOT / "_core/policy.yaml")
    arguments = parser.parse_args()
    try:
        carried = json.loads(arguments.carry_forward.read_text()) if arguments.carry_forward else []
        reviewed = json.loads(arguments.reviewed.read_text()) if arguments.reviewed else []
        result = review_customers(json.loads(arguments.input.read_text()), arguments.as_of,
                                  yaml.safe_load(arguments.policy.read_text()), arguments.window_start,
                                  arguments.account_id, arguments.account_name, carried, reviewed, arguments.milestone_months)
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({"valid": False, "error": str(error)}))
        return 2
    print(json.dumps({"valid": True, **result}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
