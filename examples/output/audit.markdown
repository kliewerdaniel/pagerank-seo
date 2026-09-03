# PageRank SEO Audit Report

**Site:** `https://example.com`  
**Generated:** 2026-09-03T11:52:17+00:00  
**Crawl budget:** max 20 pages, depth 3  
**Pages crawled:** 1 (failed: 0)  
**Crawl elapsed:** 0.24s

## Composite Score: **50.9 / 100**

| Dimension | Score | Weight | Rationale |
|---|---:|---:|---|
| Technical Integrity | 58.3 | 0.18 | Mean of ['charset_present', 'charset_utf8', 'title_present', 'title_length_ok', 'meta_description_present', 'canonical_present', 'canonical_self_or_consistent', 'noindex_not_present', 'lang_present', 'viewport_present', 'status_2xx', 'jsonld_parses'] checks across 1 page(s). |
| Information Architecture | 40.0 | 0.16 | Penalty-driven score: orphan ratio 100%, sitemap missing, robots.txt missing, no BreadcrumbList JSON-LD |
| Graph Health | 100.0 | 0.18 | Gini=0.00, WCC=1/1 |
| Internal Authority Distribution | 0.0 | 0.10 | Top-1 holds 100% of total PageRank |
| Semantic Coherence | 100.0 | 0.12 | Mean per-page semantic score 1.25; duplicate-title ratio 0% |
| Content Discoverability | 0.0 | 0.10 | 0/1 pages have ≥1 inbound internal link |
| User Experience | 20.0 | 0.08 | Mean landmark presence across 1 pages |
| Reputation Architecture | 30.0 | 0.08 | Present: HTTPS |

## Recommendations

### [HIGH] No <meta charset> declaration found.

- **Action:** Add <meta charset="utf-8"> in the first 1024 bytes of <head>.
- **Impact:** medium  **Confidence:** high  **Difficulty:** low
- **Evidence codes:** CHARSET_MISSING
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm charset is declared.

### [HIGH] 1 page(s) have no inbound internal links.

- **Action:** Add contextual internal links to each orphan page from a relevant authoritative page.
- **Impact:** high  **Confidence:** high  **Difficulty:** medium
- **Evidence codes:** ORPHAN_PAGES
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm the orphan's in-degree > 0.

### [MEDIUM] <meta name='description'> missing.

- **Action:** Add a <meta name="description"> that summarizes the page.
- **Impact:** medium  **Confidence:** high  **Difficulty:** low
- **Evidence codes:** META_DESCRIPTION_MISSING
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm the meta is present.

### [MEDIUM] <link rel="canonical"> missing.

- **Action:** Add a self-referential <link rel="canonical">.
- **Impact:** medium  **Confidence:** high  **Difficulty:** low
- **Evidence codes:** CANONICAL_MISSING
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm canonical points to the page itself.

### [MEDIUM] No JSON-LD structured data blocks found.

- **Action:** Add JSON-LD structured data appropriate to the page type (Article, Product, BreadcrumbList, etc.).
- **Impact:** medium  **Confidence:** medium  **Difficulty:** medium
- **Evidence codes:** NO_STRUCTURED_DATA
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm JSON-LD blocks parse successfully.

### [MEDIUM] Page has only 19 visible words.

- **Action:** Expand the page content to better cover the topic, or merge it into a stronger page.
- **Impact:** medium  **Confidence:** medium  **Difficulty:** high
- **Evidence codes:** THIN_CONTENT
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm word count is higher.

### [MEDIUM] No <nav> landmark found.

- **Action:** Add a <nav> landmark with primary site navigation.
- **Impact:** medium  **Confidence:** high  **Difficulty:** low
- **Evidence codes:** NAV_MISSING
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm <nav> is detected.

### [MEDIUM] No <main> landmark found.

- **Action:** Wrap the primary content in a <main> element.
- **Impact:** medium  **Confidence:** high  **Difficulty:** low
- **Evidence codes:** MAIN_MISSING
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm <main> is detected.

### [MEDIUM] No robots.txt was fetched from the site root.

- **Action:** Add a /robots.txt file. At minimum, declare the sitemap location.
- **Impact:** low  **Confidence:** high  **Difficulty:** low
- **Evidence codes:** ROBOTS_TXT_MISSING
- **Affected URLs (1):**
  - `https://example.com`
- **Verify:** Re-crawl and confirm robots.txt is fetched.

### [MEDIUM] No sitemap URL was declared in robots.txt.

- **Action:** Generate an XML sitemap and reference it from robots.txt.
- **Impact:** medium  **Confidence:** high  **Difficulty:** medium
- **Evidence codes:** SITEMAP_MISSING
- **Affected URLs (1):**
  - `https://example.com`
- **Verify:** Re-crawl and confirm sitemap URL is recorded.

### [MEDIUM] Top page holds 100% of total PageRank.

- **Action:** Add outbound internal links from the top-ranked page to related content.
- **Impact:** medium  **Confidence:** medium  **Difficulty:** medium
- **Evidence codes:** SINGLE_PAGE_DOMINATES
- **Verify:** Re-crawl and confirm top-1 PageRank share drops.

### [MEDIUM] No /about (or /about-us, /company) page was crawled.

- **Action:** Add an /about page describing who you are and what the site does.
- **Impact:** low  **Confidence:** medium  **Difficulty:** low
- **Evidence codes:** ABOUT_PAGE_MISSING
- **Affected URLs (1):**
  - `https://example.com`
- **Verify:** Re-crawl and confirm /about is discovered.

### [MEDIUM] No /contact page was crawled.

- **Action:** Add a /contact page with a way to reach you.
- **Impact:** low  **Confidence:** medium  **Difficulty:** low
- **Evidence codes:** CONTACT_PAGE_MISSING
- **Affected URLs (1):**
  - `https://example.com`
- **Verify:** Re-crawl and confirm /contact is discovered.

### [MEDIUM] No /privacy or /terms page was crawled.

- **Action:** Add a /privacy (and optionally /terms) page.
- **Impact:** low  **Confidence:** medium  **Difficulty:** low
- **Evidence codes:** LEGAL_PAGE_MISSING
- **Affected URLs (1):**
  - `https://example.com`
- **Verify:** Re-crawl and confirm /privacy is discovered.

### [MEDIUM] Home page does not declare Organization/WebSite/Person JSON-LD.

- **Action:** Add Organization or WebSite JSON-LD to the home page.
- **Impact:** medium  **Confidence:** medium  **Difficulty:** low
- **Evidence codes:** NO_ORGANIZATION_SCHEMA
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm the schema block is detected.

### [LOW] No <header> landmark found.

- **Action:** Add a <header> landmark at the top of the page.
- **Impact:** low  **Confidence:** medium  **Difficulty:** low
- **Evidence codes:** HEADER_MISSING
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm <header> is detected.

### [LOW] No <footer> landmark found.

- **Action:** Add a <footer> landmark with secondary navigation and legal links.
- **Impact:** low  **Confidence:** low  **Difficulty:** low
- **Evidence codes:** FOOTER_MISSING
- **Affected URLs (1):**
  - `https://example.com/`
- **Verify:** Re-crawl and confirm <footer> is detected.

## Graph Summary

- Nodes (pages): **1**
- Edges (internal links): **0**
- Weakly-connected components: **1**
- Strongly-connected components: **1**
- Has directed cycle: **False**
- Orphan pages (in-degree 0): **1**
- Gini(PageRank): **0.000**
- Top-1 PageRank share: **100.0%**

### Orphan pages
- `https://example.com/`

### Top PageRank pages

| URL | PageRank | Share |
|---|---:|---:|
| `https://example.com/` | 1.0000 | 100.0% |

## Findings Ledger

Total findings: **17**

### GRAPH (1)

- **SINGLE_PAGE_DOMINATES** — Top page holds 100% of total PageRank.

### IA (3)

- **ROBOTS_TXT_MISSING** — No robots.txt was fetched from the site root.
  - Evidence: `https://example.com`
- **SITEMAP_MISSING** — No sitemap URL was declared in robots.txt.
  - Evidence: `https://example.com`
- **ORPHAN_PAGES** — 1 page(s) have no inbound internal links.
  - Evidence: `https://example.com/`

### REPUTATION (4)

- **ABOUT_PAGE_MISSING** — No /about (or /about-us, /company) page was crawled.
  - Evidence: `https://example.com`
- **CONTACT_PAGE_MISSING** — No /contact page was crawled.
  - Evidence: `https://example.com`
- **LEGAL_PAGE_MISSING** — No /privacy or /terms page was crawled.
  - Evidence: `https://example.com`
- **NO_ORGANIZATION_SCHEMA** — Home page does not declare Organization/WebSite/Person JSON-LD.
  - Evidence: `https://example.com/`

### SEMANTIC (1)

- **THIN_CONTENT** — Page has only 19 visible words.
  - Evidence: `https://example.com/`

### TECHNICAL (4)

- **CHARSET_MISSING** — No <meta charset> declaration found.
  - Evidence: `https://example.com/`
- **META_DESCRIPTION_MISSING** — <meta name='description'> missing.
  - Evidence: `https://example.com/`
- **CANONICAL_MISSING** — <link rel="canonical"> missing.
  - Evidence: `https://example.com/`
- **NO_STRUCTURED_DATA** — No JSON-LD structured data blocks found.
  - Evidence: `https://example.com/`

### UX (4)

- **NAV_MISSING** — No <nav> landmark found.
  - Evidence: `https://example.com/`
- **MAIN_MISSING** — No <main> landmark found.
  - Evidence: `https://example.com/`
- **HEADER_MISSING** — No <header> landmark found.
  - Evidence: `https://example.com/`
- **FOOTER_MISSING** — No <footer> landmark found.
  - Evidence: `https://example.com/`

---

> PageRank values are an internal analytical metric, not Google's ranking signal. 
> Recommendations are grounded in public documentation (Google Search Central, W3C, 
> schema.org, the original PageRank paper) and engineering best practice. They 
> are intended to improve technical and structural quality — not as ranking hacks.
