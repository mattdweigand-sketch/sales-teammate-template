#!/usr/bin/env python3
import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path


STATUS_CLEAN = "CLEAN"
STATUS_REMOVED = "REMOVED"
STATUS_QUARANTINE = "QUARANTINE"

EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
EMAIL_VALUE_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
PERSON_SIGNAL_RE = re.compile(r"^([a-z][a-z]+[._-][a-z][a-z]+|[a-z][._-][a-z][a-z]+|[a-z][a-z]+[._-][a-z])$")
SEPARATORS_RE = re.compile(r"[._+\-]+")
DEFAULT_MAX_CLEAN_CHUNK_BYTES = 10 * 1024 * 1024
NAME_NOISE = {
    "cpa",
    "dr",
    "esq",
    "inc",
    "llc",
    "mba",
    "md",
    "mr",
    "mrs",
    "ms",
    "msa",
    "of",
    "president",
    "prof",
    "the",
}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_csv_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return sum(1 for _ in csv.DictReader(f))


def describe_output_file(path, output_dir):
    path = Path(path)
    return {
        "path": str(path.relative_to(output_dir)).replace("\\", "/"),
        "rows": count_csv_rows(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_rules(path):
    with open(path, encoding="utf-8") as f:
        rules = json.load(f)
    normalized = dict(rules)
    for key in [
        "exact_local_parts",
        "high_risk_tokens",
        "placeholder_domains",
        "blocked_domains",
        "disposable_domains",
        "free_mail_domains",
    ]:
        normalized[key] = {str(item).strip().lower() for item in rules.get(key, [])}
    normalized["collapsed_exact_local_parts"] = {collapse_token(x) for x in normalized["exact_local_parts"]}
    normalized["collapsed_high_risk_tokens"] = {collapse_token(x) for x in normalized["high_risk_tokens"]}
    return normalized


def collapse_token(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def normalize_email(raw):
    if raw is None:
        return "", []

    value = str(raw).strip().strip("\ufeff")
    notes = []
    if not value:
        return "", notes

    value = value.strip().strip('"').strip("'").strip()
    if value.lower().startswith("mailto:"):
        value = value[7:].strip()
        notes.append("NORMALIZED_MAILTO")

    parsed_name, parsed_addr = parseaddr(value)
    if parsed_addr and parsed_addr != value:
        value = parsed_addr.strip()
        notes.append("PARSED_DISPLAY_NAME")

    value = value.strip("<>").strip().lower()
    return value, notes


def looks_like_email_value(raw):
    value = str(raw or "").strip().strip('"').strip("'").strip()
    return EMAIL_VALUE_RE.fullmatch(value.lower()) is not None


def is_email_header(header):
    lowered = header.lower()
    return "email" in lowered or "e-mail" in lowered


def detect_email_columns(input_path, headers, explicit_column=None):
    if explicit_column:
        if explicit_column not in headers:
            raise SystemExit(f"Email column not found: {explicit_column}")
        return [explicit_column], "explicit"

    nonempty_counts = Counter()
    email_like_counts = Counter()
    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for header in headers:
                value = row.get(header, "")
                if str(value or "").strip():
                    nonempty_counts[header] += 1
                    if looks_like_email_value(value):
                        email_like_counts[header] += 1

    candidates = []
    for header in headers:
        email_like = email_like_counts[header]
        nonempty = nonempty_counts[header]
        ratio = email_like / nonempty if nonempty else 0
        if is_email_header(header) and (email_like > 0 or nonempty == 0):
            candidates.append(header)
        elif email_like >= 10 and ratio >= 0.5:
            candidates.append(header)

    if not candidates:
        raise SystemExit("Could not detect a usable email column. Pass --email-column explicitly.")
    return candidates, "rightmost_waterfall_auto"


def select_raw_email(row, email_columns):
    for column in reversed(email_columns):
        value = row.get(column, "")
        if str(value or "").strip():
            return value, column
    return "", ""


def split_local_domain(email):
    if email.count("@") != 1:
        return "", ""
    local, domain = email.rsplit("@", 1)
    return local, domain


def local_tokens(local):
    return [t for t in SEPARATORS_RE.split(local.lower()) if t]


def clean_name(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z]", "", ascii_text.lower())


def name_tokens(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    tokens = re.findall(r"[a-z]+", ascii_text.lower())
    return [token for token in tokens if token not in NAME_NOISE]


def explicit_last_name_tokens(value):
    tokens = name_tokens(value)
    if tokens:
        return tokens

    raw_tokens = re.findall(r"[A-Za-z]+", str(value or ""))
    preserved = []
    for token in raw_tokens:
        lowered = token.lower()
        if token.isupper() and len(token) >= 2 and (lowered not in NAME_NOISE or lowered == "ms"):
            preserved.append(token.lower())
    return preserved


def first_last_tokens(row):
    first_tokens = name_tokens(row.get("First Name"))
    last_tokens = explicit_last_name_tokens(row.get("Last Name"))

    if not first_tokens or not last_tokens:
        full_tokens = name_tokens(row.get("Full Name"))
        if not first_tokens and full_tokens:
            first_tokens = [full_tokens[0]]
        if not last_tokens and len(full_tokens) > 1:
            last_tokens = full_tokens[1:]
        if first_tokens and not last_tokens and len(first_tokens) > 1:
            last_tokens = first_tokens[1:]
            first_tokens = [first_tokens[0]]
        if last_tokens and not first_tokens and len(last_tokens) > 1:
            first_tokens = [last_tokens[0]]
            last_tokens = last_tokens[1:]

    return first_tokens, last_tokens


def local_matches_person_initials(local, row):
    collapsed = collapse_token(local.split("+", 1)[0])
    first_tokens, last_tokens = first_last_tokens(row)
    for first in first_tokens:
        for last in last_tokens:
            if first and last and collapsed == f"{first[0]}{last[0]}":
                return True
    return False


def has_person_signal(local, row):
    base = local.split("+", 1)[0].lower()
    collapsed = collapse_token(base)
    first_tokens, last_tokens = first_last_tokens(row)
    full = clean_name(row.get("Full Name"))

    person_values = set()
    for first_value in first_tokens:
        if len(first_value) >= 2:
            person_values.add(first_value)
    for last_value in last_tokens:
        if len(last_value) >= 3:
            person_values.add(last_value)
    if len(first_tokens) > 1:
        combined_first = "".join(first_tokens)
        if len(combined_first) >= 3:
            person_values.add(combined_first)
        first_initials = "".join(token[0] for token in first_tokens if token)
        if len(first_initials) >= 2:
            person_values.add(first_initials)
    if len(last_tokens) > 1:
        combined_last = "".join(last_tokens)
        if len(combined_last) >= 3:
            person_values.add(combined_last)

    first_forms = set(first_tokens)
    last_forms = set(last_tokens)
    if len(first_tokens) > 1:
        first_forms.add("".join(first_tokens))
        first_forms.add("".join(token[0] for token in first_tokens if token))
    if len(last_tokens) > 1:
        last_forms.add("".join(last_tokens))

    for first_value in first_forms:
        for last_value in last_forms:
            if not first_value or not last_value:
                continue
            person_values.update(
                {
                    f"{first_value}{last_value}",
                    f"{first_value[0]}{last_value}",
                    f"{first_value}{last_value[0]}",
                    f"{last_value}{first_value}",
                    f"{last_value}{first_value[0]}",
                }
            )
            if base in {
                    f"{first_value}.{last_value}",
                    f"{first_value}_{last_value}",
                    f"{first_value}-{last_value}",
                    f"{first_value[0]}.{last_value}",
                    f"{first_value[0]}_{last_value}",
                    f"{first_value[0]}-{last_value}",
                }:
                return True

    if collapsed in person_values:
        return True

    # First-name prefix plus full last name, e.g. damurray for Dan Murray.
    for first_value in first_forms:
        for last_value in last_forms:
            if len(last_value) >= 4 and collapsed.endswith(last_value):
                prefix = collapsed[: -len(last_value)]
                if 1 <= len(prefix) <= len(first_value) and first_value.startswith(prefix):
                    return True

    if full and collapsed == full:
        return True

    if not first_tokens and not last_tokens and re.fullmatch(r"[a-z]{3,}", collapsed):
        return True

    return PERSON_SIGNAL_RE.fullmatch(base) is not None


def has_valid_domain(domain):
    if not domain or "." not in domain or len(domain) > 253:
        return False
    if domain.endswith(".") or domain.startswith("."):
        return False
    labels = domain.split(".")
    if any(not label or len(label) > 63 for label in labels):
        return False
    if any(label.startswith("-") or label.endswith("-") for label in labels):
        return False
    if not re.fullmatch(r"[a-z0-9.-]+", domain):
        return False
    tld = labels[-1]
    if len(tld) < 2 or not re.fullmatch(r"[a-z]{2,24}", tld):
        return False
    return True


def syntax_domain_validator(email, local, domain, rules):
    codes = []
    matches = []
    vote = STATUS_CLEAN

    if not email:
        return STATUS_REMOVED, ["MISSING_EMAIL"], ["syntax:missing"]

    if any(sep in email for sep in [";", ",", " "]):
        vote = STATUS_REMOVED
        codes.append("MALFORMED_OR_MULTIPLE_EMAILS")
        matches.append("syntax:separator_or_space")

    if email.count("@") != 1 or not local or not domain:
        vote = STATUS_REMOVED
        codes.append("MALFORMED_EMAIL")
        matches.append("syntax:at_count_or_missing_part")
        return vote, codes, matches

    if not EMAIL_RE.fullmatch(email):
        vote = STATUS_REMOVED
        codes.append("MALFORMED_EMAIL")
        matches.append("syntax:email_regex")

    if local.startswith(".") or local.endswith(".") or ".." in local:
        vote = STATUS_REMOVED
        codes.append("MALFORMED_LOCAL_PART")
        matches.append("syntax:local_dot")

    if not has_valid_domain(domain):
        vote = STATUS_REMOVED
        codes.append("MALFORMED_DOMAIN")
        matches.append("syntax:domain")

    if domain in rules["placeholder_domains"]:
        vote = STATUS_REMOVED
        codes.append("PLACEHOLDER_DOMAIN")
        matches.append(f"domain:placeholder:{domain}")

    if domain in rules["blocked_domains"] or any(domain.endswith("." + d) for d in rules["blocked_domains"]):
        vote = STATUS_REMOVED
        codes.append("DISTRIBUTION_DOMAIN")
        matches.append(f"domain:blocked:{domain}")

    if domain in rules["disposable_domains"]:
        vote = STATUS_REMOVED
        codes.append("DISPOSABLE_DOMAIN")
        matches.append(f"domain:disposable:{domain}")

    return vote, codes, matches


def exact_blocklist_validator(local, rules, row):
    base = local.split("+", 1)[0].lower()
    collapsed_base = collapse_token(base)
    codes = []
    matches = []
    ambiguous_initial_roles = {"ap", "ar", "pr"}

    if base in rules["exact_local_parts"]:
        if base in ambiguous_initial_roles and local_matches_person_initials(base, row):
            return STATUS_QUARANTINE, ["AMBIGUOUS_ROLE_INITIALS"], [f"local:ambiguous_initial_role:{base}"]
        return STATUS_REMOVED, ["ROLE_EXACT"], [f"local:exact:{base}"]

    if collapsed_base in rules["collapsed_exact_local_parts"]:
        return STATUS_REMOVED, ["ROLE_VARIANT_COLLAPSED"], [f"local:collapsed:{collapsed_base}"]

    tokens = local_tokens(base)
    for token in tokens:
        collapsed = collapse_token(token)
        if token in ambiguous_initial_roles and local_matches_person_initials(token, row):
            codes.append("AMBIGUOUS_ROLE_INITIALS")
            matches.append(f"local:ambiguous_initial_role:{token}")
        elif token in rules["exact_local_parts"] or collapsed in rules["collapsed_exact_local_parts"]:
            codes.append("ROLE_TOKEN")
            matches.append(f"local:token:{token}")

    if codes:
        if all(code == "AMBIGUOUS_ROLE_INITIALS" for code in codes):
            return STATUS_QUARANTINE, codes, matches
        return STATUS_REMOVED, codes, matches
    return STATUS_CLEAN, [], []


def pattern_heuristic_validator(local, domain, rules, strict, row):
    base = local.split("+", 1)[0].lower()
    tokens = local_tokens(base)
    codes = []
    matches = []

    if any(fragment in base for fragment in ["noreply", "no-reply", "do-not-reply", "donotreply", "reply-not", "mailer-daemon"]):
        codes.append("NO_REPLY_OR_BOUNCE_ALIAS")
        matches.append("local:no_reply_fragment")

    for token in tokens:
        collapsed = collapse_token(token)
        if token in rules["high_risk_tokens"] or collapsed in rules["collapsed_high_risk_tokens"]:
            codes.append("HIGH_RISK_TOKEN")
            matches.append(f"local:high_risk_token:{token}")

    if codes:
        return STATUS_REMOVED, codes, matches

    if domain in rules["free_mail_domains"]:
        return STATUS_QUARANTINE, ["FREE_MAIL_DOMAIN"], [f"domain:free_mail:{domain}"]

    if strict and not has_person_signal(base, row):
        return STATUS_QUARANTINE, ["NO_CLEAR_PERSON_SIGNAL"], ["heuristic:person_signal"]

    return STATUS_CLEAN, [], []


def classify(row, email_columns, rules, strict, seen):
    if isinstance(email_columns, str):
        email_columns = [email_columns]
    raw_email, selected_email_column = select_raw_email(row, email_columns)
    normalized, normalize_notes = normalize_email(raw_email)
    local, domain = split_local_domain(normalized)

    votes = {}
    reason_codes = []
    matched_rule_ids = []

    vote, codes, matches = syntax_domain_validator(normalized, local, domain, rules)
    votes["SyntaxDomainRiskValidator"] = vote
    reason_codes.extend(codes)
    matched_rule_ids.extend(matches)

    if vote != STATUS_REMOVED:
        vote, codes, matches = exact_blocklist_validator(local, rules, row)
    votes["ExactBlocklistValidator"] = vote
    reason_codes.extend(codes)
    matched_rule_ids.extend(matches)

    if vote != STATUS_REMOVED:
        vote, codes, matches = pattern_heuristic_validator(local, domain, rules, strict, row)
    votes["PatternHeuristicValidator"] = vote
    reason_codes.extend(codes)
    matched_rule_ids.extend(matches)

    if normalized and normalized in seen:
        votes["DeduplicationValidator"] = STATUS_REMOVED
        reason_codes.append("DUPLICATE_EMAIL")
        matched_rule_ids.append("dedupe:normalized_email")
    else:
        votes["DeduplicationValidator"] = STATUS_CLEAN

    if STATUS_REMOVED in votes.values():
        status = STATUS_REMOVED
    elif STATUS_QUARANTINE in votes.values():
        status = STATUS_QUARANTINE
    else:
        status = STATUS_CLEAN

    if normalized and status == STATUS_CLEAN:
        seen.add(normalized)

    if normalize_notes:
        matched_rule_ids.extend([f"normalize:{n.lower()}" for n in normalize_notes])

    return {
        "status": status,
        "raw_selected_email": str(raw_email or ""),
        "selected_email_column": selected_email_column,
        "normalized_email": normalized,
        "local_part": local,
        "domain": domain,
        "reason_codes": sorted(set(reason_codes)),
        "matched_rule_ids": sorted(set(matched_rule_ids)),
        "validator_votes": votes,
    }


def make_writer(path, fieldnames):
    f = open(path, "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    return f, writer


def csv_row_bytes(fieldnames, row):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writerow({key: row.get(key, "") for key in fieldnames})
    return len(buffer.getvalue().encode("utf-8"))


def csv_header_bytes(fieldnames):
    return csv_row_bytes(fieldnames, {key: key for key in fieldnames})


def resolve_column(headers, candidates):
    lower_to_header = {h.lower(): h for h in headers}
    for candidate in candidates:
        found = lower_to_header.get(candidate.lower())
        if found:
            return found
    return None


def clean_upload_fields(headers):
    fields = []
    for header in ["First Name", "Last Name", "Title", "Company Name"]:
        found = resolve_column(headers, [header])
        if found and found not in fields:
            fields.append(found)

    website_or_domain = resolve_column(
        headers,
        [
            "Company Website",
            "Website URL",
            "Website",
            "Company Domain Name",
            "Domain",
            "Company Domain",
        ],
    )
    if website_or_domain and website_or_domain not in fields:
        fields.append(website_or_domain)

    linkedin = resolve_column(headers, ["LinkedIn", "Linkedin", "LinkedIn URL", "LinkedIn Profile"])
    if linkedin and linkedin not in fields:
        fields.append(linkedin)

    fields.append("Email")
    return fields


def augmented_row(row, decision):
    out = dict(row)
    out["raw_selected_email"] = decision["raw_selected_email"]
    out["selected_email_column"] = decision["selected_email_column"]
    out["normalized_email"] = decision["normalized_email"]
    out["local_part"] = decision["local_part"]
    out["domain"] = decision["domain"]
    out["scrub_status"] = decision["status"]
    out["reason_codes"] = "|".join(decision["reason_codes"])
    out["matched_rule_ids"] = "|".join(decision["matched_rule_ids"])
    out["validator_votes"] = json.dumps(decision["validator_votes"], sort_keys=True)
    return out


def clean_upload_row(row, decision, fieldnames):
    out = {}
    for field in fieldnames:
        if field == "Email":
            out[field] = decision["normalized_email"]
        else:
            out[field] = row.get(field, "")
    return out


def row_with_audit_name_context(row):
    out = dict(row)
    if not out.get("Full Name"):
        first = (out.get("First Name") or "").strip()
        last = (out.get("Last Name") or "").strip()
        full = " ".join(value for value in [first, last] if value)
        if full:
            out["Full Name"] = full
    return out


def write_augmented(writer, row, decision, fieldnames):
    out = augmented_row(row, decision)
    writer.writerow({key: out.get(key, "") for key in fieldnames})


def audit_clean_file(path, email_columns, rules, strict, seen=None):
    failures = []
    if seen is None:
        seen = set()
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=2):
            decision = classify(row_with_audit_name_context(row), email_columns, rules, strict, seen)
            if decision["status"] != STATUS_CLEAN:
                failures.append(
                    {
                        "file": str(path),
                        "line": idx,
                        "email": decision["normalized_email"],
                        "reason_codes": decision["reason_codes"],
                        "matched_rule_ids": decision["matched_rule_ids"],
                    }
                )
                if len(failures) >= 100:
                    break
    return failures


def scrub(args):
    start = time.perf_counter()
    if not hasattr(args, "max_clean_chunk_bytes"):
        args.max_clean_chunk_bytes = DEFAULT_MAX_CLEAN_CHUNK_BYTES
    if not hasattr(args, "clean_column_profile"):
        args.clean_column_profile = "upload"
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()
    clean_dir = output_dir / "clean_chunks"
    clean_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in clean_dir.glob("clean_part_*.csv"):
        old_file.unlink()
    for old_name in [
        "removed_leads.csv",
        "quarantine_leads.csv",
        "audit_report.json",
        "audit_report.md",
        "failure_report.json",
        "output_manifest.json",
    ]:
        old_path = output_dir / old_name
        if old_path.exists():
            old_path.unlink()

    rules = load_rules(args.rules)
    source_hash = sha256_file(input_path)

    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit("Input CSV has no header row.")
        email_columns, email_selection_strategy = detect_email_columns(input_path, reader.fieldnames, args.email_column)

        audit_fields = [
            "raw_selected_email",
            "selected_email_column",
            "normalized_email",
            "local_part",
            "domain",
            "scrub_status",
            "reason_codes",
            "matched_rule_ids",
            "validator_votes",
        ]
        output_fields = list(reader.fieldnames) + [x for x in audit_fields if x not in reader.fieldnames]
        clean_fields = clean_upload_fields(reader.fieldnames) if args.clean_column_profile == "upload" else output_fields

        removed_f, removed_writer = make_writer(output_dir / "removed_leads.csv", output_fields)
        quarantine_f = None
        quarantine_writer = None
        if args.output_profile == "review":
            quarantine_f, quarantine_writer = make_writer(output_dir / "quarantine_leads.csv", output_fields)

        clean_files = []
        clean_f = None
        clean_writer = None
        clean_in_chunk = 0
        clean_bytes_in_chunk = 0
        clean_total = 0
        chunk_index = 0
        seen = set()
        counts = Counter()
        reason_counts = Counter()
        rows_total = 0

        def next_clean_writer():
            nonlocal clean_f, clean_writer, clean_in_chunk, clean_bytes_in_chunk, chunk_index
            if clean_f:
                clean_f.close()
            chunk_index += 1
            clean_in_chunk = 0
            clean_bytes_in_chunk = csv_header_bytes(clean_fields)
            path = clean_dir / f"clean_part_{chunk_index:03d}.csv"
            clean_files.append(path)
            clean_f, clean_writer = make_writer(path, clean_fields)

        try:
            for row in reader:
                rows_total += 1
                decision = classify(row, email_columns, rules, args.strict, seen)
                status = decision["status"]
                counts[status] += 1
                for code in decision["reason_codes"]:
                    reason_counts[code] += 1

                if status == STATUS_CLEAN:
                    clean_row = (
                        clean_upload_row(row, decision, clean_fields)
                        if args.clean_column_profile == "upload"
                        else augmented_row(row, decision)
                    )
                    row_bytes = csv_row_bytes(clean_fields, clean_row)
                    if (
                        clean_writer is None
                        or clean_in_chunk >= args.chunk_size
                        or (
                            clean_in_chunk > 0
                            and clean_bytes_in_chunk + row_bytes > args.max_clean_chunk_bytes
                        )
                    ):
                        next_clean_writer()
                    clean_writer.writerow({key: clean_row.get(key, "") for key in clean_fields})
                    clean_bytes_in_chunk += row_bytes
                    clean_in_chunk += 1
                    clean_total += 1
                elif status == STATUS_REMOVED or args.output_profile == "final":
                    write_augmented(removed_writer, row, decision, output_fields)
                else:
                    write_augmented(quarantine_writer, row, decision, output_fields)
        finally:
            if clean_f:
                clean_f.close()
            removed_f.close()
            if quarantine_f:
                quarantine_f.close()

    failures = []
    clean_audit_email_columns = ["Email"] if args.clean_column_profile == "upload" else email_columns
    audit_seen = set()
    for clean_file in clean_files:
        failures.extend(audit_clean_file(clean_file, clean_audit_email_columns, rules, args.strict, audit_seen))
        if failures:
            break

    status = "PASS" if not failures else "FAIL"
    if failures:
        failure_path = output_dir / "failure_report.json"
        failure_path.write_text(json.dumps({"failures": failures}, indent=2), encoding="utf-8")

    elapsed = time.perf_counter() - start
    clean_chunk_paths = [p for p in clean_files if p.exists() and count_csv_rows(p) > 0]
    output_files = [describe_output_file(p, output_dir) for p in clean_chunk_paths]
    removed_path = output_dir / "removed_leads.csv"
    if removed_path.exists():
        output_files.append(describe_output_file(removed_path, output_dir))
    quarantine_path = output_dir / "quarantine_leads.csv"
    if quarantine_path.exists():
        output_files.append(describe_output_file(quarantine_path, output_dir))

    manifest = {
        "input_sha256": source_hash,
        "rules_version": rules.get("version"),
        "email_columns": email_columns,
        "email_selection_strategy": email_selection_strategy,
        "chunk_size": args.chunk_size,
        "max_clean_chunk_bytes": args.max_clean_chunk_bytes,
        "clean_column_profile": args.clean_column_profile,
        "clean_output_columns": clean_fields,
        "strict": args.strict,
        "output_profile": args.output_profile,
        "rows_total": rows_total,
        "counts": dict(counts),
        "deliverable_counts": {
            "clean": counts.get(STATUS_CLEAN, 0),
            "removed": counts.get(STATUS_REMOVED, 0)
            + (counts.get(STATUS_QUARANTINE, 0) if args.output_profile == "final" else 0),
            "quarantine": 0 if args.output_profile == "final" else counts.get(STATUS_QUARANTINE, 0),
        },
        "reason_code_counts": dict(reason_counts),
        "output_files": output_files,
    }
    manifest_path = output_dir / "output_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    report = {
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_path),
        "input_sha256": source_hash,
        "email_columns": email_columns,
        "email_selection_strategy": email_selection_strategy,
        "rules_file": str(Path(args.rules).resolve()),
        "rules_version": rules.get("version"),
        "chunk_size": args.chunk_size,
        "max_clean_chunk_bytes": args.max_clean_chunk_bytes,
        "clean_column_profile": args.clean_column_profile,
        "clean_output_columns": clean_fields,
        "strict": args.strict,
        "output_profile": args.output_profile,
        "rows_total": rows_total,
        "counts": dict(counts),
        "deliverable_counts": manifest["deliverable_counts"],
        "reason_code_counts": dict(reason_counts),
        "clean_chunk_files": [str(p) for p in clean_chunk_paths],
        "output_manifest": str(manifest_path),
        "output_manifest_sha256": sha256_file(manifest_path),
        "elapsed_seconds": round(elapsed, 3),
        "rows_per_second": round(rows_total / elapsed, 2) if elapsed else None,
        "audit_failures": failures,
    }
    (output_dir / "audit_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_lines = [
        "# Lead Scrub Audit Report",
        "",
        f"- Status: {status}",
        f"- Input rows: {rows_total:,}",
        f"- Email selection: {email_selection_strategy}",
        f"- Email columns: {', '.join(email_columns)}",
        f"- Clean: {counts.get(STATUS_CLEAN, 0):,}",
        f"- Removed output rows: {report['deliverable_counts']['removed']:,}",
        f"- Internal removed votes: {counts.get(STATUS_REMOVED, 0):,}",
        f"- Internal quarantine votes: {counts.get(STATUS_QUARANTINE, 0):,}",
        f"- Chunk size: {args.chunk_size:,}",
        f"- Max clean chunk size: {args.max_clean_chunk_bytes:,} bytes",
        f"- Clean column profile: {args.clean_column_profile}",
        f"- Clean chunks: {len(clean_chunk_paths)}",
        f"- Output manifest: output_manifest.json",
        f"- Runtime: {elapsed:.3f}s ({report['rows_per_second']:,} rows/sec)",
        "",
        "## Top Reason Codes",
        "",
    ]
    for code, count in reason_counts.most_common(25):
        md_lines.append(f"- {code}: {count:,}")
    (output_dir / "audit_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0 if status == "PASS" else 2


def audit_clean_output(args):
    start = time.perf_counter()
    rules = load_rules(args.rules)
    input_path = Path(args.input).resolve()
    paths = []
    if input_path.is_dir():
        paths = sorted(input_path.glob("*.csv"))
    else:
        paths = [input_path]

    if not paths:
        raise SystemExit(f"No CSV files found for audit: {input_path}")

    failures = []
    rows_total = 0
    seen = set()
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                failures.append({"file": str(path), "line": 1, "reason_codes": ["MISSING_HEADER"]})
                continue
            email_columns, _email_selection_strategy = detect_email_columns(path, reader.fieldnames, args.email_column)
            for idx, row in enumerate(reader, start=2):
                rows_total += 1
                decision = classify(row_with_audit_name_context(row), email_columns, rules, args.strict, seen)
                if decision["status"] != STATUS_CLEAN:
                    failures.append(
                        {
                            "file": str(path),
                            "line": idx,
                            "email": decision["normalized_email"],
                            "status": decision["status"],
                            "reason_codes": decision["reason_codes"],
                            "matched_rule_ids": decision["matched_rule_ids"],
                        }
                    )
                    if len(failures) >= args.max_failures:
                        break
        if len(failures) >= args.max_failures:
            break

    elapsed = time.perf_counter() - start
    report = {
        "status": "PASS" if not failures else "FAIL",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "files_audited": [str(path) for path in paths],
        "rows_total": rows_total,
        "rules_file": str(Path(args.rules).resolve()),
        "rules_version": rules.get("version"),
        "strict": args.strict,
        "elapsed_seconds": round(elapsed, 3),
        "failures": failures,
    }
    if args.report:
        Path(args.report).resolve().write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not failures else 2


def main():
    parser = argparse.ArgumentParser(description="Deterministic lead-list scrubber for pre-upload email hygiene.")
    subparsers = parser.add_subparsers(dest="command")

    scrub_parser = subparsers.add_parser("scrub", help="Scrub a raw lead CSV and write clean chunks plus audit outputs.")
    scrub_parser.add_argument("input", help="Input CSV file.")
    scrub_parser.add_argument("--email-column", help="Email column name. Auto-detected only when exactly one email-like column exists.")
    scrub_parser.add_argument("--output-dir", required=True, help="Output directory.")
    scrub_parser.add_argument("--rules", default=str(Path(__file__).resolve().parent / "email_rules.json"))
    scrub_parser.add_argument("--chunk-size", type=int, default=25000)
    scrub_parser.add_argument("--max-clean-chunk-mb", type=float, default=10.0)
    scrub_parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=True)
    scrub_parser.add_argument(
        "--clean-column-profile",
        choices=["upload", "full"],
        default="upload",
        help="upload writes slim verifier-ready clean chunks; full preserves all source/audit columns in clean chunks.",
    )
    scrub_parser.add_argument(
        "--output-profile",
        choices=["final", "review"],
        default="final",
        help="final writes only clean chunks and removed_leads.csv; review also writes quarantine_leads.csv.",
    )
    scrub_parser.set_defaults(func=scrub)

    audit_parser = subparsers.add_parser("audit-clean-output", help="Audit an existing clean CSV or clean chunk directory.")
    audit_parser.add_argument("input", help="Clean CSV file or directory of clean CSV chunks.")
    audit_parser.add_argument("--email-column", help="Email column name. Auto-detected only when exactly one email-like column exists.")
    audit_parser.add_argument("--rules", default=str(Path(__file__).resolve().parent / "email_rules.json"))
    audit_parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=True)
    audit_parser.add_argument("--max-failures", type=int, default=100)
    audit_parser.add_argument("--report", help="Optional JSON report path.")
    audit_parser.set_defaults(func=audit_clean_output)

    if len(sys.argv) > 1 and sys.argv[1] not in {"scrub", "audit-clean-output", "-h", "--help"}:
        sys.argv.insert(1, "scrub")

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    if getattr(args, "command", None) == "scrub":
        args.max_clean_chunk_bytes = int(args.max_clean_chunk_mb * 1024 * 1024)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
