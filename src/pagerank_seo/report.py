"""Report renderers for JSON, Markdown, and HTML output.

Each renderer is a pure function of the ``AuditReport``; no I/O.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from pagerank_seo.models import AuditReport


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def to_json(report: AuditReport, *, indent: int = 2) -> str:
    """Serialize the full report to JSON."""
    return json.dumps(report.to_dict(), indent=indent, sort_keys=False, default=str)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def to_markdown(report: AuditReport) -> str:
    """Render a human-readable Markdown report."""
    lines: list[str] = []
    lines.append(f"# PageRank SEO Audit Report")
    lines.append("")
    lines.append(f"**Site:** `{report.config.start_url}`  ")
    lines.append(f"**Generated:** {report.generated_at_iso}  ")
    lines.append(f"**Version:** pagerank-seo 0.2.0  ")
    lines.append(f"**Crawl budget:** max {report.config.max_pages} pages, depth {report.config.max_depth}  ")
    lines.append(f"**Pages crawled:** {report.crawl.pages_fetched} (failed: {report.crawl.pages_failed})  ")
    lines.append(f"**Crawl elapsed:** {report.crawl.crawl_elapsed_seconds:.2f}s")
    lines.append("")
    lines.append(f"## Composite Score: **{report.composite_score:.1f} / 100**")
    lines.append("")
    lines.append("| Dimension | Score | Weight | Rationale |")
    lines.append("|---|---:|---:|---|")
    for d in report.scores:
        lines.append(f"| {d.name} | {d.score:.1f} | {d.weight:.2f} | {d.rationale} |")
    lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    if not report.recommendations:
        lines.append("No issues detected. 🎉")
        lines.append("")
    else:
        for r in report.recommendations:
            lines.append(f"### [{r.priority.value}] {r.finding}")
            lines.append("")
            lines.append(f"- **Action:** {r.recommended_action}")
            lines.append(f"- **Impact:** {r.impact}  **Confidence:** {r.confidence}  **Difficulty:** {r.implementation_difficulty}")
            lines.append(f"- **Evidence codes:** {', '.join(r.evidence)}")
            if r.affected_urls:
                # Show up to 5 URLs in the report, mention total
                shown = r.affected_urls[:5]
                lines.append(f"- **Affected URLs ({len(r.affected_urls)}):**")
                for u in shown:
                    lines.append(f"  - `{u}`")
                if len(r.affected_urls) > 5:
                    lines.append(f"  - …and {len(r.affected_urls) - 5} more")
            lines.append(f"- **Verify:** {r.verification_method}")
            lines.append("")

    # Graph summary
    m = report.graph.metrics
    lines.append("## Graph Summary")
    lines.append("")
    lines.append(f"- Nodes (pages): **{m.node_count}**")
    lines.append(f"- Edges (internal links): **{m.edge_count}**")
    lines.append(f"- Weakly-connected components: **{m.weakly_connected_components}**")
    lines.append(f"- Strongly-connected components: **{m.strongly_connected_components}**")
    lines.append(f"- Has directed cycle: **{m.has_cycle}**")
    lines.append(f"- Orphan pages (in-degree 0): **{len(m.orphan_pages)}**")
    lines.append(f"- Gini(PageRank): **{m.gini_pagerank:.3f}**")
    lines.append(f"- Top-1 PageRank share: **{m.top1_share:.1%}**")
    lines.append("")
    if m.orphan_pages:
        lines.append("### Orphan pages")
        for u in m.orphan_pages[:20]:
            lines.append(f"- `{u}`")
        if len(m.orphan_pages) > 20:
            lines.append(f"- …and {len(m.orphan_pages) - 20} more")
        lines.append("")

    # Top PageRank pages
    lines.append("### Top PageRank pages")
    lines.append("")
    top_pr = sorted(m.pagerank.items(), key=lambda kv: kv[1], reverse=True)[:10]
    lines.append("| URL | PageRank | Share |")
    lines.append("|---|---:|---:|")
    total = sum(m.pagerank.values()) or 1.0
    for url, pr in top_pr:
        lines.append(f"| `{url}` | {pr:.4f} | {pr/total:.1%} |")
    lines.append("")

    # Findings ledger
    lines.append("## Findings Ledger")
    lines.append("")
    lines.append(f"Total findings: **{len(report.findings)}**")
    lines.append("")
    by_layer: dict[str, list] = {}
    for f in report.findings:
        by_layer.setdefault(f.layer, []).append(f)
    for layer in sorted(by_layer):
        lines.append(f"### {layer.upper()} ({len(by_layer[layer])})")
        lines.append("")
        for f in by_layer[layer][:50]:
            lines.append(f"- **{f.code}** — {f.message}")
            if f.evidence_urls:
                lines.append(f"  - Evidence: `{f.evidence_urls[0]}`" + (f" (+{len(f.evidence_urls)-1})" if len(f.evidence_urls) > 1 else ""))
        if len(by_layer[layer]) > 50:
            lines.append(f"- …and {len(by_layer[layer]) - 50} more")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("> PageRank values are an internal analytical metric, not Google's ranking signal. ")
    lines.append("> Recommendations are grounded in public documentation (Google Search Central, W3C, ")
    lines.append("> schema.org, the original PageRank paper) and engineering best practice. They ")
    lines.append("> are intended to improve technical and structural quality — not as ranking hacks.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PageRank SEO Audit — {start_url}</title>
<style>
:root {{
  --fg: #1f2937;
  --fg-muted: #6b7280;
  --bg: #ffffff;
  --bg-alt: #f9fafb;
  --border: #e5e7eb;
  --accent: #2563eb;
  --critical: #dc2626;
  --high: #ea580c;
  --medium: #ca8a04;
  --low: #16a34a;
}}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; color: var(--fg); background: var(--bg); }}
h1, h2, h3 {{ color: var(--fg); }}
h1 {{ border-bottom: 2px solid var(--border); padding-bottom: .5rem; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
th, td {{ border: 1px solid var(--border); padding: .5rem .75rem; text-align: left; }}
th {{ background: var(--bg-alt); }}
.score {{ font-size: 2.5rem; font-weight: 700; color: var(--accent); }}
.priority-CRITICAL {{ color: var(--critical); font-weight: 600; }}
.priority-HIGH {{ color: var(--high); font-weight: 600; }}
.priority-MEDIUM {{ color: var(--medium); font-weight: 600; }}
.priority-LOW {{ color: var(--low); font-weight: 600; }}
.bar {{ background: var(--bg-alt); border-radius: 4px; overflow: hidden; height: 1.2rem; }}
.bar > span {{ display: block; height: 100%; background: var(--accent); }}
.url {{ font-family: ui-monospace, Menlo, monospace; font-size: .85em; color: var(--fg-muted); word-break: break-all; }}
.muted {{ color: var(--fg-muted); font-size: .9em; }}
section {{ margin-bottom: 2rem; }}
footer {{ border-top: 1px solid var(--border); padding-top: 1rem; color: var(--fg-muted); font-size: .85em; }}
</style>
</head>
<body>
<h1>PageRank SEO Audit</h1>
<p class="muted"><span class="url">{start_url}</span><br>Generated {generated_at_iso}</p>
<p>Composite score</p>
<div class="score">{composite:.1f}<span style="font-size:1rem;color:var(--fg-muted);"> / 100</span></div>
<div class="bar" aria-label="score"><span style="width: {composite:.1f}%;"></span></div>

<h2>Dimensions</h2>
<table>
<thead><tr><th>Dimension</th><th>Score</th><th>Weight</th><th>Rationale</th></tr></thead>
<tbody>
{dimensions_rows}
</tbody>
</table>

<h2>Recommendations</h2>
{recommendations_html}

<h2>Graph summary</h2>
<ul>
<li>Nodes (pages): <strong>{nodes}</strong></li>
<li>Edges (internal links): <strong>{edges}</strong></li>
<li>Weakly-connected components: <strong>{wcc}</strong></li>
<li>Orphan pages (in-degree 0): <strong>{orphans}</strong></li>
<li>Gini(PageRank): <strong>{gini:.3f}</strong></li>
<li>Top-1 PageRank share: <strong>{top1:.1%}</strong></li>
</ul>

<h3>Top PageRank pages</h3>
<table>
<thead><tr><th>URL</th><th>PageRank</th><th>Share</th></tr></thead>
<tbody>
{top_pr_rows}
</tbody>
</table>

<footer>
PageRank values are an internal analytical metric, not Google's ranking signal. Recommendations are grounded in public documentation (Google Search Central, W3C, schema.org, the original PageRank paper) and engineering best practice.
</footer>
</body>
</html>
"""


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def to_html(report: AuditReport) -> str:
    """Render a self-contained HTML report."""
    rows = []
    for d in report.scores:
        rows.append(
            f"<tr><td>{_esc(d.name)}</td><td>{d.score:.1f}</td>"
            f"<td>{d.weight:.2f}</td><td>{_esc(d.rationale)}</td></tr>"
        )
    dimensions_rows = "\n".join(rows)

    rec_blocks: list[str] = []
    for r in report.recommendations:
        urls_html = "".join(f"<li><span class='url'>{_esc(u)}</span></li>" for u in r.affected_urls[:5])
        rec_blocks.append(
            f"<div style='border:1px solid var(--border); border-radius:6px; padding:.75rem 1rem; margin-bottom:1rem;'>"
            f"<div class='priority-{r.priority.value}'>[{r.priority.value}] {_esc(r.finding)}</div>"
            f"<p><strong>Action:</strong> {_esc(r.recommended_action)}</p>"
            f"<p class='muted'>Impact: {r.impact} &middot; Confidence: {r.confidence} &middot; Difficulty: {r.implementation_difficulty}</p>"
            f"<p><strong>Verify:</strong> {_esc(r.verification_method)}</p>"
            + (f"<details><summary>Affected URLs ({len(r.affected_urls)})</summary><ul>{urls_html}</ul></details>" if r.affected_urls else "")
            + "</div>"
        )
    recommendations_html = "\n".join(rec_blocks) if rec_blocks else "<p>No issues detected. 🎉</p>"

    top_rows = []
    total = sum(report.graph.metrics.pagerank.values()) or 1.0
    for url, pr in sorted(report.graph.metrics.pagerank.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        top_rows.append(
            f"<tr><td><span class='url'>{_esc(url)}</span></td><td>{pr:.4f}</td><td>{pr/total:.1%}</td></tr>"
        )
    top_pr_rows = "\n".join(top_rows)

    return _HTML_TEMPLATE.format(
        start_url=_esc(report.config.start_url),
        generated_at_iso=_esc(report.generated_at_iso),
        composite=report.composite_score,
        dimensions_rows=dimensions_rows,
        recommendations_html=recommendations_html,
        nodes=report.graph.metrics.node_count,
        edges=report.graph.metrics.edge_count,
        wcc=report.graph.metrics.weakly_connected_components,
        orphans=len(report.graph.metrics.orphan_pages),
        gini=report.graph.metrics.gini_pagerank,
        top1=report.graph.metrics.top1_share,
        top_pr_rows=top_pr_rows,
    )
