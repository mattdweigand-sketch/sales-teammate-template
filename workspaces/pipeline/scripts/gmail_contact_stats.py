#!/usr/bin/env python3
"""Reduce saved Gmail search_email outputs to per-contact stats.

Usage:
  python3 gmail_contact_stats.py <owner_email> <output_json> [<output_json> ...]
                                 --as-of <run start with local offset>
                                 [--only a@x.test,b@y.test] [--policy PATH]
                                 [--slack-replies reviewed.json]

Reads explicit JSON files that search_email calls write to
~/.perplexity/sessions/<session-id>/tool_calls/call_external_tool/,
with paired input_*.json and output_*.json files. Prints one block per
external address (addresses in policy.tooling.internal_domains and
calendar-notification senders are skipped; --only restricts to a
comma-separated list): sent count, last sent date, last inbound date and type
(substantive, ooo, bounce, calendar), unanswered count = distinct sent
messages dated after the last substantive inbound, and the newest non-bounce
message and thread id for reply threading. No bodies are printed.
A bounce from a relay address is attributed to every tracked address found in
its text. Subjects starting with Accepted, Declined, Tentative,
Tentatively accepted, Invitation, Updated invitation, Canceled event,
Canceled, or Cancelled followed by a colon are calendar notices, not
substantive. Dates are normalized before comparison; unknown dates stop for review. Summary dates use the explicit --as-of offset.
Optional reviewed Slack receipts use policy.tooling.slack_lookback_days and
report only a positive auto-move veto. Missing replies never prove absence.
"""
import argparse
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from email.utils import getaddresses
from pathlib import Path

import yaml

CORE = Path(__file__).resolve().parents[3] / "_core"
sys.path.insert(0, str(CORE / "scripts"))
from _saved_json import load_email_records, parse_email_date  # noqa: E402

OOO = re.compile(r"^\s*(?:automatic reply|auto[- ]?reply|out of (?:the )?office)(?:\s*:|\s*$)", re.I)
BOUNCE = re.compile(r"^\s*(?:undeliverable|delivery status notification|mail delivery (?:failed|failure)|delivery has failed)(?:\b)", re.I)
CALENDAR = re.compile(r"^\s*(accepted|declined|tentative(ly accepted)?|invitation|updated invitation|canceled event|cancell?ed):", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def text_of(e):
    if "_text" not in e:
        e["_text"] = " ".join(str(e.get(k) or "") for k in ("subject", "snippet", "body", "body_text"))
    return e["_text"]


def kind_of(e):
    if "_kind" not in e:
        subject = e.get("subject") or ""
        sender = addr(e.get("from_"))
        if BOUNCE.search(subject) and any(token in sender for token in ("mailer-daemon@", "postmaster@")):
            e["_kind"] = "bounce"
        elif CALENDAR.match(e.get("subject") or ""):
            e["_kind"] = "calendar"
        elif OOO.search(subject):
            e["_kind"] = "ooo"
        else:
            e["_kind"] = "substantive"
    return e["_kind"]


def addrs(values):
    if isinstance(values, str):
        values = [values]
    out = set()
    for _, a in getaddresses([str(v) for v in (values or []) if v]):
        a = a.lower().strip()
        if a and "@" in a:
            out.add(a)
    return out


def addr(s):
    got = addrs([s])
    return next(iter(got)) if got else ""


def internal(a, internal_domains):
    return any(a.endswith("@" + d) for d in internal_domains) or "calendar-notification" in a


def load_emails(paths):
    emails = {}
    for e in load_email_records(paths):
        e["_date"] = parse_email_date(e.get("date"))
        emails[e["email_id"]] = e
    return emails


def load_slack_replies(path, as_of, lookback_days):
    receipts = json.loads(Path(path).read_text())
    if not isinstance(receipts, list):
        raise ValueError("Slack reply receipts must be a reviewed list")
    latest = {}
    window_start = as_of - timedelta(days=lookback_days)
    for receipt in receipts:
        if not isinstance(receipt, dict):
            raise ValueError("Slack reply receipt must be an object")
        contact = receipt.get("contact_email")
        if not isinstance(contact, str) or not EMAIL_RE.fullmatch(contact):
            raise ValueError("Slack reply requires the verified Contact email")
        if any(type(receipt.get(field)) is not bool for field in ("verified_identity", "substantive", "is_bot")):
            raise ValueError("Slack reply requires explicit identity, substantive, and bot classifications")
        if not isinstance(receipt.get("permalink"), str) or not receipt["permalink"].strip():
            raise ValueError("Slack reply requires its returned permalink")
        try:
            timestamp = float(receipt["ts"])
            if isinstance(receipt["ts"], bool) or not math.isfinite(timestamp) or timestamp < 0:
                raise ValueError
            reply_date = datetime.fromtimestamp(timestamp, as_of.tzinfo)
        except (KeyError, ValueError, TypeError, OverflowError, OSError) as exc:
            raise ValueError("Slack reply requires a valid returned timestamp") from exc
        if reply_date > as_of:
            raise ValueError("Slack reply is later than as-of, review required")
        if not receipt["verified_identity"] or not receipt["substantive"] or receipt["is_bot"] or reply_date < window_start:
            continue
        contact = contact.lower()
        if contact not in latest or reply_date > latest[contact]:
            latest[contact] = reply_date
    return latest


def slack_reply_blocks_auto_move(last_sent, slack_reply):
    return last_sent is not None and slack_reply is not None and slack_reply >= last_sent


def main(argv=None):
    parser = argparse.ArgumentParser(description="Per-contact sent, inbound, and unanswered counts from saved search_email outputs.")
    parser.add_argument("owner", help="owner email address")
    parser.add_argument("files", nargs="+", metavar="output_json")
    parser.add_argument("--as-of", required=True, help="run-start ISO datetime with local offset")
    parser.add_argument("--only", help="comma-separated addresses to report")
    parser.add_argument("--slack-replies", help="reviewed positive Slack reply receipts, a veto only, never proof of no reply")
    parser.add_argument("--policy", default=str(CORE / "policy.yaml"))
    args = parser.parse_args(argv)
    try:
        as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
        if as_of.tzinfo is None:
            raise ValueError("--as-of needs a timezone offset")
    except ValueError as exc:
        parser.error(str(exc))
    tooling = yaml.safe_load(Path(args.policy).read_text())["tooling"]
    internal_domains = tuple(tooling["internal_domains"])
    slack_replies = load_slack_replies(args.slack_replies, as_of, tooling["slack_lookback_days"]) if args.slack_replies else {}
    only = {a.strip().lower() for a in args.only.split(",") if a.strip()} if args.only else None
    owner = args.owner.lower()
    emails = load_emails(args.files)

    by = defaultdict(list)
    for e in emails.values():
        parties = addrs([e.get("from_")]) | addrs(e.get("to")) | addrs(e.get("cc"))
        if kind_of(e) == "bounce":
            # relay bounce: attribute to the tracked addresses named in the text
            mentioned = {a.lower() for a in EMAIL_RE.findall(text_of(e))}
            tracked = {a for a in mentioned if not internal(a, internal_domains) and (not only or a in only)}
            for p in tracked:
                e.setdefault("_bounce_for", set()).add(p)
            parties |= tracked
        relay = addr(e.get("from_")) if "_bounce_for" in e else ""
        for p in parties:
            if internal(p, internal_domains) or (only and p not in only) or p == relay:
                continue
            by[p].append(e)

    for p in sorted(by):
        msgs = sorted(by[p], key=lambda e: e["_date"])
        sent = [e for e in msgs if addr(e["from_"]) == owner]
        inbound = [e for e in msgs if addr(e["from_"]) == p or p in e.get("_bounce_for", ())]
        last_sub = None
        for e in inbound:
            if kind_of(e) == "substantive":
                last_sub = e
        since = last_sub["_date"] if last_sub else None
        unanswered = len([e for e in sent if since is None or e["_date"] > since])
        newest = ([e for e in msgs if kind_of(e) != "bounce"] or msgs)[-1]   # thread for a reply, never the bounce
        print(f"\n{p}")
        print(f"  sent={len(sent)} last_sent={sent[-1]['_date'].astimezone(as_of.tzinfo).date().isoformat() if sent else '-'}")
        if inbound:
            li = inbound[-1]
            print(f"  last_inbound={li['_date'].astimezone(as_of.tzinfo).date().isoformat()} type={kind_of(li)} subject={li.get('subject','')[:60]!r}")
        else:
            print("  last_inbound=-")
        print(f"  last_substantive={last_sub['date'] if last_sub else '-'}")
        print(f"  unanswered_since_last_substantive={unanswered}")
        if args.slack_replies:
            slack_reply = slack_replies.get(p)
            blocked = slack_reply_blocks_auto_move(sent[-1]["_date"] if sent else None, slack_reply)
            print(f"  last_substantive_slack={slack_reply.isoformat() if slack_reply else '-'}")
            print(f"  slack_reply_blocks_auto_move={str(blocked).lower()}")
        print(f"  newest_message_id={newest['email_id']} thread_id={newest['thread_id']} subject={newest.get('subject','')[:60]!r}")


if __name__ == "__main__":
    main()
