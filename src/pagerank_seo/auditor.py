"""The high-level auditor: orchestrates crawl → analyze → score → recommend.

This is the SDK's main entrypoint for programmatic use:

    from pagerank_seo import AuditConfig
    from pagerank_seo.auditor import SiteAuditor

    auditor = SiteAuditor(AuditConfig(start_url="https://example.com"))
    report = auditor.audit()

The auditor also exposes individual phases so a consumer (Hermes skill,
CI pipeline, web app) can run partial audits — e.g. reuse an existing
crawl result without re-fetching.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pagerank_seo.analyzer import analyze
from pagerank_seo.crawler import Crawler, Fetcher
from pagerank_seo.graph import to_site_graph
from pagerank_seo.models import (
    AuditConfig,
    AuditReport,
    CrawlResult,
    Finding,
    Recommendation,
    SiteGraph,
)
from pagerank_seo.recommendations import build_recommendations
from pagerank_seo.scoring import compute_scores
from pagerank_seo.quality_analyzer import analyze_search_quality
from pagerank_seo.quality import SearchQualityReport


class SiteAuditor:
    """The main entrypoint for running a PageRank SEO audit."""

    def __init__(
        self,
        config: AuditConfig,
        *,
        progress_callback=None,
        fetcher: Optional[Fetcher] = None,
    ):
        self.config = config
        self.progress_callback = progress_callback
        self._fetcher = fetcher

    # ------------------------------------------------------------------
    # Public phases
    # ------------------------------------------------------------------

    def crawl(self) -> CrawlResult:
        """Run the BFS crawl and return the raw crawl result."""
        crawler = Crawler(
            self.config,
            fetcher=self._fetcher,
            progress_callback=self.progress_callback,
        )
        return crawler.crawl()

    def build_graph(self, crawl: CrawlResult) -> SiteGraph:
        """Construct the link graph from a crawl result."""
        return to_site_graph(crawl)

    def analyze(self, crawl: CrawlResult, graph: SiteGraph) -> list[Finding]:
        """Run all analyzer checks."""
        return analyze(crawl, graph)

    def analyze_quality(self, crawl: CrawlResult) -> SearchQualityReport:
        """Run the search quality analysis (page purpose, E-E-A-T, etc.)."""
        return analyze_search_quality(crawl)

    def score(self, crawl: CrawlResult, graph: SiteGraph) -> tuple[list, float]:
        """Compute the PageRank SEO Health Score dimensions + composite."""
        return compute_scores(crawl, graph)

    def recommend(
        self,
        findings: list[Finding],
        crawl: CrawlResult,
        graph: SiteGraph,
    ) -> list[Recommendation]:
        """Translate findings into prioritized recommendations."""
        return build_recommendations(findings, crawl, graph)

    # ------------------------------------------------------------------
    # End-to-end
    # ------------------------------------------------------------------

    def audit(self) -> AuditReport:
        """Run the full DISCOVER → ANALYZE → SCORE → RECOMMEND pipeline."""
        crawl = self.crawl()
        graph = self.build_graph(crawl)
        findings = self.analyze(crawl, graph)
        scores, composite = self.score(crawl, graph)
        recommendations = self.recommend(findings, crawl, graph)
        return AuditReport(
            config=self.config,
            crawl=crawl,
            graph=graph,
            findings=findings,
            recommendations=recommendations,
            scores=scores,
            composite_score=composite,
            generated_at_iso=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    def audit_with_quality(self) -> tuple[AuditReport, SearchQualityReport]:
        """Run the full audit plus the search quality analysis.

        This is the recommended entrypoint for agents that need both
        the graph-theoretic audit and the search quality evaluation.
        """
        crawl = self.crawl()
        graph = self.build_graph(crawl)
        findings = self.analyze(crawl, graph)
        scores, composite = self.score(crawl, graph)
        recommendations = self.recommend(findings, crawl, graph)
        quality = self.analyze_quality(crawl)
        report = AuditReport(
            config=self.config,
            crawl=crawl,
            graph=graph,
            findings=findings,
            recommendations=recommendations,
            scores=scores,
            composite_score=composite,
            generated_at_iso=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        return report, quality
