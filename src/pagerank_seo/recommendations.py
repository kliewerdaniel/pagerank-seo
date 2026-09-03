"""Convert findings into prioritized, evidence-traceable recommendations.

Every recommendation references the finding codes that produced it and
includes a verification step. The priority assignment is documented in
the docstrings below and is intentionally rule-based — no LLM.
"""
from __future__ import annotations

from pagerank_seo.models import (
    CrawlResult,
    Finding,
    Priority,
    Recommendation,
    SiteGraph,
)


# Critical: blocking SEO function — the site is effectively invisible or broken.
# High:     significant structural damage — likely large ranking opportunity cost.
# Medium:   clearly improvable, but the site is functional.
# Low:      polish-level observations.


# (code, priority, impact, confidence, difficulty, recommended_action, verification_method)
_ACTION_TABLE: dict[str, tuple[Priority, str, str, str, str, str]] = {
    "HTTP_ERROR": (
        Priority.CRITICAL, "high", "high", "low",
        "Fix the broken URL or remove the link.",
        "Re-audit and confirm the URL now returns 2xx (or is no longer crawled).",
    ),
    "PARSE_FAILED": (
        Priority.HIGH, "medium", "high", "low",
        "Validate the HTML and fix the parse error (often an unclosed tag or bad encoding).",
        "Re-audit and confirm the page parses cleanly.",
    ),
    "CHARSET_MISSING": (
        Priority.HIGH, "medium", "high", "low",
        "Add <meta charset=\"utf-8\"> in the first 1024 bytes of <head>.",
        "Re-crawl and confirm charset is declared.",
    ),
    "CHARSET_NOT_UTF8": (
        Priority.MEDIUM, "low", "high", "low",
        "Convert page encoding to UTF-8.",
        "Re-crawl and confirm charset is utf-8.",
    ),
    "TITLE_MISSING": (
        Priority.HIGH, "high", "high", "low",
        "Add a meaningful, unique <title> (10–200 chars).",
        "Re-crawl and confirm the title is present and unique.",
    ),
    "TITLE_LENGTH": (
        Priority.MEDIUM, "medium", "medium", "low",
        "Adjust <title> length to 10–200 characters.",
        "Re-crawl and confirm length is in range.",
    ),
    "META_DESCRIPTION_MISSING": (
        Priority.MEDIUM, "medium", "high", "low",
        "Add a <meta name=\"description\"> that summarizes the page.",
        "Re-crawl and confirm the meta is present.",
    ),
    "CANONICAL_MISSING": (
        Priority.MEDIUM, "medium", "high", "low",
        "Add a self-referential <link rel=\"canonical\">.",
        "Re-crawl and confirm canonical points to the page itself.",
    ),
    "CANONICAL_CROSS_ORIGIN": (
        Priority.HIGH, "high", "high", "low",
        "Investigate why the canonical points off-origin; correct or remove it.",
        "Re-crawl and confirm the canonical now matches the page host.",
    ),
    "NOINDEX_ON_INDEXABLE": (
        Priority.CRITICAL, "high", "high", "low",
        "Remove the noindex directive from the page (or confirm it is intentional).",
        "Re-crawl and confirm noindex is absent on indexable pages.",
    ),
    "LANG_MISSING": (
        Priority.MEDIUM, "medium", "high", "low",
        "Add a lang attribute to <html>.",
        "Re-crawl and confirm lang is detected.",
    ),
    "VIEWPORT_MISSING": (
        Priority.HIGH, "high", "high", "low",
        "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.",
        "Re-crawl and confirm viewport meta is detected.",
    ),
    "NO_STRUCTURED_DATA": (
        Priority.MEDIUM, "medium", "medium", "medium",
        "Add JSON-LD structured data appropriate to the page type (Article, Product, BreadcrumbList, etc.).",
        "Re-crawl and confirm JSON-LD blocks parse successfully.",
    ),
    "H1_MISSING": (
        Priority.MEDIUM, "high", "high", "low",
        "Add a single descriptive <h1>.",
        "Re-crawl and confirm an h1 is detected.",
    ),
    "H1_MULTIPLE": (
        Priority.LOW, "low", "high", "low",
        "Reduce to a single <h1>.",
        "Re-crawl and confirm h1 count is 1.",
    ),
    "TITLE_CONTENT_OVERLAP_LOW": (
        Priority.LOW, "low", "medium", "medium",
        "Rework the title so it reflects the page's actual topic.",
        "Re-crawl and confirm title/content overlap improves.",
    ),
    "THIN_CONTENT": (
        Priority.MEDIUM, "medium", "medium", "high",
        "Expand the page content to better cover the topic, or merge it into a stronger page.",
        "Re-crawl and confirm word count is higher.",
    ),
    "DUPLICATE_TITLE": (
        Priority.HIGH, "high", "high", "low",
        "Make each page's <title> unique.",
        "Re-crawl and confirm duplicate-title count drops.",
    ),
    "NAV_MISSING": (
        Priority.MEDIUM, "medium", "high", "low",
        "Add a <nav> landmark with primary site navigation.",
        "Re-crawl and confirm <nav> is detected.",
    ),
    "MAIN_MISSING": (
        Priority.MEDIUM, "medium", "high", "low",
        "Wrap the primary content in a <main> element.",
        "Re-crawl and confirm <main> is detected.",
    ),
    "HEADER_MISSING": (
        Priority.LOW, "low", "medium", "low",
        "Add a <header> landmark at the top of the page.",
        "Re-crawl and confirm <header> is detected.",
    ),
    "FOOTER_MISSING": (
        Priority.LOW, "low", "low", "low",
        "Add a <footer> landmark with secondary navigation and legal links.",
        "Re-crawl and confirm <footer> is detected.",
    ),
    "ALT_TEXT_GAP": (
        Priority.MEDIUM, "medium", "high", "low",
        "Add alt attributes to <img> tags where missing or uninformative.",
        "Re-crawl and confirm alt-text gap ratio drops.",
    ),
    "ROBOTS_TXT_MISSING": (
        Priority.MEDIUM, "low", "high", "low",
        "Add a /robots.txt file. At minimum, declare the sitemap location.",
        "Re-crawl and confirm robots.txt is fetched.",
    ),
    "SITEMAP_MISSING": (
        Priority.MEDIUM, "medium", "high", "medium",
        "Generate an XML sitemap and reference it from robots.txt.",
        "Re-crawl and confirm sitemap URL is recorded.",
    ),
    "ORPHAN_PAGES": (
        Priority.HIGH, "high", "high", "medium",
        "Add contextual internal links to each orphan page from a relevant authoritative page.",
        "Re-crawl and confirm the orphan's in-degree > 0.",
    ),
    "DEEP_PAGES": (
        Priority.MEDIUM, "medium", "high", "medium",
        "Add navigational links that reduce click-depth to these pages.",
        "Re-crawl and confirm the depth distribution shifts shallower.",
    ),
    "DISCONNECTED_COMPONENTS": (
        Priority.HIGH, "high", "high", "medium",
        "Identify and bridge the disconnected subgraphs with internal links.",
        "Re-crawl and confirm weakly-connected-component count drops.",
    ),
    "AUTHORITY_CONCENTRATION": (
        Priority.MEDIUM, "medium", "medium", "medium",
        "Distribute internal links away from a few hubs toward under-linked pages.",
        "Re-crawl and confirm the Gini coefficient of PageRank drops.",
    ),
    "SINGLE_PAGE_DOMINATES": (
        Priority.MEDIUM, "medium", "medium", "medium",
        "Add outbound internal links from the top-ranked page to related content.",
        "Re-crawl and confirm top-1 PageRank share drops.",
    ),
    "NO_HTTPS": (
        Priority.HIGH, "high", "high", "medium",
        "Serve the site over HTTPS.",
        "Re-crawl and confirm the start URL uses https://.",
    ),
    "ABOUT_PAGE_MISSING": (
        Priority.MEDIUM, "low", "medium", "low",
        "Add an /about page describing who you are and what the site does.",
        "Re-crawl and confirm /about is discovered.",
    ),
    "CONTACT_PAGE_MISSING": (
        Priority.MEDIUM, "low", "medium", "low",
        "Add a /contact page with a way to reach you.",
        "Re-crawl and confirm /contact is discovered.",
    ),
    "LEGAL_PAGE_MISSING": (
        Priority.MEDIUM, "low", "medium", "low",
        "Add a /privacy (and optionally /terms) page.",
        "Re-crawl and confirm /privacy is discovered.",
    ),
    "NO_ORGANIZATION_SCHEMA": (
        Priority.MEDIUM, "medium", "medium", "low",
        "Add Organization or WebSite JSON-LD to the home page.",
        "Re-crawl and confirm the schema block is detected.",
    ),
    # --- Search quality findings (v0.2.0) ---
    "PURPOSE_UNCLEAR": (
        Priority.MEDIUM, "medium", "medium", "medium",
        "Clarify the page's primary purpose. Each page should have a clear reason to exist.",
        "Re-crawl and confirm the page purpose is identifiable.",
    ),
    "PURPOSE_OBSCURED": (
        Priority.HIGH, "high", "medium", "medium",
        "Restructure the page so its purpose is immediately clear to users and crawlers.",
        "Re-crawl and confirm purpose is no longer obscured.",
    ),
    "MC_NOT_IDENTIFIED": (
        Priority.HIGH, "high", "medium", "medium",
        "Ensure the main content is clearly identifiable. Use <article> or <main> to wrap it.",
        "Re-crawl and confirm main content is identified.",
    ),
    "ADS_OVERWHELM": (
        Priority.HIGH, "high", "medium", "medium",
        "Reduce ad density so it does not interfere with the main content.",
        "Re-crawl and confirm ad density is reduced.",
    ),
    "THIN_CONTENT_PAGE_QUALITY": (
        Priority.MEDIUM, "medium", "medium", "high",
        "Expand the page content to better cover the topic, or merge it into a stronger page.",
        "Re-crawl and confirm word count is higher.",
    ),
    "DUPLICATE_CONTENT": (
        Priority.HIGH, "high", "high", "medium",
        "Make each page's content unique. Remove or rewrite duplicate sections.",
        "Re-crawl and confirm duplicate content is resolved.",
    ),
    "NEAR_DUPLICATE": (
        Priority.MEDIUM, "medium", "high", "medium",
        "Differentiate near-duplicate pages with unique content, examples, or analysis.",
        "Re-crawl and confirm pages are no longer near-duplicates.",
    ),
    "TEMPLATED_CONTENT": (
        Priority.MEDIUM, "medium", "medium", "medium",
        "Add unique value to templated pages beyond keyword substitution.",
        "Re-crawl and confirm pages contain unique content.",
    ),
    "SCALED_CONTENT_PATTERN": (
        Priority.HIGH, "high", "medium", "medium",
        "Review templated pages for unique value. Each page should offer distinct content.",
        "Re-crawl and confirm scaled-content pattern is resolved.",
    ),
    "LOW_ORIGINALITY": (
        Priority.MEDIUM, "medium", "medium", "medium",
        "Add original analysis, examples, or evidence to increase the page's unique value.",
        "Re-crawl and confirm originality score improves.",
    ),
    "LOW_EEAT": (
        Priority.MEDIUM, "medium", "medium", "medium",
        "Improve E-E-A-T evidence: add author information, credentials, and transparent ownership.",
        "Re-crawl and confirm E-E-A-T signals are present.",
    ),
    "DECEPTIVE_SIGNALS": (
        Priority.CRITICAL, "high", "high", "medium",
        "Remove deceptive patterns (clickbait, fake urgency, misleading claims).",
        "Re-crawl and confirm deceptive signals are absent.",
    ),
    "SPAM_RISK_HIGH": (
        Priority.CRITICAL, "high", "high", "medium",
        "Address high spam risk signals immediately. Review content quality and purpose.",
        "Re-crawl and confirm spam risk is reduced.",
    ),
    "REPUTATION_ABUSE_RISK": (
        Priority.HIGH, "high", "medium", "medium",
        "Review whether pages fit the website's purpose and serve genuine user needs.",
        "Re-crawl and confirm site reputation abuse risk is reduced.",
    ),
}


def build_recommendations(
    findings: list[Finding], crawl: CrawlResult, graph: SiteGraph
) -> list[Recommendation]:
    """Translate findings into prioritized recommendations.

    Each finding code has at most one recommendation; multiple findings
    of the same code are aggregated into a single recommendation with
    the union of affected URLs.
    """
    # Group findings by code
    by_code: dict[str, list[Finding]] = {}
    for f in findings:
        by_code.setdefault(f.code, []).append(f)

    out: list[Recommendation] = []
    for code, group in by_code.items():
        action = _ACTION_TABLE.get(code)
        if action is None:
            # Unknown finding code: surface as a LOW recommendation so the
            # analyst can see it without an action template.
            priority = Priority.LOW
            impact = confidence = difficulty = "low"
            recommended_action = (
                f"Investigate: {group[0].message}"
            )
            verification_method = "Manually confirm whether action is needed."
        else:
            priority, impact, confidence, difficulty, recommended_action, verification_method = action

        # Collect all evidence URLs
        evidence_urls: list[str] = []
        seen = set()
        for f in group:
            for u in f.evidence_urls:
                if u and u not in seen:
                    evidence_urls.append(u)
                    seen.add(u)

        out.append(
            Recommendation(
                priority=priority,
                finding=group[0].message,
                evidence=[f.code for f in group],
                recommended_action=recommended_action,
                impact=impact,
                confidence=confidence,
                implementation_difficulty=difficulty,
                verification_method=verification_method,
                affected_urls=evidence_urls[:25],
            )
        )

    # Sort: CRITICAL first, then HIGH, MEDIUM, LOW; within band preserve input order.
    priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
    out.sort(key=lambda r: priority_order[r.priority])
    return out
