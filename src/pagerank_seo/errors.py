"""Custom exception hierarchy for the SDK.

All SDK errors derive from ``CrawlError`` so callers can catch broadly.
Granular subclasses let callers handle specific failure modes (e.g. skip
a page with a parse error but keep crawling).
"""
from __future__ import annotations


class CrawlError(Exception):
    """Base class for all pagerank-seo errors."""


class FetchError(CrawlError):
    """A network-level failure fetching a URL (timeout, DNS, 5xx, etc.)."""


class ParseError(CrawlError):
    """A failure parsing the response body (malformed HTML beyond tolerance)."""


class RobotsTxtError(CrawlError):
    """A failure parsing the site's robots.txt."""


class SitemapError(CrawlError):
    """A failure parsing the site's XML sitemap."""
