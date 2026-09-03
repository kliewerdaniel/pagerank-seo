#!/usr/bin/env python3
"""
Render danielkliewer.com pages with Playwright and parse them with the
pagerank-seo SDK. The site is a Next.js app with client-side rendering,
so static HTML parsing sees an empty shell.
"""
import sys
from pagerank_seo.crawler import Fetcher, parse_sitemap_lenient
from pagerank_seo.models import AuditConfig, CrawlResult, Page, Link
from pagerank_seo.parser import parse_html
from pagerank_seo.graph import to_site_graph
from pagerank_seo.analyzer import analyze
from pagerank_seo.scoring import compute_scores
from pagerank_seo.recommendations import build_recommendations
from pagerank_seo.quality_analyzer import analyze_search_quality
from pagerank_seo.report import to_markdown, to_json, to_html
from pagerank_seo.errors import FetchError
from playwright.sync_api import sync_playwright
from datetime import datetime, timezone


def render_page(url: str, page=None) -> str:
    """Render a page with Playwright and return the full HTML."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="pagerank-seo/0.2 (+https://github.com/kliewerdaniel/pagerank-seo)",
        viewport={"width": 1280, "height": 800},
    )
    pg = context.new_page()
    pg.goto(url, wait_until="networkidle", timeout=30000)
    # Wait a bit more for any lazy content
    pg.wait_for_timeout(2000)
    html = pg.content()
    browser.close()
    pw.stop()
    return html


def main():
    config = AuditConfig(
        start_url="https://danielkliewer.com",
        max_pages=40,
        max_depth=3,
    )

    fetcher = Fetcher(
        user_agent=config.user_agent,
        timeout=config.request_timeout_seconds,
        max_document_bytes=config.max_document_bytes,
        max_redirects=config.max_redirects,
    )

    # Fetch sitemap to discover URLs
    print("Fetching sitemap...", file=sys.stderr)
    resp = fetcher.fetch("https://danielkliewer.com/sitemap.xml")
    sitemap_urls = parse_sitemap_lenient(resp.body.decode("utf-8", errors="replace"))
    print(f"Found {len(sitemap_urls)} URLs in sitemap", file=sys.stderr)

    # Prioritize important pages first, then fill with the rest
    priority_urls = [
        "https://www.danielkliewer.com",
        "https://www.danielkliewer.com/about",
        "https://www.danielkliewer.com/book",
        "https://www.danielkliewer.com/contact",
        "https://www.danielkliewer.com/fleet",
        "https://www.danielkliewer.com/press",
        "https://www.danielkliewer.com/privacy",
        "https://www.danielkliewer.com/terms",
        "https://www.danielkliewer.com/research",
    ]
    # Add remaining sitemap URLs
    remaining = [u for u in sitemap_urls if u not in priority_urls]
    ordered_urls = priority_urls + remaining

    # Render and parse each page
    pages: dict[str, Page] = {}
    edges: list[Link] = []

    for i, url in enumerate(ordered_urls[:config.max_pages]):
        print(f"[{i+1}/{min(len(ordered_urls), config.max_pages)}] Rendering {url}...", file=sys.stderr)
        try:
            html = render_page(url)
            page = parse_html(
                url=url,
                raw_html=html,
                status_code=200,
                content_type="text/html",
                depth=0,
            )
            pages[url] = page
            edges.extend(page.outgoing_links)
            print(f"  -> {page.text_word_count} words, {len(page.headings)} headings, {len(page.outgoing_links)} links", file=sys.stderr)
        except Exception as exc:
            print(f"  -> FAILED: {exc}", file=sys.stderr)

    print(f"\nCrawled {len(pages)} pages, {len(edges)} edges", file=sys.stderr)

    # Build crawl result
    crawl = CrawlResult(
        start_url=config.start_url,
        pages=pages,
        edges=edges,
        robots_txt="",
        sitemap_urls=sitemap_urls,
        pages_fetched=len(pages),
        pages_failed=0,
        crawl_elapsed_seconds=0.0,
    )

    # Build graph
    graph = to_site_graph(crawl)
    print(f"Graph: {graph.metrics.node_count} nodes, {graph.metrics.edge_count} edges", file=sys.stderr)

    # Analyze
    findings = analyze(crawl, graph)
    print(f"Findings: {len(findings)}", file=sys.stderr)

    # Score
    scores, composite = compute_scores(crawl, graph)
    print(f"Composite score: {composite}", file=sys.stderr)

    # Recommend
    recommendations = build_recommendations(findings, crawl, graph)
    print(f"Recommendations: {len(recommendations)}", file=sys.stderr)

    # Quality analysis
    quality = analyze_search_quality(crawl)
    print(f"Quality score: {quality.overall_quality_score}", file=sys.stderr)

    # Build report
    from pagerank_seo.models import AuditReport
    report = AuditReport(
        config=config,
        crawl=crawl,
        graph=graph,
        findings=findings,
        recommendations=recommendations,
        scores=scores,
        composite_score=composite,
        generated_at_iso=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    # Output
    import os
    os.makedirs("reports", exist_ok=True)
    with open("reports/audit-danielkliewer.com-rendered.md", "w") as f:
        f.write(to_markdown(report))
    with open("reports/audit-danielkliewer.com-rendered.json", "w") as f:
        f.write(to_json(report))
    with open("reports/audit-danielkliewer.com-rendered.html", "w") as f:
        f.write(to_html(report))

    print("\nReports written to reports/audit-danielkliewer.com-rendered.*", file=sys.stderr)


if __name__ == "__main__":
    main()
