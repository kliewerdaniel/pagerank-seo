"""Tests for the search quality analyzer (v0.2.0)."""
from __future__ import annotations

import pytest

from pagerank_seo.parser import parse_html
from pagerank_seo.quality import (
    PagePurposeType,
    NeedsMetLevel,
    QueryIntentType,
)
from pagerank_seo.quality_analyzer import (
    classify_page_purpose,
    classify_content,
    analyze_reputation,
    analyze_eeat,
    analyze_originality,
    detect_scaled_content,
    analyze_page_quality,
    analyze_search_quality,
)
from pagerank_seo.models import CrawlResult


def _page(url: str, html: str, **kwargs):
    return parse_html(url=url, raw_html=html, **kwargs)


# ---------------------------------------------------------------------------
# Page Purpose
# ---------------------------------------------------------------------------


class TestPagePurpose:
    def test_informational_page(self):
        p = _page("https://example.com/about", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>About Our Company</title></head>
        <body><main><h1>About Us</h1>
        <p>We are a company that builds widgets.</p>
        <p>Founded in 1972, we have been serving customers for decades.</p>
        </main></body></html>
        """)
        purpose = classify_page_purpose(p)
        assert purpose.purpose == PagePurposeType.INFORMATIONAL
        assert purpose.confidence in ("medium", "high")

    def test_transactional_page(self):
        p = _page("https://example.com/buy", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Buy Widgets - Shop Now</title></head>
        <body><main><h1>Shop Widgets</h1>
        <p>Add to cart and checkout. Purchase our premium widgets today.</p>
        <button>Add to Cart</button>
        </main></body></html>
        """)
        purpose = classify_page_purpose(p)
        assert purpose.purpose == PagePurposeType.TRANSACTIONAL

    def test_unknown_purpose_empty_page(self):
        p = _page("https://example.com/empty", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title></title></head><body></body></html>
        """)
        purpose = classify_page_purpose(p)
        assert purpose.purpose == PagePurposeType.UNKNOWN
        assert purpose.confidence == "low"

    def test_blog_url_detected(self):
        p = _page("https://example.com/blog/my-post", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>My Journey Learning Python</title></head>
        <body><main><h1>My Journey</h1>
        <p>This is a personal blog post about my experience.</p>
        </main></body></html>
        """)
        purpose = classify_page_purpose(p)
        assert purpose.purpose == PagePurposeType.PERSONAL_EXPRESSION


# ---------------------------------------------------------------------------
# Content Classification
# ---------------------------------------------------------------------------


class TestContentClassification:
    def test_main_content_identified(self):
        p = _page("https://example.com/", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Home</title></head>
        <body><main><h1>Welcome</h1><p>Content here.</p></main></body></html>
        """)
        content = classify_content(p)
        assert content.main_content_identified is True

    def test_ads_detected(self):
        p = _page("https://example.com/", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Home</title></head>
        <body><main><h1>Welcome</h1><p>Content.</p></main>
        <div class="ad">googleads doubleclick adsbygoogle</div>
        </body></html>
        """)
        content = classify_content(p)
        assert content.advertisements_present is True

    def test_purpose_obscured(self):
        p = _page("https://example.com/", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Completely Unrelated Title</title></head>
        <body><main><h1>Different Topic</h1>
        <p>This page discusses quantum physics and molecular biology in depth.</p>
        <p>More content about science and research and experiments.</p>
        <p>Additional words to make the page longer than thirty words total.</p>
        <p>Even more text to ensure we pass the threshold for the check.</p>
        </main></body></html>
        """)
        content = classify_content(p)
        # Title and body have very low overlap
        assert content.purpose_obscured is True


# ---------------------------------------------------------------------------
# Reputation Analysis
# ---------------------------------------------------------------------------


class TestReputationAnalysis:
    def test_https_detected(self):
        p = _page("https://example.com/", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Home</title></head><body><main><h1>Welcome</h1></main></body></html>
        """)
        crawl = CrawlResult(start_url="https://example.com/", pages={p.url: p}, edges=[])
        rep = analyze_reputation(p, crawl)
        assert any(s.signal_type.value == "https" and s.present for s in rep.signals)

    def test_organization_schema_detected(self):
        p = _page("https://example.com/", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Home</title>
        <script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script>
        </head><body><main><h1>Welcome</h1></main></body></html>
        """)
        crawl = CrawlResult(start_url="https://example.com/", pages={p.url: p}, edges=[])
        rep = analyze_reputation(p, crawl)
        assert any(s.signal_type.value == "organization_schema" and s.present for s in rep.signals)

    def test_transparency_score(self):
        p = _page("https://example.com/", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Home</title>
        <script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script>
        </head><body><main><h1>Welcome</h1></main></body></html>
        """)
        crawl = CrawlResult(start_url="https://example.com/", pages={p.url: p}, edges=[])
        rep = analyze_reputation(p, crawl)
        assert rep.transparency_score > 0


# ---------------------------------------------------------------------------
# E-E-A-T Analysis
# ---------------------------------------------------------------------------


class TestEEATAnalysis:
    def test_first_hand_experience(self):
        p = _page("https://example.com/review", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>My Experience with Widgets</title></head>
        <body><main><h1>My Experience</h1>
        <p>In my experience, these widgets are excellent.</p>
        <p>I have been using them for five years.</p>
        </main></body></html>
        """)
        eeat = analyze_eeat(p)
        assert len(eeat.first_hand_evidence) > 0

    def test_credentials_detected(self):
        p = _page("https://example.com/medical", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Health Information</title></head>
        <body><main><h1>Health Guide</h1>
        <p>Written by Dr. Smith, MD, board-certified specialist.</p>
        <p>This article was reviewed by a medical expert.</p>
        </main></body></html>
        """)
        eeat = analyze_eeat(p)
        assert len(eeat.credentials_observed) > 0

    def test_deceptive_signals(self):
        p = _page("https://example.com/scam", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Miracle Cure - Act Now!</title></head>
        <body><main><h1>Secret Miracle</h1>
        <p>Limited time offer! Guaranteed results! Act now!</p>
        <p>They don't want you to know this secret.</p>
        </main></body></html>
        """)
        eeat = analyze_eeat(p)
        assert len(eeat.deceptive_signals) > 0
        assert eeat.trust_score < 50

    def test_overall_score_bounded(self):
        p = _page("https://example.com/", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Home</title></head><body><main><h1>Welcome</h1></main></body></html>
        """)
        eeat = analyze_eeat(p)
        assert 0 <= eeat.overall_score <= 100


# ---------------------------------------------------------------------------
# Originality Analysis
# ---------------------------------------------------------------------------


class TestOriginalityAnalysis:
    def test_thin_content(self):
        p = _page("https://example.com/thin", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Thin Page</title></head>
        <body><main><h1>Thin</h1><p>Very little content.</p></main></body></html>
        """)
        orig = analyze_originality(p, {p.url: p})
        assert orig.thin_content is True

    def test_near_duplicate_detection(self):
        p1 = _page("https://example.com/page1", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Same Title</title></head>
        <body><main><h1>Same Heading</h1><p>Same content here.</p></main></body></html>
        """)
        p2 = _page("https://example.com/page2", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Same Title</title></head>
        <body><main><h1>Same Heading</h1><p>Same content here.</p></main></body></html>
        """)
        orig = analyze_originality(p1, {p1.url: p1, p2.url: p2})
        assert len(orig.near_duplicate_pages) > 0

    def test_originality_score_bounded(self):
        p = _page("https://example.com/", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Home</title></head><body><main><h1>Welcome</h1></main></body></html>
        """)
        orig = analyze_originality(p, {p.url: p})
        assert 0 <= orig.originality_score <= 100


# ---------------------------------------------------------------------------
# Scaled Content Detection
# ---------------------------------------------------------------------------


class TestScaledContent:
    def test_no_pattern_on_small_site(self):
        pages = {
            f"https://example.com/p{i}": _page(f"https://example.com/p{i}", f"""
            <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
            <title>Page {i}</title></head>
            <body><main><h1>Page {i}</h1><p>Unique content for page {i}.</p></main></body></html>
            """)
            for i in range(3)
        }
        pattern = detect_scaled_content(pages)
        assert pattern.detected is False

    def test_pattern_detected_on_templated_site(self):
        pages = {
            f"https://example.com/product-{i}": _page(f"https://example.com/product-{i}", """
            <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
            <title>Product #</title></head>
            <body><main><h1>Product</h1><p>Buy now.</p></main></body></html>
            """)
            for i in range(10)
        }
        pattern = detect_scaled_content(pages)
        assert pattern.detected is True
        assert pattern.structurally_identical_count >= 5

    def test_low_information_pages(self):
        pages = {
            f"https://example.com/p{i}": _page(f"https://example.com/p{i}", """
            <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
            <title>Page</title></head>
            <body><main><h1>Page</h1><p>Tiny.</p></main></body></html>
            """)
            for i in range(10)
        }
        pattern = detect_scaled_content(pages)
        assert pattern.detected is True


# ---------------------------------------------------------------------------
# Unified Page Quality
# ---------------------------------------------------------------------------


class TestPageQuality:
    def test_page_quality_report(self):
        p = _page("https://example.com/", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Home</title></head>
        <body><main><h1>Welcome</h1><p>Content here.</p></main></body></html>
        """)
        crawl = CrawlResult(start_url="https://example.com/", pages={p.url: p}, edges=[])
        report = analyze_page_quality(p, crawl)
        assert report.url == "https://example.com/"
        assert report.purpose is not None
        assert report.eeat is not None
        assert 0 <= report.quality_score <= 100

    def test_search_quality_report(self):
        p = _page("https://example.com/", """
        <!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
        <title>Home</title></head>
        <body><main><h1>Welcome</h1><p>Content here.</p></main></body></html>
        """)
        crawl = CrawlResult(start_url="https://example.com/", pages={p.url: p}, edges=[])
        report = analyze_search_quality(crawl)
        assert len(report.page_reports) == 1
        assert report.scaled_content is not None
        assert 0 <= report.overall_quality_score <= 100
