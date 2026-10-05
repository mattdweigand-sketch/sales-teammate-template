#!/usr/bin/env python3
"""Reduce saved Gmail search_email outputs to a short digest.

Usage: gmail_thread_digest.py <saved_output_json>... [--chars N]

Prints one block per email, newest first (dates parsed as RFC 2822 or ISO
8601; unparseable dates sort last): the first 16 characters of the raw date,
email_id, thread_id, from, to, subject, and the first N characters (default
300) of the body with HTML tags removed and whitespace collapsed. A cut body
ends with `[truncated, M more chars]`. Quoted earlier messages are not
removed. Attachments are listed by filename only, skipping names that start
with image, img_, or ATT (inline images and signature artefacts).

This is an index of the retrieved set, not the evidence. Before a decision
rests on a message (timing, blockers, order form status), read that message
in full by its email_id. Use the digest instead of raw search_email output,
which carries signed attachment URLs and full quoted threads.
"""
import argparse
import datetime as dt
import re
import sys

from _saved_json import load_email_records, parse_email_date

SKIPPED_ATTACHMENT_PREFIXES = ("image", "img_", "ATT")


def load(path):
    return load_email_records([path])


def clean(text, n):
    """Strip tags, collapse whitespace, cut to n chars and say how much was cut."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= n:
        return text
    return f"{text[:n]} [truncated, {len(text) - n} more chars]"


def parse_date(value):
    """Use the shared timestamp parser; undated digest messages sort last."""
    try:
        return parse_email_date(value)
    except ValueError:
        return None


def recipients(value):
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value or []]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Digest saved search_email outputs, newest first.")
    parser.add_argument("paths", nargs="+", metavar="saved_output_json")
    parser.add_argument("--chars", type=int, default=300, help="body characters per message (default 300)")
    args = parser.parse_args(argv)
    emails = load_email_records(args.paths)
    floor = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    emails.sort(key=lambda e: parse_date(e.get("date")) or floor, reverse=True)
    for e in emails:
        att = ", ".join(
            a.get("filename", "") for a in e.get("attachments") or []
            if not (a.get("filename") or "").startswith(SKIPPED_ATTACHMENT_PREFIXES)
        )
        print(f"{(e.get('date') or '')[:16]} | id {e.get('email_id')} thread {e.get('thread_id')} "
              f"| from {e.get('from_')} | to {', '.join(recipients(e.get('to')))}")
        print(f"  {e.get('subject')}")
        print(f"  {clean(e.get('body') or e.get('snippet'), args.chars)}")
        if att:
            print(f"  attachments: {att}")
    print(f"{len(emails)} emails")


if __name__ == "__main__":
    main(sys.argv[1:])
