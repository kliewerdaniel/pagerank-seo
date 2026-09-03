"""PageRank SEO Health Score computation.

Implements the 8-dimension weighted score from ``docs/scoring.md``.
Every dimension is computed from the crawl + graph metrics alone — no
network calls, no machine-learned scoring.

The score is a project-internal engineering health metric, not a Google
ranking predictor. See ``docs/scoring.md`` for the full rationale.

Version 0.2.0 adds two additional dimensions for the search quality
framework: Page Quality and Content Originality.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable
from urllib.parse import urlsplit

from pagerank_seo.models import (
    CrawlResult,
    DimensionScore,
    Page,
    SiteGraph,
)
from pagerank_seo.quality_analyzer import (
    analyze_page_quality,
)


# Dimension weights (sum = 1.0). See docs/scoring.md §1.
# Version 0.2.0: added page_quality and content_originality, rebalanced.
WEIGHTS = {
    "technical_integrity": 0.16,
    "information_architecture": 0.14,
    "graph_health": 0.16,
    "internal_authority_distribution": 0.09,
    "semantic_coherence": 0.11,
    "content_discoverability": 0.09,
    "user_experience": 0.07,
    "reputation_architecture": 0.07,
    "page_quality": 0.06,
    "content_originality": 0.05,
}


# ---------------------------------------------------------------------------
# Dimension 1: Technical Integrity
# ---------------------------------------------------------------------------


_TECHNICAL_CHECKS = [
    "charset_present",
    "charset_utf8",
    "title_present",
    "title_length_ok",
    "meta_description_present",
    "canonical_present",
    "canonical_self_or_consistent",
    "noindex_not_present",
    "lang_present",
    "viewport_present",
    "status_2xx",
    "jsonld_parses",
]


def _technical_per_page(page: Page) -> list[bool]:
    checks: list[bool] = []
    checks.append(bool(page.charset))
    checks.append(bool(page.charset) and page.charset.lower() == "utf-8")
    checks.append(bool(page.title))
    checks.append(bool(page.title) and 10 <= len(page.title) <= 200)
    checks.append(bool(page.meta_description))
    checks.append(bool(page.canonical_url))
    if page.canonical_url is None:
        checks.append(True)  # not "self" — but if it's missing we already flag
    else:
        checks.append(page.canonical_url == page.url or page.canonical_url == page.redirected_from)
    checks.append(not (page.robots_meta and "noindex" in page.robots_meta.lower()))
    checks.append(bool(page.lang))
    checks.append(bool(page.viewport_meta))
    checks.append((not page.status_code) or page.status_code < 400)
    checks.append(len(page.json_ld_blocks) > 0)
    return checks


def _technical_integrity(crawl: CrawlResult) -> tuple[float, str]:
    pages = [p for p in crawl.pages.values() if p.status_code == 0 or p.status_code < 400]
    if not pages:
        return 0.0, "No pages crawled."
    per_page_scores: list[float] = []
    for p in pages:
        results = _technical_per_page(p)
        per_page_scores.append(sum(results) / len(results))
    score = sum(per_page_scores) / len(per_page_scores) * 100
    return score, (
        f"Mean of {_TECHNICAL_CHECKS} checks across {len(pages)} page(s)."
    )


# ---------------------------------------------------------------------------
# Dimension 2: Information Architecture
# ---------------------------------------------------------------------------


_ABOUT_PATHS = {"/about", "/about-us", "/company", "/team", "/who-we-are"}
_PRIVACY_PATHS = {"/privacy", "/privacy-policy", "/terms", "/legal", "/imprint"}


def _information_architecture(crawl: CrawlResult, graph: SiteGraph) -> tuple[float, str]:
    if graph.metrics.node_count == 0:
        return 0.0, "No pages in graph."
    penalty = 0.0
    rationale_parts: list[str] = []

    # Orphan ratio
    orphan_ratio = len(graph.metrics.orphan_pages) / graph.metrics.node_count
    penalty += 0.30 * orphan_ratio
    if orphan_ratio > 0:
        rationale_parts.append(f"orphan ratio {orphan_ratio:.0%}")

    # Deep pages (> depth 4)
    deep = sum(1 for p in crawl.pages.values() if p.depth > 4)
    deep_ratio = deep / max(1, graph.metrics.node_count)
    penalty += 0.20 * deep_ratio
    if deep_ratio > 0:
        rationale_parts.append(f"{deep} deep pages")

    # Sitemap missing
    if not crawl.sitemap_urls:
        penalty += 0.10
        rationale_parts.append("sitemap missing")

    # robots.txt missing
    if not crawl.robots_txt:
        penalty += 0.10
        rationale_parts.append("robots.txt missing")

    # No breadcrumb: we approximate via absence of any page whose path has >1 segment AND whose title doesn't follow the path
    # Simple heuristic: count pages with depth>=1 where headings don't include a BreadcrumbList schema
    has_breadcrumb = any(
        any(b.get("@type") == "BreadcrumbList" for b in p.json_ld_blocks)
        for p in crawl.pages.values()
    )
    if not has_breadcrumb:
        penalty += 0.10
        rationale_parts.append("no BreadcrumbList JSON-LD")

    # Query-parameter-heavy URLs
    query_heavy = sum(
        1 for u in crawl.pages.keys()
        if u.count("?") >= 1 and len(urlsplit(u).query.split("&")) > 2
    )
    if query_heavy:
        penalty += 0.20 * (query_heavy / graph.metrics.node_count)
        rationale_parts.append(f"{query_heavy} URLs with >2 query params")

    score = max(0.0, min(100.0, 100 - 100 * penalty))
    rationale = "Penalty-driven score: " + (", ".join(rationale_parts) if rationale_parts else "no penalties")
    return score, rationale


# ---------------------------------------------------------------------------
# Dimension 3: Graph Health
# ---------------------------------------------------------------------------


def _graph_health(graph: SiteGraph) -> tuple[float, str]:
    if graph.metrics.node_count == 0:
        return 0.0, "Empty graph."
    gini = graph.metrics.gini_pagerank
    wcc = graph.metrics.weakly_connected_components
    nodes = graph.metrics.node_count
    # Connectivity bonus: full credit when 1 WCC, decays as more components appear.
    connectivity_bonus = 20.0 * (1.0 - min(1.0, (wcc - 1) / max(1, nodes)))
    score = max(0.0, min(100.0, 100 * (1 - gini) + connectivity_bonus - 20))
    return score, f"Gini={gini:.2f}, WCC={wcc}/{nodes}"


# ---------------------------------------------------------------------------
# Dimension 4: Internal Authority Distribution
# ---------------------------------------------------------------------------


def _authority_distribution(graph: SiteGraph) -> tuple[float, str]:
    if graph.metrics.top1_share <= 0:
        return 100.0, "No authority measured."
    score = max(0.0, min(100.0, 100 * (1 - graph.metrics.top1_share)))
    return score, f"Top-1 holds {graph.metrics.top1_share:.0%} of total PageRank"


# ---------------------------------------------------------------------------
# Dimension 5: Semantic Coherence
# ---------------------------------------------------------------------------


_STOPWORDS = set(
    "a an and are as at be but by for from has have he her his i if in into is it its"
    " of on or that the their they this to was we were what when which who will with"
    " you your our not no".split()
)


def _tokens(text: str) -> list[str]:
    if not text:
        return []
    return [t for t in re.findall(r"\w+", text.lower()) if t and t not in _STOPWORDS]


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0  # both empty → trivially "aligned"
    union = sa | sb
    return len(sa & sb) / len(union) if union else 1.0


def _semantic_per_page(page: Page) -> float:
    if page.status_code and page.status_code >= 400:
        return 0.0
    components = []
    # 0.30: title/content overlap (using headings as a proxy for content)
    title_tokens = _tokens(page.title or "")
    heading_text = " ".join(t for _, t in page.headings)
    head_tokens = _tokens(heading_text)
    overlap = _jaccard(title_tokens, head_tokens[:200])
    components.append(0.30 * overlap)
    # 0.30: h1 present
    h1_present = 1.0 if any(lvl == 1 and t for lvl, t in page.headings) else 0.0
    components.append(0.30 * h1_present)
    # 0.20: heading hierarchy roughly valid (no skipped levels)
    levels = sorted({lvl for lvl, t in page.headings if t})
    valid_h = 1.0
    if levels:
        # crude: ensure no gap > 1 between min and max
        gaps = [levels[i+1] - levels[i] for i in range(len(levels) - 1)]
        if any(g > 1 for g in gaps):
            valid_h = 0.5
    components.append(0.20 * valid_h)
    # 0.20: not a duplicate title (caller handles site-level; per-page we award 1.0)
    components.append(0.20)
    return sum(components) / 0.8  # normalize to 0-1 (sum is capped at 0.8)


def _semantic_coherence(crawl: CrawlResult) -> tuple[float, str]:
    pages = [p for p in crawl.pages.values() if (p.status_code or 0) < 400]
    if not pages:
        return 0.0, "No indexable pages."
    # Per-page mean
    per_page = sum(_semantic_per_page(p) for p in pages) / len(pages)
    # Title uniqueness penalty
    titles = Counter(p.title for p in pages if p.title)
    dup_ratio = sum(c for t, c in titles.items() if c > 1) / max(1, len(pages))
    score = max(0.0, min(100.0, per_page * 100 * (1 - dup_ratio * 0.5)))
    return score, f"Mean per-page semantic score {per_page:.2f}; duplicate-title ratio {dup_ratio:.0%}"


# ---------------------------------------------------------------------------
# Dimension 6: Content Discoverability
# ---------------------------------------------------------------------------


def _content_discoverability(graph: SiteGraph) -> tuple[float, str]:
    if graph.metrics.node_count == 0:
        return 0.0, "Empty graph."
    reachable = sum(1 for u in graph.metrics.in_degree if graph.metrics.in_degree[u] > 0)
    score = 100.0 * reachable / graph.metrics.node_count
    return score, f"{reachable}/{graph.metrics.node_count} pages have ≥1 inbound internal link"


# ---------------------------------------------------------------------------
# Dimension 7: User Experience
# ---------------------------------------------------------------------------


def _user_experience(crawl: CrawlResult) -> tuple[float, str]:
    pages = [p for p in crawl.pages.values() if (p.status_code or 0) < 400]
    if not pages:
        return 0.0, "No indexable pages."
    per_page = []
    for p in pages:
        landmarks = [p.has_nav, p.has_main, p.has_header, p.has_footer, bool(p.lang)]
        per_page.append(sum(landmarks) / len(landmarks))
    score = sum(per_page) / len(per_page) * 100
    return score, f"Mean landmark presence across {len(pages)} pages"


# ---------------------------------------------------------------------------
# Dimension 8: Reputation Architecture
# ---------------------------------------------------------------------------


def _reputation(crawl: CrawlResult) -> tuple[float, str]:
    score = 0.0
    parts: list[str] = []
    start = crawl.start_url
    # 0.30 HTTPS
    if start.lower().startswith("https://"):
        score += 30
        parts.append("HTTPS")
    # 0.20 about
    if any(u for u in crawl.pages if any(u.rstrip("/").endswith(p) for p in _ABOUT_PATHS)):
        score += 20
        parts.append("about")
    # 0.20 contact
    if any(u for u in crawl.pages if any(u.rstrip("/").endswith(p) for p in ("/contact", "/contact-us", "/support"))):
        score += 20
        parts.append("contact")
    # 0.15 legal
    if any(u for u in crawl.pages if any(u.rstrip("/").endswith(p) for p in _PRIVACY_PATHS)):
        score += 15
        parts.append("legal")
    # 0.15 organization schema
    home = crawl.pages.get(start)
    if home and any(b.get("@type") in ("Organization", "WebSite", "Person") for b in home.json_ld_blocks):
        score += 15
        parts.append("Org/WebSite schema")
    return float(score), "Present: " + (", ".join(parts) if parts else "none")


# ---------------------------------------------------------------------------
# Dimension 9: Page Quality (v0.2.0 — Search Quality Framework)
# ---------------------------------------------------------------------------


def _page_quality(crawl: CrawlResult) -> tuple[float, str]:
    """Compute the mean Page Quality score across all crawled pages.

    Derived from the Search Quality Rater Guidelines §3.0. This is a
    project-internal heuristic combining purpose clarity, content
    classification, E-E-A-T signals, and spam risk.
    """
    if not crawl.pages:
        return 0.0, "No pages crawled."
    total = 0.0
    for page in crawl.pages.values():
        report = analyze_page_quality(page, crawl)
        total += report.quality_score
    score = total / len(crawl.pages)
    return round(score, 2), f"Mean Page Quality score across {len(crawl.pages)} pages"


# ---------------------------------------------------------------------------
# Dimension 10: Content Originality (v0.2.0 — Search Quality Framework)
# ---------------------------------------------------------------------------


def _content_originality(crawl: CrawlResult) -> tuple[float, str]:
    """Compute the mean Content Originality score across all crawled pages.

    Derived from the Search Quality Rater Guidelines §4.6.5 and §4.6.6.
    Distinguishes high-quality content from content with little effort,
    originality, or added value.
    """
    if not crawl.pages:
        return 0.0, "No pages crawled."
    total = 0.0
    for page in crawl.pages.values():
        report = analyze_page_quality(page, crawl)
        if report.originality:
            total += report.originality.originality_score
    score = total / len(crawl.pages)
    return round(score, 2), f"Mean Content Originality score across {len(crawl.pages)} pages"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_scores(crawl: CrawlResult, graph: SiteGraph) -> tuple[list[DimensionScore], float]:
    """Compute all dimension scores and return ``(scores, composite)``."""
    ti, ti_r = _technical_integrity(crawl)
    ia, ia_r = _information_architecture(crawl, graph)
    gh, gh_r = _graph_health(graph)
    ad, ad_r = _authority_distribution(graph)
    sc, sc_r = _semantic_coherence(crawl)
    cd, cd_r = _content_discoverability(graph)
    ux, ux_r = _user_experience(crawl)
    rep, rep_r = _reputation(crawl)
    pq, pq_r = _page_quality(crawl)
    co, co_r = _content_originality(crawl)

    dimensions = [
        DimensionScore("Technical Integrity", round(ti, 2), WEIGHTS["technical_integrity"], ti_r),
        DimensionScore("Information Architecture", round(ia, 2), WEIGHTS["information_architecture"], ia_r),
        DimensionScore("Graph Health", round(gh, 2), WEIGHTS["graph_health"], gh_r),
        DimensionScore("Internal Authority Distribution", round(ad, 2), WEIGHTS["internal_authority_distribution"], ad_r),
        DimensionScore("Semantic Coherence", round(sc, 2), WEIGHTS["semantic_coherence"], sc_r),
        DimensionScore("Content Discoverability", round(cd, 2), WEIGHTS["content_discoverability"], cd_r),
        DimensionScore("User Experience", round(ux, 2), WEIGHTS["user_experience"], ux_r),
        DimensionScore("Reputation Architecture", round(rep, 2), WEIGHTS["reputation_architecture"], rep_r),
        DimensionScore("Page Quality", round(pq, 2), WEIGHTS["page_quality"], pq_r),
        DimensionScore("Content Originality", round(co, 2), WEIGHTS["content_originality"], co_r),
    ]
    composite = sum(d.score * d.weight for d in dimensions)
    return dimensions, round(composite, 2)
