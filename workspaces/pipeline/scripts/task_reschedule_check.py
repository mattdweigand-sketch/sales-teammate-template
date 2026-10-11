#!/usr/bin/env python3
"""Check a saved Task reschedule proposal or its immediately pre-write reread.

Usage: task_reschedule_check.py --input <sandbox.json> --phase proposal|prewrite
       --as-of <run-start timestamp with offset> --note-prefix <policy value>

Input has writer (triage|deal_thread), task (native Task), account (native
Account), opportunity (native Opportunity or null), related_account and
related_opportunity (unchanged native Salesforce query results, the latter null
only without an Opportunity), related_account_soql and related_opportunity_soql
(unchanged requested queries), current_action_task_ids, desired_date and note_line.
Native query results require records, totalSize and hasMore=false. Related queries
select all baseline fields with only WhatId and IsClosed=false filters, no LIMIT
or OFFSET. Both predicate orders and an optional ORDER BY are supported.
Task fields required: attributes.type=Task, Id, OwnerId, Subject, Status, IsClosed,
ActivityDate, LastModifiedDate, WhatId, WhoId and Description (null is valid).
Account requires attributes.type=Account and Id. Opportunity also needs
AccountId. Review IDs must resolve to these related open Tasks, not just share
a date or Account. The helper does not judge which action is current.
Optional manual_one_deal binds task_id, opportunity_id, command_text, command_url
and source_kind=operator_typed_command. Only writer=triage and one reviewed current
Task can use it, including a future Task. This is not buyer evidence or approval.
Save returned manual_one_deal as baseline_manual_one_deal for prewrite. Changed
provenance fails closed. Scheduled triage omits it and keeps future exclusions.

Proposal ready returns baseline, baseline_links and payload. Save unchanged with the
displayed proposal. Prewrite additionally requires baseline and
displayed_payload and baseline_links, and takes new Task, links, queries and review.
Only ready includes a payload, limited to Id, ActivityDate and Description.
Other statuses are no-op, stale and needs-input. Exit 1 means non-ready,
exit 2 means unusable JSON/arguments. No network or writes. Native reads and
review claims cannot be authenticated here. Ready is not approval, proof of
freshness or an atomic lock. Both writers must still obtain their contract's
approval and verify native readback. A race after the last read remains.
"""

import argparse
from collections.abc import Mapping
from datetime import date, datetime
import json
from pathlib import Path
import re
import sys
from typing import Any, Literal, NotRequired, TypedDict, cast
from urllib.parse import urlsplit


class NativeTaskSnapshot(TypedDict):
    attributes: dict[str, str]
    Id: str
    OwnerId: str
    Subject: str
    Status: str
    IsClosed: bool
    ActivityDate: str | None
    LastModifiedDate: str
    WhatId: str
    WhoId: str | None
    Description: str | None


class NativeAccountLink(TypedDict):
    attributes: dict[str, str]
    Id: str


class NativeOpportunityLink(TypedDict):
    attributes: dict[str, str]
    Id: str
    AccountId: str


class NativeRelatedTaskQuery(TypedDict):
    records: list[NativeTaskSnapshot]
    totalSize: int
    hasMore: bool


class NativeTaskLinks(TypedDict):
    account: NativeAccountLink
    opportunity: NativeOpportunityLink | None


class TaskReschedulePayload(TypedDict):
    Id: str
    ActivityDate: str
    Description: str


class ManualOneDeal(TypedDict):
    task_id: str
    opportunity_id: str
    command_text: str
    command_url: str
    source_kind: Literal["operator_typed_command"]


class TaskRescheduleRequest(TypedDict):
    writer: Literal["triage", "deal_thread"]
    task: NativeTaskSnapshot
    account: NativeAccountLink
    opportunity: NativeOpportunityLink | None
    related_account: NativeRelatedTaskQuery
    related_opportunity: NativeRelatedTaskQuery | None
    related_account_soql: str
    related_opportunity_soql: str | None
    current_action_task_ids: list[str]
    desired_date: str
    note_line: str
    baseline: NotRequired[NativeTaskSnapshot]
    baseline_links: NotRequired[NativeTaskLinks]
    displayed_payload: NotRequired[TaskReschedulePayload]
    manual_one_deal: NotRequired[ManualOneDeal]
    baseline_manual_one_deal: NotRequired[ManualOneDeal]


class TaskRescheduleResult(TypedDict):
    status: Literal["ready", "no-op", "stale", "needs-input"]
    reasons: list[str]
    baseline: NotRequired[NativeTaskSnapshot]
    baseline_links: NotRequired[NativeTaskLinks]
    payload: NotRequired[TaskReschedulePayload]
    manual_one_deal: NotRequired[ManualOneDeal]


TASK_BASELINE_FIELDS = (
    "Id", "OwnerId", "Subject", "Status", "IsClosed", "ActivityDate", "LastModifiedDate",
    "WhatId", "WhoId", "Description",
)


def _native_id(value: Any, prefix: str = "") -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?", value)) and value.startswith(prefix)


def _native_type(record: Any, object_type: str) -> bool:
    return isinstance(record, dict) and isinstance(record.get("attributes"), dict) and record["attributes"].get("type") == object_type


def _local_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be native text with an offset")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or "T" not in value:
        raise ValueError("timestamp requires time and offset")
    return parsed


def _native_date(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("date must be YYYY-MM-DD")
    return date.fromisoformat(value)


def _task_snapshot(record: Any) -> NativeTaskSnapshot:
    if not _native_type(record, "Task") or any(field not in record for field in TASK_BASELINE_FIELDS):
        raise ValueError("Task requires native type and all baseline fields")
    if not _native_id(record["Id"], "00T") or not _native_id(record["WhatId"]):
        raise ValueError("Task Id or WhatId is invalid")
    if not _native_id(record["OwnerId"]) or record["OwnerId"][:3] not in {"005", "00G"}:
        raise ValueError("Task OwnerId requires a native User or Group id")
    if record["WhoId"] is not None and not _native_id(record["WhoId"]):
        raise ValueError("Task WhoId is invalid")
    if any(not isinstance(record[field], str) or not record[field].strip() for field in ("Subject", "Status")):
        raise ValueError("Task Subject and Status require native text")
    if type(record["IsClosed"]) is not bool or (record["Status"] == "Completed" and not record["IsClosed"]):
        raise ValueError("Task closed state is missing or inconsistent")
    if record["Description"] is not None and not isinstance(record["Description"], str):
        raise ValueError("Task Description must be native text or null")
    if record["ActivityDate"] is not None:
        _native_date(record["ActivityDate"])
    _local_timestamp(record["LastModifiedDate"])
    return cast(NativeTaskSnapshot, {"attributes": {"type": "Task"}, **{field: record[field] for field in TASK_BASELINE_FIELDS}})


def _uncapped_related_query(query: Any, link_id: str) -> None:
    if not isinstance(query, str):
        raise ValueError("unchanged requested related-Task SOQL is required")
    link_filter = r"WhatId\s*=\s*'(?-i:" + re.escape(link_id) + ")'"
    open_filter = r"IsClosed\s*=\s*false"
    predicates = f"(?:{link_filter}\\s+AND\\s+{open_filter}|{open_filter}\\s+AND\\s+{link_filter})"
    order = r"(?:\s+ORDER\s+BY\s+\w+(?:\s+(?:ASC|DESC))?(?:\s+NULLS\s+(?:FIRST|LAST))?)?"
    matched = re.fullmatch(r"\s*SELECT\s+([\w\s,]+)\s+FROM\s+Task\s+WHERE\s+" + predicates + order + r"\s*", query, re.I)
    if matched is None:
        raise ValueError("related query must read all open Tasks for the native link, without LIMIT, OFFSET or extra filters")
    fields = {field.strip().casefold() for field in matched[1].split(",")}
    if not {field.casefold() for field in TASK_BASELINE_FIELDS} <= fields:
        raise ValueError("related query must select every native Task baseline field")


def _related_tasks(envelope: Any, link_id: str, query: Any) -> dict[str, dict[str, Any]]:
    _uncapped_related_query(query, link_id)
    if not isinstance(envelope, dict) or envelope.get("hasMore") is not False:
        raise ValueError("related Tasks require native hasMore explicitly false")
    if set(envelope) != {"totalSize", "records", "hasMore"}:
        raise ValueError("related native result has paging, error or unsupported schema markers")
    records = envelope.get("records")
    if not isinstance(records, list) or type(envelope.get("totalSize")) is not int or envelope["totalSize"] != len(records):
        raise ValueError("related Task count must match the complete native records")
    indexed = {}
    for record in records:
        snapshot = _task_snapshot(record)
        if snapshot["WhatId"] != link_id or snapshot["IsClosed"] or snapshot["Id"] in indexed:
            raise ValueError("related Task is closed, duplicated or bound to a different record")
        indexed[snapshot["Id"]] = snapshot
    return indexed


def _task_link_snapshot(request: Any) -> NativeTaskLinks:
    if not isinstance(request, Mapping):
        raise ValueError("native link snapshot is required")
    account, opportunity = request.get("account"), request.get("opportunity")
    if not _native_type(account, "Account") or not _native_id(account.get("Id"), "001"):
        raise ValueError("native Account link is required")
    opportunity_link = None
    if opportunity is not None:
        if not _native_type(opportunity, "Opportunity") or not _native_id(opportunity.get("Id"), "006") or opportunity.get("AccountId") != account["Id"]:
            raise ValueError("native Opportunity must bind to the supplied Account")
        opportunity_link = {"attributes": {"type": "Opportunity"}, "Id": opportunity["Id"], "AccountId": opportunity["AccountId"]}
    elif "opportunity" not in request:
        raise ValueError("Opportunity absence must be explicit")
    return {"account": {"attributes": {"type": "Account"}, "Id": account["Id"]}, "opportunity": opportunity_link}


def _bound_action_tasks(request: Mapping[str, Any], task: dict[str, Any]) -> list[str]:
    links = _task_link_snapshot(request)
    account, opportunity = links["account"], links["opportunity"]
    related = _related_tasks(request.get("related_account"), account["Id"], request.get("related_account_soql"))
    target_links = {account["Id"]}
    if opportunity is not None:
        opportunity_tasks = _related_tasks(request.get("related_opportunity"), opportunity["Id"], request.get("related_opportunity_soql"))
        if related.keys() & opportunity_tasks.keys():
            raise ValueError("one native Task ID cannot bind to both Account and Opportunity")
        related.update(opportunity_tasks)
        target_links.add(opportunity["Id"])
    elif "opportunity" not in request or "related_opportunity" not in request or request.get("related_opportunity") is not None or "related_opportunity_soql" not in request or request.get("related_opportunity_soql") is not None:
        raise ValueError("Opportunity absence must be explicit and consistent")
    if task["WhatId"] not in target_links:
        raise ValueError("exact Task is not linked to the supplied Opportunity or Account")
    if not task["IsClosed"] and related.get(task["Id"]) != task:
        raise ValueError("exact open Task is missing or inconsistent in related native reads")
    reviewed = request.get("current_action_task_ids")
    if not isinstance(reviewed, list) or (not reviewed and not task["IsClosed"]) or any(not _native_id(task_id, "00T") for task_id in reviewed):
        raise ValueError("reviewed current-action Task IDs are required")
    if len(set(reviewed)) != len(reviewed) or any(task_id not in related for task_id in reviewed):
        raise ValueError("reviewed IDs must uniquely bind to supplied related open Tasks")
    return reviewed


def check_task_reschedule(
    request: TaskRescheduleRequest, *, phase: Literal["proposal", "prewrite"],
    as_of: str, note_prefix: str,
) -> TaskRescheduleResult:
    """Fail closed on native evidence gaps, without judging intent or approval."""
    try:
        if phase not in ("proposal", "prewrite") or not isinstance(request, Mapping):
            raise ValueError("request and proposal/prewrite phase are required")
        run_start = _local_timestamp(as_of)
        if not isinstance(note_prefix, str) or not note_prefix.startswith("M/D/YY") or not note_prefix[len("M/D/YY"):].strip():
            raise ValueError("note prefix requires the policy M/D/YY placeholder")
        writer = request.get("writer")
        if writer not in ("triage", "deal_thread"):
            raise ValueError("writer must be triage or deal_thread")
        task = _task_snapshot(request.get("task"))
        links = _task_link_snapshot(request)
        reviewed = _bound_action_tasks(request, task)
        manual = request.get("manual_one_deal")
        if "manual_one_deal" in request:
            fields = {"task_id", "opportunity_id", "command_text", "command_url", "source_kind"}
            if writer != "triage" or not isinstance(manual, dict) or set(manual) != fields:
                raise ValueError("manual one-deal requires its exact typed-command fields and writer=triage")
            opportunity = links["opportunity"]
            if opportunity is None or manual["opportunity_id"] != opportunity["Id"] or manual["task_id"] != task["Id"] or reviewed != [task["Id"]]:
                raise ValueError("manual one-deal must bind the selected Opportunity and its single current-action Task")
            if manual["source_kind"] != "operator_typed_command" or not isinstance(manual["command_text"], str) or not manual["command_text"].strip():
                raise ValueError("manual source must be Operator's nonempty typed command, never buyer evidence")
            command_url = manual["command_url"]
            if not isinstance(command_url, str) or any(character.isspace() for character in command_url) or urlsplit(command_url).scheme != "https" or not urlsplit(command_url).netloc:
                raise ValueError("manual command needs its native https source link")
        if phase == "prewrite" and request.get("baseline_manual_one_deal") != manual:
            raise ValueError("manual command provenance changed from the proposal baseline")
        desired = _native_date(request.get("desired_date"))
        note = request.get("note_line")
        written_prefix = note_prefix.replace("M/D/YY", f"{run_start.month}/{run_start.day}/{run_start:%y}")
        if not isinstance(note, str) or not note.startswith(written_prefix) or not note[len(written_prefix):].strip() or any(char in note for char in "\r\n"):
            raise ValueError("note must be one displayed line with the dated policy prefix")
        baseline = _task_snapshot(request.get("baseline")) if phase == "prewrite" else task
        baseline_links = _task_link_snapshot(request.get("baseline_links")) if phase == "prewrite" else links
        if baseline["Id"] != task["Id"]:
            raise ValueError("proposal baseline must identify the exact Task")
        baseline_link_ids = {baseline_links["account"]["Id"]}
        if baseline_links["opportunity"] is not None:
            baseline_link_ids.add(baseline_links["opportunity"]["Id"])
        if baseline["WhatId"] not in baseline_link_ids:
            raise ValueError("baseline Task must bind to its saved native links")
        payload: TaskReschedulePayload = {"Id": task["Id"], "ActivityDate": desired.isoformat(),
                   "Description": note + ("\n" + baseline["Description"] if baseline["Description"] else "")}
        if phase == "prewrite" and request.get("displayed_payload") != payload:
            raise ValueError("prewrite payload must exactly match the displayed date and note with history")
    except (ValueError, TypeError) as error:
        return {"status": "needs-input", "reasons": [str(error)]}
    if len(reviewed) > 1:
        return {"status": "needs-input", "reasons": ["current-action review is ambiguous"]}
    if task["IsClosed"]:
        return {"status": "no-op", "reasons": ["Task is completed or closed"]}
    if reviewed[0] != task["Id"]:
        return {"status": "no-op", "reasons": ["Task was replaced by the verified current-action Task"]}
    if task["ActivityDate"] == desired.isoformat():
        return {"status": "no-op", "reasons": ["desired date is already satisfied, without a new note"]}
    changed = [field for field in TASK_BASELINE_FIELDS if baseline[field] != task[field]]
    if baseline_links != links:
        changed.append("Opportunity/Account linkage")
    if changed:
        return {"status": "stale", "reasons": ["proposal baseline changed: " + ", ".join(changed)]}
    if writer == "triage" and manual is None and task["ActivityDate"] is not None and _native_date(task["ActivityDate"]) > run_start.date():
        return {"status": "no-op", "reasons": ["future-dated Task is outside the triage queue"]}
    result: TaskRescheduleResult = {"status": "ready", "reasons": [], "baseline": baseline, "baseline_links": baseline_links, "payload": payload}
    if manual is not None:
        result["manual_one_deal"] = dict(manual)
    return result


def main() -> int:
    """Run the offline check on a saved sandbox request."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=("proposal", "prewrite"))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--note-prefix", required=True)
    arguments = parser.parse_args()
    try:
        request = json.loads(arguments.input.read_text())
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    result = check_task_reschedule(request, phase=arguments.phase, as_of=arguments.as_of, note_prefix=arguments.note_prefix)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    sys.exit(main())
