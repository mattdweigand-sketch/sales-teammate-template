#!/usr/bin/env python3
"""Normalize an event list and label reviewed exclusion evidence without writes.

Needs policy.prospecting.event.exclude and recent_reply_days,
policy.prospecting.identity.sfdc_user_id, and policy.tooling.generic_email_domains.
Existing Operator-owned Accounts and approved outreach-owner rows on house-owned or missing Accounts are in scope.
Outreach-owner column and Operator's value are per-run inputs; house owners and missing-Account inclusion come from policy.
Named-account scope is required even if an older exclusion config omits it, and cannot be overridden.
Labels are proposals, not approval.
Input is CSV or a reviewed JSON list. Outputs and per-list overrides stay outside Git.
"""
import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import yaml


EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
ALIASES = {
    "first_name": ("first_name", "First Name"),
    "last_name": ("last_name", "Last Name"),
    "email": ("email", "Email", "Email Business"),
    "company": ("company", "Company Name"),
    "website": ("website", "Website"),
    "contact_id": ("contact_id", "Contact Id"),
}
EVIDENCE_FIELDS = ("account_checked", "account_id", "account_owner_id", "opportunities_checked",
                   "open_opportunity", "replies_checked", "last_reply_at", "email_provider",
                   "email_status", "catchall_domain", "email_operation", "run_start",
                   "apollo_match_email", "apollo_match_catchall_domain", "apollo_match_run_start",
                   "apollo_contacts_checked", "apollo_contact_id", "apollo_contact_email",
                   "apollo_crm_linked", "apollo_crm_owner_id", "active_sequence",
                   "event_app_invite_export_supplied", "event_app_invite_checked", "event_app_invite")


def clean(value):
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).strip().split())


def boolean(value):
    if type(value) is bool:
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    return None


def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp requires an explicit timezone offset")
    return parsed


def website_host(value):
    value = clean(value).lower()
    try:
        host = urlsplit(value if "://" in value else f"//{value}").hostname or ""
    except ValueError:
        return ""
    return host.rstrip(".").removeprefix("www.")


def email_domain(value):
    return clean(value).lower().rsplit("@", 1)[-1] if EMAIL.fullmatch(clean(value)) else ""


def normalize(row):
    if not isinstance(row, dict):
        raise ValueError("Every event contact must be an object")
    result = {key: clean(next((row[name] for name in names if clean(row.get(name))), ""))
              for key, names in ALIASES.items()}
    result["email"] = result["email"].lower()
    result["website"] = result["website"].lower()
    for field in EVIDENCE_FIELDS:
        result[field] = row.get(field)
    for field in ("account_checked", "opportunities_checked", "open_opportunity", "replies_checked", "catchall_domain",
                  "apollo_match_catchall_domain", "apollo_contacts_checked", "apollo_crm_linked", "active_sequence",
                  "event_app_invite_export_supplied", "event_app_invite_checked", "event_app_invite"):
        result[field] = boolean(result[field])
    for field in ("account_id", "account_owner_id", "email_provider", "email_status", "email_operation",
                  "apollo_match_email", "apollo_contact_id", "apollo_contact_email", "apollo_crm_owner_id"):
        result[field] = clean(result[field])
    result["email_provider"] = result["email_provider"].lower()
    result["email_status"] = result["email_status"].lower()
    result["email_operation"] = result["email_operation"].lower()
    result["apollo_match_email"] = result["apollo_match_email"].lower()
    result["apollo_contact_email"] = result["apollo_contact_email"].lower()
    result["website_host"] = website_host(result["website"])
    result["reply_timestamp_present"] = "last_reply_at" in row
    return result


def resolve_catchall(contact, as_of):
    contact["catchall_source"] = None
    if contact["email_provider"] != "apollo":
        return
    if contact["catchall_domain"] is not None:
        contact["catchall_source"] = {"kind": "native_apollo", "operation": contact["email_operation"]}
        return
    if contact["email_operation"] != "apollo_waterfall" or contact["apollo_match_catchall_domain"] is None:
        return
    domain = email_domain(contact["email"])
    if not domain or domain != email_domain(contact["apollo_match_email"]):
        return
    try:
        run_start = timestamp(contact["run_start"])
        match_start = timestamp(contact["apollo_match_run_start"])
        if run_start != match_start or run_start > as_of:
            return
    except (ValueError, TypeError):
        return
    contact["catchall_domain"] = contact["apollo_match_catchall_domain"]
    contact["catchall_source"] = {"kind": "same_run_apollo_match", "email": contact["apollo_match_email"],
                                 "domain": domain, "run_start": run_start.isoformat()}


def exclusions(contact, prospecting, tooling, as_of):
    reasons = {}
    gaps = []
    email_gaps = []

    def add_email_gap(reason):
        gaps.append(reason)
        email_gaps.append(reason)

    if not contact["first_name"] or not contact["last_name"]:
        gaps.append("Missing first or last name for batch preparation")
    if contact.get("outreach_owner_issue"):
        gaps.append(contact["outreach_owner_issue"])
    contact["scope"] = None
    if contact["account_checked"] is not True:
        gaps.append("Account identity and ownership not completely checked")
    elif contact["account_id"] and not contact["account_owner_id"]:
        gaps.append("Resolved Account has no verified owner")
    elif contact["account_owner_id"] and not contact["account_id"]:
        gaps.append("Owner evidence has no resolved Account")
    else:
        scope = prospecting["event"].get("outreach_owner_scope", {})
        if contact["account_id"] and contact["account_owner_id"] == prospecting["identity"]["sfdc_user_id"]:
            contact["scope"] = "named_account"
        elif contact.get("outreach_owner_marked") is True and (
            (contact["account_id"] and contact["account_owner_id"] in scope.get("house_owner_ids", []))
            or (not contact["account_id"] and scope.get("include_missing_account") is True)
        ):
            contact["scope"] = "outreach_owner"
        else:
            reasons["outside_named_accounts"] = "Outside Operator-owned Accounts and the approved outreach-owner scope"
    if contact["opportunities_checked"] is not True or contact["open_opportunity"] is None:
        gaps.append("Open-Opportunity evidence not completely checked")
    if contact["open_opportunity"] is True:
        reasons["open_opportunity"] = "An open Opportunity routes this contact to Pipeline"
    if contact["apollo_contacts_checked"] is not True or contact["active_sequence"] is None:
        add_email_gap("Apollo existing-contact and active-sequence evidence not completely checked")
    if contact["apollo_contact_id"]:
        native_email = contact["apollo_contact_email"]
        if not EMAIL.fullmatch(native_email) or native_email != contact["email"]:
            gaps.append("Existing Apollo contact has a missing or different email")
        if email_domain(native_email) in tooling["generic_email_domains"]:
            gaps.append("Existing Apollo contact has a personal email")
        if contact["apollo_crm_linked"] is None:
            gaps.append("Existing Apollo contact CRM linkage not completely checked")
        elif contact["apollo_crm_linked"] is True:
            if not contact["apollo_crm_owner_id"]:
                gaps.append("Existing Apollo contact linked CRM record has no checked owner")
            elif contact["apollo_crm_owner_id"] != prospecting["identity"]["sfdc_user_id"] and not (
                    contact["scope"] == "outreach_owner" and contact["apollo_crm_owner_id"] in
                    prospecting["event"].get("outreach_owner_scope", {}).get("house_owner_ids", [])):
                gaps.append("Existing Apollo contact is linked to another owner's CRM record")
        elif contact["apollo_crm_owner_id"]:
            gaps.append("Existing Apollo contact CRM owner conflicts with no-link evidence")
    elif contact["apollo_contact_email"] or contact["apollo_crm_linked"] is True or contact["apollo_crm_owner_id"]:
        gaps.append("Existing Apollo contact evidence has no Contact ID")
    if contact["active_sequence"] is True:
        reasons["active_sequence"] = "Apollo contact data shows an active sequence"
    if contact["event_app_invite_export_supplied"] is None:
        gaps.append("Event invite export availability not stated")
    elif contact["event_app_invite_export_supplied"] is True:
        if contact["event_app_invite_checked"] is not True or contact["event_app_invite"] is None:
            add_email_gap("Supplied event invite export not completely matched")
        elif contact["event_app_invite"] is True:
            reasons["event_app_invite"] = "Contact matches Operator's supplied event invite export"
    elif contact["event_app_invite"] is True:
        gaps.append("Event invite match has no supplied export")
    if contact["replies_checked"] is not True or not contact["reply_timestamp_present"]:
        add_email_gap("Recent substantive reply evidence not completely checked")
    elif contact["last_reply_at"] not in (None, ""):
        try:
            replied = timestamp(contact["last_reply_at"])
            if replied > as_of:
                add_email_gap("Reply timestamp is in the future")
            elif replied >= as_of - timedelta(days=prospecting["event"]["recent_reply_days"]):
                reasons["recent_reply"] = "Substantive reply falls within the configured recent-reply window"
        except (ValueError, TypeError):
            add_email_gap("Reply timestamp is invalid or has no timezone")
    provider_verified = contact["email_provider"] == "apollo" and contact["email_status"] == "verified"
    verified = provider_verified and contact["catchall_domain"] is False
    if contact["catchall_domain"] is True:
        reasons["catch_all_email"] = "Provider evidence marks the email domain catch-all"
    if not provider_verified or contact["catchall_domain"] is None:
        reasons["unverified_email"] = "No Apollo verified non-catch-all evidence"
    if contact["email_operation"] == "apollo_waterfall" and contact["catchall_domain"] is None:
        gaps.append("Waterfall catch-all evidence has no same-run same-domain Apollo match")
    if not EMAIL.fullmatch(contact["email"]):
        reasons["unverified_email"] = "Recipient email is missing or malformed and needs enrichment or review"
        verified = False
    return reasons, gaps, verified, email_gaps


def prepare(rows, policy, as_of, overrides=None, *, outreach_owner_column=None, outreach_owner_value=None,
            outreach_owner_column_ambiguous=False):
    if not isinstance(rows, list):
        raise ValueError("Event input must be a list of contact rows")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Run timestamp requires an explicit timezone offset")
    if bool(clean(outreach_owner_column)) != bool(clean(outreach_owner_value)):
        raise ValueError("Outreach-owner column and Operator's value must be supplied together")
    prospecting = policy["prospecting"]
    scope = prospecting["event"].get("outreach_owner_scope", {})
    if (not isinstance(scope, dict) or not isinstance(scope.get("house_owner_ids", []), list)
            or any(not isinstance(item, str) or not item.strip() for item in scope.get("house_owner_ids", []))
            or type(scope.get("include_missing_account", False)) is not bool):
        raise ValueError("Invalid outreach-owner scope policy types")
    configured = prospecting["event"]["exclude"]
    overrides = overrides if overrides is not None else {}
    if not isinstance(overrides, dict):
        raise ValueError("Per-list overrides must map row IDs to exclusion lists")
    contacts = []
    duplicates = []
    seen = {}
    for position, row in enumerate(rows, 1):
        contact = normalize(row)
        contact.update(outreach_owner_marked=False, outreach_owner_issue=None)
        if outreach_owner_column:
            marker = row.get(outreach_owner_column)
            if outreach_owner_column_ambiguous or outreach_owner_column not in row or not isinstance(marker, (str, int, float, bool)):
                contact.update(outreach_owner_marked=None, outreach_owner_issue="Outreach-owner column is missing or ambiguous")
            else:
                contact["outreach_owner_marked"] = clean(str(marker)) == clean(outreach_owner_value)
                if outreach_owner_column not in contact:
                    contact[outreach_owner_column] = marker
        row_id = f"event-{position}"
        keys = []
        if contact["email"]:
            keys.append(("email", contact["email"]))
        if contact["contact_id"]:
            keys.append(("contact", contact["contact_id"]))
        if not keys:
            keys.append(("intake", *(contact[field].casefold() for field in ("first_name", "last_name", "company", "website"))))
        matches = []
        for key in keys:
            if key in seen and all(seen[key] is not match for match in matches):
                matches.append(seen[key])
        if matches:
            original = matches[0]
            comparison = (*ALIASES, *EVIDENCE_FIELDS, "reply_timestamp_present", "outreach_owner_marked", "outreach_owner_issue")
            for match in matches:
                match["handoff_required"] = match["handoff_required"] or contact["open_opportunity"] is True
                if len(matches) > 1 or any(match[field] != contact[field] for field in comparison):
                    match["duplicate_conflict"] = True
            original["source_rows"].append(position)
            duplicates.append({"row_id": row_id, "kept_row_id": original["row_id"], "reason": "Duplicate normalized email, contact ID, or identical intake"})
            for key in keys:
                seen.setdefault(key, original)
            continue
        contact.update(row_id=row_id, source_rows=[position], duplicate_conflict=False,
                       handoff_required=contact["open_opportunity"] is True)
        for key in keys:
            seen[key] = contact
        contacts.append(contact)
    known_ids = {contact["row_id"] for contact in contacts}
    if set(overrides) - known_ids:
        raise ValueError("Override refers to an unknown or duplicate row ID")
    for contact in contacts:
        requested = overrides.get(contact["row_id"], [])
        if not isinstance(requested, list) or any(not isinstance(item, str) or item not in configured for item in requested):
            raise ValueError("Override must name configured exclusions for this contact only")
        if "outside_named_accounts" in requested:
            raise ValueError("Named-account scope cannot be overridden")
        resolve_catchall(contact, as_of)
        reasons, gaps, verified, email_gaps = exclusions(contact, prospecting, policy["tooling"], as_of)
        if contact["duplicate_conflict"]:
            gaps.append("Duplicate rows disagree, reconcile identity and evidence before enrollment")
        matched = [name for name in configured if name in reasons]
        if "outside_named_accounts" in reasons and "outside_named_accounts" not in matched:
            matched.insert(0, "outside_named_accounts")
        for name in ("active_sequence", "event_app_invite"):
            if name in reasons and name not in matched:
                matched.append(name)
        remaining = [name for name in matched if name not in requested]
        if not EMAIL.fullmatch(contact["email"]) and "unverified_email" in requested:
            gaps.append("An override cannot supply a missing or malformed recipient email")
        invite_status = "not checked"
        if contact["event_app_invite_export_supplied"] is False:
            invite_status = "none checked, no export supplied"
        elif (contact["event_app_invite_export_supplied"] is True and contact["event_app_invite_checked"] is True
              and contact["event_app_invite"] is not None):
            invite_status = "checked"
        enrichment_gaps = gaps if EMAIL.fullmatch(contact["email"]) else [gap for gap in gaps if gap not in email_gaps]
        contact.update(exclusions=[{"label": name, "reason": reasons[name]} for name in matched],
                       overrides_applied=[name for name in matched if name in requested],
                       needs_input=gaps, enrichment_needed=not verified and not enrichment_gaps and matched == ["unverified_email"],
                       event_app_invite_status=invite_status)
        if gaps:
            contact.update(label="needs_input", reason="; ".join(gaps))
        elif remaining:
            contact.update(label=remaining[0], reason=reasons[remaining[0]])
        else:
            contact.update(label="enroll", reason="Reviewed checks pass or named per-list exclusions were overridden, still requires exact enrollment approval")
    counts = dict(Counter(contact["label"] for contact in contacts))
    return {"status": "needs-input" if counts.get("needs_input") else "review-ready",
            "outreach_owner_column": outreach_owner_column, "outreach_owner_value": outreach_owner_value,
            "as_of": as_of.isoformat(), "input_rows": len(rows), "unique_contacts": len(contacts),
            "duplicate_rows": len(duplicates), "counts": counts, "contacts": contacts, "duplicates": duplicates,
            "enrichment_candidates": [contact["row_id"] for contact in contacts if contact["enrichment_needed"]],
            "pipeline_handoff": [contact["row_id"] for contact in contacts if contact["handoff_required"]],
            "authorization": "Proposal labels only, never approval to enrich or enroll"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Intake CSV or reviewed JSON contact list")
    parser.add_argument("--as-of", required=True, help="Run-start timestamp with explicit local offset")
    parser.add_argument("--policy", type=Path, default=Path(__file__).resolve().parents[5] / "_core" / "policy.yaml")
    parser.add_argument("--overrides", type=Path, help="This list only, row-ID to explicit exclusion-name lists")
    parser.add_argument("--outreach-owner-column", help="Outreach-owner column from the event list Operator named")
    parser.add_argument("--outreach-owner-value", help="Exact value marking Operator in that column")
    parser.add_argument("--output", type=Path, help="Sandbox JSON output, otherwise stdout")
    args = parser.parse_args(argv)
    ambiguous_column = False
    if args.input.suffix.lower() == ".csv":
        with args.input.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            ambiguous_column = bool(args.outreach_owner_column and (reader.fieldnames or []).count(args.outreach_owner_column) > 1)
            rows = list(reader)
    else:
        rows = json.loads(args.input.read_text())
    result = prepare(rows, yaml.safe_load(args.policy.read_text()), timestamp(args.as_of),
                     json.loads(args.overrides.read_text()) if args.overrides else None,
                     outreach_owner_column=args.outreach_owner_column, outreach_owner_value=args.outreach_owner_value,
                     outreach_owner_column_ambiguous=ambiguous_column)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
