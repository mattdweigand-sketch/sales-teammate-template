#!/usr/bin/env python3
"""Build sequencer upload batches from scrubber clean chunks.

Keeps exactly First Name, Last Name, Email. Drops rows missing any of them,
in-run duplicates, and emails listed in --exclude (e.g. Salesforce matches).
Holds rows whose email domain does not match the company website column in
domain_mismatch.csv, unless the email is listed in --allow.
Writes '<CODE> 1.csv', '<CODE> 2.csv', ... and batches_report.json.
"""
import argparse
import csv
import json
import re
from pathlib import Path

COLS = ["First Name", "Last Name", "Email"]
SITE_HINTS = ("website", "domain")


def site_domain(value):
    v = (value or "").strip().lower()
    v = re.sub(r"^[a-z]+://", "", v).split("/")[0].split("?")[0]
    return v[4:] if v.startswith("www.") else v


def domain_matches(email_domain, site):
    return email_domain == site or email_domain.endswith("." + site) or site.endswith("." + email_domain)


def read_emails(path):
    if not path:
        return set()
    return {l.strip().lower() for l in open(path, encoding="utf-8") if l.strip()}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("clean_dir")
    p.add_argument("--code", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--batch-size", type=int, default=5000)
    p.add_argument("--exclude", help="Text file, one email per line, to remove.")
    p.add_argument("--allow", help="Text file, one email per line, exempt from the domain check.")
    a = p.parse_args()

    exclude = read_emails(a.exclude)
    allow = read_emails(a.allow)

    rows, seen, mismatches = [], set(), []
    counts = {"input": 0, "missing_name_or_email": 0, "duplicate": 0, "excluded": 0, "domain_mismatch": 0}
    for f in sorted(Path(a.clean_dir).glob("*.csv")):
        with open(f, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            site_col = next((h for h in reader.fieldnames or [] if any(k in h.lower() for k in SITE_HINTS)), None)
            for r in reader:
                counts["input"] += 1
                vals = [(r.get(c) or "").strip() for c in COLS]
                if not all(vals):
                    counts["missing_name_or_email"] += 1
                    continue
                key = vals[2].lower()
                if key in seen:
                    counts["duplicate"] += 1
                    continue
                if key in exclude:
                    counts["excluded"] += 1
                    continue
                site = site_domain(r.get(site_col)) if site_col else ""
                if site and key not in allow and not domain_matches(key.split("@")[-1], site):
                    counts["domain_mismatch"] += 1
                    mismatches.append(vals + [r.get("Company Name", ""), site])
                    continue
                seen.add(key)
                rows.append(vals)

    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for i in range(0, len(rows), a.batch_size):
        path = out / f"{a.code} {i // a.batch_size + 1}.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(COLS)
            w.writerows(rows[i : i + a.batch_size])
        files.append({"path": str(path), "rows": len(rows[i : i + a.batch_size])})

    if mismatches:
        with open(out / "domain_mismatch.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(COLS + ["Company Name", "Website"])
            w.writerows(mismatches)

    report = {"counts": counts, "final_rows": len(rows), "batches": files,
              "domain_mismatch_file": str(out / "domain_mismatch.csv") if mismatches else None}
    (out / "batches_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
