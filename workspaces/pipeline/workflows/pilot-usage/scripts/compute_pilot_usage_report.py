"""Compute a pilot usage report from one normalized input; fail closed on bad input.

Called by build_pilot_usage_report.py. `validate_computed_pilot_usage_report` recomputes a report
and compares it whole; render calls it before writing HTML.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

def parse_pilot_iso_date(value: str, field_name: str) -> date:
    """Parse an exact date so time-zone truncation never moves pilot boundaries."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc


def _require_non_empty(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _validate_reviewed_pilot_input(normalized_input: dict[str, Any]) -> None:
    if normalized_input["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    if not normalized_input["organization_scopes"]:
        raise ValueError("organization_scopes must not be empty")
    for scope in normalized_input["organization_scopes"]:
        _require_non_empty(scope["organization_uuid"], "organization_uuid")
        if scope["reviewed"] is not True:
            raise ValueError("every organization scope must be explicitly reviewed")
    if normalized_input["reviewed_narratives"]["reviewed"] is not True:
        raise ValueError("reviewed_narratives must be explicitly reviewed")

    report = normalized_input["report"]
    pilot_start = parse_pilot_iso_date(report["pilot_start"], "pilot_start")
    pilot_end = parse_pilot_iso_date(report["pilot_end"], "pilot_end")
    data_through = parse_pilot_iso_date(report["data_through"], "data_through")
    if pilot_start >= pilot_end:
        raise ValueError("pilot_end must be after pilot_start")
    if not pilot_start <= data_through <= pilot_end:
        raise ValueError("data_through must fall inside the pilot window")

    roster_ids = [user["user_id"] for user in normalized_input["roster"]]
    if len(roster_ids) != len(set(roster_ids)):
        raise ValueError("roster contains duplicate user_id values")
    category_ids = [category["category_id"] for category in normalized_input["categories"]]
    if len(category_ids) != len(set(category_ids)):
        raise ValueError("categories contains duplicate category_id values")

    known_users = set(roster_ids)
    known_categories = set(category_ids)
    contexts: set[str] = set()
    for session in normalized_input["sessions"]:
        context_uuid = session["context_uuid"]
        if context_uuid in contexts:
            raise ValueError(f"duplicate context_uuid: {context_uuid}")
        contexts.add(context_uuid)
        if session["user_id"] not in known_users:
            raise ValueError(
                f"session references unknown user_id: {session['user_id']}"
            )
        if session["category_id"] not in known_categories:
            raise ValueError(
                f"session references unknown category_id: {session['category_id']}"
            )
        if session["classification_reviewed"] is not True:
            raise ValueError(f"session classification is not reviewed: {context_uuid}")
        session_date = parse_pilot_iso_date(session["date"], "session date")
        if not pilot_start <= session_date <= data_through:
            raise ValueError(
                f"session date is outside the report window: {context_uuid}"
            )
        if session["credits"] < 0:
            raise ValueError(f"session credits must be non-negative: {context_uuid}")

    for card in normalized_input["reviewed_narratives"]["representative_work"]:
        unknown = set(card["user_ids"]) - known_users
        if unknown:
            raise ValueError(
                f"representative work references unknown users: {sorted(unknown)}"
            )


def _rounded_share_percent(credits: int, credits_used: int) -> int:
    if credits_used == 0:
        return 0
    share = Decimal(credits) * Decimal(100) / Decimal(credits_used)
    return int(share.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _precise_share_percent(credits: int, credits_used: int) -> str:
    if credits_used == 0:
        return "0.0"
    share = Decimal(credits) * Decimal(100) / Decimal(credits_used)
    return str(share.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def compute_pilot_usage_report(normalized_input: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Compute all report metrics and fail closed on source or review mismatches."""
    _validate_reviewed_pilot_input(normalized_input)
    if policy["task_grain"] != "context_uuid":
        raise ValueError("policy task_grain must be context_uuid")
    if policy["credit_unit"] != "cent":
        raise ValueError("policy credit_unit must be cent")
    if policy["credit_display_rule"] != "round_half_up_per_context_then_sum":
        raise ValueError(
            "policy credit_display_rule must be round_half_up_per_context_then_sum"
        )
    palette = policy["category_palette"]
    if not palette:
        raise ValueError("policy category_palette must not be empty")
    if len(normalized_input["categories"]) > len(palette):
        raise ValueError(
            f"{len(normalized_input['categories'])} categories (including the uncategorized one) exceed "
            f"the {len(palette)}-color policy category_palette; merge categories in the review"
        )

    report = normalized_input["report"]
    pilot_start = parse_pilot_iso_date(report["pilot_start"], "pilot_start")
    pilot_end = parse_pilot_iso_date(report["pilot_end"], "pilot_end")
    data_through = parse_pilot_iso_date(report["data_through"], "data_through")
    # Week one runs from pilot_start for week_one_length_days; everything after, through
    # data_through, is one "After" bucket. When data_through is still inside week one the
    # After bucket is empty and week_two_start is None.
    week_one_end = min(
        pilot_start + timedelta(days=policy["week_one_length_days"] - 1),
        data_through,
    )
    week_two_start: date | None = week_one_end + timedelta(days=1)
    if week_two_start > data_through:
        week_two_start = None

    sessions = normalized_input["sessions"]
    task_count = len(sessions)
    credits_used = sum(session["credits"] for session in sessions)
    granted_credits = report["total_granted_credits"]
    if credits_used > granted_credits:
        raise ValueError("credits used cannot exceed granted credits")

    sessions_by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in sessions:
        sessions_by_user[session["user_id"]].append(session)

    users: list[dict[str, Any]] = []
    for roster_user in normalized_input["roster"]:
        user_id = roster_user["user_id"]
        user_sessions = sessions_by_user[user_id]
        session_days = [date.fromisoformat(session["date"]) for session in user_sessions]
        week_one_tasks = sum(1 for day in session_days if day <= week_one_end)
        users.append(
            {
                "user_id": user_id,
                "display_name": roster_user["display_name"],
                "task_count": len(user_sessions),
                "week_one_tasks": week_one_tasks,
                "week_two_tasks": len(user_sessions) - week_one_tasks,
                "credits": sum(session["credits"] for session in user_sessions),
                "active_days": len(set(session_days)),
                "participation_note": roster_user.get("participation_note", ""),
            }
        )
    users.sort(
        key=lambda user: (-user["credits"], -user["task_count"], user["display_name"])
    )

    daily_counts = Counter(session["date"] for session in sessions)
    elapsed_days = (data_through - pilot_start).days + 1
    daily_tasks = [
        {
            "date": (pilot_start + timedelta(days=offset)).isoformat(),
            "task_count": daily_counts[
                (pilot_start + timedelta(days=offset)).isoformat()
            ],
        }
        for offset in range(elapsed_days)
    ]

    category_task_counts = Counter(session["category_id"] for session in sessions)
    category_credit_counts: dict[str, int] = defaultdict(int)
    for session in sessions:
        category_credit_counts[session["category_id"]] += session["credits"]
    categories = [
        {
            "category_id": category["category_id"],
            "label": category["label"],
            "description": category["description"],
            "task_count": category_task_counts[category["category_id"]],
            "credits": category_credit_counts[category["category_id"]],
            "share_percent": _rounded_share_percent(
                category_credit_counts[category["category_id"]], credits_used
            ),
            "share_percent_precise": _precise_share_percent(
                category_credit_counts[category["category_id"]], credits_used
            ),
            "color": palette[index],
        }
        for index, category in enumerate(normalized_input["categories"])
    ]
    categories.sort(key=lambda category: (-category["credits"], category["label"]))

    active_users = [user for user in users if user["task_count"] > 0]
    most_consistent = max(
        active_users,
        key=lambda user: (user["active_days"], user["task_count"], user["credits"]),
        default=None,
    )
    top_user_count = min(policy["top_users"], len(active_users))
    top_user_credits = sum(user["credits"] for user in active_users[:top_user_count])
    day_one_only_user_count = sum(
        1
        for user in active_users
        if {session["date"] for session in sessions_by_user[user["user_id"]]}
        == {pilot_start.isoformat()}
    )

    return {
        "schema_version": 1,
        "report_title": policy["report_title"],
        "report": report,
        "headline": {
            "active_users": len(active_users),
            "seat_count": len(users),
            "task_count": task_count,
            "credits_used": credits_used,
            "active_days": sum(1 for row in daily_tasks if row["task_count"] > 0),
            "elapsed_days": elapsed_days,
            "granted_credits": granted_credits,
            "remaining_credits": granted_credits - credits_used,
        },
        "periods": {
            "week_one_start": pilot_start.isoformat(),
            "week_one_end": week_one_end.isoformat(),
            "week_two_start": week_two_start.isoformat() if week_two_start else None,
            "week_two_end": data_through.isoformat(),
            "pilot_day_number": elapsed_days,
            "pilot_total_days": (pilot_end - pilot_start).days + 1,
        },
        "users": users,
        "daily_tasks": daily_tasks,
        "categories": categories,
        "computed_highlights": {
            "top_user_count": top_user_count,
            "top_user_credit_share_percent": _rounded_share_percent(
                top_user_credits, credits_used
            ),
            "most_consistent_user_id": (
                most_consistent["user_id"] if most_consistent else None
            ),
            "most_consistent_active_days": (
                most_consistent["active_days"] if most_consistent else 0
            ),
            "inactive_user_count": len(users) - len(active_users),
            "day_one_only_user_count": day_one_only_user_count,
        },
        "reviewed_narratives": normalized_input["reviewed_narratives"],
    }



def validate_computed_pilot_usage_report(
    normalized_input: dict[str, Any], policy: dict[str, Any], computed_report: dict[str, Any]
) -> list[str]:
    """Return exact validation failures; an empty list is safe to render."""
    try:
        expected_report = compute_pilot_usage_report(normalized_input, policy)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return [f"input_or_policy_invalid:{exc}"]
    if computed_report != expected_report:
        return ["computed_report_differs_from_recomputed_report"]
    return []
