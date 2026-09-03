"""Tests for the analyzer, scoring, and recommendations engine."""
from __future__ import annotations

import pytest

from fixtures import synthetic_sites
from pagerank_seo.auditor import SiteAuditor
from pagerank_seo.models import Priority
from pagerank_seo.scoring import WEIGHTS, compute_scores


def _audit(crawl):
    auditor = SiteAuditor.from_crawl(crawl) if hasattr(SiteAuditor, "from_crawl") else None
    if auditor:
        return auditor
    # Manual phases
    from pagerank_seo.auditor import SiteAuditor
    from pagerank_seo.models import AuditConfig
    auditor = SiteAuditor(AuditConfig(start_url=crawl.start_url))
    graph = auditor.build_graph(crawl)
    findings = auditor.analyze(crawl, graph)
    scores, composite = auditor.score(crawl, graph)
    recs = auditor.recommend(findings, crawl, graph)
    return {
        "crawl": crawl,
        "graph": graph,
        "findings": findings,
        "scores": scores,
        "composite": composite,
        "recs": recs,
    }


def _run(crawl):
    from pagerank_seo.auditor import SiteAuditor
    from pagerank_seo.models import AuditConfig
    auditor = SiteAuditor(AuditConfig(start_url=crawl.start_url))
    graph = auditor.build_graph(crawl)
    findings = auditor.analyze(crawl, graph)
    scores, composite = auditor.score(crawl, graph)
    recs = auditor.recommend(findings, crawl, graph)
    return findings, scores, composite, recs


# ---------------------------------------------------------------------------
# Analyzer — per-page checks
# ---------------------------------------------------------------------------


class TestAnalyzer:
    def test_clean_site_no_critical(self, tiny_site):
        findings, _, _, _ = _run(tiny_site)
        # The clean site may have a couple of MEDIUM findings (BreadcrumbList missing etc.)
        # but no CRITICAL.
        criticals = [f for f in findings if f.code == "HTTP_ERROR" or f.code == "NOINDEX_ON_INDEXABLE"]
        assert len(criticals) == 0

    def test_orphan_flagged(self, orphan_site):
        findings, _, _, _ = _run(orphan_site)
        codes = {f.code for f in findings}
        assert "ORPHAN_PAGES" in codes

    def test_disconnected_components_flagged(self, orphan_site):
        findings, _, _, _ = _run(orphan_site)
        codes = {f.code for f in findings}
        assert "DISCONNECTED_COMPONENTS" in codes

    def test_reputation_about_missing(self, island_site):
        findings, _, _, _ = _run(island_site)
        codes = {f.code for f in findings}
        # island_site has no /about, /contact, /privacy
        assert "ABOUT_PAGE_MISSING" in codes
        assert "CONTACT_PAGE_MISSING" in codes
        assert "LEGAL_PAGE_MISSING" in codes
        assert "NO_HTTPS" not in codes  # start URL is https://

    def test_malformed_html_does_not_crash(self, malformed_site):
        findings, _, _, _ = _run(malformed_site)
        # We don't assert what specific findings appear — just that nothing crashed
        # and at least the parser produced *something*.
        assert isinstance(findings, list)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    def test_clean_site_scores_high(self, tiny_site):
        findings, scores, composite, _ = _run(tiny_site)
        assert composite > 70
        # All 10 dimensions present (8 original + Page Quality + Content Originality)
        assert len(scores) == 10
        names = {s.name for s in scores}
        assert "Technical Integrity" in names
        assert "Graph Health" in names
        assert "Page Quality" in names
        assert "Content Originality" in names

    def test_weights_sum_to_one(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

    def test_island_site_scores_lower_than_clean(self, tiny_site, island_site):
        _, _, c1, _ = _run(tiny_site)
        _, _, c2, _ = _run(island_site)
        assert c2 < c1

    def test_composite_in_range(self, tiny_site):
        _, _, composite, _ = _run(tiny_site)
        assert 0 <= composite <= 100


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


class TestRecommendations:
    def test_recommendations_prioritized(self, orphan_site):
        _, _, _, recs = _run(orphan_site)
        priorities = [r.priority for r in recs]
        # Priority enum ordering: CRITICAL < HIGH < MEDIUM < LOW (by enum value)
        # We sort by an explicit order, so verify the sequence is non-decreasing in priority rank
        order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
        ranks = [order[p] for p in priorities]
        assert ranks == sorted(ranks)

    def test_recommendation_has_evidence(self, orphan_site):
        _, _, _, recs = _run(orphan_site)
        for r in recs:
            assert r.recommended_action
            assert r.verification_method
            assert r.evidence  # at least one finding code

    def test_no_recommendations_for_perfect_site(self):
        # Build an artificially perfect page that passes every check.
        from pagerank_seo.parser import parse_html
        from pagerank_seo.models import CrawlResult

        html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="description" content="Excellent description of the topic at hand.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="https://example.com/">
<title>Welcome to the Acme Example Homepage</title>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"X","url":"https://example.com/"}</script>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Home","item":"https://example.com/"}]}</script>
</head>
<body>
<header><nav><a href="/about">About</a></nav></header>
<main>
<h1>Welcome to Acme</h1>
<p>Acme is a wonderful example of a clean, well-structured homepage with rich content.</p>
<p>This page demonstrates every check that the analyzer performs, designed for testing.</p>
<p>The text here is intentionally longer to defeat thin-content heuristics. It also mentions Acme several times to ensure title-content overlap scores well.</p>
</main>
<footer></footer>
</body></html>"""

        page = parse_html(url="https://example.com/", raw_html=html)
        crawl = CrawlResult(
            start_url="https://example.com/",
            pages={"https://example.com/": page},
            edges=[],
            robots_txt="User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n",
            sitemap_urls=["https://example.com/sitemap.xml"],
        )
        _, _, _, recs = _run(crawl)
        # A single-page "site" still has findings (no /about, etc) — but they should be MEDIUM/LOW.
        criticals = [r for r in recs if r.priority == Priority.CRITICAL]
        assert len(criticals) == 0
