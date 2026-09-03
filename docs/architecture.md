# PageRank SEO — Architecture

> Version 0.2.0 — Search Quality Framework integrated

## System overview

```
                    PAGE RANK SEO ENGINE
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
       CRAWLER           ANALYZER          SDK
          │                 │                 │
          │        ┌────────┼────────┐        │
          │        │        │        │        │
          │      GRAPH    QUALITY   INTENT    │
          │        │        │        │        │
          │        │        │        │        │
          └────────┴────────┴────────┴────────┘
                            │
                     RECOMMENDATIONS
                            │
                       HERMES SKILL
                            │
                       IMPLEMENTATION
                            │
                       RE-AUDIT
```

## Module layout

```
pagerank_seo/
├── __init__.py              # Public API exports
├── models.py                # Core dataclasses (AuditConfig, Page, Link, GraphMetrics, ...)
├── quality.py               # Search quality dataclasses (PagePurpose, EEAT, Originality, ...)
├── crawler.py               # BFS crawl, robots.txt, rate-limit
├── parser.py                # HTML parsing, metadata, structured data, links
├── graph.py                 # NetworkX graph builder, PageRank, centrality
├── analyzer.py              # Six-layer analyzer + search quality findings
├── quality_analyzer.py      # Page purpose, content classification, reputation, E-E-A-T
├── scoring.py               # 10-dimension PageRank SEO Health Score
├── recommendations.py       # Prioritized, evidence-traceable recommendations
├── report.py                # JSON / Markdown / HTML renderers
├── cli.py                   # pagerank-seo audit <url>
├── errors.py                # Exception types
└── utils.py                 # URL normalization, depth, same-origin
```

## Data flow

```
URL → Crawler.crawl() → CrawlResult
                          │
                          ├─→ build_graph() → SiteGraph (NetworkX + metrics)
                          │
                          ├─→ analyze() → list[Finding]
                          │     └─ per-page: technical, semantic, ux
                          │     └─ site-level: ia, graph, duplicate titles, reputation
                          │     └─ per-page: search quality (purpose, content, eeat, originality)
                          │     └─ site-level: scaled content
                          │
                          ├─→ analyze_quality() → SearchQualityReport
                          │     └─ per-page: PageQualityReport
                          │     └─ site-level: ScaledContentPattern
                          │
                          ├─→ score() → (list[DimensionScore], composite)
                          │
                          └─→ recommend() → list[Recommendation]
```

## Search Quality Framework

The v0.2.0 release integrates a Search Quality Evaluation Framework derived
from publicly documented search-quality concepts. This is organized as a
separate analytical layer that complements (not replaces) the graph-theoretic
audit.

### Two conceptual layers

```text
PAGE QUALITY                         NEEDS MET
"What is this page and               "Given this query and user intent,
how well does it fulfill              how useful is this page/result?"
its own purpose?"
```

These are modeled as separate layers because a high-quality page can still
fail to meet a particular query, and a result can be topically relevant
but untrustworthy.

### Quality model

```python
PageQualityReport:
    url: str
    purpose: PagePurpose                    # classification + confidence
    content_classification: ContentClassification  # MC / SC / Ads
    reputation: ReputationAnalysis          # on-site signals + transparency
    eeat: EEATAnalysis                      # Experience / Expertise / Authority / Trust
    originality: OriginalityAnalysis        # duplicate / thin / templated detection
    spam_risk: str                          # high | medium | low
    quality_score: float                    # 0-100, project heuristic
```

### Scaled content detection

```python
ScaledContentPattern:
    detected: bool
    structurally_identical_count: int
    template_pages: list[str]
    variation_score: float                  # 0 = identical, 1 = highly varied
    programmatic_substitution: bool
    low_information_pages: list[str]
    confidence: str                         # high | medium | low
```

## Scoring system

The composite score is a weighted sum of 10 dimensions. See
[docs/scoring.md](docs/scoring.md) for the full formula.

## Crawl safety

- Respects robots.txt by default (RFC 9309)
- Configurable max pages, max depth, rate limit, max document bytes, max redirect
- Conservative default: 50 pages, depth 3, 2 req/s
- Same-origin only by default (no external link following unless opted in)

## Testing

```bash
pytest tests/                    # full suite
pytest tests/ --cov=pagerank_seo  # with coverage
```

136 tests cover: parser, crawler, graph, scoring, recommendations, SDK API,
CLI, robots.txt, sitemaps, synthetic-site audits, and search quality analysis.

## Version history

- **0.2.0** — Search Quality Framework: page purpose, content classification,
  reputation analysis, E-E-A-T, originality, scaled-content detection,
  10-dimension score (up from 8).
- **0.1.0** — Initial release: graph audit, six-layer analyzer, 8-dimension
  score, Hermes skill, CLI.
