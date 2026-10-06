#!/usr/bin/env python3
"""Check one outreach packet before a Gmail draft proposal. Never sends or proves approval.

Caller: signal-outreach. Usage: python3 workspaces/prospecting/workflows/signal-prospecting/02-outreach/scripts/prospect_outreach_gate.py --packet p.json
[--core _core] [--now ISO-with-offset]. --now is for tests only.

Policy input requires prospecting.identity.timezone, prospecting.identity.sfdc_user_id, prospecting.outreach.bundle_checked_max_age_hours,
prospecting.outreach.suppression_days, prospecting.outreach.suppressing_task_subtypes,
prospecting.outreach.recipient_sources, prospecting.user_scan.bundle_keys, prospecting.user_scan.adoption_values,
and prospecting.user_scan.statements.

Packet:
  account: current complete Salesforce receipt {account_exists: true, account_id, owner_id, open_opportunity_ids: [], account_domain}
    account_domain is the verified domain of that Salesforce Account, bound to the bundle below.
  bundle: the current prospect_evidence_gate bundle as emitted (gate prospect_evidence_gate, source_url, date_basis, checked_at,
    classification active_initiative, relevance employee_use), or a paid_individuals_present wrapper with
    published_date, checked_at, quote, account_name, account_domain, date_basis warehouse, and the complete
    privacy-checked adoption_bundle.
  talk_track: {angle: plain-language angle from talk-track.md, persona: verified responsibility,
               pick_reason: one sentence connecting the source, person, and message}
  recipient: {email, name, source, title, contact_id: Salesforce Contact Id or null}
  activity: unfiltered live-read rows {kind: task|event|gmail_sent, date: YYYY-MM-DD,
             who: Contact/Lead Id|email|null, status and subtype for tasks}. [] means completed empty reads.
  draft: {subject, body}

Checks: current named-account route scan; qualifying signal id; complete web bundle with active employee-use evidence; warehouse privacy and the
exact statement in the wrapper quote; published-date freshness; aware checked_at within policy; nonempty messaging
judgment; talk-track review date; recipient identity, domain and source; contact-specific suppression; numbers
grounded in the quote, with meeting-invitation minute spans in the single question exempt. Claim support, role fit
and wording remain the agent's review and Operator's exact proposal approval.

Exit 0 allow, 1 block, 2 unusable input; always JSON. Required reads and exact approval/readback are
performed by the stage contract; a fabricated packet is not proof of provider reads or human approval.
"""
import argparse
import json
import re
import sys
from datetime import date, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "scripts"))
import prospect_common  # noqa: E402
import prospect_account_route  # noqa: E402
import prospect_privacy_check  # noqa: E402

NUM = re.compile(r"\d[\d,.]*\d|\d")
TALK_TRACK = Path(__file__).resolve().parents[1] / "references" / "talk-track.md"


def load_talk_track(core=prospect_common.CORE):
    """Read Outreach's private reference, or the explicit fixture directory."""
    path = TALK_TRACK if Path(core).resolve() == prospect_common.CORE.resolve() else Path(core) / "talk-track.md"
    return prospect_common.markdown_document(path)


def norm(t):
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\u00a0", " ")
    return re.sub(r"\s+", " ", t).strip().lower()


def d(s):
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        raise ValueError("date must be YYYY-MM-DD")
    return date.fromisoformat(s)


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def domain(value):
    """A plain DNS domain, not a URL, email address, or empty suffix."""
    if not nonblank(value):
        return None
    value = value.strip().lower()
    label = r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    return value if re.fullmatch(label + r"(?:\." + label + r")+", value) else None


def email_domain(value):
    if nonblank(value) and re.fullmatch(r"[^\s@<>,;]+@[^\s@<>,;]+", value.strip()):
        return domain(value.strip().rsplit("@", 1)[1])
    return None


def numbers(t):
    return {n.rstrip(".,") for n in NUM.findall(t or "")}


INVITE = re.compile(
    r"\b(?:(?:worth|have|spare|for|grab|find)\s+(?:a\s+)?\d+\s+minutes?\b"
    r"|\d+\s+minute\s+(?:call|chat|conversation|meeting)\b)", re.I)


def question_sentence(body):
    parts = [x for x in re.split(r"(?<=[.?!])\s+", body.strip()) if x.strip()]
    hits = [x for x in parts if "?" in x]
    return hits[0] if len(hits) == 1 else ""


def strip_invite_minutes(body):
    """Remove meeting-invitation minute spans from the one question sentence only.

    Whitelisted shapes. 'worth 20 minutes', 'have 20 minutes', 'a 20 minute call'.
    Any other number in the question, including 'save 20 minutes per report', stays and is checked.
    Code cannot recognize an invitation by meaning. Drafting review owns that.
    """
    q = question_sentence(body)
    if not q:
        return body
    return body.replace(q, INVITE.sub(" ", q), 1)


def warehouse_reasons(b, us):
    """Check 1 for a signal type whose taxonomy entry names a non-web source. us is policy user_scan."""
    ab = b.get("adoption_bundle")
    if not isinstance(ab, dict):
        return [f"{b['signal_type']} needs adoption_bundle, the privacy-checked signal-user-scan bundle"]
    reasons = [f"adoption_bundle failed prospect_privacy_check: {x}"
               for x in prospect_privacy_check.check(ab, us["bundle_keys"], list(us["adoption_values"]))]
    if ab.get("adoption") != "individuals_only":
        reasons.append(f"adoption_bundle adoption is {ab.get('adoption')!r}, {b['signal_type']} needs individuals_only")
    if norm(b.get("quote") or "") != norm(us["statements"]["individuals_only"]):
        reasons.append("bundle quote must equal user_scan.statements.individuals_only")
    for key in ("account_name", "account_domain", "salesforce_account_id", "data_through_date"):
        if not nonblank(ab.get(key)):
            reasons.append(f"adoption_bundle {key} must be a nonempty string")
    for wrapper_key, embedded_key in (("account_name", "account_name"), ("account_domain", "account_domain"),
                                      ("published_date", "data_through_date")):
        left, right = b.get(wrapper_key), ab.get(embedded_key)
        matches = nonblank(left) and nonblank(right) and (
            left == right if wrapper_key == "published_date" else norm(left) == norm(right))
        if not matches:
            reasons.append(f"bundle {wrapper_key} must match adoption_bundle {embedded_key}")
    return reasons


def check(p, policy, core, now):
    """policy is the loaded policy.yaml. core locates talk-track.md and signals.md."""
    pol = policy["outreach"]
    reasons = []
    current_route = prospect_account_route.route(p["account"], policy)
    if current_route != "scan":
        reasons.append(f"Account route {current_route} is not an eligible Operator-owned named Account without an open Opportunity")
    now = now.astimezone(prospect_common.policy_tz(policy))
    today = now.date()
    b, tt, rc, act, dr = p["bundle"], p["talk_track"], p["recipient"], p["activity"], p["draft"]
    for label, obj in (("bundle", b), ("talk_track", tt), ("recipient", rc), ("draft", dr)):
        if not isinstance(obj, dict):
            raise ValueError(f"{label} must be an object")
    if not isinstance(act, list):
        raise ValueError("activity must be the unfiltered live-read list, empty when no rows exist")
    adoption = b.get("adoption_bundle")
    if isinstance(adoption, dict) and adoption.get("salesforce_account_id") != p["account"]["account_id"]:
        reasons.append("adoption_bundle salesforce_account_id must match the current named Account")
    for key in ("account_name", "quote"):
        if not nonblank(b.get(key)):
            reasons.append(f"bundle {key} must be a nonempty string")
    account_domain = domain(b.get("account_domain"))
    if account_domain is None:
        reasons.append("bundle account_domain must be a usable domain")
    current_domain = domain(p["account"].get("account_domain"))
    if current_domain is None or current_domain != account_domain:
        reasons.append("bundle account_domain must match the verified current named Account domain")
    for key in ("subject", "body"):
        if not nonblank(dr.get(key)):
            raise ValueError(f"draft {key} must be a nonempty string")
    meta = load_talk_track(core)["meta"]
    stype, _tier = prospect_common.taxonomy_entry(prospect_common.load_taxonomy(core), b["signal_type"])
    warehouse = bool(stype and stype.get("source"))
    if stype is None:
        reasons.append(f"bundle signal_type not a tier1 or tier2 id: {b['signal_type']}")
    else:
        if not warehouse:
            if b.get("gate") != "evidence_gate":
                reasons.append("web bundle must be an prospect_evidence_gate output (gate prospect_evidence_gate); rescan")
            if not re.match(r"^https?://", b.get("source_url") or ""):
                reasons.append("web bundle needs its source_url; rescan")
            if not nonblank(b.get("date_basis")):
                reasons.append("web bundle needs date_basis; rescan")
            if b.get("classification") != "active_initiative":
                reasons.append("web bundle needs active_initiative classification; rescan old bundles")
            if b.get("relevance") != "employee_use":
                reasons.append("web bundle must establish employee_use; API and unclear findings do not enter this stage")
        if warehouse:
            if b.get("gate") == "evidence_gate" or b.get("source_url"):
                reasons.append(f"{b['signal_type']} is sourced from the {stype['source']}, not the web. "
                               "A page never qualifies it. Use the signal-user-scan bundle")
            reasons.extend(warehouse_reasons(b, policy["user_scan"]))
        published = d(b["published_date"])
        if published > max(today, now.astimezone(timezone.utc).date()):
            reasons.append("bundle published_date is in the future")
        age = (today - published).days
        if age > stype["freshness_days"]:
            reasons.append(f"bundle published_date {age} days old, {b['signal_type']} freshness is {stype['freshness_days']} days")
    checked = prospect_common.parse_iso(b.get("checked_at"))
    if checked is None:
        reasons.append("bundle checked_at needs an ISO timestamp with a timezone offset. Re-read the source")
    elif checked > now:
        reasons.append("bundle checked_at is in the future. Re-read the source")
    elif now - checked > timedelta(hours=pol["bundle_checked_max_age_hours"]):
        reasons.append("bundle checked_at older than policy. Re-read the source")
    # Judgment must be stated for human review; code does not determine its truth.
    for key in ("angle", "persona", "pick_reason"):
        if not nonblank(tt.get(key)):
            reasons.append(f"talk_track.{key} must be a nonempty explanation")
    body, subj = dr["body"], dr["subject"]
    review_by = str(meta.get("review_by") or "")
    if not review_by:
        reasons.append("talk-track.md meta.review_by missing. Review the track and set the date")
    elif d(review_by) < today:
        reasons.append(f"talk-track.md meta.review_by {review_by[:10]} is past. Review the track and move the date")
    if not nonblank(rc.get("title")):
        reasons.append("recipient title or verified responsibility must be stated")
    email = rc.get("email")
    dom = email_domain(email)
    if dom is None:
        reasons.append("recipient email must be a usable address")
    elif account_domain and dom != account_domain and not dom.endswith("." + account_domain):
        reasons.append("recipient domain does not match bundle account_domain")
    if rc.get("source") not in pol["recipient_sources"]:
        reasons.append("recipient source not in policy. Needs Operator to supply the address in this conversation")
    contact_id = rc.get("contact_id")
    if rc.get("source") == "existing Salesforce Contact with Email" and not nonblank(contact_id):
        reasons.append("Salesforce Contact recipient needs a nonempty contact_id")
    elif contact_id is not None and not nonblank(contact_id):
        reasons.append("recipient contact_id must be a nonempty string or null")
    # check 7
    cutoff = today - timedelta(days=pol["suppression_days"])
    me = {v.strip().lower() for v in (email, contact_id) if nonblank(v)}
    for a in act:
        if not isinstance(a, dict) or a.get("kind") not in ("task", "event", "gmail_sent"):
            raise ValueError("activity row needs kind task, event, or gmail_sent")
        activity_date = d(a.get("date"))
        if a["kind"] == "task" and (not nonblank(a.get("status")) or not nonblank(a.get("subtype"))):
            raise ValueError("activity task needs a nonempty status and subtype")
        who = a.get("who")
        if who is not None and not isinstance(who, str):
            raise ValueError("activity who must be a string or null")
        if nonblank(who) and not (email_domain(who) or re.fullmatch(r"(?:003|00Q)[A-Za-z0-9]+", who.strip(), re.I)):
            raise ValueError("activity who must be a Contact/Lead Id or email address, or blank when unknown")
        done = a["kind"] in ("gmail_sent", "event") or (
            a["status"] == "Completed" and a["subtype"] in pol["suppressing_task_subtypes"])
        mine = not nonblank(who) or who.strip().lower() in me
        if done and mine and activity_date >= cutoff:
            reasons.append(f"suppressed: {a['kind']} on {a['date']} to the recipient inside suppression window")
            break
    # check 8
    stray = sorted(numbers(strip_invite_minutes(body)) - numbers(b.get("quote")))
    if stray:
        reasons.append(f"numbers in body not in the bundle quote: {', '.join(stray)}")
    return reasons


def parse_now(s, policy):
    """Clock for the run. None means now in identity.timezone. A bare date means noon there. A naive timestamp is an error."""
    if not s:
        return prospect_common.policy_now(policy)
    t = prospect_common.parse_iso(s, policy)
    if t is None:
        raise ValueError(f"--now needs a date or an ISO timestamp with a timezone offset: {s!r}")
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packet", required=True)
    ap.add_argument("--core", default=str(prospect_common.CORE))
    ap.add_argument("--now", default=None,
                    help="ISO timestamp with offset, or a bare date meaning noon in identity.timezone. Defaults to now in that zone")
    a = ap.parse_args()
    try:
        core = Path(a.core)
        policy = prospect_common.load_policy(core)
        p = json.loads(Path(a.packet).read_text())
        reasons = check(p, policy, core, parse_now(a.now, policy))
    except prospect_common.INPUT_ERRORS as e:
        print(prospect_common.error_json(e))
        return 2
    if reasons:
        print(json.dumps({"verdict": "block", "reasons": reasons}, indent=2))
        return 1
    print(json.dumps({"verdict": "allow", "recipient": p["recipient"]["email"], "signal_type": p["bundle"]["signal_type"],
                      "angle": p["talk_track"]["angle"], "pick_reason": p["talk_track"]["pick_reason"],
                      "persona": p["talk_track"]["persona"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
