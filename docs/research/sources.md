# Research Sources

Primary sources used to ground the PageRank SEO methodology. Every heuristic in the analyzer
traces back to one or more of these references.

## 1. Original PageRank paper (foundational)

- **Page, L., Brin, S., Motwani, R., Winograd, T. (1999).** *The PageRank Citation Ranking: Bringing Order to the Web.* Stanford InfoLab Technical Report 1999-66.
  <http://ilpubs.stanford.edu:8090/422/1/1999-66.pdf>
  Used for: the formal PageRank definition (eigenvector of the link graph with a damping factor
  for the random-surfer model), and the explicit distinction between "backlinks count" (simple
  citation counting) and PageRank (citation counting weighted by source authority). The paper
  also establishes the rank-sink solution that motivates the damping factor — directly relevant
  to how we model authority sinks in our graph.

- **Wikipedia: PageRank.** <https://en.wikipedia.org/wiki/PageRank>
  Used for: historical context (origins in academic citation analysis, predecessor systems like
  HITS/Kleinberg and TrustRank) and the explicit note that PageRank's patents have all expired —
  the algorithm is in the public domain.

## 2. Google Search Central (authoritative public docs)

- **How Google Search Works.** <https://developers.google.com/search/docs/fundamentals/how-search-works>
  Used for: the three-stage model (Crawling → Indexing → Serving), the role of `robots.txt`,
  JavaScript rendering with a recent Chrome build, and the explicit statement that
  "Google doesn't accept payment to crawl a site more frequently, or rank it higher."

- **Spam Policies for Google Web Search.** <https://developers.google.com/search/docs/essentials/spam-policies>
  Used for: definitions of cloaking, doorway abuse, hidden text and link abuse, keyword
  stuffing, link spam, sneaky redirects, thin affiliation, and site-reputation abuse. The
  analyzer flags patterns that **match these documented anti-patterns** — not as a claim about
  Google's manual actions, but as a warning that the patterns Google has publicly said it
  considers spam exist on the audited site.

- **URL Canonicalization.** <https://developers.google.com/search/docs/crawling-indexing/canonicalization>
  Used for: the four canonicalization signals (HTTPS vs HTTP, redirects, sitemap inclusion,
  `rel="canonical"` link), and the explicit framing that canonical is a *hint*, not a rule.

- **Introduction to Structured Data.** <https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data>
  Used for: JSON-LD as the recommended format, the explicit "don't create blank pages just to
  hold structured data" guidance, and the use of `sameAs` for entity disambiguation.

- **Introduction to robots.txt.** <https://developers.google.com/search/docs/crawling-indexing/robots/intro>
  Used for: the warning that robots.txt is not an access-control mechanism — a page disallowed
  in robots.txt can still be indexed if linked to from elsewhere. The crawler's robots.txt
  handling is conservative-by-default for the same reason.

- **Learn about Sitemaps.** <https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview>
  Used for: when a sitemap is recommended (large sites, new sites with few external links,
  rich media content) and the 500-page heuristic.

- **Core Web Vitals and Google Search Results.** <https://developers.google.com/search/docs/appearance/core-web-vitals>
  Used for: the three documented metrics (LCP < 2.5s, INP < 200ms, CLS < 0.1) and the explicit
  framing that these are part of a broader "page experience" set, not the only ranking signals.

## 3. Search Quality Rater Guidelines (v0.2.0)

- **Google Search Quality Rater Guidelines — General Guidelines Version 10.1.1, September 9, 2025.**
  Publicly documented guidance for search quality raters. 181 pages. Used for the conceptual
  framework in `docs/methodology.md` §3 and the `quality.py` / `quality_analyzer.py` modules.

  Key sections integrated:
  - §0.0 The Search Experience — foundational context
  - §2.2 Understanding the Purpose of a Webpage — page purpose classification
  - §2.4.1 Main Content / §2.4.2 Supplementary Content / §2.4.3 Advertisements — content classification
  - §3.3 Reputation — reputation analysis framework
  - §3.4 E-E-A-T — Experience, Expertise, Authoritativeness, Trust
  - §4.6.4 Site Reputation Abuse — site reputation abuse detection
  - §4.6.5 Scaled Content Abuse — scaled content detection
  - §4.6.6 Little Effort / Originality / Added Value — originality analysis
  - §12.7 Understanding User Intent — query intent classification
  - §13.0 Needs Met — query satisfaction analysis
  - §14.0 Relationship Between Page Quality and Needs Met — the critical distinction

  **Epistemic note:** The guidelines describe how human raters evaluate search quality.
  They are NOT a public description of Google's complete ranking algorithm. Human ratings
  do not directly move individual pages up or down in search results. The project uses
  these concepts as an analytical framework, not as a reproduction of Google's systems.

## 4. Standards and specifications

- **RFC 9309 — Robots Exclusion Protocol (2022).** <https://www.rfc-editor.org/rfc/rfc9309.html>
  The official IETF specification of robots.txt syntax (user-agent, allow, disallow). The
  crawler implements this — supports `User-agent` matching (case-insensitive substring),
  `Allow`/`Disallow` path-pattern rules, and combined groups.

- **Sitemaps Protocol 0.9.** <https://www.sitemaps.org/protocol.html>
  Used for: the `<urlset>` / `<url>` / `<loc>` / `<lastmod>` / `<changefreq>` / `<priority>`
  format. The crawler can parse an optional sitemap to seed URL discovery (in addition to
  BFS).

- **HTML Living Standard (WHATWG), §4.3 Sections.** <https://html.spec.whatwg.org/multipage/sections.html>
  Used for: definitions of `body`, `article`, `section`, `nav`, `aside`, `header`, `footer`,
  `h1`–`h6`, `address` — these are the semantic landmarks the analyzer checks for.

- **HTML `<meta>` element — MDN.** <https://developer.mozilla.org/en-US/docs/Web/HTML/Element/meta>
  Used for: charset declaration rules (UTF-8 only, first 1024 bytes), `name`/`http-equiv`/
  `content` attribute semantics, and meta-refresh behavior.

- **schema.org.** <https://schema.org/docs/schemas.html>
  Used for: the entity vocabulary (Organization, Person, Article, BreadcrumbList, WebSite,
  Product, etc.) the analyzer looks for in JSON-LD blocks.

- **WCAG 2.2 — W3C.** <https://www.w3.org/WAI/standards-guidelines/wcag/>
  Used for: the four accessibility principles (Perceivable, Operable, Understandable, Robust)
  and the heuristic checks we surface (alt-text on images, `lang` on `<html>`, landmark
  elements). The analyzer checks for **observable accessibility issues**, not full WCAG
  conformance — full conformance requires manual review.

## 5. Methodology framing

The decision to call the methodology "PageRank SEO" (PRSEO) rests on three points:

1. PageRank is a **public-domain algorithm** (all patents expired as of September 24, 2019).
   Its definition is fixed in the 1999 Stanford paper. We can implement and reason about it.
2. The **information-graph framing** is well established in the IR literature: web pages are
   nodes, hyperlinks are edges, importance propagates through the graph. This is the same
   framing Page & Brin used in 1999 and that HITS, TrustRank, and SALSA all share.
3. **Google Search Central explicitly documents** that crawlers extract links from known
   pages to discover new pages. Internal linking is therefore a directly observable property
   of how crawlers navigate a site — not a speculation.

What we **do not** claim:

- That our PageRank implementation matches Google's production ranking. Google's system has
  evolved through many components (Hummingbird, RankBrain, Panda, Penguin, Helpful Content
  updates, AI Overviews); any modern system uses hundreds of signals.
- That any specific PageRank score corresponds to a Google ranking position.
- That fixing the recommendations we surface will guarantee higher rankings. The
  recommendations are grounded in public documentation and graph theory — they improve the
  *technical and structural quality* of a site, which is a defensible engineering goal
  independent of any specific ranking algorithm.

## 6. Hypotheses requiring empirical validation

Several heuristics in the analyzer are **reasonable inferences** rather than documented
Google behaviors. They are flagged in the source code with `# HYPOTHESIS:` comments:

- **Position-weighted links** — links higher in the DOM (e.g., inside `<nav>`) are weighted
  more heavily. This follows the "user attention" intuition (above-the-fold links get more
  clicks) but Google has not publicly stated this. We mark it as a weighting choice for
  *internal graph analysis*, not as a ranking claim.
- **Title/content overlap** as a proxy for topical focus — a heuristic from classical IR
  (tf-idf). Used for the "semantic coherence" dimension.
- **Breadcrumb presence** as a UX and IA signal — documented in schema.org as
  `BreadcrumbList`, and broadly accepted as best practice, but not explicitly required by
  Google for ranking.

These heuristics are **tools for the analyst**, not **truths about Google's algorithm**.
