"""Unit tests for the HTML parser.

These tests verify that the parser correctly extracts:
- Title, meta description, canonical, robots, viewport, lang, charset
- Semantic landmarks (nav, main, header, footer)
- Headings and h1
- JSON-LD structured-data blocks
- Links with their rel attribute and position weight
- Image alt-text statistics
- Robustness against malformed HTML
"""
from __future__ import annotations

import pytest

from pagerank_seo.models import RelType
from pagerank_seo.parser import parse_html, _extract_jsonld


# ---------------------------------------------------------------------------
# Title / meta / canonical / robots / viewport / lang / charset
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_title_extracted(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Hello World</title></head><body></body></html>',
        )
        assert p.title == "Hello World"

    def test_meta_description_extracted(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="description" content="A description."><title>T</title></head><body></body></html>',
        )
        assert p.meta_description == "A description."

    def test_canonical_extracted_and_resolved(self):
        p = parse_html(
            url="https://example.com/page",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><link rel="canonical" href="https://example.com/canonical"><title>T</title></head><body></body></html>',
        )
        assert p.canonical_url == "https://example.com/canonical"

    def test_robots_meta_extracted(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex, nofollow"><title>T</title></head><body></body></html>',
        )
        assert p.robots_meta is not None
        assert "noindex" in p.robots_meta

    def test_viewport_extracted(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>T</title></head><body></body></html>',
        )
        assert p.viewport_meta is not None
        assert "width=device-width" in p.viewport_meta

    def test_lang_attribute_extracted(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8"><title>T</title></head><body></body></html>',
        )
        assert p.lang == "en-GB"

    def test_charset_extracted_utf8(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body></body></html>',
        )
        assert p.charset == "utf-8"

    def test_charset_via_http_equiv(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html><head><meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-1"><title>T</title></head><body></body></html>',
        )
        assert p.charset == "iso-8859-1"


# ---------------------------------------------------------------------------
# Landmarks
# ---------------------------------------------------------------------------


class TestLandmarks:
    def test_landmarks_detected(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><header></header><nav></nav><main></main><footer></footer></body></html>',
        )
        assert p.has_nav
        assert p.has_main
        assert p.has_header
        assert p.has_footer

    def test_no_landmarks(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><div>hi</div></body></html>',
        )
        assert not p.has_nav
        assert not p.has_main
        assert not p.has_header
        assert not p.has_footer


# ---------------------------------------------------------------------------
# Headings
# ---------------------------------------------------------------------------


class TestHeadings:
    def test_single_h1(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><h1>The Title</h1><h2>Sub</h2></body></html>',
        )
        assert p.h1 == "The Title"
        levels = [l for l, _ in p.headings if _]
        assert 1 in levels
        assert 2 in levels

    def test_missing_h1(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><h2>Sub</h2></body></html>',
        )
        assert p.h1 is None


# ---------------------------------------------------------------------------
# JSON-LD
# ---------------------------------------------------------------------------


class TestJsonLd:
    def test_single_block(self):
        html = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article","headline":"X"}</script>
</head><body></body></html>'''
        p = parse_html(url="https://example.com/", raw_html=html)
        assert len(p.json_ld_blocks) == 1
        assert p.json_ld_blocks[0]["@type"] == "Article"

    def test_graph_form(self):
        html = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title>
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"A"},{"@type":"B"}]}</script>
</head><body></body></html>'''
        p = parse_html(url="https://example.com/", raw_html=html)
        assert len(p.json_ld_blocks) == 2
        types = {b["@type"] for b in p.json_ld_blocks}
        assert types == {"A", "B"}

    def test_malformed_block_ignored(self):
        html = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title>
<script type="application/ld+json">{not json</script>
</head><body></body></html>'''
        p = parse_html(url="https://example.com/", raw_html=html)
        assert p.json_ld_blocks == []


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


class TestLinks:
    def test_navigation_link_weight_1(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><nav><a href="/about">About</a></nav></body></html>',
        )
        assert len(p.outgoing_links) == 1
        l = p.outgoing_links[0]
        assert l.target_url == "https://example.com/about"
        assert l.position_weight == 1.0
        assert l.in_navigation
        assert l.rel == RelType.DOFOLLOW
        assert l.anchor == "About"

    def test_footer_link_weight(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><footer><a href="/privacy">Privacy</a></footer></body></html>',
        )
        assert p.outgoing_links[0].position_weight == 0.25

    def test_body_link_weight(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><main><a href="/x">x</a></main></body></html>',
        )
        assert p.outgoing_links[0].position_weight == 0.6

    def test_nofollow(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><main><a href="/x" rel="nofollow">x</a></main></body></html>',
        )
        assert p.outgoing_links[0].rel == RelType.NOFOLLOW

    def test_rel_with_space_separated_string(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><main><a href="/x" rel="nofollow noopener">x</a></main></body></html>',
        )
        assert p.outgoing_links[0].rel == RelType.NOFOLLOW

    def test_rel_with_list(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><main><a href="/x" rel="sponsored">x</a></main></body></html>',
        )
        assert p.outgoing_links[0].rel == RelType.SPONSORED

    def test_rel_ugc(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><main><a href="/x" rel="ugc">x</a></main></body></html>',
        )
        assert p.outgoing_links[0].rel == RelType.UGC

    def test_skips_javascript_href(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><main><a href="javascript:void(0)">x</a></main></body></html>',
        )
        assert p.outgoing_links == []

    def test_skips_anchor_only(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><main><a href="#section">x</a></main></body></html>',
        )
        assert p.outgoing_links == []

    def test_external_link_normalized(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><main><a href="https://other.example/x">x</a></main></body></html>',
        )
        assert p.outgoing_links[0].target_url == "https://other.example/x"

    def test_image_only_link(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><main><a href="/x"><img src="/y.png" alt="x"></a></main></body></html>',
        )
        assert p.outgoing_links[0].anchor is None

    def test_dedupes_repeated_targets(self):
        p = parse_html(
            url="https://example.com/",
            raw_html='<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head><body><main><a href="/x">x1</a><a href="/x">x2</a></main></body></html>',
        )
        assert len(p.outgoing_links) == 1


# ---------------------------------------------------------------------------
# Images / alt text
# ---------------------------------------------------------------------------


class TestImages:
    def test_image_alt_counts(self):
        html = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head>
<body><main>
<img src="/a.png" alt="A">
<img src="/b.png" alt="">
<img src="/c.png">
</main></body></html>'''
        p = parse_html(url="https://example.com/", raw_html=html)
        assert p.images_total == 3
        # An empty alt attribute counts as present (per HTML spec — empty alt
        # is meaningful for decorative images). Only the missing-alt case counts.
        assert p.images_without_alt == 1


# ---------------------------------------------------------------------------
# Word count
# ---------------------------------------------------------------------------


class TestWordCount:
    def test_text_word_count(self):
        html = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>T</title></head>
<body><main><h1>Heading</h1><p>one two three four five six seven eight nine ten</p></main></body></html>'''
        p = parse_html(url="https://example.com/", raw_html=html)
        # Body text includes both the h1 and the paragraph.
        assert p.text_word_count == 11


# ---------------------------------------------------------------------------
# Malformed HTML robustness
# ---------------------------------------------------------------------------


class TestMalformed:
    def test_unclosed_tags(self):
        html = '<html><head><meta charset="utf-8"><title>T'  # truncated
        p = parse_html(url="https://example.com/", raw_html=html)
        # Should not raise; should still produce a Page.
        assert p.title is None or "T" in (p.title or "")

    def test_garbage_input(self):
        p = parse_html(url="https://example.com/", raw_html="<<<not html at all>>>")
        assert p.error is None or p.error.startswith("parse_failed")
