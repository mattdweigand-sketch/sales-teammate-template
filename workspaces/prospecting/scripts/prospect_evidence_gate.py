#!/usr/bin/env python3
"""Check one public-evidence receipt against the fetched page and emit the signal bundle.

Caller: signal-scan (one run per selected source).

Policy input requires prospecting.scan.quote_min_words and prospecting.identity.timezone.

    python3 workspaces/prospecting/scripts/prospect_evidence_gate.py --receipt receipt.json --page page.txt \
        [--core _core] [--now 2026-09-21T14:00:00-07:00]

receipt.json
    {"account_name": str, "account_aliases": [str], "account_domain": str|null,
     "source_url": str, "published_date": "YYYY-MM-DD"|null, "quote": str,
     "evidence_subject": str, "signal_type": str, "quote_speaker": "account"|"third_party",
     "classification": "active_initiative"|"early_indication"|"general_mention",
     "relevance": "employee_use"|"customer_product"|"unclear",
     "event_date": "YYYY-MM-DD" (required only when published_date is null)}
    published_date null means a live first-party page with no trustworthy publication date. The page must
    then name a dated event: event_date must appear in the page text in a prospect_common written form. Freshness is
    checked against event_date and the bundle carries published_date = event_date, date_basis "page_event".
    A LinkedIn post URL (linkedin.com/posts/...-activity-<id>-..., feed/update/urn:li:activity:<id>, or any
    urn:li:ugcPost:<id> or urn:li:share:<id>, percent-encoded or not) carries its own date: the top 41 bits of the id
    (id >> 22) are milliseconds since the Unix epoch, read as an identity.timezone date. With published_date null the
    decoded date governs, event_date is not needed, and date_basis is "linkedin_post_id". With published_date given,
    it must equal the decoded instant's calendar date at some UTC offset from -12:00 to +14:00, else exit 2
    published_date_disagrees_with_post_id. A URL whose id decodes before 2010 is treated as not decodable.
    quote_speaker "account" means the account or a named alias said or wrote the quote. "third_party" means
    someone else (vendor, reporter) paraphrased them.

Checks. Active initiative and employee use required for qualification; other findings remain in the research report. Required keys present. account_aliases is a list. source_url is http(s). quote_speaker is account or
third_party. quote has at least policy scan.quote_min_words words and appears verbatim in the page text (whitespace
and curly quotes normalized). evidence_subject is account_name or a declared alias. signal_type is a tier1 or tier2
id in the taxonomy whose entry names no non-web `source` (paid_individuals_present comes from the warehouse, never
from a page). The governing date is ISO, not in the future (exit 2), and within that signal
type's freshness_days (else exit 1, stale). Today is the identity.timezone date. A date is future only when it is
after both that date and the UTC date at read time, so a page dated today in UTC still passes late in the Pacific
evening. Age counts from the identity.timezone date. Qualified bundles carry "warnings":
["third_party_paraphrase"] when quote_speaker is third_party and signal_type is exec_ai_statements.

Qualified bundles carry checked_on (date) and checked_at (timestamp with timezone offset, the moment of the read).
prospect_outreach_gate.py measures bundle age from checked_at. --now replays a read at a given moment, tests only. It must
carry an offset. checked_at is that instant in identity.timezone and checked_on is its date there. Stages never pass it.

Exit 0 qualified, bundle JSON on stdout. Exit 1 no_usable_signal (never proof of absence).
Exit 2 unusable input, {"outcome": "unusable", "reason": ...}. Always JSON on stdout, never a traceback.
"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote

import prospect_common

REQUIRED = ("account_name", "account_aliases", "account_domain", "source_url",
            "published_date", "quote", "evidence_subject", "signal_type", "quote_speaker", "classification", "relevance")
SPEAKERS = ("account", "third_party")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")


def date_forms(d):
    """Written forms of a date that a page may use. Case-insensitive match on the normalized page."""
    month = MONTHS[d.month - 1]
    forms = [d.isoformat(), f"{month} {d.day}, {d.year}", f"{month} {d.day} {d.year}", f"{d.day} {month} {d.year}",
             f"{month[:3]} {d.day}, {d.year}", f"{month[:3]}. {d.day}, {d.year}", f"{d.day} {month[:3]} {d.year}",
             f"{d.month}/{d.day}/{d.year}", f"{d.month:02d}/{d.day:02d}/{d.year}"]
    if month == "September":
        forms += [f"Sept {d.day}, {d.year}", f"Sept. {d.day}, {d.year}"]
    return forms


LINKEDIN_HOST = re.compile(r"^https?://([a-z0-9-]+\.)*linkedin\.com(/|$)", re.I)
LINKEDIN_ID = (re.compile(r"/posts/[^/?#]*-(?:activity|ugcPost|share)-(\d{15,19})(?:-|$|[/?#])"),
               re.compile(r"urn:li:(?:activity|ugcPost|share):(\d{15,19})"))
LINKEDIN_EPOCH_FLOOR = datetime(2010, 1, 1, tzinfo=timezone.utc)  # id format fact, not policy. Older ids are not time-based


def linkedin_post_instant(url):
    """UTC instant encoded in a LinkedIn post URL's activity, ugcPost, or share id, or None when the URL has none."""
    if not isinstance(url, str) or not LINKEDIN_HOST.match(url):
        return None
    text = unquote(url)
    for pattern in LINKEDIN_ID:
        m = pattern.search(text)
        if m:
            try:
                instant = datetime.fromtimestamp((int(m.group(1)) >> 22) / 1000, timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
            return instant if instant >= LINKEDIN_EPOCH_FLOOR else None
    return None


def normalize(text):
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def norm_name(name):
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def load_rules(core=prospect_common.CORE):
    """(policy, {signal_type: {tier, freshness_days, source}})."""
    return prospect_common.load_policy(core), prospect_common.taxonomy_types(prospect_common.load_taxonomy(core))


def grade(receipt, page_text, policy, types, today, checked_at=None):
    """checked_at is the timezone-aware moment the page was read. Defaults to now in identity.timezone. prospect_outreach_gate.py
    measures elapsed time from it. The UTC date of checked_at widens the future-date check by at most one day. Without
    checked_at, today alone governs. A LinkedIn post id date is read in checked_at's timezone."""
    scan_policy = policy["scan"]
    utc_today = checked_at.astimezone(timezone.utc).date() if checked_at else today
    checked_at = checked_at or datetime.now(prospect_common.policy_tz(policy))
    tz = checked_at.tzinfo
    missing = [k for k in REQUIRED if k not in receipt]
    if missing:
        return 2, {"outcome": "unusable", "reason": "missing_keys", "keys": missing}
    if not isinstance(receipt["account_aliases"], list):
        return 2, {"outcome": "unusable", "reason": "account_aliases_not_list"}
    not_str = [k for k in ("account_name", "quote", "evidence_subject", "signal_type", "quote_speaker")
               if not isinstance(receipt[k], str)]
    not_str += [f"account_aliases[{i}]" for i, a in enumerate(receipt["account_aliases"]) if not isinstance(a, str)]
    if not_str:
        return 2, {"outcome": "unusable", "reason": "fields_not_strings", "keys": not_str}
    if not re.match(r"^https?://", receipt["source_url"] or ""):
        return 2, {"outcome": "unusable", "reason": "source_url_not_http"}
    if receipt["quote_speaker"] not in SPEAKERS:
        return 2, {"outcome": "unusable", "reason": "quote_speaker_not_allowed", "allowed": list(SPEAKERS)}

    quote = normalize(receipt["quote"])
    if len(quote.split()) < scan_policy["quote_min_words"]:
        return 1, {"outcome": "no_usable_signal", "reason": "quote_too_short"}
    if quote not in normalize(page_text):
        return 1, {"outcome": "no_usable_signal", "reason": "quote_not_in_page"}

    owned = {norm_name(receipt["account_name"])} | {norm_name(a) for a in receipt["account_aliases"]}
    if norm_name(receipt["evidence_subject"]) not in owned:
        return 1, {"outcome": "no_usable_signal", "reason": "evidence_subject_not_account_owned",
                   "evidence_subject": receipt["evidence_subject"]}

    if receipt["classification"] not in ("active_initiative", "early_indication", "general_mention"):
        return 2, {"outcome": "unusable", "reason": "invalid_classification"}
    if receipt["relevance"] not in ("employee_use", "customer_product", "unclear"):
        return 2, {"outcome": "unusable", "reason": "invalid_relevance"}
    if receipt["classification"] != "active_initiative" or receipt["relevance"] != "employee_use":
        return 1, {"outcome": "no_usable_signal", "reason": "discovery_only",
                   "classification": receipt["classification"], "relevance": receipt["relevance"]}

    signal = types.get(receipt["signal_type"])
    if signal is None:
        return 2, {"outcome": "unusable", "reason": "signal_type_not_in_taxonomy"}
    if signal["tier"] == "tier3":
        return 1, {"outcome": "no_usable_signal", "reason": "tier3_never_qualifies"}
    if signal.get("source"):
        return 1, {"outcome": "no_usable_signal", "reason": "signal_type_not_web_sourced",
                   "source": signal["source"], "signal_type": receipt["signal_type"]}

    post_instant = linkedin_post_instant(receipt["source_url"])
    if receipt["published_date"] is None and post_instant is not None:
        receipt = dict(receipt, published_date=post_instant.astimezone(tz).date().isoformat())
        date_field, date_basis = "published_date", "linkedin_post_id"
    elif receipt["published_date"] is None:
        if not receipt.get("event_date"):
            return 1, {"outcome": "no_usable_signal", "reason": "undated_page_without_event_date"}
        date_field, date_basis = "event_date", "page_event"
    else:
        date_field, date_basis = "published_date", "published"
    try:
        governing = date.fromisoformat(receipt[date_field])
    except (ValueError, TypeError):
        return 2, {"outcome": "unusable", "reason": f"{date_field}_not_iso"}
    if post_instant is not None and date_basis == "published":
        edges = {(post_instant + timedelta(hours=h)).date() for h in (-12, 14)}
        if not min(edges) <= governing <= max(edges):
            return 2, {"outcome": "unusable", "reason": "published_date_disagrees_with_post_id",
                       "published_date": receipt["published_date"],
                       "post_id_date": post_instant.astimezone(tz).date().isoformat()}
    if governing > max(today, utc_today):
        return 2, {"outcome": "unusable", "reason": f"{date_field}_in_future"}
    if date_basis == "page_event":
        page_norm = normalize(page_text).lower()
        if not any(f.lower() in page_norm for f in date_forms(governing)):
            return 1, {"outcome": "no_usable_signal", "reason": "event_date_not_in_page",
                       "event_date": receipt["event_date"]}
    age = (today - governing).days
    if age > signal["freshness_days"]:
        return 1, {"outcome": "no_usable_signal", "reason": "stale", "date_basis": date_basis,
                   "age_days": age, "freshness_days": signal["freshness_days"]}

    bundle = {k: receipt[k] for k in REQUIRED}
    bundle["published_date"] = governing.isoformat()
    bundle.update({"tier": signal["tier"], "date_basis": date_basis, "checked_on": today.isoformat(),
                   "checked_at": checked_at.isoformat(timespec="seconds"), "gate": "evidence_gate"})
    warnings = []
    if receipt["quote_speaker"] == "third_party" and receipt["signal_type"] == "exec_ai_statements":
        warnings.append("third_party_paraphrase")
    if warnings:
        bundle["warnings"] = warnings
    return 0, {"outcome": "qualified", "bundle": bundle}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--page", required=True)
    ap.add_argument("--core", default=str(prospect_common.CORE))
    ap.add_argument("--now", default=None, help="ISO timestamp with offset. Tests only. Sets checked_at, today is its identity.timezone date")
    args = ap.parse_args()
    try:
        receipt = json.loads(Path(args.receipt).read_text())
        if not isinstance(receipt, dict):
            raise ValueError("receipt must be a JSON object")
        page_text = Path(args.page).read_text(errors="replace")
        policy, types = load_rules(Path(args.core))
        now = prospect_common.policy_now(policy)
        if args.now:
            given = prospect_common.parse_iso(args.now)
            if given is None:
                raise ValueError("--now must be an ISO timestamp with a timezone offset")
            now = given.astimezone(prospect_common.policy_tz(policy))
        code, payload = grade(receipt, page_text, policy, types, now.date(), checked_at=now)
    except prospect_common.INPUT_ERRORS as exc:  # bad input, never a traceback
        print(json.dumps({"outcome": "unusable", "reason": "input_error", "detail": f"{type(exc).__name__}: {exc}"}))
        return 2
    print(json.dumps(payload, indent=1))
    return code


if __name__ == "__main__":
    sys.exit(main())
