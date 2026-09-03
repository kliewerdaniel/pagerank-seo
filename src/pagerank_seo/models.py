"""Public SDK model types.

All audit results are returned as instances of these dataclasses so that
SDK consumers (CI, agents, web apps) get structured, type-stable data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Priority(str, Enum):
    """Recommendation priority band.

    Strings serialize cleanly to JSON/YAML; the enum keeps consumers from
    passing arbitrary strings.
    """
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RelType(str, Enum):
    """The ``rel`` attribute(s) on an ``<a>`` tag relevant to link-graph analysis.

    Following Google Search Central: ``nofollow``, ``sponsored``, and ``ugc`` are
    treated as weight-reduction hints (not removals).
    """
    DOFOLLOW = "dofollow"
    NOFOLLOW = "nofollow"
    SPONSORED = "sponsored"
    UGC = "ugc"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class AuditConfig:
    """Runtime configuration for an audit.

    All bounds are conservative defaults. The crawler is non-aggressive by
    design — see ``docs/security.md`` and the skill SKILL.md for safe usage.
    """
    start_url: str
    max_pages: int = 50
    max_depth: int = 3
    request_timeout_seconds: float = 10.0
    requests_per_second: float = 2.0
    user_agent: str = "pagerank-seo/0.1 (+https://github.com/kliewerdaniel/pagerank-seo)"
    respect_robots_txt: bool = True
    follow_external_links: bool = False
    allowed_domain_suffixes: tuple[str, ...] = ()
    max_document_bytes: int = 5_000_000  # 5 MiB cap per document
    max_redirects: int = 5

    def __post_init__(self) -> None:
        if self.max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        if self.max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be > 0")
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be > 0")
        if not self.start_url.lower().startswith(("http://", "https://")):
            raise ValueError("start_url must be an http(s) URL")


# ---------------------------------------------------------------------------
# Crawl artifacts
# ---------------------------------------------------------------------------


@dataclass
class Link:
    """A directed hyperlink discovered on a page.

    ``anchor`` is the visible anchor text (None if the ``<a>`` had no text,
    e.g. an icon-only link). ``position_weight`` is a heuristic from the
    parser indicating how prominent the link is in the page (1.0 for
    navigation, 0.5 for body, 0.25 for footer). See ``parser.py``.
    """
    source_url: str
    target_url: str
    anchor: Optional[str] = None
    rel: RelType = RelType.DOFOLLOW
    position_weight: float = 0.5
    in_navigation: bool = False


@dataclass
class Page:
    """A crawled page with all extracted properties.

    All fields default to safe empty values so a partial extraction never
    crashes downstream analysis. The analyzer treats ``None``/empty as
    'unknown / not present' and decides whether to flag accordingly.
    """
    url: str
    status_code: int = 0
    content_type: str = ""
    raw_html: str = ""
    title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical_url: Optional[str] = None
    robots_meta: Optional[str] = None
    lang: Optional[str] = None
    viewport_meta: Optional[str] = None
    charset: Optional[str] = None
    h1: Optional[str] = None
    headings: list[tuple[int, str]] = field(default_factory=list)
    json_ld_blocks: list[dict] = field(default_factory=list)
    images_without_alt: int = 0
    images_total: int = 0
    has_nav: bool = False
    has_main: bool = False
    has_header: bool = False
    has_footer: bool = False
    text_word_count: int = 0
    outgoing_links: list[Link] = field(default_factory=list)
    depth: int = 0
    error: Optional[str] = None
    redirected_from: Optional[str] = None


@dataclass
class CrawlResult:
    """The full set of pages and edges discovered during a crawl."""
    start_url: str
    pages: dict[str, Page]  # canonical_url -> Page
    edges: list[Link]
    robots_txt: Optional[str] = None
    sitemap_urls: list[str] = field(default_factory=list)
    pages_fetched: int = 0
    pages_failed: int = 0
    crawl_elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Graph metrics
# ---------------------------------------------------------------------------


@dataclass
class GraphMetrics:
    """Pre-computed graph metrics for the crawled graph.

    All PageRank values are raw, not normalized to a 0-100 scale. The
    ``gini_pagerank`` and ``top1_share`` are normalized statistics.
    """
    node_count: int
    edge_count: int
    pagerank: dict[str, float]      # url -> raw PageRank
    weighted_pagerank: dict[str, float]
    in_degree: dict[str, int]
    out_degree: dict[str, int]
    weakly_connected_components: int
    orphan_pages: list[str]         # pages with in-degree 0 (excluding the seed if applicable)
    gini_pagerank: float
    top1_share: float               # share of total PageRank held by the highest-PR page
    has_cycle: bool
    strongly_connected_components: int


# ---------------------------------------------------------------------------
# Analysis results
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A single observed property of the site that is informative.

    Findings are neutral observations (e.g. "page X has 0 inbound links").
    They are not recommendations in themselves — recommendations reference
    findings as evidence.
    """
    layer: str       # one of: technical | ia | graph | semantic | ux | reputation
    code: str        # short stable code, e.g. "ORPHAN_PAGE"
    message: str
    evidence_urls: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


@dataclass
class Recommendation:
    """A prioritized, actionable recommendation.

    Each recommendation references one or more findings via ``evidence``.
    ``verification_method`` describes how to confirm the change worked.
    """
    priority: Priority
    finding: str
    evidence: list[str] = field(default_factory=list)  # finding codes
    recommended_action: str = ""
    impact: str = "medium"   # informational: high | medium | low
    confidence: str = "medium"  # informational: high | medium | low
    implementation_difficulty: str = "medium"
    verification_method: str = ""
    affected_urls: list[str] = field(default_factory=list)


@dataclass
class DimensionScore:
    """A single dimension of the PageRank SEO Health Score."""
    name: str
    score: float
    weight: float
    rationale: str


@dataclass
class SiteGraph:
    """The site's directed link graph as analyzed."""
    pages: dict[str, Page]
    metrics: GraphMetrics


@dataclass
class AuditReport:
    """The full output of a SEO audit."""
    config: AuditConfig
    crawl: CrawlResult
    graph: SiteGraph
    findings: list[Finding]
    recommendations: list[Recommendation]
    scores: list[DimensionScore]
    composite_score: float
    generated_at_iso: str

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict (enum values as strings)."""
        from dataclasses import asdict
        from pagerank_seo.utils import _stringify_enums
        return _stringify_enums(asdict(self))
