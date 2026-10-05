#!/usr/bin/env python3
"""Emit the verdict and Next line for one signal-scan run. signal-scan copies both verbatim.

Usage:
    python3 workspaces/prospecting/workflows/research/scripts/prospect_scan_verdict.py --route <current route> [<gate_output.json> ...]

--route values are scan, active_deal, owned_elsewhere, warm_engaged, outside_named_accounts, and unresolved.
Missing or unknown values require eligibility checks. Policy input requires no keys.

Arguments are prospect_evidence_gate.py outputs in report order. Zero arguments means no source was worth fetching and
yields the nothing-qualified verdict. Position is the report's signal number (the first file is Signal 1).
Each file is {"outcome": "qualified", "bundle": {...}} or a no_usable_signal / unusable output. Files that did
not qualify are counted and otherwise ignored. Reads no policy, so it takes no --core.

Rule, in code so no run can add a bar. Any qualified signal on an owned account is a reason to
consider an Outreach handoff after alias and fit review. Account route is read from current CRM and engagement checks. Unknown eligibility never recommends Outreach. Recommended signal is the newest tier1, else the newest tier2, ties to the lower number.
Only current named-account route scan can recommend Outreach.

A fit rejection is not made here. The report names it per item as "Rejected on fit, <reason>" and
the verdict line stays as emitted.

Exit 0 verdict JSON on stdout. Exit 2 unusable input, {"outcome": "unusable", "reason": ...}. Never a traceback.
"""
import argparse
import json
import sys
from datetime import date

TIER_ORDER = {"tier1": 0, "tier2": 1}


def load(paths):
    outs = []
    for p in paths:
        try:
            with open(p) as fh:
                outs.append(json.load(fh))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            return None, {"outcome": "unusable", "reason": "unreadable_gate_output", "path": p,
                          "detail": f"{type(e).__name__}: {e}"}
    return outs, None


def verdict(outs, route="unresolved"):
    qualified = []
    for n, o in enumerate(outs, start=1):
        if not isinstance(o, dict) or o.get("outcome") != "qualified":
            continue
        b = o.get("bundle")
        if not isinstance(b, dict):
            return {"outcome": "unusable", "reason": "qualified_bundle_not_object", "signal": n}
        tier = b.get("tier")
        if not isinstance(tier, str) or tier not in TIER_ORDER:
            return {"outcome": "unusable", "reason": "qualified_bundle_without_tier", "signal": n}
        try:
            published = date.fromisoformat(b["published_date"])
        except (KeyError, TypeError, ValueError):
            return {"outcome": "unusable", "reason": "qualified_bundle_invalid_date", "signal": n}
        qualified.append({"signal": n, "signal_type": b.get("signal_type"), "tier": tier,
                          "published_date": published.isoformat()})
    checked = len(outs)
    if not qualified:
        return {"checked": checked, "qualified": [], "recommended": None,
                "verdict": "Nothing qualified. Not proof of absence.",
                "next": "Stop"}
    rec = min(qualified, key=lambda q: (TIER_ORDER[q["tier"]], -date.fromisoformat(q["published_date"]).toordinal(), q["signal"]))
    next_step = {
        "scan": f"Confirm account aliases and fit before signal-outreach with Signal {rec['signal']}",
        "active_deal": "Hand evidence to Pipeline. Stop prospecting",
        "owned_elsewhere": "Hand evidence to the Account owner. Stop prospecting",
        "warm_engaged": "Stop cold outreach. Report the existing conversation",
        "outside_named_accounts": "Stop prospecting. Only existing Operator-owned named Accounts are in scope",
    }.get(route, "Resolve Account identity and verify current ownership and open Opportunities before any Outreach handoff")
    return {"checked": checked, "qualified": qualified, "recommended": rec["signal"],
            "verdict": f"Signal {rec['signal']} qualified.", "next": next_step}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verdict and Next line for one signal-scan run.")
    ap.add_argument("outputs", nargs="*", metavar="gate_output.json",
                    help="prospect_evidence_gate.py outputs in report order. None means nothing was worth fetching")
    ap.add_argument("--route", default="unresolved",
                    help="Current CRM/engagement route: scan, active_deal, owned_elsewhere, warm_engaged, "
                         "outside_named_accounts, unresolved. Missing or unknown route requires eligibility checks")
    a = ap.parse_args(argv)
    outs, err = load(a.outputs)
    if err:
        print(json.dumps(err))
        return 2
    v = verdict(outs, a.route)
    print(json.dumps(v, indent=1))
    return 2 if v.get("outcome") == "unusable" else 0


if __name__ == "__main__":
    sys.exit(main())
