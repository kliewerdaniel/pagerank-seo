"""Tests for the CLI: argument parsing, exit codes, output formats."""
from __future__ import annotations

import json
import sys
from io import StringIO

import pytest

from pagerank_seo.cli import main


def test_version(capsys):
    rc = main(["--version"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "pagerank-seo" in captured.out


def test_help(capsys):
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "usage" in captured.out.lower() or "audit" in captured.out.lower()


def test_audit_unknown_format(capsys):
    rc = main([
        "audit", "https://example.com/",
        "--output", "xml",
        "--max-pages", "1",
        "--max-depth", "0",
        "--rate", "5",
    ])
    captured = capsys.readouterr()
    assert rc == 2
    assert "unknown format" in captured.err.lower()


def test_audit_invalid_url(capsys):
    """An invalid URL scheme should be rejected with a clear error."""
    rc = main(["audit", "not-a-url"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "invalid configuration" in captured.err.lower()
