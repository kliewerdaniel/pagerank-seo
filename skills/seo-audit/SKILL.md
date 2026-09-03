---
name: seo-audit
description: PageRank-oriented SEO audit using the pagerank-seo SDK. Use when the user asks to audit, review, or improve a website's SEO; to diagnose orphan pages, weak internal linking, or information-architecture problems; to turn a website into an information graph and reason about prioritization; or to iteratively measure improvements over time.
---

# SEO Audit — PageRank-Oriented Skill

This skill teaches an autonomous agent how to audit a website's SEO using the
**pagerank-seo** SDK. The methodology treats a website as an **information graph**
(pages = nodes, hyperlinks = edges) and produces prioritized, evidence-traceable
recommendations.

> **Do not optimize blindly. Measure the information architecture first.**

> **Epistemic boundary.** This skill does NOT have access to Google's proprietary
> ranking algorithm. The PageRank numbers produced by the SDK are *analytical
> tools*, not Google's score. Every recommendation is grounded in publicly
> documented behavior (Google Search Central, W3C, schema.org, the original
> PageRank paper, and the publicly documented Search Quality Rater Guidelines)
> or in explicitly named heuristics. See the project's
> `docs/research/sources.md` for the source ledger.

## When to use this skill

Use this skill when the user:

- Asks to "audit", "review", or "improve" a website's SEO.
- Wants to diagnose orphan pages, weak internal linking, broken metadata, or
  poor information architecture.
- Wants to evaluate page purpose, content quality, reputation, E-E-A-T signals,
  or originality.
- Wants to compare two audits before/after a change.
- Wants a reproducible, evidence-traceable SEO health report.

Do **not** use this skill when the user wants:

- A backlink profile / domain authority report (those require external data).
- Live page-speed / Core Web Vitals measurements (this SDK does not run a
  headless browser; it observes HTML signals only).
- A guarantee of ranking improvements (no SEO tool can promise that).

## What the skill produces

A single audit run produces an `AuditReport` containing:

- A `CrawlResult` (every page fetched, every internal link discovered).
- A `SiteGraph` with computed metrics (PageRank, in/out degree, weakly-connected
  components, orphan pages, Gini coefficient, top-1 PageRank share).
- A list of `Finding` objects — neutral observations about the site.
- A list of `Recommendation` objects, prioritized CRITICAL / HIGH / MEDIUM / LOW,
  each with `finding`, `evidence` (finding codes), `recommended_action`,
  `impact`, `confidence`, `implementation_difficulty`, `verification_method`,
  and `affected_urls`.
- A 10-dimension `PageRank SEO Health Score` and a composite 0–100 score.

Plus a `SearchQualityReport` containing:

- Per-page `PageQualityReport` objects with purpose classification, content
  classification (MC/SC/Ads), reputation analysis, E-E-A-T analysis, and
  originality analysis.
- Site-level `ScaledContentPattern` detection.
- Overall quality score and confidence.

Output formats: JSON, Markdown, HTML. See "Reports" below.

## Installation

The skill requires the `pagerank-seo` Python SDK. Install once:

```bash
pip install pagerank-seo
```

Verify:

```bash
pagerank-seo --version
```

If you are running this in a project that already vendors the SDK (e.g. the
`pagerank-seo` repository itself), install it editable:

```bash
pip install -e .
```

The skill assumes a Python 3.9+ interpreter with `requests`, `beautifulsoup4`,
`lxml`, `networkx`, `numpy`, and `scipy` available. They are listed in the
SDK's `pyproject.toml` and installed automatically.

## The agent workflow

Every audit follows one loop. Do not skip steps; do not assume more changes
automatically improve SEO.

```
DISCOVER SITE
      ↓
UNDERSTAND SITE PURPOSE
      ↓
CRAWL
      ↓
BUILD INFORMATION GRAPH
      ↓
CLASSIFY PAGE CONTENT
      ↓
ANALYZE PAGE PURPOSE
      ↓
ANALYZE TECHNICAL STRUCTURE
      ↓
ANALYZE INTERNAL LINK GRAPH
      ↓
ANALYZE CONTENT QUALITY
      ↓
ANALYZE ORIGINALITY / ADDED VALUE
      ↓
ANALYZE REPUTATION
      ↓
ANALYZE E-E-A-T
      ↓
IDENTIFY SPAM / ABUSE PATTERNS
      ↓
MODEL QUERY INTENT
      ↓
ANALYZE QUERY-PAGE FIT
      ↓
GENERATE RECOMMENDATIONS
      ↓
IMPLEMENT APPROVED CHANGES
      ↓
RE-CRAWL
      ↓
COMPARE BEFORE / AFTER
```

## Distinguishing what you know

Every response from the agent should make clear **which of these categories**
each statement falls into:

- **Factual finding.** Directly observed by the audit (e.g. "page /privacy
  has zero inbound internal links").
- **Inferred relationship.** A graph-derived statistic (e.g. "PageRank on the
  home page holds 47% of the total — interpreted as authority concentration").
- **Recommendation.** A prioritized change with a verification method.
- **Assumption.** Something you are taking as given (e.g. "the site is in
  English because the `<html lang>` attribute is `en`").
- **Changes actually made.** Edits performed in this session.
- **Changes that still require human approval.** Edits the agent proposed but
  did not make.

When you write back to the user, surface these distinctions explicitly.

## Step-by-step

### 1. Identify the target

Ask the user for the start URL if it is not already clear. Confirm scope
(single site, single section, multi-domain). Do not crawl sites the operator
does not own or have explicit permission to audit.

Default conservative budget for a first audit:

- max pages: 50
- max depth: 3
- requests per second: 2.0
- respect robots.txt: yes
- follow external links: no

For a deeper audit, raise `max_pages` and `max_depth` after the first run.

### 2. Run the audit (CLI)

```bash
pagerank-seo audit https://example.com \
    --max-pages 50 \
    --max-depth 3 \
    --output markdown \
    --out-dir reports/
```

Available output formats (comma-separated): `json`, `markdown`, `html`.

`--verbose` prints per-page crawl progress to stderr.

Exit codes:

- 0 — success
- 1 — network/audit failure
- 2 — invalid configuration (bad URL, bad flag)

### 3. Run the audit (Python SDK)

```python
from pagerank_seo import AuditConfig
from pagerank_seo.auditor import SiteAuditor
from pagerank_seo.report import to_json, to_markdown, to_html

auditor = SiteAuditor(AuditConfig(
    start_url="https://example.com",
    max_pages=50,
    max_depth=3,
))

# Run the full audit plus search quality analysis
report, quality = auditor.audit_with_quality()

print("Composite score:", report.composite_score)
print("Quality score:", quality.overall_quality_score)
print("Findings:", len(report.findings))
print("Top recommendation:", report.recommendations[0])

# Per-page quality reports
for page_report in quality.page_reports:
    print(f"  {page_report.url}: {page_report.purpose.purpose.value} "
          f"(confidence: {page_report.purpose.confidence})")

# Save outputs
with open("reports/audit.md", "w") as f:
    f.write(to_markdown(report))
with open("reports/audit.json", "w") as f:
    f.write(to_json(report))
```

### 4. Interpret the report

Read the report top-down:

1. **Composite score** (0–100). A rough health band:
   - 85+ Excellent, 70–84 Good, 50–69 Fair, 25–49 Poor, 0–24 Critical.
2. **The 10 dimensions.** Each has a `score`, a `weight`, and a one-line
   `rationale` (the actual heuristic, not a marketing phrase).
3. **Recommendations**, prioritized CRITICAL → LOW. Each carries:
   - `finding` — what was observed
   - `evidence` — the finding codes that triggered this recommendation
   - `recommended_action` — concrete change
   - `impact` / `confidence` / `implementation_difficulty` — qualitative bands
   - `verification_method` — how to confirm the change worked
   - `affected_urls` — where to apply the change
4. **Graph summary** — node/edge counts, orphan pages, PageRank distribution.
5. **Findings ledger** — every observation, grouped by layer
   (`technical | ia | graph | semantic | ux | reputation`).

Then read the search quality report:

6. **Per-page quality** — purpose, content classification, reputation, E-E-A-T,
   originality scores.
7. **Scaled content** — whether the site shows patterns of mass-produced
   low-value content.
8. **Site reputation abuse risk** — whether pages fit the site's purpose.

### 5. Prioritize and propose

Always work CRITICAL → HIGH → MEDIUM → LOW. For each recommendation:

- State the **reason** (which finding code(s) and which URLs).
- State the **expected outcome** (e.g. "the orphan page's in-degree should
  become > 0 after we add a contextual link from /blog/").
- State the **implementation** (what to change, where).
- State the **verification step** (the `verification_method` field).

If the user has not authorized changes, stop after PROPOSE and wait for approval.

### 6. Implement (only when authorized)

When the user approves, make the change. Then re-run the audit. Compare:

- Did the composite score move? In which dimensions?
- Did the specific recommendation disappear?
- Did any *new* recommendation appear (regression)?
- Did any dimension get worse?

### 7. Verify and explain

Write a short explanation back to the user covering:

- What was changed (file paths, line numbers, snippets if small).
- What the re-audit shows.
- What is now different (cite the specific findings/recommendations that
  changed).
- What still requires human judgment (e.g. content rewrites, design changes,
  decisions about cross-domain canonicalization).

## Agent guardrails

The agent must NOT:

- Keyword stuff or mass-generate thin pages.
- Manufacture expertise, credentials, reviews, or citations.
- Manipulate reputation or create deceptive pages.
- Create unrelated topical pages purely for traffic.
- Hide important content or obscure monetization.
- Claim Google's internal algorithm is known.
- Treat PageRank as equivalent to Google's complete ranking system.

The agent should optimize for:

- Usefulness, clarity, originality, trust.
- Accessibility, information architecture, semantic coherence.
- Appropriate authority and good user experience.

## Pitfalls

- **Don't run audits against sites you don't own or have permission to audit.**
  This SDK is not a stealth tool. Always check before crawling.
- **Don't conflate the score with Google rankings.** The score is an internal
  engineering metric, not a ranking predictor. A "100" score does not mean
  the page ranks first.
- **Don't trust a single audit blindly.** Always re-audit after a change and
  compare.
- **Don't fire every recommendation at once.** Prioritization matters. A
  CRITICAL recommendation almost always beats a dozen LOW ones.
- **Don't optimize for the score itself.** The score is a *proxy* for the
  underlying property (information architecture quality, technical integrity).
  Optimizing for the number is Goodhart's Law.
- **Don't add structured data to a page that doesn't have visible content.**
  Google Search Central explicitly says this is a spam signal.
- **Don't use `<meta http-equiv="refresh">` for redirects.** It works, but
  Google discourages it. Use HTTP 301/302.
- **Don't claim "noindex is fine" for indexable pages.** A noindex on a page
  you actually want indexed is a CRITICAL bug. Always flag and require a
  human to confirm.
- **Don't treat "thin content" as a single threshold.** The current
  heuristic flags pages with fewer than 80 visible words; real thin pages
  are context-dependent. Pair the heuristic with human judgment.

## Reference: the ten dimensions

| Dimension | What it measures |
|---|---|
| Technical Integrity | HTML parseability, charset, title, meta, canonical, robots, viewport |
| Information Architecture | URL depth, breadcrumbs, sitemap, robots.txt, orphan ratio, query-heavy URLs |
| Graph Health | PageRank distribution, weakly-connected components |
| Internal Authority Distribution | Top-1 PageRank share (lower = more even) |
| Semantic Coherence | Title/content overlap, headings hierarchy, duplicate-title ratio |
| Content Discoverability | Fraction of pages with ≥1 inbound internal link |
| User Experience | `<nav>`, `<main>`, `<header>`, `<footer>`, `lang` |
| Reputation Architecture | HTTPS, `/about`, `/contact`, `/privacy`, Organization schema |
| Page Quality | Purpose clarity, content classification, E-E-A-T, spam risk |
| Content Originality | Originality score, added value, templated content |

## Reference: the recommendation priority bands

| Band | Meaning | Default action |
|---|---|---|
| CRITICAL | Blocking SEO function (noindex on indexable pages, 4xx/5xx on the seed, deceptive signals) | Stop and fix immediately |
| HIGH | Significant structural damage (orphan clusters, disconnected components, duplicate titles across many pages, missing viewport, templated content) | Fix in the next iteration |
| MEDIUM | Clearly improvable (missing structured data, thin content, missing sitemap, unclear purpose, low E-E-A-T) | Schedule for the next sprint |
| LOW | Polish (multiple H1s, missing landmarks on non-indexable pages) | Backlog |

## Reference: SDK public API (cheat sheet)

```python
from pagerank_seo import (
    AuditConfig,
    CrawlResult,
    Finding,
    GraphMetrics,
    Link,
    Page,
    Priority,
    RelType,
    SiteGraph,
    # Search quality
    ContentClassification,
    EEATAnalysis,
    NeedsMetAnalysis,
    OriginalityAnalysis,
    PagePurpose,
    PagePurposeType,
    PageQualityReport,
    QueryIntent,
    QueryIntentType,
    ReputationAnalysis,
    ReputationSignal,
    ScaledContentPattern,
    SearchQualityReport,
)
from pagerank_seo.auditor import SiteAuditor
from pagerank_seo.report import to_html, to_json, to_markdown
```

`SiteAuditor` exposes each phase individually:

- `auditor.crawl()` → `CrawlResult`
- `auditor.build_graph(crawl)` → `SiteGraph`
- `auditor.analyze(crawl, graph)` → `list[Finding]`
- `auditor.analyze_quality(crawl)` → `SearchQualityReport`
- `auditor.score(crawl, graph)` → `(list[DimensionScore], float)`
- `auditor.recommend(findings, crawl, graph)` → `list[Recommendation]`
- `auditor.audit()` → `AuditReport` (core phases)
- `auditor.audit_with_quality()` → `(AuditReport, SearchQualityReport)` (full)

`AuditReport.to_dict()` produces a JSON-safe dict (enum values as strings).

## Reference: CLI flags

```
pagerank-seo audit <url>
    --max-pages N            default 50
    --max-depth N            default 3
    --timeout SECONDS        default 10
    --rate REQUESTS/SEC      default 2
    --max-bytes BYTES        default 5_000_000 (5 MiB)
    --user-agent STRING      default identifies the tool
    --ignore-robots          off by default
    --follow-external        off by default
    --output json,html,markdown
    --out-dir PATH           write to <path>/audit-<slug>.<fmt>
    --verbose / -v           print per-page crawl progress to stderr
```

## Verification checklist (before reporting back)

- [ ] I named every finding's category (factual / inferred / recommendation / assumption / change made / pending approval).
- [ ] I prioritized recommendations CRITICAL → LOW.
- [ ] I cited the verification step for each recommendation I proposed.
- [ ] I re-ran the audit after any change and compared.
- [ ] I did not claim the score is a ranking predictor.
- [ ] I did not claim Google's algorithm.
- [ ] I noted any human-approval-required actions.
- [ ] I distinguished Page Quality from Needs Met when discussing query fit.
- [ ] I did not fabricate expertise, credentials, or reputation claims.
- [ ] I flagged scaled-content patterns as observations, not automatic spam classifications.
