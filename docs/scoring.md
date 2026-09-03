# PageRank SEO Health Score — Scoring System

> The score is a project-internal engineering health metric, **not** a Google ranking
> predictor. It is comparable across re-audits of the same site, and across sites of
> similar shape (e.g., documentation sites, marketing sites). It is **not** meaningful
> as an absolute ranking claim.

## 0. Design principles

1. **Transparent.** Every point is traceable to a specific check in the analyzer.
2. **Decomposable.** The score is the weighted sum of eight named dimensions; each
   dimension is reported separately.
3. **Comparable.** A re-audit of the same site produces a comparable score; the
   methodology documents exactly which checks moved.
4. **Non-gameable.** No single high-leverage optimization can swing the score
   disproportionately.

## 1. The eight dimensions

Each dimension is scored 0–100. The composite score is a weighted sum.

| Dimension | Weight | Source layer | What it measures |
|---|---:|---|---|
| **Technical Integrity** | 0.18 | §2.1 | HTML parseability, charset, title, meta, canonical, robots, mobile viewport |
| **Information Architecture** | 0.16 | §2.2 | URL depth, breadcrumbs, sitemap, robots.txt consistency, orphan ratio |
| **Graph Health** | 0.18 | §2.3 | Internal PageRank distribution, weakly-connected-components count, link density |
| **Internal Authority Distribution** | 0.10 | §2.3 | Gini coefficient of PageRank, top-1 share |
| **Semantic Coherence** | 0.12 | §2.4 | Title/content overlap, headings hierarchy, duplicate-title count |
| **Content Discoverability** | 0.10 | §2.2/§2.5 | Nav/main/header/footer landmarks, internal-link coverage of pages |
| **User Experience** | 0.08 | §2.5 | Landmarks, alt-text sample, lang attribute, viewport |
| **Reputation Architecture** | 0.08 | §2.6 | HTTPS, About/Contact presence, Organization schema, external authoritative links |

Total: 1.00.

## 2. How each dimension is computed

### 2.1 Technical Integrity

Score = `100 · (sum_of_passing_checks / total_checks)` where each failing check subtracts
equally. Checks:

1. HTML parses without raising (`BeautifulSoup` returns a parse tree).
2. `<meta charset="utf-8">` (case-insensitive) is present.
3. `<title>` is present, non-empty, length ∈ [10, 200].
4. `<meta name="description">` is present and non-empty.
5. `<link rel="canonical">` is present.
6. `rel="canonical"` is self-referential OR consistent with no duplicate detected.
7. `<meta name="robots">` does not include `noindex` on a presumably-indexable page.
8. `<meta name="viewport" content="...width=device-width...">` is present.
9. `<html lang="...">` is present.
10. Page returns HTTP 2xx (or a soft 3xx followed by 2xx).
11. At least one JSON-LD `<script type="application/ld+json">` parses successfully.

For a site-level Technical Integrity score, we use the **mean** across crawled pages.

### 2.2 Information Architecture

Score = `100 · (1 - penalty)` where penalty = sum of:

- 0.30 × `fraction_orphan_pages` (orphan = in-degree 0 within the crawled graph)
- 0.20 × `fraction_pages_depth_gt_4` (where depth is the minimum BFS distance from
  the seed URL)
- 0.10 × (1 if sitemap missing, 0 otherwise)
- 0.10 × (1 if robots.txt missing or malformed, 0 otherwise)
- 0.10 × (1 if no breadcrumb navigation detected, 0 otherwise)
- 0.10 × (1 if URL has >2 query parameters)
- 0.20 × `fraction_pages_breadcrumb_mismatch` (URL path segments don't match
  breadcrumb labels)

Cap: `max(0, 100 - 100·penalty)`.

### 2.3 Graph Health

Score = `100 · (1 - gini_pagerank)` clamped to [0, 100], plus a connectivity bonus:

```
gini = Gini coefficient of the PageRank vector across nodes
connectivity_bonus = 20 · (1 - weakly_connected_components / total_nodes)
                     (zero when more than 1 WCC exists)
score = clamp(0, 100, 100·(1 - gini) + connectivity_bonus - 20)
```

A perfectly even authority distribution would score near 100; a single-page-eats-all
distribution scores near 0. A multi-cluster graph is penalized through the WCC factor.

### 2.4 Internal Authority Distribution

Score = `100 · (1 - top1_share)` where `top1_share = max(pagerank) / sum(pagerank)`.

A score of 100 means authority is evenly distributed across all pages. A score of 0
means all authority concentrates in a single page. Real sites land in 60–95.

### 2.5 Semantic Coherence

Per-page checks, site-scored as the mean:

- 0.30 × `title_content_overlap` (Jaccard of non-stopword tokens)
- 0.30 × `h1_present`
- 0.20 × `headings_hierarchy_valid` (no skipped levels beyond h1→h2→h3…)
- 0.20 × `unique_title_across_site`

### 2.6 Content Discoverability

Score = `100 · fraction_pages_with_at_least_one_inbound_internal_link`.

A page with zero inbound links is effectively undiscoverable by the crawler via the
link graph (the sitemap is the only path). We expect this to be ≥90% for a healthy site.

### 2.7 User Experience

Score = `100 · mean(per_page_landmark_score)` where the per-page landmark score is the
fraction of expected landmarks present (nav, main, header, footer, lang).

### 2.8 Reputation Architecture

Site-level checks:

- 0.30 — site is served over HTTPS
- 0.20 — at least one of `/about`, `/about-us`, `/company` resolves
- 0.20 — at least one of `/contact`, `/contact-us` resolves
- 0.15 — at least one of `/privacy`, `/privacy-policy` resolves
- 0.15 — home page includes `Organization` or `WebSite` JSON-LD

## 3. Composite score

```python
score = (
    0.18 * technical_integrity
    + 0.16 * information_architecture
    + 0.18 * graph_health
    + 0.10 * internal_authority_distribution
    + 0.12 * semantic_coherence
    + 0.10 * content_discoverability
    + 0.08 * user_experience
    + 0.08 * reputation_architecture
)
```

Rounded to one decimal place.

## 4. Score bands (for human readers only)

| Band | Range | Interpretation |
|---|---|---|
| Excellent | 85–100 | Healthy site; minor optimizations available. |
| Good | 70–84.9 | Solid foundation; clear opportunities for improvement. |
| Fair | 50–69.9 | Significant structural issues; prioritize HIGH/CRITICAL recommendations. |
| Poor | 25–49.9 | Major problems across multiple layers. |
| Critical | 0–24.9 | Likely crawl/index problems blocking visibility. |

These bands are **opinionated heuristics**, not statistical thresholds. They are intended
to help a reader interpret the absolute number, not to be used as a quality gate.

## 5. What the score does NOT measure

- Backlink profile quality (requires data from sources outside the site)
- Search rankings (requires external SERP observation)
- Conversion or business outcomes (orthogonal to SEO health)
- Page-speed at runtime (the SDK measures observable HTML signals, not LCP/INP/CLS —
  those need a headless browser and are out of scope for the core SDK; the README
  documents how to layer them on)
- International/multilingual SEO (single-language audits only)
