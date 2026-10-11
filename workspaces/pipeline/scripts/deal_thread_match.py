#!/usr/bin/env python3
"""Match Account names using saved project pages and a search for every Account.

Usage: deal_thread_match.py --input <sandbox.json>
Input: {pages: [{offset, sessions: <raw list>}], limit, project_uuid,
        accounts: [{account_id, account_name}], account_searches:
        {account_id: <raw session_list JSON response, or null on failure>}}.
Output: {status: complete|incomplete, reasons, accounts: [{account_id,
         account_name, status: owner|local|needs_input, ...}]}.
Top-level status reports page shape, not discovery coverage.
Offsets must start at zero and advance by limit. All but the last page are
full, and the last is short (possibly empty). These are page-shape checks,
not proof of discovery coverage. A listing alone never proves absence or
uniqueness. Every Account needs a valid saved search, including listed owners.
Only normalized exact titles ending in " deal"
match. Trademark symbols are removed on both sides before normalization.
Session status is retained, not interpreted as a lifecycle filter.
Session URLs may be absolute HTTPS or exact /computer/tasks/<id> paths.
Output links are absolute; raw saved pages are never changed.
Distinct Accounts sharing a normalized name with candidate threads are held.
Owner and local both require a saved Account search with fewer than 100 results.
Local requires that search and the project pages to contain
no exact same-project deal title. Search gaps hold only that Account.
Nonmatching search titles and unprojected sessions are not candidates.
Candidate-title rows require valid fields, project metadata and URLs.
Search responses have exactly {sessions: <list>}. Legacy saved raw lists
remain accepted. Unknown response shapes hold the affected Account. A search
row that is not an object or has no string title is unknown, not negative
evidence, and holds the Account. A multi-line title is localized. Proved
unrelated to every reviewed Account it is skipped. A possible candidate for an
Account holds that Account and is never stripped into a match. Raw rows stay
unchanged.
No network calls, writes, fuzzy matching, or sales decisions.
Exit 0 emits JSON, including incomplete listings. Exit 2 is unusable input.
"""
import argparse
import json
from pathlib import Path
import re
import string
import sys
import unicodedata
from urllib.parse import urlsplit


LEGAL_SUFFIXES = frozenset(("inc", "llc", "llp", "ltd", "limited", "corp", "corporation",
                            "co", "company", "plc", "lp", "pc", "pllc", "gmbh", "ag", "sa", "bv", "nv"))


def normalize(name: str) -> str:
    text = "".join(" " if char != "&" and (char in string.punctuation or unicodedata.category(char).startswith("P")) else char
                   for char in name.casefold() if char not in "®™©℠")
    tokens = text.split()
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def one_line(value):
    return isinstance(value, str) and bool(value.strip()) and not any(char in value for char in "\r\n")


def deal_key(title):
    """Normalized Account key of a possible `<Account> deal` title, or None. Comparison only, the raw title is kept."""
    if not isinstance(title, str):
        return None
    collapsed = " ".join(title.split())
    if not collapsed.casefold().endswith(" deal"):
        return None
    return normalize(collapsed[:-5]) or None


def session_url(value):
    if not isinstance(value, str) or any(char.isspace() or ord(char) < 32 for char in value) or "\\" in value:
        return None
    if re.fullmatch(r"/computer/tasks/[A-Za-z0-9_-]+", value):
        return "https://www.perplexity.ai" + value
    if value.startswith("https://"):
        try:
            parsed = urlsplit(value)
            if parsed.hostname and (parsed.port is None or 0 <= parsed.port <= 65535):
                return value
        except ValueError:
            pass
    return None


def listing_reasons(data):
    limit, project_uuid, pages = data.get("limit"), data.get("project_uuid"), data.get("pages")
    reasons = []
    if type(limit) is not int or limit <= 0:
        reasons.append("limit must be a positive integer")
    if not one_line(project_uuid):
        reasons.append("project_uuid is required")
    if not isinstance(pages, list) or not pages:
        reasons.append("pages must include a final short page")
    if reasons:
        return reasons
    seen = set()
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            reasons.append(f"page {index} must bind offset to its raw sessions list")
            continue
        offset = page.get("offset")
        if type(offset) is not int or offset != index * limit:
            reasons.append(f"page {index} offset must be {index * limit}")
        sessions = page.get("sessions")
        if not isinstance(sessions, list):
            reasons.append(f"page {index} sessions must be a raw list")
            continue
        if (index < len(pages) - 1 and len(sessions) != limit) or (index == len(pages) - 1 and len(sessions) >= limit):
            reasons.append(f"page {index} must be {'full' if index < len(pages) - 1 else 'short'}")
        for row_index, session in enumerate(sessions):
            where = f"page {index} session {row_index}"
            if not isinstance(session, dict):
                reasons.append(f"{where} must be an object")
                continue
            for field in ("context_uuid", "url", "status"):
                if not one_line(session.get(field)):
                    reasons.append(f"{where} needs {field}")
            if not isinstance(session.get("title"), str):
                reasons.append(f"{where} needs title")
            if session_url(session.get("url")) is None:
                reasons.append(f"{where} needs an https url or /computer/tasks/<id> path")
            identifier = session.get("context_uuid")
            if one_line(identifier):
                if identifier in seen:
                    reasons.append(f"{where} duplicates context_uuid {identifier}")
                seen.add(identifier)
            project = session.get("project")
            if not isinstance(project, dict) or project.get("uuid") != project_uuid:
                reasons.append(f"{where} project does not match project_uuid")
    return reasons


def search_candidates(response, account_key, project_uuid):
    if isinstance(response, dict):
        if set(response) != {"sessions"}:
            return [], "account search has an unknown response shape"
        sessions = response["sessions"]
    else:
        sessions = response
    if not isinstance(sessions, list):
        return [], "account search failed or has no sessions list"
    if len(sessions) >= 100:
        return [], "account search reached limit 100"
    candidates = []
    for index, session in enumerate(sessions):
        if not isinstance(session, dict) or not isinstance(session.get("title"), str):
            return [], f"account search session {index} has an unknown title or row"
        if not one_line(session["title"]):
            if deal_key(session["title"]) == account_key:
                return [], f"account search session {index} has a malformed candidate title"
            continue
        title = session["title"].strip()
        if not title.casefold().endswith(" deal") or normalize(title[:-5]) != account_key:
            continue
        if "project" in session and session["project"] is None:
            continue
        if not all(one_line(session.get(field)) for field in ("context_uuid", "title", "url", "status")):
            return [], f"account search session {index} has missing or malformed fields"
        project = session.get("project")
        if session.get("type") != "computer" or not isinstance(project, dict) or not one_line(project.get("uuid")):
            return [], f"account search session {index} has malformed type or project"
        url = session_url(session["url"])
        if url is None:
            return [], f"account search session {index} has a malformed url"
        if project["uuid"] == project_uuid:
            candidates.append({"context_uuid": session["context_uuid"], "title": session["title"], "status": session["status"], "url": url})
    return candidates, None


def match_threads(data):
    if not isinstance(data, dict) or not isinstance(data.get("accounts"), list):
        raise ValueError("input must be an object with an accounts list")
    seen = set()
    account_names = {}
    for account in data["accounts"]:
        if not isinstance(account, dict) or not all(one_line(account.get(field)) for field in ("account_id", "account_name")):
            raise ValueError("each account needs account_id and account_name")
        if account["account_id"] in seen:
            raise ValueError("accounts must have unique account_id values")
        seen.add(account["account_id"])
        account_names.setdefault(normalize(account["account_name"]), set()).add(account["account_id"])
    reasons = listing_reasons(data)
    candidates = {}
    malformed = set()
    if not reasons:
        for page in data["pages"]:
            for session in page["sessions"]:
                if not one_line(session["title"]):
                    key = deal_key(session["title"])
                    if key in account_names:
                        malformed.add(key)
                    continue
                title = session["title"].strip()
                if not title.casefold().endswith(" deal"):
                    continue
                key = normalize(title[:-5])
                if key:
                    candidate = {field: session[field] for field in ("context_uuid", "title", "status")}
                    candidate["url"] = session_url(session["url"])
                    candidates.setdefault(key, {})[candidate["context_uuid"]] = candidate
    searches = data.get("account_searches", {})
    search_errors = {}
    if not reasons and isinstance(searches, dict):
        for account in data["accounts"]:
            if account["account_id"] not in searches:
                continue
            key = normalize(account["account_name"])
            found, error = search_candidates(searches[account["account_id"]], key, data["project_uuid"])
            if error:
                search_errors[account["account_id"]] = error
            else:
                for candidate in found:
                    candidates.setdefault(key, {}).setdefault(candidate["context_uuid"], candidate)
    rows = []
    for account in data["accounts"]:
        row = {field: account[field] for field in ("account_id", "account_name")}
        key = normalize(account["account_name"])
        matches = sorted(candidates.get(key, {}).values(), key=lambda candidate: candidate["context_uuid"])
        if reasons:
            row.update(status="needs_input", reason="incomplete project listing")
        elif not key:
            row.update(status="needs_input", reason="account name normalizes to empty")
        elif key in malformed:
            row.update(status="needs_input", reason="malformed deal thread title in project listing")
        elif account["account_id"] in search_errors:
            row.update(status="needs_input", reason=search_errors[account["account_id"]])
        elif not isinstance(searches, dict) or account["account_id"] not in searches:
            row.update(status="needs_input", reason="account search required before ownership")
        elif matches and len(account_names[key]) > 1:
            row.update(status="needs_input", reason="multiple Accounts share this normalized name", candidates=matches)
        elif len(matches) == 1:
            row.update(status="owner", context_uuid=matches[0]["context_uuid"], url=matches[0]["url"])
        elif matches:
            row.update(status="needs_input", reason="ambiguous deal threads", candidates=matches)
        else:
            row.update(status="local")
        rows.append(row)
    return {"status": "incomplete" if reasons else "complete", "reasons": reasons, "accounts": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Saved offset-bound pages, limit, project_uuid and accounts JSON")
    args = parser.parse_args()
    try:
        result = match_threads(json.loads(Path(args.input).read_text()))
    except (OSError, ValueError) as error:
        print(f"deal_thread_match: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
