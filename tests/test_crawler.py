"""End-to-end crawler test against a local in-process HTTP server.

Spins up a tiny BaseHTTPRequestHandler that serves a fixed corpus of
HTML pages with known inter-link structure. Verifies the BFS, robots.txt
handling, sitemap handling, depth limits, and page limits.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

import pytest

from pagerank_seo.crawler import Crawler
from pagerank_seo.errors import CrawlError
from pagerank_seo.models import AuditConfig


# ---------------------------------------------------------------------------
# Local test server
# ---------------------------------------------------------------------------


_TEST_CORPUS = {
    "/": """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Home</title>
<meta name="description" content="Home page"><meta name="viewport" content="width=device-width">
<link rel="canonical" href="/"></head>
<body>
<header><nav><a href="/a">A</a><a href="/b">B</a></nav></header>
<main><h1>Home</h1><p>Welcome. Words here to defeat thin-content heuristics, more words.</p></main>
<footer><a href="/privacy">Privacy</a></footer>
</body></html>""",
    "/a": """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>A</title>
<meta name="description" content="A page"><meta name="viewport" content="width=device-width">
<link rel="canonical" href="/a"></head>
<body>
<header><nav><a href="/">Home</a><a href="/b">B</a></nav></header>
<main><h1>A</h1><p>This is the A page with sufficient content to avoid the thin-content heuristic.</p></main>
<footer></footer></body></html>""",
    "/b": """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>B</title>
<meta name="description" content="B page"><meta name="viewport" content="width=device-width">
<link rel="canonical" href="/b"></head>
<body>
<header><nav><a href="/">Home</a><a href="/a">A</a></nav></header>
<main><h1>B</h1><p>This is the B page with enough content to defeat thin-content heuristic.</p></main>
<footer></footer></body></html>""",
    "/privacy": """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Privacy</title>
<meta name="description" content="Privacy"><meta name="viewport" content="width=device-width">
<link rel="canonical" href="/privacy"></head>
<body>
<main><h1>Privacy</h1><p>This page describes the privacy policy in long form to defeat thin-content heuristics.</p></main>
</body></html>""",
    "/secret": """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Secret</title></head>
<body><main><h1>Secret</h1><p>You shouldn't be able to reach this via /.</p></main></body></html>""",
}

_ROBOTS_TXT = "User-agent: *\nDisallow: /secret\nAllow: /\nSitemap: /sitemap.xml\n"

_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>/</loc></url>
<url><loc>/a</loc></url>
<url><loc>/b</loc></url>
<url><loc>/privacy</loc></url>
</urlset>"""


class _TestHandler(BaseHTTPRequestHandler):
    corpus = _TEST_CORPUS
    robots_txt = _ROBOTS_TXT
    sitemap_xml = _SITEMAP_XML

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/robots.txt":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(self.robots_txt)))
            self.end_headers()
            self.wfile.write(self.robots_txt.encode("utf-8"))
            return
        if path == "/sitemap.xml":
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(self.sitemap_xml)))
            self.end_headers()
            self.wfile.write(self.sitemap_xml.encode("utf-8"))
            return
        if path in self.corpus:
            body = self.corpus[path]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"not found")

    def log_message(self, *_args, **_kwargs):
        # Silence the test server's stderr noise.
        pass


@pytest.fixture(scope="module")
def http_server():
    server = HTTPServer(("127.0.0.1", 0), _TestHandler)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://{host}:{port}"
    server.shutdown()
    thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCrawlerEndToEnd:
    def test_basic_crawl(self, http_server):
        config = AuditConfig(
            start_url=http_server + "/",
            max_pages=10,
            max_depth=3,
            requests_per_second=10.0,
        )
        crawler = Crawler(config)
        result = crawler.crawl()
        # We should have crawled: /, /a, /b, /privacy (from sitemap) — but not /secret (robots disallow).
        urls = set(result.pages.keys())
        assert any(u.endswith("/") for u in urls)
        assert any(u.endswith("/a") for u in urls)
        assert any(u.endswith("/b") for u in urls)
        assert any(u.endswith("/privacy") for u in urls)
        assert not any(u.endswith("/secret") for u in urls)

    def test_robots_txt_fetched(self, http_server):
        config = AuditConfig(
            start_url=http_server + "/",
            max_pages=10,
            max_depth=2,
            requests_per_second=10.0,
        )
        result = Crawler(config).crawl()
        assert result.robots_txt is not None
        assert "Disallow: /secret" in result.robots_txt

    def test_sitemap_fetched(self, http_server):
        config = AuditConfig(
            start_url=http_server + "/",
            max_pages=10,
            max_depth=2,
            requests_per_second=10.0,
        )
        result = Crawler(config).crawl()
        assert len(result.sitemap_urls) == 1
        assert result.sitemap_urls[0].endswith("/sitemap.xml")

    def test_max_pages_respected(self, http_server):
        config = AuditConfig(
            start_url=http_server + "/",
            max_pages=2,
            max_depth=3,
            requests_per_second=10.0,
        )
        result = Crawler(config).crawl()
        assert len(result.pages) <= 2

    def test_max_depth_respected(self, http_server):
        # With depth=0, we should only fetch the start URL.
        config = AuditConfig(
            start_url=http_server + "/",
            max_pages=20,
            max_depth=0,
            requests_per_second=10.0,
        )
        result = Crawler(config).crawl()
        assert len(result.pages) == 1

    def test_robots_disallowed_url_excluded(self, http_server):
        config = AuditConfig(
            start_url=http_server + "/",
            max_pages=20,
            max_depth=3,
            requests_per_second=10.0,
            respect_robots_txt=True,
        )
        result = Crawler(config).crawl()
        # /secret is in no sitemap, but also disallowed. Either way it must not appear.
        assert not any(u.endswith("/secret") for u in result.pages)
