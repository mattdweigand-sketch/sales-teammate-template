#!/usr/bin/env python3
"""Build the forecast-weekly notification from verified coverage and the workflow status.

Usage: python3 forecast_notify.py --since <ISO datetime with offset, run start, weekly mode only>
                                  --thread-url <URL of this run thread>
                                  [--summary "<one line: booked, call, gap, candidates>"]
                                  [--policy PATH] [--schedule "<cadence text>"]
                                  [--process-status ready|incomplete|review-needed]

Run from the sandbox root. Runs coverage_check.py --scope forecast --since <since>
itself in JSON mode and checks its exit code, ready flag, and completion status. Prints one JSON object for send_notification:
title "Weekly forecast ready" only when coverage is complete and the caller reports ready, otherwise
"Weekly forecast incomplete" with the coverage lines in the body. The body
always carries the summary (when given), the coverage line, and the thread URL.
Exit 0 when the payload was built; exit 2 when coverage_check could not run.
Send the printed payload unchanged.

Monday tracking uses --tracking-input reviewed.json instead of forecast-only coverage. --since is not required there.
It validates the tracking calculation and reads_complete, returning {notify, payload}.
Unavailable prior open Ids are listed with their reviewed reasons and the kept baseline, never suppressed as unchanged.
Tracking summaries are built from that calculation. --summary is ignored in tracking mode.
Only complete, ready, unchanged baseline runs have notify false. Missing reads or invalid
tracking input produce an incomplete payload. Send only payload unchanged when notify is true.
"""
import argparse
from decimal import Decimal
import json
import subprocess
import sys
from pathlib import Path

import yaml

COVERAGE = Path(__file__).resolve().parents[5] / "_core" / "scripts" / "coverage_check.py"
READY, INCOMPLETE = "Weekly forecast ready", "Weekly forecast incomplete"


def run_coverage(since: str, policy: str | None, calls_dir: Path | None = None) -> tuple[int, str]:
    cmd = [sys.executable, str(COVERAGE), "--scope", "forecast", "--since", since, "--json"]
    if policy:
        cmd += ["--policy", policy]
    if calls_dir is not None:
        cmd += ["--calls-dir", str(calls_dir)]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def build_payload(code: int, coverage: str, summary: str, thread_url: str, schedule: str | None, process_status: str = "ready") -> dict:
    try:
        result = json.loads(coverage)
    except ValueError:
        result = None
    ready = code == 0 and isinstance(result, dict) and result.get("ready") is True and result.get("process_status") == "complete" and process_status == "ready"
    lines = result.get("lines", []) if isinstance(result, dict) else [l for l in coverage.splitlines() if l.strip()]
    if process_status != "ready":
        lines.append("Workflow status: " + process_status)
    code = 0 if ready else 1
    parts = []
    if summary:
        parts.append(summary.strip())
    if code == 0:
        parts.extend(lines or ["Coverage ready."])
    else:
        parts.append("Forecast incomplete. " + " ".join(lines) if lines else "Forecast incomplete: coverage check returned no output.")
    parts.append(thread_url)
    payload = {"title": READY if code == 0 else INCOMPLETE, "body": " ".join(parts), "channels": ["in_app"]}
    if schedule:
        payload["schedule_description"] = schedule
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Forecast notification payload gated on coverage_check.")
    parser.add_argument("--since", help="Run start with offset. Required for weekly coverage, ignored by --tracking-input")
    parser.add_argument("--thread-url", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--policy")
    parser.add_argument("--calls-dir", type=Path, help="Explicit saved connector result directory passed to coverage_check")
    parser.add_argument("--schedule")
    parser.add_argument("--process-status", choices=["ready", "incomplete", "review-needed"], default="ready")
    parser.add_argument("--tracking-input", type=Path, help="Monday tracking input, gates complete reads and material changes without forecast-only coverage")
    args = parser.parse_args(argv)
    if args.tracking_input:
        policy_path = Path(args.policy) if args.policy else Path(__file__).resolve().parents[5] / "_core/policy.yaml"
        try:
            data = json.loads(args.tracking_input.read_text())
            policy = yaml.safe_load(policy_path.read_text())
            decision = tracking_decision(data, policy, args.summary, args.thread_url, args.process_status)
        except (OSError, ValueError, TypeError, KeyError, ArithmeticError) as error:
            decision = {"notify": True, "payload": tracking_payload(False, str(error), args.thread_url)}
        print(json.dumps(decision))
        return 0
    if not args.since:
        parser.error("--since is required for the weekly forecast notification")
    code, coverage = run_coverage(args.since, args.policy, args.calls_dir)
    if code not in (0, 1):
        print(f"coverage_check did not run (exit {code}): {coverage}", file=sys.stderr)
        return 2
    print(json.dumps(build_payload(code, coverage, args.summary, args.thread_url, args.schedule, args.process_status)))
    return 0


def tracking_payload(ready, summary, thread_url):
    return {"title": "Monday pace report ready" if ready else "Monday pace report incomplete",
            "body": "\n".join(part for part in (summary.strip(), thread_url) if part), "channels": ["in_app"]}


def _tracking_notification_summary(result: dict, policy: dict) -> str:
    """Render notification figures only from calculate_tracking, never caller prose."""
    def dollars(value):
        return "unavailable" if value is None else f"${Decimal(value):,.2f}"

    def coverage(value):
        return "target covered" if value is None else value + "x"

    lines = []
    for scope in ("quarter", "year"):
        period = result[scope]
        share = period["largest_two_share_percent"]
        lines.append(
            f'{period["period"]} booked {dollars(period["booked"])} of {dollars(period["target"])}. '
            f'Gap {dollars(period["gap"])}. Linear pace {dollars(period["linear_pace"])}. '
            f'Required per week {dollars(period["required_per_week"])}. Coverage {coverage(period["coverage"])}. '
            f'Largest two {"unavailable" if share is None else share + "%"}. '
            f'Coverage without largest two {coverage(period["coverage_without_largest_two"])}.'
        )
    minimum = str(policy["forecast"]["tracking"]["coverage_min"])
    forward = result["forward_quarters"]
    lines.append("Forward coverage " + (" | ".join(
        f'{row["period"]} {coverage(row["coverage"])} against {minimum}x. '
        f'Target {dollars(row["target"])}. Pipeline {dollars(row["open_pipeline"])}. '
        f'Shortfall {dollars(row["coverage_shortfall"])}.' for row in forward) or "not configured."))
    created = result["created_arr"]
    if created is None:
        lines.append("Created ARR not configured.")
    else:
        contributions = " | ".join(
            f'{row["period"]} {dollars(row["required_created_arr_per_week"])}' for row in forward)
        lines.append(f'Created ARR {dollars(created["amount"])} in {created["window_days"]} days '
                     f'against {dollars(created["required_per_week"])} weekly creation need. {contributions}.')
    if result["unavailable_prior"]:
        lines.append(f'Comparison incomplete, baseline {result["baseline_as_of"]} kept. Prior open Ids unavailable, not closed or moved: '
                     + " | ".join(f'{row["Id"]} ({row["reason"]})' for row in result["unavailable_prior"]) + ".")
    return "\n".join(lines)


def tracking_decision(data, policy, summary, thread_url, process_status="ready"):
    from forecast_math import calculate_tracking
    result = calculate_tracking(data, policy)
    ready = data.get("reads_complete") is True and process_status == "ready"
    if ready and result["baseline_available"] and not result["material_change"]:
        return {"notify": False, "payload": None}
    summary = _tracking_notification_summary(result, policy)
    if not ready:
        summary = "Salesforce reads not verified complete or workflow needs review. " + summary
    return {"notify": True, "payload": tracking_payload(ready, summary, thread_url)}


if __name__ == "__main__":
    sys.exit(main())
