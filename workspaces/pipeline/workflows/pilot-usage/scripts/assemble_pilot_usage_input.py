"""Build the normalized pilot-usage input from saved warehouse results plus the approved review file.

Called by build_pilot_usage_report.py. Nothing here talks to a connector.

`load_marked_results` reads three explicitly selected Snowflake submit handles. Their marker,
organization, fixed report dates, and complete terminal results must match; no fallback to older calls.
`assemble_input` applies the review file the user approved in chat and returns the input for
compute_pilot_usage_report.py. Roster rows and tasks whose email domain is in
`policy.tooling.internal_domains` are dropped, as are tasks outside pilot_start..data_through.

Review file keys:
    customer_name, organization_uuid, prepared_by, pilot_end (ISO, required), approved (bool)
    pilot_start, data_through (resolved ISO dates, required before querying tasks)
    optional: confidentiality_label (default: policy), display_names {email: name}, participation_notes {email: text}
    categories: [{category_id, label, description}]
    task_categories: {context_uuid: category_id}   missing -> policy uncategorized id
    narratives: {scope_note, usage_highlights[{label,text}], representative_work[{title,user_emails,summary}],
                 work_interpretation[str], business_value[{label,text}], source_note}
"""

from __future__ import annotations

import re
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pilot_usage_shared import read_json

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "_core" / "scripts"))
from _saved_json import resolve_calls_dir

MARKERS = ("q1_roster", "q4_grants", "q5_tasks")
WAREHOUSE_TIMEZONE = ZoneInfo("America/Los_Angeles")  # q5 dates are date_pt


def default_tool_calls_dir() -> Path:
    """Resolve the one live session directory, or the legacy cwd-relative directory."""
    return resolve_calls_dir()


def _column_names(metadata: Any) -> list[str]:
    if isinstance(metadata, dict):
        metadata = metadata.get("row_type")
    if not isinstance(metadata, list) or not metadata:
        raise RuntimeError("saved result has no column metadata")
    return [column["name"].lower() for column in metadata]


def _merge_partitions(handle: str, pages: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """Concatenate one handle's saved result pages. Only page 0 carries column metadata."""
    ordered = [pages[index] for index in sorted(pages)]
    metadata = next((page["result_set_meta_data"] for page in ordered if page.get("result_set_meta_data")), None)
    if metadata is None:
        raise RuntimeError(f"no saved result page with column metadata for {handle}")
    expected_pages = int(ordered[0].get("total_partitions") or len(ordered))
    if sorted(pages) != list(range(expected_pages)):
        raise RuntimeError(
            f"saved result pages incomplete for {handle}: have {sorted(pages)}, expected {expected_pages}"
        )
    data = [row for page in ordered for row in page["data"]]
    expected_rows = ordered[0].get("total_row_count")
    if expected_rows is not None and len(data) != int(expected_rows):
        raise RuntimeError(f"saved result rows for {handle} total {len(data)}, expected {expected_rows}")
    columns = _column_names(metadata)
    if any(len(row) != len(columns) for row in data):
        raise RuntimeError(f"saved result row width differs from metadata for {handle}")
    return [dict(zip(columns, row)) for row in data]


def _marked_failed(result: dict[str, Any]) -> bool:
    """True when the saved page carries a failure marker, whatever rows it also carries."""
    status = str(result.get("status") or result.get("state") or "").upper()
    return bool(result.get("error")) or any(word in status for word in ("FAIL", "ABORT", "CANCEL", "ERROR"))


def _failure_text(result: dict[str, Any]) -> str:
    return str(result.get("error") or result.get("message") or result.get("status") or result.get("state"))


def _verify_statement(statement: str, marker: str, organization_uuid: str,
                      pilot_start: str | None, data_through: str) -> None:
    """Check the supported SQL scope before trusting its saved result."""
    if not statement.lstrip().startswith(f"-- pilot_usage {marker}\n"):
        raise RuntimeError(f"selected {marker} submit has the wrong SQL marker")
    sql = re.sub(r"--[^\n]*", "", statement)
    orgs = re.findall(r"\borganization_uuid\s*=\s*'([^']+)'", sql, re.I)
    if orgs != [organization_uuid] or re.search(r"\bOR\b", sql, re.I):
        raise RuntimeError(f"selected {marker} submit has the wrong organization scope")
    if marker == "q4_grants":
        dates = re.findall(r"effective_at_pt\s*::\s*DATE\s*<=\s*'([^']+)'", sql, re.I)
        if dates != [data_through]:
            raise RuntimeError("selected q4_grants submit has the wrong report window")
    else:
        snapshots = re.findall(r"(?<![\w.])date_pt\s*=\s*'([^']+)'", sql, re.I)
        if snapshots != [data_through]:
            raise RuntimeError(f"selected {marker} submit has the wrong roster snapshot")
        if marker == "q5_tasks":
            windows = re.findall(r"\b([bq])\.date_pt\s+BETWEEN\s+'([^']+)'\s+AND\s+'([^']+)'", sql, re.I)
            if sorted(windows) != [("b", pilot_start, data_through), ("q", pilot_start, data_through)]:
                raise RuntimeError("selected q5_tasks submit has the wrong report window")


def load_marked_results(tool_calls_dir: Path, statement_handles: dict[str, str],
                        organization_uuid: str, pilot_start: str | None,
                        data_through: str) -> dict[str, list[dict[str, Any]]]:
    """Read only the explicitly selected submits and their complete terminal results."""
    if not statement_handles or set(statement_handles) - set(MARKERS):
        raise ValueError("select known pilot statement handles")
    if len(set(statement_handles.values())) != len(statement_handles) or not all(statement_handles.values()):
        raise ValueError("each query must have a distinct nonempty statement handle")
    statements: dict[str, str] = {}
    for input_path in tool_calls_dir.glob("input_*.json"):
        call = read_json(input_path)
        statement = str(call.get("arguments", {}).get("input", {}).get("statement", ""))
        if not statement:
            continue
        output_path = input_path.with_name(input_path.name.replace("input_", "output_", 1))
        if not output_path.is_file():
            continue
        saved = read_json(output_path)
        result = saved.get("result") if isinstance(saved, dict) else None
        handle = result.get("statement_handle") if isinstance(result, dict) else None
        if handle in statement_handles.values():
            if handle in statements and statements[handle] != statement:
                raise RuntimeError(f"conflicting saved submits for {handle}")
            statements[handle] = statement

    for marker, handle in statement_handles.items():
        if handle not in statements:
            raise RuntimeError(f"no saved submit for selected {marker} handle {handle}")
        _verify_statement(statements[handle], marker, organization_uuid, pilot_start, data_through)

    completed: dict[str, dict[int, dict[str, Any]]] = {}
    failed: dict[str, str] = {}
    for output_path in tool_calls_dir.glob("output_*.json"):
        saved = read_json(output_path)
        result = saved.get("result") if isinstance(saved, dict) else None
        if not isinstance(result, dict):
            continue
        handle = result.get("statement_handle")
        if handle not in statement_handles.values():
            continue
        # A failure page may carry `data: null`; check the marker before the row shape.
        if _marked_failed(result):
            failed[handle] = _failure_text(result)
            completed.pop(handle, None)
            continue
        if handle in failed or not isinstance(result.get("data"), list):
            continue
        status = str(result.get("status") or result.get("state") or "").upper()
        if status and status not in {"SUCCESS", "SUCCEEDED", "COMPLETED", "COMPLETE", "DONE"}:
            continue
        # Status-less connector results must still carry an explicit, consistent row count.
        count = result.get("row_count")
        if count is None or int(count) != len(result["data"]):
            continue
        if not result.get("result_set_meta_data") and not result.get("partition"):
            continue
        partition = int(result.get("partition") or 0)
        pages = completed.setdefault(handle, {})
        current = pages.get(partition)
        if current is not None:
            fields = ("data", "result_set_meta_data", "total_partitions", "total_row_count")
            if any(current.get(key) is not None and result.get(key) is not None
                   and current[key] != result[key] for key in fields):
                raise RuntimeError(f"conflicting saved terminal pages for {handle} partition {partition}")
        pages[partition] = {**(current or {}), **result}

    rows: dict[str, list[dict[str, Any]]] = {}
    for marker, handle in statement_handles.items():
        if handle in failed:
            raise RuntimeError(f"selected {marker} result {handle} is marked failed ({failed[handle]})")
        if handle not in completed:
            raise RuntimeError(f"no completed saved result for selected {marker} handle {handle}")
        rows[marker] = _merge_partitions(handle, completed[handle])
    return rows


def _round_half_up(value: str | float | int | Decimal) -> int:
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _parse_day(value: str) -> date:
    return datetime.fromisoformat(str(value)[:19]).date()


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


def _require_pilot_end(review: dict[str, Any]) -> str:
    value = review.get("pilot_end")
    if not value or not str(value).strip():
        raise ValueError("pilot_end missing")
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError as exc:
        raise ValueError("pilot_end must be an ISO date") from exc


def assemble_input(
    results: dict[str, list[dict[str, Any]]], review: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    if review.get("approved") is not True:
        raise ValueError("review approved must be JSON Boolean true")
    approved = True
    today = datetime.now(WAREHOUSE_TIMEZONE).date()
    data_through = date.fromisoformat(review["data_through"])
    pilot_end = _require_pilot_end(review)
    internal_domains = set(policy["internal_domains"])

    grants = [
        g for g in results["q4_grants"]
        if g.get("voided_at") is None and _parse_day(g["effective_at"]) <= data_through
    ]
    if not grants:
        raise RuntimeError("no non-voided credit grants effective on or before data_through")
    pilot_start = date.fromisoformat(review["pilot_start"])
    grants_dollars = sum(Decimal(str(g["amount_dollars"])) for g in grants)

    display_names: dict[str, str] = review.get("display_names", {})
    notes: dict[str, str] = review.get("participation_notes", {})
    roster_emails = [
        r["user_email"] for r in results["q1_roster"] if _email_domain(r["user_email"]) not in internal_domains
    ]
    roster = [
        {
            "user_id": email,
            "display_name": display_names.get(email, email.split("@")[0]),
            "participation_note": notes.get(email, ""),
        }
        for email in roster_emails
    ]
    known = set(roster_emails)

    uncategorized_id = policy["uncategorized_category_id"]
    categories = list(review["categories"])
    if all(c["category_id"] != uncategorized_id for c in categories):
        categories.append(
            {"category_id": uncategorized_id, "label": policy["uncategorized_label"],
             "description": policy["uncategorized_description"]}
        )
    if len(categories) > len(policy["category_palette"]):
        raise ValueError("category cap includes the reserved Uncategorized category")
    task_categories: dict[str, str] = review.get("task_categories", {})

    sessions = []
    for task in results["q5_tasks"]:
        email = task["user_email"]
        if _email_domain(email) in internal_domains:
            continue
        task_day = _parse_day(task["first_date"])
        if not pilot_start <= task_day <= data_through:
            continue
        if email not in known:
            raise RuntimeError(f"task user is not on the roster: {email}")
        sessions.append(
            {
                "context_uuid": task["context_uuid"],
                "user_id": email,
                "date": task_day.isoformat(),
                "credits": _round_half_up(task["amount_cents"]),
                "category_id": task_categories.get(task["context_uuid"], uncategorized_id),
                "task_title": (task.get("task_title") or "").strip(),
                "classification_reviewed": approved,
            }
        )

    narratives = review["narratives"]
    representative_work = [
        {"title": card["title"], "user_ids": list(card["user_emails"]), "summary": card["summary"]}
        for card in narratives.get("representative_work", [])
    ]

    return {
        "schema_version": 1,
        "report": {
            "customer_name": review["customer_name"],
            "prepared_date": today.isoformat(),
            "prepared_by": review["prepared_by"],
            "pilot_start": pilot_start.isoformat(),
            "pilot_end": pilot_end,
            "data_through": data_through.isoformat(),
            "total_granted_credits": _round_half_up(grants_dollars * 100),
            "confidentiality_label": review.get("confidentiality_label") or policy["confidentiality_label"],
        },
        "organization_scopes": [
            {"organization_uuid": review["organization_uuid"], "workspace_role": "pilot org",
             "reviewed": approved}
        ],
        "roster": roster,
        "categories": categories,
        "sessions": sessions,
        "reviewed_narratives": {
            "reviewed": approved,
            "scope_note": narratives.get("scope_note", ""),
            "usage_highlights": narratives.get("usage_highlights", []),
            "representative_work": representative_work,
            "work_interpretation": narratives.get("work_interpretation", []),
            "business_value": narratives.get("business_value", []),
            "source_note": narratives.get("source_note", ""),
        },
    }
