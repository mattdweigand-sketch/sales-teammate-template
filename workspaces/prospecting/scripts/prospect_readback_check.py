#!/usr/bin/env python3
"""Compare a provider readback with the exact fields approved for one write.

Called by signal-outreach and signal-followup.
Policy input requires no keys. This helper compares only the supplied provider fields.
Pass --expected proposal.json and --actual readback.json. Both contain objects;
expected contains only the approved provider field names. Actual is the returned
record, or a literal extraction of those returned fields, never a reconstruction
from the proposal. For Gmail use --gmail with all of to, subject and body; preserve
any returned cc/bcc fields, which must be absent or empty. Top-level provider
metadata may be extra; changed field values/types and list order differences fail.

This verifies field equality, not provider authenticity or human authorization.
Exit 0 match; 1 mismatch (stop, do not repair or repeat the write); 2 bad input.
"""
import argparse
import json


def differences(expected, actual, path=""):
    if type(expected) is not type(actual):
        return [path or "$ (type)"]
    if isinstance(expected, dict):
        found = [f"{path}.{key} (unexpected)" for key in actual if key not in expected]
        for key, value in expected.items():
            child = f"{path}.{key}" if path else key
            if key not in actual:
                found.append(child + " (missing)")
            else:
                found.extend(differences(value, actual[key], child))
        return found
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [path + " (length)"]
        return [difference for index, value in enumerate(expected)
                for difference in differences(value, actual[index], f"{path}[{index}]")]
    return [] if expected == actual else [path or "$"]


def compare(expected, actual, gmail=False):
    if not isinstance(expected, dict) or not expected or not isinstance(actual, dict):
        raise ValueError("expected must be a nonempty object and actual a provider object")
    changed = []
    if gmail:
        if not {"to", "subject", "body"} <= set(expected):
            raise ValueError("Gmail comparison requires approved to, subject, and body")
        for record in (expected, actual):
            for key, value in record.items():
                if key.lower() in ("cc", "bcc") and value not in ([], ""):
                    changed.append(key + " (unexpected recipients)")
    for key, value in expected.items():
        if key not in actual:
            changed.append(key + " (missing)")
        else:
            changed.extend(differences(value, actual[key], key))
    return {"verdict": "mismatch" if changed else "match", "fields": changed}


def load(path):
    def invalid_constant(value):
        raise ValueError(f"invalid JSON number {value}")
    with open(path, encoding="utf-8") as stream:
        return json.load(stream, parse_constant=invalid_constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--actual", required=True)
    parser.add_argument("--gmail", action="store_true", help="require complete draft fields and no CC/BCC recipients")
    args = parser.parse_args()
    try:
        result = compare(load(args.expected), load(args.actual), gmail=args.gmail)
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"verdict": "error", "reason": str(error)}))
        return 2
    print(json.dumps(result))
    return 0 if result["verdict"] == "match" else 1


if __name__ == "__main__":
    raise SystemExit(main())
