#!/usr/bin/env python3
"""Check the fresh, complete Task collection before closing task-triage-speed-run.

Usage: closeout_check.py <saved_result.json> --as-of <ISO datetime with offset>
"""
import argparse
from datetime import date, datetime
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "_core" / "scripts"))
from _saved_json import load_saved, records_of  # noqa: E402

CLOSED_STATUSES = {'completed', 'closed'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result')
    parser.add_argument('--as-of', required=True, help='Run timestamp with offset; sets the local date')
    args = parser.parse_args(argv)
    try:
        as_of = datetime.fromisoformat(args.as_of.replace('Z', '+00:00'))
        if as_of.tzinfo is None:
            raise ValueError('--as-of needs a timezone offset')
        today = as_of.date()
        rows = records_of(load_saved(args.result))
    except (OSError, ValueError, TypeError) as exc:
        print(f'FAIL closeout source/date: {exc}')
        return 1
    bad = []
    for rec in rows:
        if rec.get('IsClosed') is True or str(rec.get('Status') or '').strip().lower() in CLOSED_STATUSES:
            continue
        try:
            due = date.fromisoformat(str(rec.get('ActivityDate') or ''))
        except ValueError:
            due = None
        if due is None or due <= today:
            bad.append(rec)
    if bad:
        print(f'FAIL {len(bad)} open Task(s) due today, overdue, or undated:')
        for rec in bad:
            print(f"- {rec['Id']} | {rec.get('Subject')} | due {rec.get('ActivityDate') or 'none'}")
        return 1
    print(f'PASS no open Tasks due today, overdue, or undated (as of {today})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
