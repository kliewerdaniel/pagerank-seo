"""Tests for the SDK's internal helpers (URL normalization, depth)."""
from __future__ import annotations

import pytest

from pagerank_seo.utils import normalize_url, same_origin, url_depth


class TestNormalizeUrl:
    def test_lowercase_scheme_host(self):
        assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"

    def test_drop_default_https_port(self):
        assert normalize_url("https://example.com:443/x") == "https://example.com/x"

    def test_drop_default_http_port(self):
        assert normalize_url("http://example.com:80/x") == "http://example.com/x"

    def test_drop_trailing_slash(self):
        assert normalize_url("https://example.com/x/") == "https://example.com/x"

    def test_preserve_root_slash(self):
        assert normalize_url("https://example.com/") == "https://example.com/"

    def test_sort_query(self):
        a = normalize_url("https://example.com/x?b=2&a=1")
        b = normalize_url("https://example.com/x?a=1&b=2")
        assert a == b
        assert a == "https://example.com/x?a=1&b=2"

    def test_drop_fragment(self):
        assert normalize_url("https://example.com/x#section") == "https://example.com/x"

    def test_empty_string(self):
        assert normalize_url("") == ""

    def test_garbage_does_not_crash(self):
        # Malformed URLs are returned as-is rather than raising.
        out = normalize_url("http://[invalid")
        assert out == "http://[invalid"


class TestUrlDepth:
    def test_root(self):
        assert url_depth("https://example.com/") == 0
        assert url_depth("https://example.com") == 0

    def test_one_level(self):
        assert url_depth("https://example.com/foo") == 1

    def test_three_levels(self):
        assert url_depth("https://example.com/foo/bar/baz") == 3


class TestSameOrigin:
    def test_same_origin(self):
        assert same_origin("https://example.com/a", "https://example.com/b")

    def test_different_host(self):
        assert not same_origin("https://example.com/a", "https://other.com/a")

    def test_different_scheme(self):
        assert not same_origin("http://example.com/a", "https://example.com/a")
