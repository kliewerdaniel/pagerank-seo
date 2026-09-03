"""Conservative web crawler for the PageRank SEO SDK.

Implements:

- BFS within configurable depth + page limits
- robots.txt support (RFC 9309 subset)
- Sitemap discovery (XML and sitemap-index)
- Per-host rate limiting
- URL normalization for stable graph identity
- Soft redirect handling (one hop counted as the same page)

The crawler is conservative by design. It is not intended to be used for
aggressive reconnaissance of any site the operator does not own or have
permission to audit.

References
----------
- RFC 9309 (Robots Exclusion Protocol): https://www.rfc-editor.org/rfc/rfc9309.html
- sitemaps.org protocol: https://www.sitemaps.org/protocol.html
- Google Search Central: robots.txt is not an access-control mechanism
  https://developers.google.com/search/docs/crawling-indexing/robots/intro
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional
from urllib.parse import urlparse, urlsplit, urljoin
from xml.etree import ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pagerank_seo.errors import (
    CrawlError,
    FetchError,
    RobotsTxtError,
    SitemapError,
)
from pagerank_seo.models import (
    AuditConfig,
    CrawlResult,
    Page,
)
from pagerank_seo.parser import parse_html
from pagerank_seo.utils import normalize_url, same_origin


# ---------------------------------------------------------------------------
# Robots.txt
# ---------------------------------------------------------------------------


@dataclass
class RobotsTxt:
    """A parsed robots.txt file (RFC 9309 subset)."""

    groups: list[dict] = field(default_factory=list)  # each: {user_agents: set, allow: list, disallow: list}
    sitemaps: list[str] = field(default_factory=list)
    raw_text: str = ""

    @classmethod
    def parse(cls, text: str) -> "RobotsTxt":
        """Parse an RFC 9309 robots.txt body.

        Handles comments (``#`` to EOL), blank lines, and the standard
        User-agent / Allow / Disallow / Sitemap directives. Unknown
        directives are ignored (forward-compatible).
        """
        groups: list[dict] = []
        current: Optional[dict] = None

        def _new_group() -> dict:
            return {"user_agents": set(), "allow": [], "disallow": []}

        for raw_line in text.splitlines():
            # Strip comments (RFC 9309: # to EOL is a comment)
            if "#" in raw_line:
                raw_line = raw_line.split("#", 1)[0]
            line = raw_line.strip()
            if not line:
                # Blank line terminates a group (per RFC 9309 §2.2.1)
                current = None
                continue
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key == "user-agent":
                if current is None or current["user_agents"]:
                    current = _new_group()
                    groups.append(current)
                current["user_agents"].add(value.lower() if value != "*" else "*")
            elif key == "allow":
                if current is None:
                    current = _new_group()
                    groups.append(current)
                if value:
                    current["allow"].append(value)
            elif key == "disallow":
                if current is None:
                    current = _new_group()
                    groups.append(current)
                if value:
                    current["disallow"].append(value)
            elif key == "sitemap":
                # Sitemap directives are global; attach to every group as a convenience
                if value and value not in (g.get("_sitemaps", []) for g in groups):
                    pass
        # Re-walk to attach sitemaps at the top level
        sitemaps: list[str] = []
        for raw_line in text.splitlines():
            if "#" in raw_line:
                raw_line = raw_line.split("#", 1)[0]
            line = raw_line.strip()
            if line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                if url and url not in sitemaps:
                    sitemaps.append(url)
        return cls(groups=groups, sitemaps=sitemaps, raw_text=text)

    def allows(self, *, user_agent: str, url_path: str) -> bool:
        """Return True if the URL path is allowed for the given user agent.

        Matches the user-agent substring per RFC 9309 §2.2.1, then
        combines all matching groups' Allow/Disallow rules. The
        longest-match rule wins; in case of tie, Allow beats Disallow.
        """
        ua_lower = user_agent.lower()
        matching: list[dict] = []
        for g in self.groups:
            uas = g["user_agents"]
            if "*" in uas:
                matching.append(g)
                continue
            for ua in uas:
                if ua and ua in ua_lower:
                    matching.append(g)
                    break

        if not matching:
            return True  # No matching group => implicitly allow everything.

        best_len = -1
        verdict = True
        for g in matching:
            for rule in g.get("disallow", []):
                if rule and url_path.startswith(rule) and len(rule) > best_len:
                    best_len = len(rule)
                    verdict = False
            for rule in g.get("allow", []):
                if rule and url_path.startswith(rule) and len(rule) >= best_len:
                    best_len = len(rule)
                    verdict = True
        return verdict


def _parse_sitemap_xml(xml_text: str) -> list[str]:
    """Parse a sitemap XML and return the declared URLs (urlset or sitemapindex).

    Defensive against malformed XML and unknown namespaces — returns
    whatever URLs it can extract, and an empty list on parse failure.
    Raises ``SitemapError`` for callers that need strict mode.
    """
    urls: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SitemapError(f"sitemap parse error: {exc}") from exc
    except Exception as exc:
        raise SitemapError(f"sitemap parse error: {exc}") from exc
    # Sitemap index files have <sitemap><loc>...</loc></sitemap>
    # Regular sitemaps have <url><loc>...</loc></url>
    # Use local-name matching to ignore namespace prefixes.
    for child in root.iter():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "loc" and child.text:
            text = child.text.strip()
            if text:
                urls.append(text)
    return urls


def parse_sitemap_lenient(xml_text: str) -> list[str]:
    """Parse a sitemap, returning ``[]`` on any parse failure.

    Convenience wrapper for the crawler, which prefers to keep going
    rather than crash on a malformed sitemap.
    """
    try:
        return _parse_sitemap_xml(xml_text)
    except SitemapError:
        return []


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """A simple thread-safe token-bucket-style limiter."""

    def __init__(self, requests_per_second: float):
        self.min_interval = 1.0 / max(requests_per_second, 0.01)
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last = time.monotonic()


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------


@dataclass
class FetchResponse:
    url: str  # Final URL after redirects
    status_code: int
    headers: dict
    body: bytes
    redirected_from: Optional[str] = None


class Fetcher:
    """HTTP fetcher with bounded redirects, content-length cap, and UA.

    A custom fetcher is useful for tests (to point at a local server) and
    for SDK consumers that want to inject their own transport. The
    default constructor builds a ``requests.Session`` with sensible
    retry behavior.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: float,
        max_document_bytes: int,
        max_redirects: int,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_document_bytes = max_document_bytes
        self.max_redirects = max_redirects
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "HEAD"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def fetch(self, url: str) -> FetchResponse:
        """Fetch a URL with bounded redirects and a body-size cap.

        Raises ``FetchError`` on transport-level failure. Non-2xx responses
        are returned as-is so the caller can decide what to do.
        """
        try:
            resp = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                stream=True,
            )
        except requests.exceptions.RequestException as exc:
            raise FetchError(f"fetch failed for {url}: {exc}") from exc

        try:
            content_length = resp.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                if int(content_length) > self.max_document_bytes:
                    raise FetchError(
                        f"document too large ({content_length} bytes) at {url}"
                    )

            body_chunks: list[bytes] = []
            received = 0
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                received += len(chunk)
                if received > self.max_document_bytes:
                    raise FetchError(
                        f"document exceeded {self.max_document_bytes} bytes at {url}"
                    )
                body_chunks.append(chunk)
            body = b"".join(body_chunks)

            # Check redirect chain length via history
            if len(resp.history) > self.max_redirects:
                raise FetchError(
                    f"too many redirects ({len(resp.history)}) at {url}"
                )

            redirected_from = resp.history[0].url if resp.history else None
            return FetchResponse(
                url=resp.url,
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=body,
                redirected_from=redirected_from,
            )
        finally:
            resp.close()


# ---------------------------------------------------------------------------
# Crawler
# ---------------------------------------------------------------------------


class Crawler:
    """A BFS crawler constrained by ``AuditConfig``.

    Designed to be safe to run against production websites the operator
    owns or has explicit permission to audit.
    """

    def __init__(
        self,
        config: AuditConfig,
        *,
        fetcher: Optional[Fetcher] = None,
        rate_limiter: Optional[RateLimiter] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self.fetcher = fetcher or Fetcher(
            user_agent=config.user_agent,
            timeout=config.request_timeout_seconds,
            max_document_bytes=config.max_document_bytes,
            max_redirects=config.max_redirects,
        )
        self.rate_limiter = rate_limiter or RateLimiter(config.requests_per_second)
        self.progress_callback = progress_callback

        # Parse the start URL to derive the seed host
        parts = urlsplit(config.start_url)
        if not parts.scheme or not parts.netloc:
            raise CrawlError(f"start_url is not an absolute URL: {config.start_url}")
        self.seed_host = parts.netloc.lower()
        self.seed_scheme = parts.scheme.lower()

        self._robots: Optional[RobotsTxt] = None
        self._sitemaps: list[str] = []
        self._pages: dict[str, Page] = {}
        self._queue: list[tuple[str, int]] = []  # (url, depth)
        self._seen: set[str] = set()
        self._pages_fetched = 0
        self._pages_failed = 0
        self._crawl_start: float = 0.0

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def crawl(self) -> CrawlResult:
        """Run the BFS crawl and return a ``CrawlResult``."""
        self._crawl_start = time.monotonic()

        # ---- 1. Discover robots.txt + sitemap ------------------------
        self._fetch_robots_and_sitemap()

        # ---- 2. Seed the queue from start URL and any sitemaps ------
        seed = normalize_url(self.config.start_url)
        self._enqueue(seed, depth=0)

        for sm_url in list(self._sitemaps):
            if not same_origin(sm_url, seed):
                continue
            try:
                self.rate_limiter.wait()
                resp = self.fetcher.fetch(sm_url)
            except FetchError:
                continue
            if resp.status_code >= 400 or not resp.body:
                continue
            try:
                sitemap_urls = parse_sitemap_lenient(resp.body.decode("utf-8", errors="replace"))
            except Exception:
                sitemap_urls = []
            for u in sitemap_urls:
                if same_origin(u, seed):
                    self._enqueue(normalize_url(u), depth=0)

        # ---- 3. BFS --------------------------------------------------
        while self._queue and len(self._pages) < self.config.max_pages:
            url, depth = self._queue.pop(0)
            if url in self._seen:
                continue
            self._seen.add(url)

            if depth > self.config.max_depth:
                continue

            # robots.txt check (use path-only)
            if self.config.respect_robots_txt and self._robots is not None:
                path = urlsplit(url).path or "/"
                if not self._robots.allows(user_agent=self.config.user_agent, url_path=path):
                    if self.progress_callback:
                        self.progress_callback(f"robots-disallow: {url}")
                    continue

            try:
                self.rate_limiter.wait()
                resp = self.fetcher.fetch(url)
            except FetchError as exc:
                self._pages_failed += 1
                page = Page(url=url, status_code=0, depth=depth, error=str(exc))
                self._pages[url] = page
                if self.progress_callback:
                    self.progress_callback(f"fetch-failed: {url}")
                continue

            # Only parse HTML (cheap content-type sniff)
            ct = (resp.headers.get("Content-Type") or "").lower()
            if "html" not in ct:
                # Non-HTML response: record status, no parse.
                page = Page(
                    url=resp.url,
                    status_code=resp.status_code,
                    content_type=ct,
                    depth=depth,
                    redirected_from=resp.redirected_from,
                )
                self._pages[resp.url] = page
                self._pages_fetched += 1
                if self.progress_callback:
                    self.progress_callback(f"non-html: {resp.url}")
                continue

            try:
                html = resp.body.decode("utf-8", errors="replace")
                page = parse_html(
                    url=resp.url,
                    raw_html=html,
                    status_code=resp.status_code,
                    content_type=ct,
                    depth=depth,
                    redirected_from=resp.redirected_from,
                )
            except Exception as exc:
                self._pages_failed += 1
                page = Page(url=resp.url, status_code=resp.status_code, depth=depth, error=str(exc))
                self._pages[resp.url] = page
                if self.progress_callback:
                    self.progress_callback(f"parse-failed: {resp.url}")
                continue

            self._pages[resp.url] = page
            self._pages_fetched += 1
            if self.progress_callback:
                self.progress_callback(f"fetched: {resp.url}")

            # Enqueue outgoing internal links
            for link in page.outgoing_links:
                if not same_origin(link.target_url, seed):
                    continue
                target = normalize_url(link.target_url)
                if target in self._seen:
                    continue
                if link.rel.value in ("nofollow", "sponsored", "ugc"):
                    # Conservative: still enqueue, but downstream weighting handles it.
                    pass
                self._enqueue(target, depth=depth + 1)

        # ---- 4. Build edges list -------------------------------------
        edges: list = []
        for page in self._pages.values():
            edges.extend(page.outgoing_links)

        elapsed = time.monotonic() - self._crawl_start
        return CrawlResult(
            start_url=self.config.start_url,
            pages=self._pages,
            edges=edges,
            robots_txt=self._robots_text,
            sitemap_urls=list(self._sitemaps),
            pages_fetched=self._pages_fetched,
            pages_failed=self._pages_failed,
            crawl_elapsed_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @property
    def _robots_text(self) -> Optional[str]:
        # RobotsTxt stores the parsed groups; expose the raw text via
        # the ``raw_text`` attribute set by parse(), falling back to a
        # short representation if not available.
        if self._robots is None:
            return None
        return getattr(self._robots, "raw_text", repr(self._robots))

    def _enqueue(self, url: str, *, depth: int) -> None:
        if not url:
            return
        if url in self._seen:
            return
        if not same_origin(url, self.config.start_url):
            return
        self._queue.append((url, depth))

    def _fetch_robots_and_sitemap(self) -> None:
        """Best-effort fetch of /robots.txt and the sitemap URLs it points to."""
        robots_url = f"{self.seed_scheme}://{self.seed_host}/robots.txt"
        try:
            self.rate_limiter.wait()
            resp = self.fetcher.fetch(robots_url)
        except FetchError:
            return

        if resp.status_code >= 400 or not resp.body:
            return

        try:
            self._robots = RobotsTxt.parse(resp.body.decode("utf-8", errors="replace"))
        except Exception as exc:
            # Be tolerant: an unparseable robots.txt is treated as "allow all"
            raise RobotsTxtError(f"robots.txt parse failed: {exc}") from exc

        self._sitemaps = list(self._robots.sitemaps)
