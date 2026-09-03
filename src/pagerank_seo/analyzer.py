"""Heuristic analyzer: produces findings from a crawl + graph.

The analyzer is purely a function of observable properties of the site.
It never reaches outside the crawl result and never makes network calls.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable
from urllib.parse import urlsplit

from pagerank_seo.models import (
    CrawlResult,
    Finding,
    Page,
    SiteGraph,
)
from pagerank_seo.quality import PagePurposeType


_STOPWORDS = set(
    """a about above after again against all am an and any are as at be because been before
    being below between both but by can did do does doing down during each few for from
    further had has have having he her here hers herself him himself his how i if in into
    is it its itself just like me more most my myself no nor not now of off on once only
    or other our ours ourselves out over own same she should so some such than that the
    their theirs them themselves then there these they this those through to too under
    until up very was we were what when where which while who whom why with would you
    your yours yourself yourselves""".split()
)


def _tokens(text: str) -> list[str]:
    if not text:
        return []
    return [t for t in re.findall(r"\w+", text.lower()) if t and t not in _STOPWORDS]


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


# ---------------------------------------------------------------------------
# Per-page checks
# ---------------------------------------------------------------------------


def _check_technical(page: Page) -> list[Finding]:
    out: list[Finding] = []
    if page.status_code and page.status_code >= 400:
        out.append(Finding(
            layer="technical",
            code="HTTP_ERROR",
            message=f"Page returned HTTP {page.status_code}.",
            evidence_urls=[page.url],
            details={"status": page.status_code},
        ))
    if page.error:
        out.append(Finding(
            layer="technical",
            code="PARSE_FAILED",
            message=f"HTML could not be parsed: {page.error}",
            evidence_urls=[page.url],
        ))
    if not page.charset:
        out.append(Finding(
            layer="technical",
            code="CHARSET_MISSING",
            message="No <meta charset> declaration found.",
            evidence_urls=[page.url],
        ))
    elif page.charset and page.charset.lower() != "utf-8":
        out.append(Finding(
            layer="technical",
            code="CHARSET_NOT_UTF8",
            message=f"Charset is '{page.charset}' (utf-8 recommended).",
            evidence_urls=[page.url],
        ))
    if not page.title:
        out.append(Finding(
            layer="technical",
            code="TITLE_MISSING",
            message="<title> element missing or empty.",
            evidence_urls=[page.url],
        ))
    elif len(page.title) < 10 or len(page.title) > 200:
        out.append(Finding(
            layer="technical",
            code="TITLE_LENGTH",
            message=f"<title> length is {len(page.title)} chars (10–200 recommended).",
            evidence_urls=[page.url],
            details={"length": len(page.title)},
        ))
    if not page.meta_description:
        out.append(Finding(
            layer="technical",
            code="META_DESCRIPTION_MISSING",
            message="<meta name='description'> missing.",
            evidence_urls=[page.url],
        ))
    if not page.canonical_url:
        out.append(Finding(
            layer="technical",
            code="CANONICAL_MISSING",
            message='<link rel="canonical"> missing.',
            evidence_urls=[page.url],
        ))
    elif page.canonical_url and page.canonical_url != page.url:
        # canonical points elsewhere: only flag if it points to a different origin
        # (we can't always tell — but if it's a known different host, that's odd)
        # Skip the warning when the canonical is the redirected destination.
        if urlsplit(page.canonical_url).netloc != urlsplit(page.url).netloc:
            out.append(Finding(
                layer="technical",
                code="CANONICAL_CROSS_ORIGIN",
                message=f"Canonical URL points to a different host ({page.canonical_url}).",
                evidence_urls=[page.url],
                details={"canonical": page.canonical_url},
            ))
    if page.robots_meta and "noindex" in page.robots_meta.lower():
        out.append(Finding(
            layer="technical",
            code="NOINDEX_ON_INDEXABLE",
            message="Page contains 'noindex' directive in robots meta.",
            evidence_urls=[page.url],
            details={"robots_meta": page.robots_meta},
        ))
    if not page.lang:
        out.append(Finding(
            layer="technical",
            code="LANG_MISSING",
            message="<html lang> attribute missing.",
            evidence_urls=[page.url],
        ))
    if not page.viewport_meta:
        out.append(Finding(
            layer="technical",
            code="VIEWPORT_MISSING",
            message="<meta name='viewport'> missing (mobile rendering may degrade).",
            evidence_urls=[page.url],
        ))
    if not page.json_ld_blocks:
        out.append(Finding(
            layer="technical",
            code="NO_STRUCTURED_DATA",
            message="No JSON-LD structured data blocks found.",
            evidence_urls=[page.url],
        ))
    return out


def _check_semantic(page: Page) -> list[Finding]:
    out: list[Finding] = []
    h1s = [t for level, t in page.headings if level == 1 and t]
    if not h1s:
        out.append(Finding(
            layer="semantic",
            code="H1_MISSING",
            message="No non-empty <h1> found.",
            evidence_urls=[page.url],
        ))
    elif len(h1s) > 1:
        out.append(Finding(
            layer="semantic",
            code="H1_MULTIPLE",
            message=f"{len(h1s)} non-empty <h1> elements found (one is conventional).",
            evidence_urls=[page.url],
            details={"count": len(h1s)},
        ))
    if not page.title and not h1s:
        pass  # already flagged in technical
    # Title / content overlap
    title_tokens = _tokens(page.title or "")
    body_tokens = _tokens(" ".join(t for _lvl, t in page.headings))[:500]
    if title_tokens and body_tokens:
        overlap = _jaccard(title_tokens, body_tokens)
        if overlap < 0.1:
            out.append(Finding(
                layer="semantic",
                code="TITLE_CONTENT_OVERLAP_LOW",
                message=f"Title and heading content have very low overlap (Jaccard={overlap:.2f}).",
                evidence_urls=[page.url],
                details={"jaccard": round(overlap, 3)},
            ))
    # Thin content
    if page.text_word_count and page.text_word_count < 80:
        out.append(Finding(
            layer="semantic",
            code="THIN_CONTENT",
            message=f"Page has only {page.text_word_count} visible words.",
            evidence_urls=[page.url],
            details={"word_count": page.text_word_count},
        ))
    return out


def _check_ux(page: Page) -> list[Finding]:
    out: list[Finding] = []
    if not page.has_nav:
        out.append(Finding(
            layer="ux",
            code="NAV_MISSING",
            message="No <nav> landmark found.",
            evidence_urls=[page.url],
        ))
    if not page.has_main:
        out.append(Finding(
            layer="ux",
            code="MAIN_MISSING",
            message="No <main> landmark found.",
            evidence_urls=[page.url],
        ))
    if not page.has_header:
        out.append(Finding(
            layer="ux",
            code="HEADER_MISSING",
            message="No <header> landmark found.",
            evidence_urls=[page.url],
        ))
    if not page.has_footer:
        out.append(Finding(
            layer="ux",
            code="FOOTER_MISSING",
            message="No <footer> landmark found.",
            evidence_urls=[page.url],
        ))
    if page.images_total > 0 and page.images_without_alt > 0:
        ratio = page.images_without_alt / page.images_total
        if ratio > 0.2:
            out.append(Finding(
                layer="ux",
                code="ALT_TEXT_GAP",
                message=f"{page.images_without_alt}/{page.images_total} <img> tags lack alt text.",
                evidence_urls=[page.url],
                details={"without_alt": page.images_without_alt, "total": page.images_total},
            ))
    return out


# ---------------------------------------------------------------------------
# Site-level checks
# ---------------------------------------------------------------------------


def _check_ia(crawl: CrawlResult, graph: SiteGraph) -> list[Finding]:
    out: list[Finding] = []
    if not crawl.robots_txt:
        out.append(Finding(
            layer="ia",
            code="ROBOTS_TXT_MISSING",
            message="No robots.txt was fetched from the site root.",
            evidence_urls=[crawl.start_url],
        ))
    if not crawl.sitemap_urls:
        out.append(Finding(
            layer="ia",
            code="SITEMAP_MISSING",
            message="No sitemap URL was declared in robots.txt.",
            evidence_urls=[crawl.start_url],
        ))
    # Orphan pages
    if graph.metrics.orphan_pages:
        out.append(Finding(
            layer="ia",
            code="ORPHAN_PAGES",
            message=f"{len(graph.metrics.orphan_pages)} page(s) have no inbound internal links.",
            evidence_urls=graph.metrics.orphan_pages[:10],
            details={"count": len(graph.metrics.orphan_pages)},
        ))
    # Depth distribution
    depths = [p.depth for p in crawl.pages.values() if p.status_code and p.status_code < 400]
    if depths:
        avg_depth = sum(depths) / len(depths)
        max_depth = max(depths)
        deep = sum(1 for d in depths if d > 4)
        if deep:
            out.append(Finding(
                layer="ia",
                code="DEEP_PAGES",
                message=f"{deep} page(s) are deeper than 4 clicks from the seed.",
                evidence_urls=[u for u, p in crawl.pages.items() if p.depth > 4][:10],
                details={"count": deep, "max_depth": max_depth, "avg_depth": round(avg_depth, 2)},
            ))
    # WCC > 1
    if graph.metrics.node_count > 1 and graph.metrics.weakly_connected_components > 1:
        out.append(Finding(
            layer="ia",
            code="DISCONNECTED_COMPONENTS",
            message=f"Graph has {graph.metrics.weakly_connected_components} weakly-connected components.",
            evidence_urls=[],
            details={"wcc": graph.metrics.weakly_connected_components},
        ))
    return out


def _check_graph(graph: SiteGraph) -> list[Finding]:
    out: list[Finding] = []
    if graph.metrics.gini_pagerank > 0.6:
        out.append(Finding(
            layer="graph",
            code="AUTHORITY_CONCENTRATION",
            message=f"PageRank distribution is highly concentrated (Gini={graph.metrics.gini_pagerank:.2f}).",
            evidence_urls=[],
            details={"gini": round(graph.metrics.gini_pagerank, 3)},
        ))
    if graph.metrics.top1_share > 0.5:
        out.append(Finding(
            layer="graph",
            code="SINGLE_PAGE_DOMINATES",
            message=f"Top page holds {graph.metrics.top1_share:.0%} of total PageRank.",
            evidence_urls=[],
            details={"top1_share": round(graph.metrics.top1_share, 3)},
        ))
    return out


def _check_duplicate_titles(crawl: CrawlResult) -> list[Finding]:
    out: list[Finding] = []
    titles = Counter()
    title_to_url: dict[str, list[str]] = {}
    for url, page in crawl.pages.items():
        if page.title:
            titles[page.title] += 1
            title_to_url.setdefault(page.title, []).append(url)
    for title, count in titles.items():
        if count > 1:
            urls = title_to_url[title]
            out.append(Finding(
                layer="semantic",
                code="DUPLICATE_TITLE",
                message=f"Title '{title[:60]}' appears on {count} pages.",
                evidence_urls=urls[:10],
                details={"title": title, "count": count},
            ))
    return out


def _check_reputation(crawl: CrawlResult) -> list[Finding]:
    out: list[Finding] = []
    start = crawl.start_url
    if not start.lower().startswith("https://"):
        out.append(Finding(
            layer="reputation",
            code="NO_HTTPS",
            message="Start URL is not HTTPS.",
            evidence_urls=[start],
        ))
    # Look for standard reputation URLs among crawled pages
    crawled_urls = set(crawl.pages.keys())
    about_candidates = {"/about", "/about-us", "/company", "/team"}
    contact_candidates = {"/contact", "/contact-us", "/support"}
    legal_candidates = {"/privacy", "/privacy-policy", "/terms", "/legal"}
    has_about = any(any(u.endswith(p) or u.endswith(p + "/") for p in about_candidates) for u in crawled_urls)
    has_contact = any(any(u.endswith(p) or u.endswith(p + "/") for p in contact_candidates) for u in crawled_urls)
    has_legal = any(any(u.endswith(p) or u.endswith(p + "/") for p in legal_candidates) for u in crawled_urls)
    if not has_about:
        out.append(Finding(
            layer="reputation",
            code="ABOUT_PAGE_MISSING",
            message="No /about (or /about-us, /company) page was crawled.",
            evidence_urls=[start],
        ))
    if not has_contact:
        out.append(Finding(
            layer="reputation",
            code="CONTACT_PAGE_MISSING",
            message="No /contact page was crawled.",
            evidence_urls=[start],
        ))
    if not has_legal:
        out.append(Finding(
            layer="reputation",
            code="LEGAL_PAGE_MISSING",
            message="No /privacy or /terms page was crawled.",
            evidence_urls=[start],
        ))
    # Organization schema on home
    home_page = crawl.pages.get(start) or next(iter(crawl.pages.values()), None)
    if home_page:
        if not any(b.get("@type") in ("Organization", "WebSite", "Person") for b in home_page.json_ld_blocks):
            out.append(Finding(
                layer="reputation",
                code="NO_ORGANIZATION_SCHEMA",
                message="Home page does not declare Organization/WebSite/Person JSON-LD.",
                evidence_urls=[home_page.url],
            ))
    return out


# ---------------------------------------------------------------------------
# Search quality checks (v0.2.0)
# ---------------------------------------------------------------------------


def _check_search_quality(page: Page, crawl: CrawlResult) -> list[Finding]:
    """Produce findings from the search quality analysis."""
    from pagerank_seo.quality_analyzer import (
        classify_page_purpose,
        classify_content,
        analyze_eeat,
        analyze_originality,
    )
    out: list[Finding] = []
    purpose = classify_page_purpose(page)
    content = classify_content(page)
    eeat = analyze_eeat(page)
    originality = analyze_originality(page, crawl.pages)

    if purpose.purpose == PagePurposeType.UNKNOWN:
        out.append(Finding(
            layer="semantic",
            code="PURPOSE_UNCLEAR",
            message=f"Page purpose is unclear (confidence: {purpose.confidence}).",
            evidence_urls=[page.url],
            details={"signals": purpose.signals},
        ))

    if content.purpose_obscured:
        out.append(Finding(
            layer="semantic",
            code="PURPOSE_OBSCURED",
            message="Page purpose is obscured — title and body have almost no overlap.",
            evidence_urls=[page.url],
        ))

    if not content.main_content_identified:
        out.append(Finding(
            layer="semantic",
            code="MC_NOT_IDENTIFIED",
            message="Main content could not be clearly identified.",
            evidence_urls=[page.url],
        ))

    if content.ad_density == "high":
        out.append(Finding(
            layer="ux",
            code="ADS_OVERWHELM",
            message=f"High ad density detected ({content.ad_density}).",
            evidence_urls=[page.url],
        ))

    if originality.thin_content:
        out.append(Finding(
            layer="semantic",
            code="THIN_CONTENT",
            message=f"Page has only {page.text_word_count} visible words.",
            evidence_urls=[page.url],
            details={"word_count": page.text_word_count},
        ))

    if originality.near_duplicate_pages:
        out.append(Finding(
            layer="semantic",
            code="NEAR_DUPLICATE",
            message=f"Page has {len(originality.near_duplicate_pages)} near-duplicate(s).",
            evidence_urls=[page.url] + originality.near_duplicate_pages[:5],
            details={"count": len(originality.near_duplicate_pages)},
        ))

    if originality.lack_of_differentiation:
        out.append(Finding(
            layer="semantic",
            code="TEMPLATED_CONTENT",
            message="Page appears to be templated with little differentiation.",
            evidence_urls=[page.url],
        ))

    if originality.originality_score < 40:
        out.append(Finding(
            layer="semantic",
            code="LOW_ORIGINALITY",
            message=f"Content originality score is low ({originality.originality_score:.0f}/100).",
            evidence_urls=[page.url],
            details={"score": originality.originality_score},
        ))

    if eeat.overall_score < 30:
        out.append(Finding(
            layer="reputation",
            code="LOW_EEAT",
            message=f"E-E-A-T evidence is weak ({eeat.overall_score:.0f}/100).",
            evidence_urls=[page.url],
            details={"score": eeat.overall_score},
        ))

    if eeat.deceptive_signals:
        out.append(Finding(
            layer="reputation",
            code="DECEPTIVE_SIGNALS",
            message=f"Deceptive patterns detected: {', '.join(eeat.deceptive_signals[:3])}.",
            evidence_urls=[page.url],
            details={"signals": eeat.deceptive_signals},
        ))

    return out


def _check_scaled_content(crawl: CrawlResult) -> list[Finding]:
    """Produce findings from scaled-content detection."""
    from pagerank_seo.quality_analyzer import detect_scaled_content
    out: list[Finding] = []
    pattern = detect_scaled_content(crawl.pages)
    if pattern.detected:
        out.append(Finding(
            layer="semantic",
            code="SCALED_CONTENT_PATTERN",
            message=f"Potential scaled-content pattern: {pattern.evidence[0] if pattern.evidence else 'structural similarity detected'}.",
            evidence_urls=pattern.template_pages[:10],
            details={
                "structurally_identical_count": pattern.structurally_identical_count,
                "variation_score": pattern.variation_score,
                "confidence": pattern.confidence,
            },
        ))
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def analyze(crawl: CrawlResult, graph: SiteGraph) -> list[Finding]:
    """Run every check and return the combined list of findings."""
    findings: list[Finding] = []
    for page in crawl.pages.values():
        findings.extend(_check_technical(page))
        findings.extend(_check_semantic(page))
        findings.extend(_check_ux(page))
        findings.extend(_check_search_quality(page, crawl))
    findings.extend(_check_ia(crawl, graph))
    findings.extend(_check_graph(graph))
    findings.extend(_check_duplicate_titles(crawl))
    findings.extend(_check_reputation(crawl))
    findings.extend(_check_scaled_content(crawl))
    return findings
