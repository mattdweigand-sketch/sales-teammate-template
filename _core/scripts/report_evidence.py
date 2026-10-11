"""Shared saved-source evidence checks for Pipeline presentation helpers."""
import html
import re
from datetime import date, datetime
from pathlib import Path
from _saved_json import load_saved, parse_email_date

EVIDENCE_SOURCES = {"Gmail", "Calendar", "Slack", "Salesforce", "Operator", "Pilot report"}
RETRIEVED_SOURCES = {"Gmail", "Calendar"}
QUOTE_MIN_CHARS = 12

def plain(text):
    """Comparable text: tags removed, entities decoded, whitespace collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", str(text or ""))).split())


def load_sources(folder):
    """Index saved Gmail messages by email_id and Calendar events by event_id. Unreadable files are skipped."""
    found = {"Gmail": {}, "Calendar": {}}
    for path in sorted(Path(folder).glob("output_*.json")) if Path(folder).is_dir() else []:
        try:
            result = load_saved(path)
        except (OSError, ValueError):
            continue
        if not isinstance(result, dict):
            continue
        for key, rows, source, rid in (("email_results", "emails", "Gmail", "email_id"),
                                       ("calendar_event_list", "events", "Calendar", "event_id")):
            page = result.get(key)
            for rec in (page.get(rows) if isinstance(page, dict) else None) or []:
                if isinstance(rec, dict) and rec.get(rid):
                    found[source][rec[rid]] = rec
    return found


def md(d):
    return f"{d.month}/{d.day}/{d.strftime('%y')}"


class EvidenceMixin:
    def check_evidence(self, items, where, required=True):
        if required and not items:
            self.err(f"{where}: needs at least one evidence item")
        for n, e in enumerate(items or [], 1):
            w = f"{where} evidence {n}"
            if "_resolved" in e:
                self.err(f"{w}: _resolved is internal; remove it from the run file")
                continue
            if e.get("source") in RETRIEVED_SOURCES:
                self.resolve_retrieved(e, w)
            if not e.get("date") or not e.get("fact"):
                self.err(f"{w}: date and fact are required")
            if e.get("source") not in EVIDENCE_SOURCES:
                self.err(f"{w}: source must be one of {sorted(EVIDENCE_SOURCES)}")
            if e.get("source") == "Slack" and not all(e.get(key) for key in ("who", "title", "link")):
                self.err(f"{w}: Slack evidence needs a sender, title, and returned permalink")
            link = e.get("link")
            if link and not re.match(r"^https://\S+$", link):
                self.err(f"{w}: link must be a returned https URL, never constructed")
            if link and not e.get("title"):
                self.err(f"{w}: a link needs a title to display")


    def resolve_retrieved(self, e, w):
        """Gmail and Calendar evidence must point at a saved record. Date, title, and link come from it."""
        src = e["source"]
        if id(e) in self.resolved_evidence:
            return
        supplied = [k for k in ("date", "title", "link") if e.get(k)]
        if supplied:
            self.err(f"{w}: {', '.join(supplied)} must come from the saved {src} record; remove from the run file")
        rec = self.sources[src].get(e.get("source_id"))
        if rec is None:
            self.err(f"{w}: source_id {e.get('source_id')!r} is not in this run's saved {src} results")
            return
        if src == "Gmail":
            quote = plain(e.get("quote"))
            bodies = [plain(rec.get(k)) for k in ("body_uncompressed", "body")]
            if len(quote) < QUOTE_MIN_CHARS:
                self.err(f"{w}: Gmail evidence needs a quote of at least {QUOTE_MIN_CHARS} characters from the message body")
            elif not any(quote in b for b in bodies):
                self.err(f"{w}: quote is not in the saved message body for {e.get('source_id')}")
            when = parse_email_date(rec.get("date"))
            title, link = rec.get("subject"), rec.get("web_link")
        else:
            start = str(rec.get("start") or "")
            when = datetime.fromisoformat(start.replace("Z", "+00:00")) if "T" in start else date.fromisoformat(start[:10])
            title, link = rec.get("title"), rec.get("html_link") or rec.get("web_link")
        if isinstance(when, datetime) and self.tz:
            when = when.astimezone(self.tz)
        e.update(date=md(when), title=title or None, link=link if link and str(link).startswith("https://") else None)
        self.resolved_evidence.add(id(e))
