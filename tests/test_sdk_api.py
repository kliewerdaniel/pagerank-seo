"""Tests for the high-level SDK API: SiteAuditor, models, end-to-end."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from fixtures import synthetic_sites
from pagerank_seo.auditor import SiteAuditor
from pagerank_seo.models import (
    AuditConfig,
    AuditReport,
    CrawlResult,
    Page,
    Priority,
)
from pagerank_seo.report import to_html, to_json, to_markdown


class TestAuditConfig:
    def test_minimal_config(self):
        cfg = AuditConfig(start_url="https://example.com/")
        assert cfg.max_pages == 50
        assert cfg.max_depth == 3

    def test_invalid_max_pages(self):
        with pytest.raises(ValueError):
            AuditConfig(start_url="https://example.com/", max_pages=0)

    def test_invalid_max_depth(self):
        with pytest.raises(ValueError):
            AuditConfig(start_url="https://example.com/", max_depth=-1)

    def test_invalid_url_scheme(self):
        with pytest.raises(ValueError):
            AuditConfig(start_url="example.com/")

    def test_invalid_timeout(self):
        with pytest.raises(ValueError):
            AuditConfig(start_url="https://example.com/", request_timeout_seconds=0)


class TestSiteAuditorPhases:
    """Each phase of the audit can be invoked individually."""

    def test_build_graph_phase(self, tiny_site):
        auditor = SiteAuditor(AuditConfig(start_url=tiny_site.start_url))
        graph = auditor.build_graph(tiny_site)
        assert graph.metrics.node_count == len(tiny_site.pages)

    def test_analyze_phase(self, tiny_site):
        auditor = SiteAuditor(AuditConfig(start_url=tiny_site.start_url))
        graph = auditor.build_graph(tiny_site)
        findings = auditor.analyze(tiny_site, graph)
        assert isinstance(findings, list)

    def test_score_phase(self, tiny_site):
        auditor = SiteAuditor(AuditConfig(start_url=tiny_site.start_url))
        graph = auditor.build_graph(tiny_site)
        scores, composite = auditor.score(tiny_site, graph)
        assert isinstance(scores, list)
        assert isinstance(composite, float)

    def test_recommend_phase(self, tiny_site):
        auditor = SiteAuditor(AuditConfig(start_url=tiny_site.start_url))
        graph = auditor.build_graph(tiny_site)
        findings = auditor.analyze(tiny_site, graph)
        recs = auditor.recommend(findings, tiny_site, graph)
        assert isinstance(recs, list)


class TestEndToEnd:
    def test_full_audit_on_synthetic_site(self, orphan_site):
        auditor = SiteAuditor(AuditConfig(start_url=orphan_site.start_url))
        report = auditor.audit()
        assert isinstance(report, AuditReport)
        assert report.composite_score > 0
        assert len(report.findings) > 0
        assert len(report.recommendations) > 0
        assert len(report.scores) == 10
        assert report.generated_at_iso


class TestReportRenderers:
    @pytest.fixture
    def report(self, orphan_site):
        auditor = SiteAuditor(AuditConfig(start_url=orphan_site.start_url))
        return auditor.audit()

    def test_json_round_trip(self, report):
        text = to_json(report)
        # Should be valid JSON
        parsed = json.loads(text)
        assert parsed["composite_score"] == report.composite_score
        assert parsed["config"]["start_url"] == report.config.start_url

    def test_markdown_contains_key_sections(self, report):
        text = to_markdown(report)
        assert "PageRank SEO Audit Report" in text
        assert "Composite Score" in text
        assert "Recommendations" in text
        assert "Graph Summary" in text
        # Every recommendation priority should appear
        for r in report.recommendations:
            assert r.priority.value in text

    def test_html_is_self_contained(self, report):
        html = to_html(report)
        assert "<!DOCTYPE html>" in html
        assert "Composite" in html
        assert html.count("<tr>") > 5  # at least the dimension table + top PageRank table
        # No external resource references (we embed CSS)
        assert "http://" not in html.replace("http://", "", 1)  # tolerate start URL
        # Specifically: no <link rel="stylesheet"
        assert 'rel="stylesheet"' not in html


class TestSerializationStability:
    def test_to_dict_handles_enums(self, orphan_site):
        auditor = SiteAuditor(AuditConfig(start_url=orphan_site.start_url))
        report = auditor.audit()
        d = report.to_dict()
        # All enum values should be strings (not Enum objects)
        assert d["crawl"]["start_url"] == orphan_site.start_url
        # Check that a recommendation priority serialized to string
        for r in d["recommendations"]:
            assert r["priority"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
            assert isinstance(r["priority"], str)
