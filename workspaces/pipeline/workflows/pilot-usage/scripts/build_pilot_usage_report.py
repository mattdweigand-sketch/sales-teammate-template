#!/usr/bin/env python3
"""Resolve the grant-derived window, or build a PDF from exact saved query handles.

window --review review.json --grants-handle HANDLE [--tool-calls DIR]
build --review review.json --roster-handle HANDLE --grants-handle HANDLE
      --tasks-handle HANDLE --output /tmp/pilot-usage/customer.pdf [--renderer BINARY]

The window command fills pilot_start in the local review and resets approval. Set
data_through before submitting grants. The build command runs assemble, compute, render, and print in order;
connector submission and human approval stay in the workflow contract.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from assemble_pilot_usage_input import (
    MARKERS, _parse_day, _require_pilot_end, assemble_input, default_tool_calls_dir, load_marked_results,
)
from compute_pilot_usage_report import compute_pilot_usage_report
from pilot_usage_shared import (
    DEFAULT_POLICY, load_pilot_usage_policy, read_json, require_local_only_output_path, write_local_json,
)
from render_pilot_usage_report import print_pilot_usage_pdf, write_validated_pilot_usage_report_html


def resolve_window(review: dict, grants: list[dict]) -> dict:
    through = date.fromisoformat(review["data_through"])
    end = date.fromisoformat(_require_pilot_end(review))
    kept = [g for g in grants if g.get("voided_at") is None and _parse_day(g["effective_at"]) <= through]
    if not kept:
        raise ValueError("no non-voided grants effective on or before data_through")
    start = date.fromisoformat(review["pilot_start"]) if review.get("pilot_start") else min(_parse_day(g["effective_at"]) for g in kept)
    if not start <= through <= end or start >= end:
        raise ValueError("resolved report window must fall inside the pilot")
    return {**review, "pilot_start": start.isoformat(), "data_through": through.isoformat(), "approved": False}


def build_report(review: dict, tool_calls: Path, handles: dict[str, str],
                 policy: dict, output: Path, renderer: str = "auto") -> dict:
    output = require_local_only_output_path(output)
    results = load_marked_results(tool_calls, handles, review["organization_uuid"],
                                 review["pilot_start"], review["data_through"])
    normalized = assemble_input(results, review, policy)
    computed = compute_pilot_usage_report(normalized, policy)
    write_local_json(output.with_suffix(".input.json"), normalized)
    write_local_json(output.with_suffix(".report.json"), computed)
    html_path = write_validated_pilot_usage_report_html(normalized, policy, computed, output.with_suffix(".html"))
    inspection = print_pilot_usage_pdf(html_path, output, policy, chromium_binary=renderer)
    return {"valid": True, "output": str(output), "page_count": inspection.page_count,
            "billed_contexts": computed["headline"]["task_count"],
            "credits_used": computed["headline"]["credits_used"],
            "granted_credits": computed["headline"]["granted_credits"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("window", "build"))
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--grants-handle", required=True)
    parser.add_argument("--roster-handle")
    parser.add_argument("--tasks-handle")
    parser.add_argument("--tool-calls", type=Path)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--renderer", default="auto")
    args = parser.parse_args()
    review = read_json(args.review)
    calls = args.tool_calls or default_tool_calls_dir()
    if args.action == "window":
        grants = load_marked_results(calls, {"q4_grants": args.grants_handle}, review["organization_uuid"],
                                     None, review["data_through"])["q4_grants"]
        updated = resolve_window(review, grants)
        write_local_json(args.review, updated)
        result = {"pilot_start": updated["pilot_start"], "data_through": updated["data_through"], "approved": False}
    else:
        if not all((args.roster_handle, args.tasks_handle, args.output)):
            parser.error("build requires --roster-handle, --tasks-handle and --output")
        handles = dict(zip(MARKERS, (args.roster_handle, args.grants_handle, args.tasks_handle)))
        result = build_report(review, calls, handles, load_pilot_usage_policy(args.policy), args.output, args.renderer)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
