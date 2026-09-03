# PageRank SEO Methodology (PRSEO)

> **Status:** Documented methodology for the `pagerank-seo` SDK and skill.
> **Version:** 0.2.0
> **Last updated:** 2026-09-03

## 0. Epistemic boundary

PRSEO does **not** claim access to Google's proprietary ranking algorithm or any
confidential PageRank implementation. It is a **graph-theoretic analytical framework**
grounded in:

1. The original 1999 PageRank paper (Page, Brin, Motwani, Winograd).
2. Public Google Search Central documentation.
3. IETF, W3C, WHATWG, and schema.org standards.
4. Classical information-retrieval concepts.
5. The publicly documented Search Quality Rater Guidelines (General Guidelines
   v10.1.1, September 2025) — summarized and cited, not reproduced.

The PageRank numbers produced by this SDK are **analytical tools**, not Google ranks.
See `research/sources.md` for the full source ledger.

## 1. The core thesis

A website is an **information graph**: a directed graph whose nodes are pages and whose
edges are hyperlinks. SEO, properly understood, is the discipline of optimizing this graph
across six interacting layers, evaluated through the lens of search quality:

```
        ┌──────────────────────────┐
        │  Reputation / E-E-A-T    │  ← public-facing trust signals
        └────────────┬─────────────┘
                     │
        ┌────────────┴─────────────┐
        │  User Experience         │  ← usability, accessibility, navigation
        └────────────┬─────────────┘
                     │
        ┌────────────┴─────────────┐
        │  Semantic Relevance      │  ← entities, topics, intent alignment
        └────────────┬─────────────┘
                     │
        ┌────────────┴─────────────┐
        │  Link Graph              │  ← PageRank, internal authority flow
        └────────────┬─────────────┘
                     │
        ┌────────────┴─────────────┐
        │  Information Arch.       │  ← URL/page hierarchy, depth, orphans
        └────────────┬─────────────┘
                     │
        ┌────────────┴─────────────┐
        │  Technical Representation│  ← HTML, metadata, structured data, HTTP
        └──────────────────────────┘
```

The bottom layer is necessary but not sufficient. A site can be technically perfect and
still fail SEO if its link graph is broken (orphan pages), its information architecture
is incoherent (deep URLs with no breadcrumbs), or its content is semantically off-topic.

## 2. The six layers

### 2.1 Technical Representation

What the crawler actually sees when it fetches a page. The analyzer checks for:

| Property | Source | Why it matters |
|---|---|---|
| HTML parses cleanly | WHATWG | Broken HTML hides content from crawlers. |
| Valid UTF-8 charset declared within first 1024 bytes | MDN `<meta>` | Crawlers may refuse to index mis-encoded pages. |
| Unique, non-empty `<title>` (10–70 chars recommended) | Google Search Central | Title is one of the primary content signals. |
| Meaningful `<meta name="description">` | MDN | Used in search-result snippets. |
| `rel="canonical"` present and self-consistent | Google canonicalization doc | Prevents duplicate-content dilution. |
| `robots` meta-tag respects intent | Google | `noindex` on indexable pages is a common bug. |
| `lang` attribute on `<html>` | WCAG, HTML spec | Language signal for indexing and accessibility. |
| Valid JSON-LD structured data | schema.org + Google | Enables rich-result eligibility. |
| Mobile viewport meta | Google mobile docs | Required for mobile-friendly rendering. |
| No client-side redirect via `<meta http-equiv="refresh">` | Google | Search Central discourages meta-refresh for redirects. |
| Accessibility landmarks (`<header>`, `<nav>`, `<main>`, `<footer>`) | HTML spec, WCAG | Discoverability and assistive-tech navigation. |

### 2.2 Information Architecture

How pages are organized for both users and crawlers.

| Property | Source |
|---|---|
| URL hierarchy depth (≤4 segments preferred) | Common IA practice, Google "URL structure" docs |
| Breadcrumbs present (visible or in `BreadcrumbList` schema) | schema.org |
| Sitemap present and parseable | sitemaps.org protocol |
| `robots.txt` present and consistent with sitemap | RFC 9309 |
| Orphan pages (in sitemap but not linked from any other crawled page) | PageRank paper §2.4 (loop / rank sink) |
| Crawl-depth distribution | Google how-search-works doc |
| Hub pages (high out-degree that aggregate topical clusters) | Inferred from PageRank structure |

### 2.3 Link Graph

The directed graph `G = (V, E)` where `V` is the set of crawled pages and `E` is the set
of internal hyperlinks. The SDK computes:

| Metric | Definition | Use |
|---|---|---|
| **Standard PageRank** | `R = c · (A + E·1ᵀ) · R` (damping factor default 0.85) | Authority distribution |
| **Weighted PageRank** | Edge weights derived from (a) link position in DOM and (b) `rel` attribute (nofollow/sponsored/ugc edges down-weighted) | Internal authority flow that respects documented link semantics |
| **Degree centrality** | in-degree, out-degree | Hubs and authorities (raw counts) |
| **Weakly-connected components** | Subgraphs reachable via undirected edges | Detect isolated clusters |
| **Orphan pages** | Nodes with in-degree = 0 in the crawled graph | Discovery holes |
| **Authority concentration** | Gini coefficient of PageRank distribution | Whether a few pages dominate |

`rel="nofollow"` (and `sponsored`/`ugc`) are **down-weighted, not removed**: Google's
[2009 announcement](https://webmasters.googleblog.com/2009/09/handling-pays-for-placement.html)
of how it treats nofollow has evolved (2020 and 2022 updates added hint semantics);
the SDK follows the conservative interpretation: treat as a weight reduction. We do not
claim Google's exact current semantics.

### 2.4 Semantic Relevance

Per-page and cross-page analysis:

- **Title ↔ content overlap** — tokenize title and body, compute Jaccard similarity over
  non-stopword tokens. Pages with very low overlap are flagged.
- **Headings hierarchy** — `<h1>` count (ideally 1), descending `<h2>`→`<h3>`→...`</h6>`
  structure.
- **Structured-data entities** — extract `@type` and `@id` from JSON-LD blocks.
- **Duplicate-title detection** — flags pages whose `<title>` exactly matches another
  crawled page's title.
- **Thin pages** — pages with very low text content relative to markup (heuristic).

### 2.5 User Experience

Observable, non-runtime signals:

- Has a `<nav>` landmark?
- Has a `<main>` landmark?
- Has a `<header>` and `<footer>`?
- Has a mobile viewport meta?
- Has `lang` on `<html>`?
- Has alt text on `<img>` tags? (sample-based, with a configurable threshold)
- Has visible breadcrumbs?
- Has an `<h1>` that is not empty?

### 2.6 Reputation Architecture

Defensible concepts only. **No claims** about Google's internal scoring. Distinguishes:

- **Reputation signals** (publicly observable, defensible):
  - HTTPS (the URL scheme)
  - Presence of `/about`, `/contact`, legal pages (`/privacy`, `/terms`)
  - `Organization` or `Person` schema on the home page
  - Author information on article pages (`Article` schema with `author`)
  - External links to authoritative sources (count, sampled)
- **Ranking signals** (we explicitly do not score these):
  - Backlink profile
  - Domain authority
  - Anything derived from third-party metrics

The framework surfaces **what is observable** and lets the analyst decide what to act on.

## 3. Search Quality Framework (v0.2.0)

The methodology now incorporates concepts derived from the publicly documented
Search Quality Rater Guidelines (General Guidelines v10.1.1, September 2025).
These are project-internal analytical constructs — they do NOT reproduce Google's
proprietary ranking system.

### 3.1 Page Purpose

The guidelines explicitly make identifying the true purpose of a page an early step
in Page Quality evaluation. The SDK classifies pages into:

- informational, transactional, navigational, entertainment, community,
  software/tool, commerce, personal expression, reference, service, unknown

Each classification includes a confidence level and the signals that produced it.

### 3.2 Content Classification (MC / SC / Ads)

Derived from the guidelines §2.4:

- **Main Content (MC):** directly helps the page achieve its purpose
- **Supplementary Content (SC):** contributes to UX without being primary
- **Advertisements/Monetization:** treated separately

The guidelines explicitly state that advertising itself is NOT inherently a reason
for a low Page Quality rating. The SDK models it as a structural observation.

### 3.3 Reputation Graph

The guidelines treat reputation as something that requires investigation beyond what
a website says about itself — independent reviews, references, news articles, etc.

The SDK's automated analysis observes on-site signals (HTTPS, Organization schema,
author markup, transparency). The skill instructs the agent to investigate
independent sources separately.

### 3.4 E-E-A-T

Experience, Expertise, Authoritativeness, Trust — analyzed as evidence, not keywords:

- **Experience:** first-hand evidence, demonstrations, original observations
- **Expertise:** credentials, depth of knowledge, technical accuracy
- **Authoritativeness:** recognized authorship, citations, independent references
- **Trust:** transparency, accuracy, responsible ownership, disclosures

### 3.5 Originality and Added Value

Derived from the guidelines §4.6.5 (Scaled Content Abuse) and §4.6.6 (Little Effort
/ Originality / Added Value). The framework distinguishes high-quality content from
content that has little effort, little originality, or little added value.

### 3.6 Scaled Content Detection

The guidelines specifically identify scaled content abuse as a lowest-quality/spam
concept when content is produced at scale with little effort, originality, or added
value. The SDK detects patterns such as hundreds of structurally identical pages,
minimal variation, programmatic keyword substitution, and low-information pages.

### 3.7 Page Quality vs Needs Met

The guidelines state that:

- **Page Quality** is evaluated based on the landing page itself.
- **Needs Met** depends on the query and user intent.
- A high-quality page can still fail to meet a particular query.
- A result can be topically relevant but untrustworthy and therefore fail the user need.

The SDK models both as separate analytical layers.

## 4. The iterative audit loop

The skill and the CLI share the same workflow:

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

A change without a predicted effect and a verification step is **not** a recommendation;
it is a guess. The methodology rejects blind optimization.

## 5. What the methodology explicitly does not claim

- That PageRank as computed here equals Google's ranking signal. It does not. PageRank is
  one idea among many in Google's system; modern Google uses hundreds of signals,
  machine-learned models, and continuous updates (see `research/sources.md` §1).
- That higher internal PageRank causes higher rankings. Internal PageRank distribution
  is an *indicator* of information architecture quality.
- That the score produced by the SDK corresponds to any external ranking position.
  The score is a **project-internal health metric**, useful for comparison and
  trend-tracking, not for ranking prediction.
- That any specific recommendation is required by Google. Recommendations are grounded
  in public documentation and engineering best practice; they reduce the surface area
  for misunderstanding, but no single one is a "ranking hack."
- That the Search Quality Rater Guidelines are a public description of Google's complete
  ranking algorithm. They are not. Human ratings do not directly move individual pages
  up or down in search results.
- That this project reproduces Google's ranking system. It does not. The project's
  scores are analytical heuristics.

## 6. Versioning

This methodology is versioned with the SDK. Breaking changes to the analyzer require a
minor-version bump. Score formula changes are also minor-version bumps. The score is
**never** silently reweighted — old reports stay interpretable.
