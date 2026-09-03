"""HTML parsing for the PageRank SEO SDK.

The parser extracts everything the analyzer needs from a single HTML
response: metadata, semantic landmarks, structured-data blocks, headings,
anchor-text links, and a link-position heuristic used to weight edges.

The parser is intentionally lenient — it never raises on malformed HTML;
it returns a ``Page`` with whatever it could extract and leaves the
remaining fields at their default values. The crawler decides whether
to surface the page as a failed fetch.

References
----------
- HTML Living Standard: https://html.spec.whatwg.org/
- MDN <meta>: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/meta
- schema.org: https://schema.org/
"""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from pagerank_seo.models import Link, Page, RelType
from pagerank_seo.utils import normalize_url

if TYPE_CHECKING:
    from pagerank_seo.crawler import RobotsTxt


# ---------------------------------------------------------------------------
# Heuristic link-position weight
# ---------------------------------------------------------------------------
#
# This is a HYPOTHESIS (see docs/research/sources.md §5), not a documented
# Google ranking factor. Above-the-fold / navigation links are typically the
# primary discoverability path within a site, so we model that intuition for
# the internal weighted-PageRank calculation.
#
# Position weight table (multiplier applied to edge weight):
#   - <nav>                     -> 1.00
#   - <header>                  -> 0.90
#   - top-level body content    -> 0.60
#   - <aside>                   -> 0.40
#   - <footer>                  -> 0.25


_LINK_WEIGHT_NAV = 1.0
_LINK_WEIGHT_HEADER = 0.9
_LINK_WEIGHT_BODY = 0.6
_LINK_WEIGHT_ASIDE = 0.4
_LINK_WEIGHT_FOOTER = 0.25


# ---------------------------------------------------------------------------
# JSON-LD extraction helpers
# ---------------------------------------------------------------------------


_JSON_LD_RE = re.compile(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)


def _extract_jsonld(html: str) -> list[dict]:
    """Extract every JSON-LD block's parsed ``@graph``/object dict."""
    blocks: list[dict] = []
    for match in _JSON_LD_RE.finditer(html):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            # A JSON-LD object may be either a single dict or {"@graph": [...]}
            if "@graph" in data and isinstance(data["@graph"], list):
                for item in data["@graph"]:
                    if isinstance(item, dict):
                        blocks.append(item)
            else:
                blocks.append(data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "@graph" in item and isinstance(item["@graph"], list):
                        for sub in item["@graph"]:
                            if isinstance(sub, dict):
                                blocks.append(sub)
                    else:
                        blocks.append(item)
    return blocks


# ---------------------------------------------------------------------------
# Anchor text collection
# ---------------------------------------------------------------------------


def _anchor_text(a: Tag) -> str:
    """Return the visible anchor text of an ``<a>`` element.

    Concatenates the textual content of all child nodes; collapses whitespace.
    Falls back to empty string for image-only or empty links.
    """
    parts: list[str] = []
    for child in a.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            # Don't descend into nested <a> to avoid double counting.
            if child.name == "a":
                continue
            parts.append(child.get_text(" ", strip=True))
    text = " ".join("".join(parts).split())
    return text


# ---------------------------------------------------------------------------
# Public parser
# ---------------------------------------------------------------------------


def parse_html(
    *,
    url: str,
    raw_html: str,
    status_code: int = 200,
    content_type: str = "text/html",
    depth: int = 0,
    redirected_from: Optional[str] = None,
) -> Page:
    """Parse one HTML document and return a populated ``Page``.

    Tolerant of malformed HTML; never raises for parse failures.
    """
    page = Page(
        url=url,
        status_code=status_code,
        content_type=content_type,
        raw_html=raw_html,
        depth=depth,
        redirected_from=redirected_from,
    )

    # ------------------------------------------------------------------
    # Pre-parse: JSON-LD (raw regex, before BS4 mangles it)
    # ------------------------------------------------------------------
    page.json_ld_blocks = _extract_jsonld(raw_html)

    # ------------------------------------------------------------------
    # BeautifulSoup parse
    # ------------------------------------------------------------------
    try:
        soup = BeautifulSoup(raw_html, "lxml")
    except Exception:
        # Even lxml rarely fails; BeautifulSoup's html.parser is the fallback.
        try:
            soup = BeautifulSoup(raw_html, "html.parser")
        except Exception as exc:
            page.error = f"parse_failed: {exc}"
            return page

    # ---- charset --------------------------------------------------------
    # Per MDN, charset declaration must be in the first 1024 bytes.
    head = soup.find("head")
    if head is None:
        # Some malformed pages have no <head>; still proceed with body.
        pass
    charset_meta = soup.find("meta", attrs={"charset": True})
    if charset_meta and charset_meta.get("charset"):
        page.charset = str(charset_meta.get("charset")).strip().lower()
    else:
        # http-equiv="Content-Type" with charset
        http_equiv_meta = soup.find("meta", attrs={"http-equiv": re.compile(r"content-type", re.I)})
        if http_equiv_meta and http_equiv_meta.get("content"):
            m = re.search(r"charset=([\w-]+)", str(http_equiv_meta.get("content")), re.I)
            if m:
                page.charset = m.group(1).strip().lower()

    # ---- <html lang> ----------------------------------------------------
    if soup.html is not None and soup.html.get("lang"):
        page.lang = str(soup.html.get("lang")).strip()

    # ---- <title> --------------------------------------------------------
    if soup.title and soup.title.string:
        page.title = " ".join(soup.title.string.split())

    # ---- meta description / robots / viewport ---------------------------
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").strip().lower()
        prop = (meta.get("property") or "").strip().lower()
        http_equiv = (meta.get("http-equiv") or "").strip().lower()
        content = (meta.get("content") or "").strip()
        if not content:
            continue
        if name == "description" and not page.meta_description:
            page.meta_description = content
        elif name == "robots" and not page.robots_meta:
            page.robots_meta = content
        elif http_equiv == "refresh":
            # meta-refresh redirect: surface via robots_meta style note on the error
            page.robots_meta = page.robots_meta or f"refresh: {content}"
        if name == "viewport" and not page.viewport_meta:
            page.viewport_meta = content
        if prop == "og:title" and not page.title:
            page.title = content
        if prop == "og:description" and not page.meta_description:
            page.meta_description = content

    # ---- canonical ------------------------------------------------------
    canonical = soup.find("link", rel=re.compile(r"\bcanonical\b", re.I))
    if canonical and canonical.get("href"):
        page.canonical_url = normalize_url(urljoin(url, canonical["href"]))

    # ---- landmarks ------------------------------------------------------
    page.has_nav = bool(soup.find("nav"))
    page.has_main = bool(soup.find("main"))
    page.has_header = bool(soup.find("header"))
    page.has_footer = bool(soup.find("footer"))

    # ---- headings -------------------------------------------------------
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            txt = " ".join(h.get_text(" ", strip=True).split())
            page.headings.append((level, txt))
    # First h1 wins
    for level, txt in page.headings:
        if level == 1 and txt:
            page.h1 = txt
            break

    # ---- images / alt ---------------------------------------------------
    # Per HTML spec, an *empty* alt attribute (``alt=""``) is meaningful and
    # indicates a decorative image — it counts as "present". Only an absent
    # attribute counts as "missing alt text".
    imgs = soup.find_all("img")
    page.images_total = len(imgs)
    page.images_without_alt = sum(
        1 for img in imgs if img.get("alt") is None
    )

    # ---- body text word count ------------------------------------------
    if soup.body is not None:
        page.text_word_count = len(" ".join(soup.body.get_text(" ", strip=True).split()).split())

    # ---- outgoing links -------------------------------------------------
    page.outgoing_links = _extract_links(soup, page_url=url)

    return page


def _extract_links(soup: BeautifulSoup, *, page_url: str) -> list[Link]:
    """Walk every ``<a>`` in the soup and emit a ``Link``.

    Computes the position-weight using the section the link sits inside.
    Resolves each href against ``page_url`` and normalizes.
    """
    out: list[Link] = []
    seen_targets: set[str] = set()

    # Pre-compute ancestor lookup helpers — for each <a> we'll walk up to find
    # the first semantic landmark (<nav>, <header>, <aside>, <footer>).
    body = soup.body or soup

    for a in soup.find_all("a"):
        href = a.get("href")
        if not href or not isinstance(href, str):
            continue
        href = href.strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        target = normalize_url(urljoin(page_url, href))
        if not target or target in seen_targets:
            continue
        seen_targets.add(target)

        rel_attr = a.get("rel")
        rel_tokens: set[str] = set()
        if isinstance(rel_attr, str):
            for tok in rel_attr.split():
                rel_tokens.add(tok.strip().lower())
        elif rel_attr is not None:
            for r in rel_attr:
                if r is None:
                    continue
                rel_tokens.add(str(r).strip().lower())
        if "nofollow" in rel_tokens:
            rel = RelType.NOFOLLOW
        elif "sponsored" in rel_tokens:
            rel = RelType.SPONSORED
        elif "ugc" in rel_tokens:
            rel = RelType.UGC
        else:
            rel = RelType.DOFOLLOW

        # Determine section / position weight
        position_weight, in_navigation = _position_weight(a, body)

        out.append(
            Link(
                source_url=page_url,
                target_url=target,
                anchor=_anchor_text(a) or None,
                rel=rel,
                position_weight=position_weight,
                in_navigation=in_navigation,
            )
        )

    return out


def _position_weight(a: Tag, body: Tag) -> tuple[float, bool]:
    """Walk up the DOM from ``a`` to find the first landmark.

    Returns ``(position_weight, in_navigation)``. ``in_navigation`` is True
    when the link lives inside any ``<nav>`` element (directly or
    transitively).
    """
    cur: Optional[Tag] = a
    in_nav = False
    # Walk up at most 12 ancestors — practical bound.
    for _ in range(12):
        if cur is None or cur is body or cur.name == "body":
            break
        name = cur.name
        if name == "nav":
            in_nav = True
            return _LINK_WEIGHT_NAV, True
        if name == "header":
            return _LINK_WEIGHT_HEADER, False
        if name == "aside":
            return _LINK_WEIGHT_ASIDE, False
        if name == "footer":
            return _LINK_WEIGHT_FOOTER, False
        if name == "[document]" or name == "html":
            break
        cur = cur.parent
    # No landmark ancestor: treat as body content.
    return _LINK_WEIGHT_BODY, in_nav


# ---------------------------------------------------------------------------
# Convenience: robots.txt parser (very small subset)
# ---------------------------------------------------------------------------


def parse_robots_txt(text: str) -> "RobotsTxt":
    """Parse a robots.txt body into a ``RobotsTxt``.

    Implements the RFC 9309 subset we care about: ``User-agent``,
    ``Allow``, ``Disallow``, ``Sitemap``. We do not implement crawl-delay
    (Google deprecated it in 2023) or other directives.
    """
    from pagerank_seo.crawler import RobotsTxt as _RobotsTxt  # late import to avoid cycle
    return _RobotsTxt.parse(text)


# ---------------------------------------------------------------------------
# Convenience: XML sitemap parser
# ---------------------------------------------------------------------------


def parse_sitemap(xml_text: str) -> list[str]:
    """Parse an XML sitemap and return the URLs declared inside.

    Supports both ``<urlset>`` and ``<sitemapindex>`` documents.
    Returns an empty list on parse failure.
    """
    from pagerank_seo.crawler import _parse_sitemap_xml  # late import to avoid cycle
    return _parse_sitemap_xml(xml_text)
