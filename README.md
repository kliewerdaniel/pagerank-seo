# pagerank-seo

> **PageRank-oriented SEO analysis:** turn a website into an information graph and produce prioritized, evidence-traceable recommendations.

[![Tests](https://github.com/kliewerdaniel/pagerank-seo/actions/workflows/ci.yml/badge.svg)](https://github.com/kliewerdaniel/pagerank-seo/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## What is PageRank SEO?

Modern SEO is an engineering discipline where search reputation, information
architecture, code quality, machine-readable representation, and user
experience converge. **SEO should be understood not as optimizing individual
pages, but as optimizing the information graph a website presents to search
engines and users.**

`pagerank-seo` is a Python SDK and CLI that crawls a website, constructs its
link graph, computes PageRank and other graph metrics, applies a six-layer
analyzer (technical, IA, graph, semantic, UX, reputation), incorporates
search-quality concepts (page purpose, E-E-A-T, originality, scaled-content
detection), and produces prioritized, evidence-traceable recommendations.

**PageRank values are an internal analytical metric, not Google's ranking
signal.** Recommendations are grounded in public documentation (Google Search
Central, W3C, schema.org, the original PageRank paper, and the publicly
documented Search Quality Rater Guidelines). See
[docs/research/sources.md](docs/research/sources.md) for the full source
ledger.

## Why this project exists

Most SEO tools still talk about pages. Write a better title. Add some
keywords. Get a few backlinks.

That advice isn't wrong — it's incomplete. **A website is not a pile of pages.
It is a graph.** Search engines crawl that graph, index that graph, and reason
about authority *through* that graph. The fact that we still talk about SEO as
if it were a per-page craft is a category error.

This project exists to make the graph-theoretic view of SEO executable. Read
the full thesis in the
[article](https://danielkliewer.com/blog/pagerank-seo-information-architecture-problem)
and the [methodology docs](docs/methodology.md).

## How it differs from conventional SEO tools

| Conventional tools | pagerank-seo |
|---|---|
| Per-page scoring | Graph-theoretic analysis (PageRank, authority flow, connectivity) |
| Keyword density checks | Information architecture analysis (orphan pages, depth, hierarchy) |
| Backlink counting | Internal-link graph construction and analysis |
| Opaque scores | Transparent, decomposable 10-dimension score |
| No search-quality framing | Page purpose, E-E-A-T, originality, scaled-content detection |
| No agent integration | Hermes skill + Python SDK for autonomous agents |

## Installation

```bash
pip install pagerank-seo
```

Requires Python 3.9+. Dependencies: `requests`, `beautifulsoup4`, `lxml`,
`networkx`, `numpy`, `scipy`.

## Quick start

### CLI

```bash
pagerank-seo audit https://example.com \
    --max-pages 50 \
    --max-depth 3 \
    --output markdown \
    --out-dir reports/
```

### Python SDK

```python
from pagerank_seo import AuditConfig
from pagerank_seo.auditor import SiteAuditor

auditor = SiteAuditor(AuditConfig(
    start_url="https://example.com",
    max_pages=50,
    max_depth=3,
))

report, quality = auditor.audit_with_quality()

print(f"Composite score: {report.composite_score}")
print(f"Quality score:  {quality.overall_quality_score}")
print(f"Findings:       {len(report.findings)}")
print(f"Recommendations: {len(report.recommendations)}")

for r in report.recommendations[:5]:
    print(f"  [{r.priority.value}] {r.finding}")
```

## Architecture

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

See [docs/architecture.md](docs/architecture.md) for the full architecture
documentation.

## The ten dimensions

The composite score is the weighted sum of ten named dimensions:

| Dimension | Weight | What it measures |
|---|---:|---|
| Technical Integrity | 0.16 | HTML parseability, charset, title, meta, canonical, robots, viewport |
| Information Architecture | 0.14 | URL depth, breadcrumbs, sitemap, robots.txt, orphan ratio |
| Graph Health | 0.16 | PageRank distribution, weakly-connected components |
| Internal Authority Distribution | 0.09 | Top-1 PageRank share |
| Semantic Coherence | 0.11 | Title/content overlap, headings hierarchy, duplicate-title ratio |
| Content Discoverability | 0.09 | Fraction of pages with ≥1 inbound internal link |
| User Experience | 0.07 | Landmarks, alt-text, lang, viewport |
| Reputation Architecture | 0.07 | HTTPS, About/Contact/Presence, Organization schema |
| Page Quality | 0.06 | Purpose clarity, content classification, E-E-A-T, spam risk |
| Content Originality | 0.05 | Originality score, added value, templated content |

## Hermes skill

The repository includes a [Hermes skill](skills/seo-audit/SKILL.md) that
teaches any Hermes installation how to run an audit, interpret the report,
prioritize changes, propose them with evidence, and re-audit to verify.

## Documentation

| Document | What it covers |
|---|---|
| [docs/methodology.md](docs/methodology.md) | The full PageRank SEO methodology |
| [docs/scoring.md](docs/scoring.md) | How the score is computed |
| [docs/architecture.md](docs/architecture.md) | System architecture |
| [docs/research/sources.md](docs/research/sources.md) | Primary sources and references |
| [docs/article/pagerank-seo.md](docs/article/pagerank-seo.md) | The technical article |
| [skills/seo-audit/SKILL.md](skills/seo-audit/SKILL.md) | Hermes skill |

## Limitations

- **Not Google's algorithm.** The PageRank computed is the public-domain
  algorithm from 1999. Google's modern ranking system contains hundreds of
  signals, machine-learned models, and continuous updates.
- **Not a ranking predictor.** The score is a project-internal engineering
  health metric, not an absolute ranking claim.
- **No runtime page-speed measurement.** The SDK observes HTML signals only;
  it does not run a headless browser.
- **No backlink analysis.** The SDK analyzes internal linking only; external
  backlink profiles require third-party data.
- **Single-language.** The SDK audits one language at a time.

## Contributing

Bug reports, feature requests, and pull requests are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT. See [LICENSE](LICENSE).

---

*Read the full article:
[PageRank SEO: Why Modern Search Optimization Is an Information Architecture Problem](https://danielkliewer.com/blog/pagerank-seo-information-architecture-problem)*
