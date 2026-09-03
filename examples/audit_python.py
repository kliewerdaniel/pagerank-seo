"""End-to-end audit using the pagerank-seo SDK.

Run from the repository root:

    env -u PYTHONPATH -u VIRTUAL_ENV .venv/bin/python examples/audit_python.py

Or against any site:

    python examples/audit_python.py https://your-site.example/
"""
from __future__ import annotations

import sys
from pathlib import Path

from pagerank_seo import AuditConfig
from pagerank_seo.auditor import SiteAuditor
from pagerank_seo.report import to_html, to_json, to_markdown


def main(argv: list[str]) -> int:
    url = argv[1] if len(argv) > 1 else "https://example.com"
    out_dir = Path(argv[2]) if len(argv) > 2 else Path("examples/output")
    out_dir.mkdir(parents=True, exist_ok=True)

    auditor = SiteAuditor(AuditConfig(
        start_url=url,
        max_pages=20,
        max_depth=3,
        requests_per_second=5.0,
    ))

    report = auditor.audit()

    # Machine-readable
    (out_dir / "audit.json").write_text(to_json(report))
    # Human-readable
    (out_dir / "audit.markdown").write_text(to_markdown(report))
    # Visual
    (out_dir / "audit.html").write_text(to_html(report))

    print(f"Composite score: {report.composite_score:.1f} / 100")
    print(f"Pages crawled:   {report.crawl.pages_fetched}")
    print(f"Findings:        {len(report.findings)}")
    print(f"Recommendations: {len(report.recommendations)}")
    print()
    print("Top recommendations:")
    for r in report.recommendations[:5]:
        print(f"  [{r.priority.value}] {r.finding}")
    print()
    print(f"Wrote: {out_dir}/audit.{{json,markdown,html}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
