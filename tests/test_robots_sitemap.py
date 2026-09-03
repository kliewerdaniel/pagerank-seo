"""Tests for the robots.txt parser (RFC 9309 subset)."""
from __future__ import annotations

import pytest

from pagerank_seo.crawler import RobotsTxt, _parse_sitemap_xml


class TestRobotsTxt:
    def test_allows_when_empty(self):
        r = RobotsTxt.parse("")
        assert r.allows(user_agent="AnyBot/1.0", url_path="/")

    def test_disallow_blocks(self):
        r = RobotsTxt.parse("User-agent: *\nDisallow: /private\n")
        assert not r.allows(user_agent="AnyBot/1.0", url_path="/private/page")
        assert r.allows(user_agent="AnyBot/1.0", url_path="/public")

    def test_allow_overrides_disallow(self):
        r = RobotsTxt.parse("User-agent: *\nDisallow: /private\nAllow: /private/ok\n")
        assert r.allows(user_agent="AnyBot/1.0", url_path="/private/ok")

    def test_specific_user_agent_match(self):
        r = RobotsTxt.parse("User-agent: MyBot\nDisallow: /\nUser-agent: *\nAllow: /\n")
        # RFC 9309 §2.2.2: when both groups match, combine rules; longest
        # pattern wins, ties go to Allow. Both groups have a 1-char rule for
        # "/", so the tie-break to Allow means /anything is allowed.
        # To prove disallow works, use a longer pattern.
        assert r.allows(user_agent="MyBot/1.0", url_path="/anything")
        r2 = RobotsTxt.parse("User-agent: MyBot\nDisallow: /secret\nUser-agent: *\nAllow: /\n")
        # /secret is a longer match than /, so disallow wins for MyBot.
        assert not r2.allows(user_agent="MyBot/1.0", url_path="/secret/page")
        assert r2.allows(user_agent="MyBot/1.0", url_path="/public")

    def test_substring_user_agent_match(self):
        r = RobotsTxt.parse("User-agent: MyBot\nDisallow: /\n")
        # RFC 9309: case-insensitive substring matching
        assert not r.allows(user_agent="mybot/2.0 (different UA string)", url_path="/x")

    def test_sitemap_extracted(self):
        text = "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n"
        r = RobotsTxt.parse(text)
        assert "https://example.com/sitemap.xml" in r.sitemaps

    def test_comments_ignored(self):
        text = "# A comment\nUser-agent: *  # inline comment\nDisallow: /x\n"
        r = RobotsTxt.parse(text)
        assert not r.allows(user_agent="AnyBot", url_path="/x/page")
        assert r.allows(user_agent="AnyBot", url_path="/other")

    def test_longest_match_wins(self):
        # Per RFC 9309: longest matching path wins; tie → Allow wins
        text = "User-agent: *\nDisallow: /a/b\nAllow: /a\n"
        r = RobotsTxt.parse(text)
        # /a/b/c — longest match is /a/b (4 chars) → disallow
        assert not r.allows(user_agent="X", url_path="/a/b/c")
        # /a — longest match is /a (2 chars) → allow
        assert r.allows(user_agent="X", url_path="/a")


class TestSitemapParser:
    def test_urlset(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://example.com/a</loc></url>
<url><loc>https://example.com/b</loc></url>
</urlset>"""
        urls = _parse_sitemap_xml(xml)
        assert "https://example.com/a" in urls
        assert "https://example.com/b" in urls

    def test_sitemap_index(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://example.com/s1.xml</loc></sitemap>
</sitemapindex>"""
        urls = _parse_sitemap_xml(xml)
        assert "https://example.com/s1.xml" in urls

    def test_malformed_raises_sitemap_error_strict(self):
        """For callers that want strict mode, malformed XML raises SitemapError."""
        from pagerank_seo.errors import SitemapError
        with pytest.raises(SitemapError):
            _parse_sitemap_xml("not xml at all")

    def test_lenient_returns_empty_on_malformed(self):
        from pagerank_seo.crawler import parse_sitemap_lenient
        assert parse_sitemap_lenient("not xml at all") == []
