"""pagerank-seo — PageRank-oriented SEO analysis SDK.

Turn a website into an information graph and produce prioritized,
evidence-traceable recommendations.

PageRank values are an internal analytical metric, not Google's ranking
signal. Recommendations are grounded in public documentation (Google Search
Central, W3C, schema.org, the original PageRank paper) and engineering
best practice.
"""
from pagerank_seo.models import (
    AuditConfig,
    AuditReport,
    CrawlResult,
    DimensionScore,
    Finding,
    GraphMetrics,
    Link,
    Page,
    Priority,
    Recommendation,
    RelType,
    SiteGraph,
)
from pagerank_seo.quality import (
    ContentClassification,
    EEATAnalysis,
    NeedsMetAnalysis,
    NeedsMetLevel,
    OriginalityAnalysis,
    PagePurpose,
    PagePurposeType,
    PageQualityReport,
    QueryIntent,
    QueryIntentType,
    ReputationAnalysis,
    ReputationSignal,
    ReputationSignalType,
    ScaledContentPattern,
    SearchQualityReport,
)

__version__ = "0.2.0"

__all__ = [
    "AuditConfig",
    "AuditReport",
    "CrawlResult",
    "DimensionScore",
    "Finding",
    "GraphMetrics",
    "Link",
    "Page",
    "Priority",
    "Recommendation",
    "RelType",
    "SiteGraph",
    # Search quality
    "ContentClassification",
    "EEATAnalysis",
    "NeedsMetAnalysis",
    "NeedsMetLevel",
    "OriginalityAnalysis",
    "PagePurpose",
    "PagePurposeType",
    "PageQualityReport",
    "QueryIntent",
    "QueryIntentType",
    "ReputationAnalysis",
    "ReputationSignal",
    "ReputationSignalType",
    "ScaledContentPattern",
    "SearchQualityReport",
]
