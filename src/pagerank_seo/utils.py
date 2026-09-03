"""Internal SDK utilities (not part of the public API)."""
from __future__ import annotations

from enum import Enum
from typing import Any


def _stringify_enums(obj: Any) -> Any:
    """Recursively convert Enum values to their ``.value`` (string)."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _stringify_enums(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_stringify_enums(x) for x in obj]
    return obj


def normalize_url(url: str, base: str | None = None) -> str:
    """Normalize a URL for graph identity.

    Steps (defensive; we don't try to be RFC-3986-perfect):
        1. Strip whitespace.
        2. Resolve relative references against ``base``.
        3. Lowercase the scheme and host.
        4. Drop the default port (:80 for http, :443 for https).
        5. Drop trailing slash from the path (except for the bare "/").
        6. Sort query parameters by name (for stable identity).
        7. Drop the URL fragment.

    Returns the original string if normalization fails (so a malformed
    URL still gets recorded as itself rather than disappearing).
    """
    from urllib.parse import urlsplit, urlunsplit, urljoin

    try:
        url = (url or "").strip()
        if not url:
            return url
        if base:
            url = urljoin(base, url)
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()
        if (scheme == "http" and netloc.endswith(":80")) or (
            scheme == "https" and netloc.endswith(":443")
        ):
            netloc = netloc.rsplit(":", 1)[0]
        path = parts.path or "/"
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        query_pairs = []
        if parts.query:
            for kv in parts.query.split("&"):
                if not kv:
                    continue
                if "=" in kv:
                    k, v = kv.split("=", 1)
                else:
                    k, v = kv, ""
                query_pairs.append((k, v))
            query_pairs.sort()
            query = "&".join(f"{k}={v}" if v else k for k, v in query_pairs)
        else:
            query = ""
        return urlunsplit((scheme, netloc, path, query, ""))
    except Exception:
        return url


def url_depth(url: str) -> int:
    """Return the URL path-segment depth (excluding the root)."""
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    path = parts.path.strip("/")
    if not path:
        return 0
    return len([seg for seg in path.split("/") if seg])


def same_origin(url_a: str, url_b: str) -> bool:
    """True if two URLs share scheme + host (+port). Path/query irrelevant."""
    from urllib.parse import urlsplit
    a, b = urlsplit(url_a), urlsplit(url_b)
    return (a.scheme.lower(), a.hostname.lower() if a.hostname else "") == (
        b.scheme.lower(),
        b.hostname.lower() if b.hostname else "",
    )
