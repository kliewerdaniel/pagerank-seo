"""Synthetic-site HTML fixtures for deterministic testing.

These fixtures are designed to exercise specific analyzer paths and
graph shapes without touching the network.
"""
from __future__ import annotations

from typing import Callable

from pagerank_seo.parser import parse_html
from pagerank_seo.models import CrawlResult, Link, Page


def _page(*, url: str, raw_html: str, status_code: int = 200, depth: int = 0) -> Page:
    """Parse an HTML string and return a Page at the given URL."""
    return parse_html(url=url, raw_html=raw_html, status_code=status_code, depth=depth)


# ---------------------------------------------------------------------------
# Tiny site: home -> about -> contact. Clean, well-linked, no orphans.
# ---------------------------------------------------------------------------

HOME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Acme Corp - Home</title>
<meta name="description" content="Acme Corp provides excellent widgets for sale.">
<link rel="canonical" href="https://acme.example/">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"Acme"}</script>
</head>
<body>
<header><nav><a href="/about">About</a><a href="/contact">Contact</a></nav></header>
<main>
<h1>Welcome to Acme</h1>
<p>We build excellent widgets for sale to consumers and businesses worldwide.</p>
<p>Acme Corp has been producing reliable widgets since 1972.</p>
</main>
<footer><a href="/privacy">Privacy</a></footer>
</body>
</html>"""

ABOUT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>About Acme Corp</title>
<meta name="description" content="About Acme Corp.">
<link rel="canonical" href="https://acme.example/about">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
<header><nav><a href="/">Home</a><a href="/contact">Contact</a></nav></header>
<main>
<h1>About Acme</h1>
<p>Acme Corp was founded in 1972 by a small team of engineers.</p>
<p>We believe that widgets should be both well-designed and durable.</p>
<p>This page describes our mission, our values, and our team.</p>
</main>
<footer><a href="/privacy">Privacy</a></footer>
</body>
</html>"""

CONTACT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Contact Acme Corp</title>
<meta name="description" content="How to contact Acme Corp.">
<link rel="canonical" href="https://acme.example/contact">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
<header><nav><a href="/">Home</a><a href="/about">About</a></nav></header>
<main>
<h1>Contact us</h1>
<p>Reach Acme by email at hello@acme.example.</p>
<p>We respond to inquiries within two business days.</p>
</main>
<footer><a href="/privacy">Privacy</a></footer>
</body>
</html>"""

PRIVACY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Privacy Policy - Acme Corp</title>
<meta name="description" content="Acme Corp privacy policy.">
<link rel="canonical" href="https://acme.example/privacy">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
<header><nav><a href="/">Home</a><a href="/about">About</a></nav></header>
<main>
<h1>Privacy</h1>
<p>This page describes what data Acme Corp collects and how we use it.</p>
<p>We never sell your personal data to third parties.</p>
<p>You may request a copy of your data at any time.</p>
</main>
<footer></footer>
</body>
</html>"""


def tiny_clean_site(start: str = "https://acme.example/") -> CrawlResult:
    """Build a small 4-page synthetic site with no orphan pages."""
    urls = [
        ("https://acme.example/", HOME_HTML, 0),
        ("https://acme.example/about", ABOUT_HTML, 1),
        ("https://acme.example/contact", CONTACT_HTML, 1),
        ("https://acme.example/privacy", PRIVACY_HTML, 1),
    ]
    pages: dict[str, Page] = {}
    for url, html, depth in urls:
        pages[url] = _page(url=url, raw_html=html, depth=depth)
    edges: list[Link] = []
    for p in pages.values():
        edges.extend(p.outgoing_links)
    return CrawlResult(
        start_url=start,
        pages=pages,
        edges=edges,
        robots_txt="User-agent: *\nAllow: /\nSitemap: https://acme.example/sitemap.xml\n",
        sitemap_urls=["https://acme.example/sitemap.xml"],
        pages_fetched=len(pages),
    )


# ---------------------------------------------------------------------------
# Site with an orphan: hidden page that no one links to.
# ---------------------------------------------------------------------------


HIDDEN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Hidden Acme Page</title>
<meta name="description" content="A page nobody links to.">
<link rel="canonical" href="https://acme.example/hidden">
<meta name="viewport" content="width=device-width">
</head>
<body>
<main><h1>Hidden</h1><p>This page is intentionally orphaned.</p></main>
</body>
</html>"""


def site_with_orphan(start: str = "https://acme.example/") -> CrawlResult:
    """Build the tiny site plus an orphan page."""
    base = tiny_clean_site(start=start)
    base.pages["https://acme.example/hidden"] = _page(
        url="https://acme.example/hidden",
        raw_html=HIDDEN_HTML,
        depth=2,
    )
    return base


# ---------------------------------------------------------------------------
# Site with a malformed HTML page (parser must still produce a Page).
# ---------------------------------------------------------------------------


MALFORMED_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Broken
<meta name="description" content="Unclosed meta tag">
"""
# No closing tags, no body. Parser should still produce *something*.


def site_with_malformed_page(start: str = "https://acme.example/") -> CrawlResult:
    """Build the tiny site plus a malformed HTML page."""
    base = tiny_clean_site(start=start)
    base.pages["https://acme.example/broken"] = _page(
        url="https://acme.example/broken",
        raw_html=MALFORMED_HTML,
        depth=1,
    )
    # Don't link from anywhere — also an orphan
    return base


# ---------------------------------------------------------------------------
# Site with a nofollow link
# ---------------------------------------------------------------------------


NOFOLLOW_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Acme - With Nofollow</title>
<meta name="description" content="Page that nofollows external links.">
<link rel="canonical" href="https://acme.example/nofollow">
<meta name="viewport" content="width=device-width">
</head>
<body>
<main>
<h1>Nofollow demo</h1>
<p>This page links externally with rel="nofollow".</p>
<a href="https://other.example/" rel="nofollow">External (nofollow)</a>
<a href="https://acme.example/contact">Internal (dofollow)</a>
</main>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Site with a cycle: A -> B -> C -> A
# ---------------------------------------------------------------------------


def cycle_site(start: str = "https://acme.example/") -> CrawlResult:
    """Build a 3-node cyclic graph."""
    pages = {
        "https://acme.example/": _page(url="https://acme.example/", raw_html=HOME_HTML, depth=0),
        "https://acme.example/a": _page(url="https://acme.example/a", raw_html=ABOUT_HTML, depth=1),
        "https://acme.example/b": _page(url="https://acme.example/b", raw_html=CONTACT_HTML, depth=1),
    }
    # Override the outgoing links to form a cycle
    pages["https://acme.example/"].outgoing_links = [
        Link(source_url="https://acme.example/", target_url="https://acme.example/a", position_weight=1.0, in_navigation=True),
        Link(source_url="https://acme.example/", target_url="https://acme.example/b", position_weight=1.0, in_navigation=True),
    ]
    pages["https://acme.example/a"].outgoing_links = [
        Link(source_url="https://acme.example/a", target_url="https://acme.example/b", position_weight=1.0, in_navigation=True),
    ]
    pages["https://acme.example/b"].outgoing_links = [
        Link(source_url="https://acme.example/b", target_url="https://acme.example/", position_weight=1.0, in_navigation=True),
        Link(source_url="https://acme.example/b", target_url="https://acme.example/a", position_weight=1.0, in_navigation=True),
    ]
    edges = []
    for p in pages.values():
        edges.extend(p.outgoing_links)
    return CrawlResult(start_url=start, pages=pages, edges=edges)


# ---------------------------------------------------------------------------
# Site with no internal links at all (every page is an island).
# ---------------------------------------------------------------------------


def island_site(start: str = "https://acme.example/") -> CrawlResult:
    """Build a 3-page site where no page links to any other."""
    pages = {
        f"https://acme.example/p{i}": _page(
            url=f"https://acme.example/p{i}",
            raw_html=ABOUT_HTML,
            depth=1,
        )
        for i in range(3)
    }
    # Clear outgoing links
    for p in pages.values():
        p.outgoing_links = []
    return CrawlResult(start_url=start, pages=pages, edges=[])
