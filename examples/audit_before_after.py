"""Compare two audits and print the differences.

Usage:

    python examples/audit_before_after.py BEFORE.json AFTER.json

The two JSON files should be the output of ``pagerank-seo audit --output json``
at two points in time (e.g. before and after a code change).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pagerank_seo import AuditReport


def _load(path: str) -> AuditReport:
    data = json.loads(Path(path).read_text())
    # We rely on the dataclass round-trip; for an example we just read
    # the relevant scalar fields back out of the dict.
    return data


def _diff_summary(before: dict, after: dict) -> str:
    out: list[str] = []
    out.append(f"Composite score: {before['composite_score']:.1f} → {after['composite_score']:.1f}")
    out.append("")
    out.append("Dimension deltas:")
    by_name_before = {s["name"]: s["score"] for s in before["scores"]}
    by_name_after = {s["name"]: s["score"] for s in after["scores"]}
    out.append(f"  {'Dimension':40s} {'Before':>8s} {'After':>8s} {'Δ':>8s}")
    for name in sorted(by_name_before):
        b = by_name_before[name]
        a = by_name_after.get(name, 0.0)
        delta = a - b
        sign = "+" if delta >= 0 else ""
        out.append(f"  {name:40s} {b:>8.1f} {a:>8.1f} {sign}{delta:>7.1f}")
    out.append("")

    # Recommendation code deltas
    codes_before = {r["evidence"][0] if r["evidence"] else r["finding"] for r in before["recommendations"]}
    codes_after = {r["evidence"][0] if r["evidence"] else r["finding"] for r in after["recommendations"]}
    new = codes_after - codes_before
    resolved = codes_before - codes_after
    if new:
        out.append("New (regressions or new findings):")
        for c in sorted(new):
            out.append(f"  + {c}")
    if resolved:
        out.append("Resolved:")
        for c in sorted(resolved):
            out.append(f"  - {c}")
    if not new and not resolved:
        out.append("No recommendation-code changes.")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: audit_before_after.py BEFORE.json AFTER.json", file=sys.stderr)
        return 2
    before = _load(argv[1])
    after = _load(argv[2])
    print(_diff_summary(before, after))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
