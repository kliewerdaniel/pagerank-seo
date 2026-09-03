"""Pytest fixtures available to every test in the suite."""
from __future__ import annotations

import sys
from pathlib import Path

# Make the tests/ directory importable so we can do ``from fixtures import synthetic_sites``.
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

import pytest  # noqa: E402

from fixtures import synthetic_sites  # noqa: E402

from pagerank_seo.auditor import SiteAuditor  # noqa: E402
from pagerank_seo.models import AuditConfig  # noqa: E402


@pytest.fixture
def tiny_site():
    return synthetic_sites.tiny_clean_site()


@pytest.fixture
def orphan_site():
    return synthetic_sites.site_with_orphan()


@pytest.fixture
def malformed_site():
    return synthetic_sites.site_with_malformed_page()


@pytest.fixture
def cycle_site():
    return synthetic_sites.cycle_site()


@pytest.fixture
def island_site():
    return synthetic_sites.island_site()


@pytest.fixture
def default_auditor():
    return SiteAuditor(AuditConfig(start_url="https://acme.example/"))
