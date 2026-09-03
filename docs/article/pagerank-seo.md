---
title: "PageRank SEO: Why Modern Search Optimization Is an Information Architecture Problem"
slug: pagerank-seo-information-architecture-problem
date: 2026-09-03
author: Daniel Kliewer
description: Why modern SEO is increasingly an information-architecture and systems-engineering problem, and how the pagerank-seo SDK turns the idea into a working, evidence-traceable auditor.
tags: ["SEO", "PageRank", "graph", "information-architecture", "search", "MCP", "agent", "open-source", "local-first", "SDK", "Hermes"]
canonical_url: /blog/pagerank-seo-information-architecture-problem
image: /images/1103012.png
---

# PageRank SEO: Why Modern Search Optimization Is an Information Architecture Problem

*September 3, 2026 · Daniel Kliewer*

**Modern SEO is an engineering discipline where search reputation, information architecture, code quality, machine-readable representation, and user experience converge.** It should be understood not as optimizing individual pages, but as optimizing the information graph a website presents to search engines and users.

This essay makes the case, walks through the implementation, and releases the open-source [pagerank-seo](https://github.com/kliewerdaniel/pagerank-seo) SDK that turns the idea into something a Python script, a CI pipeline, or an autonomous agent can run.

---

## From keyword stuffing to graph reasoning

SEO used to be a textual problem. In the late 1990s, the problem was literal text: keyword density, meta keywords, hidden text. The [original PageRank paper](http://ilpubs.stanford.edu:8090/422/1/1999-66.pdf) already disagreed. The paper opens by noting that *"the importance of a web page is an inherently subjective matter… But there is still much that can be said objectively about the relative importance of web pages."* The objective thing Page and Brin said was: a page's importance propagates through the **links** pointing at it, not the words inside it.

Twenty-six years later, almost every documented Google concern about a website is, at some level, a graph concern:

- **Crawlable structure.** Crawlers extract links from known pages to discover new ones. A site with a broken internal-link graph *cannot be fully crawled.*
- **Canonicalization.** Google clusters duplicate pages and chooses a canonical representative. A site that fans out into hundreds of near-duplicate URLs forces the engine to do more work, with worse results, for everyone.
- **Helpful content.** The unit of analysis is not a page; it's a *site* — and a site's quality is, in part, a graph property.
- **Sitemaps.** Sitemaps tell Google about pages and the *relationships between them*. The word is literally "site-map" — a map of the structure.

The unit of optimization that matters is the site-as-graph, not the page-as-text.

---

## Modeling a website as a graph

A graph `G = (V, E)` has nodes and edges. For a website:

- Each **page** is a node.
- Each **internal hyperlink** is a directed edge, carrying metadata (anchor text, `rel` attribute, DOM position).

From this graph we compute **PageRank** (public-domain algorithm, damping factor 0.85, dangling-node correction), **weighted PageRank** (edges weighted by link position and `rel`), **in/out degree**, **weakly-connected components**, **orphan pages** (in-degree zero, excluding seed), **Gini coefficient of PageRank**, and **top-1 PageRank share**.

I am explicitly *not* claiming that the PageRank number produced here equals Google's score. It is an analytical tool for reasoning about the site. All the original PageRank patents expired in September 2019.

---

## The six layers

SEO splits into six interacting layers, each depending on the ones below it:

1. **Technical representation** — charset, title, meta description, canonical, viewport, JSON-LD, robots directives.
2. **Information architecture** — URL hierarchy, breadcrumbs, sitemap, orphan pages, deep pages.
3. **Link graph** — PageRank, weighted PageRank, in/out degree, weakly-connected components, Gini, top-1 share.
4. **Semantic relevance** — title/content overlap, heading structure, duplicate titles, thin content.
5. **User experience** — `<nav>`, `<main>`, `<header>`, `<footer>`, `lang`, `alt`.
6. **Reputation architecture** — HTTPS, `/about`, `/contact`, `/privacy`, Organization schema.

I am careful to distinguish **reputation signals** (publicly observable properties) from **ranking signals** (whatever is actually inside Google's head). I do not claim to know the latter.

---

## The Search Quality upgrade

The methodology now incorporates concepts derived from the publicly documented **Search Quality Rater Guidelines** (General Guidelines v10.1.1, September 2025). This is a significant upgrade.

The guidelines make explicit that SEO engineering must care about two distinct questions:

**Page Quality** asks: *"What is this page and how well does it fulfill its own purpose?"*

**Needs Met** asks: *"Given this query and user intent, how useful is this page?"*

A high-quality page can fail a particular query. A keyword-stuffed page can fail every query. The SDK models both.

### Page Purpose

The guidelines make identifying the true purpose of a page an early step. The SDK classifies pages into: informational, transactional, navigational, entertainment, community, software/tool, commerce, personal expression, reference, service.

### Content Classification (MC / SC / Ads)

The guidelines distinguish:
- **Main Content (MC):** directly helps the page achieve its purpose
- **Supplementary Content (SC):** contributes to UX without being primary
- **Advertisements/Monetization:** treated separately

Advertising is NOT inherently a reason for a low Page Quality rating. The SDK models it as a structural observation, not a penalty.

### E-E-A-T

Experience, Expertise, Authoritativeness, Trust — analyzed as **evidence**, not keywords:
- **Experience:** first-hand evidence, demonstrations, original observations
- **Expertise:** credentials, depth of knowledge, technical accuracy
- **Authoritativeness:** recognized authorship, citations, independent references
- **Trust:** transparency, accuracy, responsible ownership, disclosures

### Originality and Scaled Content

The guidelines identify scaled content abuse as a lowest-quality concept: content produced at scale with little effort, originality, or added value. The SDK detects patterns like hundreds of structurally identical pages, minimal variation, and programmatic keyword substitution.

### The Reputation Graph

The guidelines treat reputation as requiring investigation beyond what a website says about itself — independent reviews, references, news articles. The SDK observes on-site signals and instructs the agent to investigate independent sources separately.

---

## The SDK: `pagerank-seo`

```bash
pip install pagerank-seo
pagerank-seo audit https://example.com \
    --max-pages 50 \
    --max-depth 3 \
    --output markdown \
    --out-dir reports/
```

Or in Python:

```python
from pagerank_seo import AuditConfig
from pagerank_seo.auditor import SiteAuditor

auditor = SiteAuditor(AuditConfig(
    start_url="https://example.com",
    max_pages=50,
    max_depth=3,
))

report, quality = auditor.audit_with_quality()

print(report.composite_score)          # 50.9 (real run against example.com)
print(quality.overall_quality_score)   # Page Quality heuristic
print(report.recommendations[:3])      # CRITICAL → LOW prioritized
print(quality.scaled_content.detected) # scaled-content pattern?
```

The output is a structured `AuditReport` plus a `SearchQualityReport` containing per-page quality reports, scaled-content detection, and site reputation abuse risk.

---

## The honest constraints

**It is not Google's algorithm.** The PageRank computed is the public-domain algorithm from 1999. Google's modern ranking system contains hundreds of signals.

**It is not a ranking predictor.** The composite score is a project-internal engineering health metric. A "100" score does not guarantee first-page rankings.

**It does not measure page speed at runtime.** The SDK observes HTML signals only; it does not run a headless browser.

**It does not crawl sites you don't own.** The crawler respects robots.txt by default and exposes conservative knobs.

**The Search Quality Rater Guidelines are not a ranking formula.** Human ratings do not directly move individual pages up or down in search results. The project uses these concepts as an analytical framework, not as a reproduction of Google's systems.

---

## The agent workflow: an executable loop

```
DISCOVER SITE → UNDERSTAND SITE PURPOSE → CRAWL → BUILD INFORMATION GRAPH
→ CLASSIFY PAGE CONTENT → ANALYZE PAGE PURPOSE → ANALYZE TECHNICAL STRUCTURE
→ ANALYZE INTERNAL LINK GRAPH → ANALYZE CONTENT QUALITY → ANALYZE ORIGINALITY
→ ANALYZE REPUTATION → ANALYZE E-E-A-T → IDENTIFY SPAM / ABUSE PATTERNS
→ MODEL QUERY INTENT → ANALYZE QUERY-PAGE FIT → GENERATE RECOMMENDATIONS
→ IMPLEMENT APPROVED CHANGES → RE-CRAWL → COMPARE BEFORE / AFTER
```

I shipped this loop as a [Hermes skill](https://github.com/kliewerdaniel/pagerank-seo/tree/main/skills/seo-audit). The critical instruction:

> **Do not optimize blindly. Measure the information architecture first.**

Every recommendation carries a `verification_method`. No change without a reason, no reason without evidence, no evidence without a re-audit to confirm.

---

## Try it

```bash
pip install pagerank-seo
pagerank-seo audit https://your-site.example/ --output markdown
```

Repository: [github.com/kliewerdaniel/pagerank-seo](https://github.com/kliewerdaniel/pagerank-seo) · Hermes skill: `skills/seo-audit/SKILL.md` · Methodology: `docs/methodology.md` · Score formula: `docs/scoring.md` · Sources: `docs/research/sources.md`

If you find a real bug, open an issue. If you build something with it, I'd like to hear about it.

---

*Daniel Kliewer is a software engineer who has worked around search-quality evaluation and built the open-source sovereign-knowledge-compiler, kleincannon-video-pipeline, and other local-first tools. He writes at [danielkliewer.com](https://danielkliewer.com).*
