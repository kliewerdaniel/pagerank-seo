"""Search Quality analyzer — page purpose, content, reputation, E-E-A-T, originality.

This module extends the core analyzer with concepts derived from the publicly
documented Search Quality Rater Guidelines (General Guidelines v10.1.1,
September 2025). These are project-internal analytical constructs.

See `docs/methodology.md` §Search Quality and `docs/research/sources.md` for
the full epistemic framing.
"""
from __future__ import annotations

import re

from pagerank_seo.models import CrawlResult, Page
from pagerank_seo.quality import (
    ContentClassification,
    EEATAnalysis,
    OriginalityAnalysis,
    PagePurpose,
    PagePurposeType,
    PageQualityReport,
    ReputationAnalysis,
    ReputationSignal,
    ReputationSignalType,
    ScaledContentPattern,
    SearchQualityReport,
)


# ---------------------------------------------------------------------------
# Page Purpose classifier
# ---------------------------------------------------------------------------


# Heuristic signals for page purpose. Each entry maps a pattern to a purpose.
_PURPOSE_SIGNALS: list[tuple[str, PagePurposeType, list[str]]] = [
    # Transactional / commerce signals
    (r"\b(buy|cart|checkout|order|purchase|shop|add.to.cart|price)\b", PagePurposeType.TRANSACTIONAL, ["cart", "checkout", "buy"]),
    (r"\b(subscribe|sign.up|register|join.free)\b", PagePurposeType.TRANSACTIONAL, ["subscribe", "register"]),
    (r"\b(download|get.started|start.free.trial)\b", PagePurposeType.TRANSACTIONAL, ["download", "trial"]),
    # Software / tool signals
    (r"\b(open.source|github.com|npm|pip install|api.documentation)\b", PagePurposeType.SOFTWARE_TOOL, ["github", "api", "docs"]),
    # Community signals
    (r"\b(forum|community|discussion|thread|comment|reply)\b", PagePurposeType.COMMUNITY, ["forum", "community"]),
    # Entertainment signals
    (r"\b(watch|stream|play|game|video|trailer)\b", PagePurposeType.ENTERTAINMENT, ["watch", "stream", "play"]),
    # Reference signals
    (r"\b(documentation|reference|glossary|dictionary|wiki|faq)\b", PagePurposeType.REFERENCE, ["docs", "reference"]),
    # Service signals
    (r"\b(book.appointment|schedule|hire|consultation|service)\b", PagePurposeType.SERVICE, ["appointment", "service"]),
    # Personal expression signals
    (r"\b(blog|diary|personal|my.journey|my.story)\b", PagePurposeType.PERSONAL_EXPRESSION, ["blog", "personal"]),
]


def classify_page_purpose(page: Page) -> PagePurpose:
    """Heuristically classify a page's primary purpose.

    This observes structural signals (URL patterns, headings, body text)
    and content patterns. It does NOT know authorial intent. Confidence
    reflects signal clarity.
    """
    signals: list[str] = []
    purpose_scores: dict[PagePurposeType, int] = {p: 0 for p in PagePurposeType}

    title = (page.title or "").lower()
    h1 = (page.h1 or "").lower()
    body_text = " ".join(t for _, t in page.headings).lower()
    meta_desc = (page.meta_description or "").lower()

    # Parse URL path for pattern matching
    from urllib.parse import urlsplit
    url_path = urlsplit(page.url).path.lower()

    # Combine textual signals
    combined = f"{title} {h1} {body_text} {meta_desc}"

    # Check URL patterns
    if re.search(r"^/blog", url_path):
        purpose_scores[PagePurposeType.PERSONAL_EXPRESSION] += 2
        signals.append("url:blog_path")
    if re.search(r"^/docs?", url_path) or re.search(r"/documentation", url_path):
        purpose_scores[PagePurposeType.REFERENCE] += 2
        signals.append("url:docs_path")
    if re.search(r"^/about", url_path):
        purpose_scores[PagePurposeType.INFORMATIONAL] += 2
        signals.append("url:about_path")
    if re.search(r"^/contact", url_path):
        purpose_scores[PagePurposeType.NAVIGATIONAL] += 2
        signals.append("url:contact_path")
    if re.search(r"^/product", url_path) or re.search(r"/shop/", url_path):
        purpose_scores[PagePurposeType.COMMERCE] += 2
        signals.append("url:product_path")
    if re.search(r"^/tool", url_path) or re.search(r"/api/", url_path):
        purpose_scores[PagePurposeType.SOFTWARE_TOOL] += 2
        signals.append("url:tool_path")

    # Check content patterns
    for pattern, purpose, signal_ids in _PURPOSE_SIGNALS:
        if re.search(pattern, combined):
            purpose_scores[purpose] += 1
            signals.extend(signal_ids)

    # Determine the winner
    max_score = max(purpose_scores.values()) if purpose_scores else 0
    if max_score == 0:
        # Default to informational for pages with substantial content
        if page.text_word_count and page.text_word_count > 50:
            return PagePurpose(
                purpose=PagePurposeType.INFORMATIONAL,
                confidence="low",
                signals=["content_length"],
            )
        return PagePurpose(
            purpose=PagePurposeType.UNKNOWN,
            confidence="low",
            signals=[],
        )

    # Find the purpose with the max score
    winner = max(purpose_scores.items(), key=lambda item: item[1])[0]
    confidence = "high" if max_score >= 3 else ("medium" if max_score >= 2 else "low")

    return PagePurpose(
        purpose=winner,
        confidence=confidence,
        signals=[s for s in set(signals)],
    )


# ---------------------------------------------------------------------------
# Content Classification
# ---------------------------------------------------------------------------


def classify_content(page: Page) -> ContentClassification:
    """Heuristically classify page content into MC / SC / Ads buckets.

    Derived from the Search Quality Rater Guidelines §2.4. This is a
    structural observation, not a quality judgment.
    """
    out = ContentClassification()

    # Main content: the <main> element, <article>, or the largest text block
    if page.has_main:
        out.main_content_identified = True
        out.main_content_evidence.append("<main> landmark present")
    elif any(h[0] == 1 for h in page.headings):
        out.main_content_identified = True
        out.main_content_evidence.append("<h1> present (proxy for MC)")
    elif page.text_word_count and page.text_word_count > 80:
        out.main_content_identified = True
        out.main_content_evidence.append(f"substantial body text ({page.text_word_count} words)")
    else:
        out.main_content_identified = False
        out.notes.append("No clear main content identified")

    # Supplementary content: nav, aside, header, footer, sidebar
    if page.has_nav:
        out.supplementary_content_present = True
    if page.has_header and page.has_footer:
        out.supplementary_content_present = True

    # Advertisements: heuristic — count common ad-related patterns in HTML
    ad_signals = 0
    html_lower = page.raw_html.lower()
    ad_patterns = [
        r"googleads", r"googlesyndication", r"adsbygoogle",
        r"doubleclick", r"amazon-adsystem", r"advertisement",
        r"class=[\"'][^\"']*ad[^\"']*[\"']", r"id=[\"'][^\"']*ad[^\"']*[\"']",
    ]
    for pat in ad_patterns:
        if re.search(pat, html_lower):
            ad_signals += 1

    if ad_signals > 0:
        out.advertisements_present = True
        if ad_signals >= 3:
            out.ad_density = "high"
        elif ad_signals >= 2:
            out.ad_density = "medium"
        else:
            out.ad_density = "low"

    # Purpose obscured: title/content overlap very low
    if page.title and page.text_word_count and page.text_word_count > 30:
        title_tokens = set(re.findall(r"\w+", page.title.lower()))
        body_text = " ".join(t for _, t in page.headings).lower()
        body_tokens = set(re.findall(r"\w+", body_text))
        if title_tokens and body_tokens:
            overlap = len(title_tokens & body_tokens) / len(title_tokens | body_tokens)
            if overlap < 0.05:
                out.purpose_obscured = True
                out.notes.append("Title and body have almost no word overlap")

    return out


# ---------------------------------------------------------------------------
# Reputation Analysis
# ---------------------------------------------------------------------------


def analyze_reputation(page: Page, crawl: CrawlResult) -> ReputationAnalysis:
    """Analyze reputation signals for a page or site.

    Derived from the Search Quality Rater Guidelines §3.3. The guidelines
    treat reputation as requiring investigation beyond what a website says
    about itself. Our automated analysis can only observe on-site signals.
    """
    out = ReputationAnalysis()

    # HTTPS
    if page.url.startswith("https://"):
        out.signals.append(ReputationSignal(
            signal_type=ReputationSignalType.HTTPS,
            present=True,
            evidence="Page served over HTTPS",
        ))

    # Author information: look for common author patterns
    html_lower = page.raw_html.lower()
    author_patterns = [
        r"class=[\"'][^\"']*author[^\"']*[\"']",
        r"rel=[\"']author[\"']",
        r"byline", r"written.by",
    ]
    author_found = any(re.search(p, html_lower) for p in author_patterns)
    out.signals.append(ReputationSignal(
        signal_type=ReputationSignalType.AUTHOR_INFO,
        present=author_found,
        evidence="Author markup detected" if author_found else "No author markup",
    ))

    # Organization schema
    has_org_schema = any(
        b.get("@type") in ("Organization", "WebSite", "Person")
        for b in page.json_ld_blocks
    )
    out.signals.append(ReputationSignal(
        signal_type=ReputationSignalType.ORGANIZATION_SCHEMA,
        present=has_org_schema,
        evidence="Organization/Person JSON-LD present" if has_org_schema else "No Organization schema",
    ))

    # Transparency signals
    transparency_score = 0.0
    if has_org_schema:
        transparency_score += 40
    if author_found:
        transparency_score += 30
    if page.url.startswith("https://"):
        transparency_score += 30
    out.transparency_score = transparency_score

    # Self-serving ratio: pages on a site are inherently self-serving
    # (they're the site talking about itself). We note this as a structural
    # observation, not a judgment.
    out.self_serving_ratio = 1.0
    out.notes.append(
        "Reputation claims are self-serving by default; "
        "independent verification requires external research"
    )

    return out


# ---------------------------------------------------------------------------
# E-E-A-T Analysis
# ---------------------------------------------------------------------------


def analyze_eeat(page: Page) -> EEATAnalysis:
    """Analyze Experience, Expertise, Authoritativeness, Trust signals.

    Derived from the Search Quality Rater Guidelines §3.4. E-E-A-T is
    a framework for evaluating the evidence a page provides about its
    creators and their qualifications — not a keyword checklist.
    """
    out = EEATAnalysis()
    html_lower = page.raw_html.lower()

    # --- Experience ---
    experience_signals = [
        r"in.my.experience", r"i.have.been", r"i.found", r"after.years.of",
        r"first.hand", r"hands.on", r"case.study",
    ]
    for pat in experience_signals:
        if re.search(pat, html_lower):
            out.first_hand_evidence.append(pat)
    out.experience_score = min(100, len(out.first_hand_evidence) * 25)

    # --- Expertise ---
    expertise_signals = [
        r"\b(phd|md|dr\.|professor|certified|expert|specialist)\b",
        r"\b(years.of.experience|decade|industry.veteran)\b",
    ]
    for pat in expertise_signals:
        if re.search(pat, html_lower):
            out.credentials_observed.append(pat)
    if out.credentials_observed:
        out.expertise_score = min(100, 40 + len(out.credentials_observed) * 20)
        out.depth_of_knowledge = "medium"
    else:
        out.expertise_score = 20  # baseline for any content
        out.depth_of_knowledge = "unknown"

    # --- Authoritativeness ---
    if re.search(r"rel=[\"']author[\"']", html_lower) or re.search(r"class=[\"'][^\"']*author", html_lower):
        out.recognized_authorship = True
        out.authoritativeness_score += 30
    if page.json_ld_blocks:
        for block in page.json_ld_blocks:
            if block.get("@type") == "Person":
                out.authoritativeness_score += 30
            if block.get("@type") == "Organization":
                out.authoritativeness_score += 20
    out.authoritativeness_score = min(100, out.authoritativeness_score)

    # --- Trust ---
    if page.url.startswith("https://"):
        out.transparency.append("HTTPS")
        out.trust_score += 30
    if out.recognized_authorship:
        out.transparency.append("recognized authorship")
        out.trust_score += 25
    if any(b.get("@type") == "Organization" for b in page.json_ld_blocks):
        out.transparency.append("Organization schema")
        out.trust_score += 20
    # Deceptive signals
    deceptive_patterns = [
        r"click.here", r"act.now", r"limited.time", r"guaranteed.results",
        r"miracle", r"secret", r"they.don't.want.you.to.know",
    ]
    for pat in deceptive_patterns:
        if re.search(pat, html_lower):
            out.deceptive_signals.append(pat)
    out.trust_score -= len(out.deceptive_signals) * 10
    out.trust_score = max(0, min(100, out.trust_score))

    # Overall E-E-A-T
    out.overall_score = (
        out.experience_score * 0.25
        + out.expertise_score * 0.25
        + out.authoritativeness_score * 0.25
        + out.trust_score * 0.25
    )
    out.notes.append("E-E-A-T scores are heuristic observations, not verified credentials")

    return out


# ---------------------------------------------------------------------------
# Originality Analysis
# ---------------------------------------------------------------------------


def analyze_originality(page: Page, all_pages: dict[str, Page]) -> OriginalityAnalysis:
    """Analyze originality and added value of a page.

    Derived from the Search Quality Rater Guidelines §4.6.5 and §4.6.6.
    Distinguishes high-quality content from content with little effort,
    originality, or added value.
    """
    out = OriginalityAnalysis()

    # Thin content
    if page.text_word_count and page.text_word_count < 80:
        out.thin_content = True

    # Missing original analysis: if the page has very little unique text
    if page.text_word_count and page.text_word_count < 30:
        out.missing_original_analysis = True

    # Check for near-duplicate content across the site
    page_title = (page.title or "").strip().lower()
    page_headings = " ".join(t for _, t in page.headings).lower()
    for url, other in all_pages.items():
        if url == page.url:
            continue
        other_title = (other.title or "").strip().lower()
        other_headings = " ".join(t for _, t in other.headings).lower()
        # Exact title match
        if page_title and other_title and page_title == other_title:
            out.near_duplicate_pages.append(url)
        # High heading overlap
        elif page_headings and other_headings:
            ptokens = set(re.findall(r"\w+", page_headings))
            otokens = set(re.findall(r"\w+", other_headings))
            if ptokens and otokens:
                overlap = len(ptokens & otokens) / len(ptokens | otokens)
                if overlap > 0.8:
                    out.near_duplicate_pages.append(url)

    out.lack_of_differentiation = len(out.near_duplicate_pages) > 0

    # Original entities / facts / examples: look for specific patterns
    combined = f"{page.title or ''} {page_headings}".lower()
    if re.search(r"\b(study|research|survey|data|statistics)\b", combined):
        out.unique_facts.append("references to research/data")
    if re.search(r"\b(example|case.study|demo|screenshot)\b", combined):
        out.unique_examples.append("examples/demos")

    # Originality score
    originality_score = 50.0  # baseline
    if not out.thin_content:
        originality_score += 20
    if not out.lack_of_differentiation:
        originality_score += 20
    if out.unique_facts:
        originality_score += 10
    if out.unique_examples:
        originality_score += 10
    out.originality_score = min(100, originality_score)

    # Added value score
    added_value = 40.0
    if page.text_word_count and page.text_word_count >= 200:
        added_value += 20
    if page.json_ld_blocks:
        added_value += 10
    if out.unique_facts:
        added_value += 15
    if out.unique_examples:
        added_value += 15
    out.added_value_score = min(100, added_value)

    return out


# ---------------------------------------------------------------------------
# Scaled Content Detection
# ---------------------------------------------------------------------------


def detect_scaled_content(all_pages: dict[str, Page]) -> ScaledContentPattern:
    """Detect potential scaled-content patterns across the site.

    Derived from the Search Quality Rater Guidelines §4.6.5. The auditor
    looks for patterns such as hundreds of structurally identical pages,
    minimal variation, programmatic keyword substitution, scraped
    information, and low-information pages.
    """
    out = ScaledContentPattern()

    if len(all_pages) < 5:
        return out  # Not enough pages to detect a pattern

    # Group pages by their heading structure signature
    signatures: dict[str, list[str]] = {}
    for url, page in all_pages.items():
        # Signature: sequence of heading levels + title pattern
        heading_sig = "-".join(str(lvl) for lvl, _ in page.headings)
        title_pattern = re.sub(r"\d+", "#", page.title or "")
        sig = f"{heading_sig}|{title_pattern[:50]}"
        signatures.setdefault(sig, []).append(url)

    # Find the largest group
    if signatures:
        largest_sig = max(signatures, key=lambda k: len(signatures[k]))
        largest_group = signatures[largest_sig]
        ratio = len(largest_group) / len(all_pages)

        if ratio > 0.5 and len(largest_group) >= 5:
            out.detected = True
            out.structurally_identical_count = len(largest_group)
            out.template_pages = largest_group[:20]
            out.variation_score = 1.0 - ratio
            out.confidence = "high" if ratio > 0.8 else "medium"
            out.evidence.append(
                f"{len(largest_group)}/{len(all_pages)} pages share the same "
                f"heading structure signature"
            )
            out.recommended_action = (
                "Review templated pages for unique value. Each page should "
                "offer distinct content, not just keyword substitution."
            )

    # Low-information pages
    low_info = [
        url for url, p in all_pages.items()
        if p.text_word_count and p.text_word_count < 50
    ]
    if len(low_info) > len(all_pages) * 0.3:
        out.low_information_pages = low_info[:20]
        if not out.detected:
            out.detected = True
            out.confidence = "medium"
        out.evidence.append(
            f"{len(low_info)} pages have fewer than 50 words"
        )

    return out


# ---------------------------------------------------------------------------
# Unified Page Quality
# ---------------------------------------------------------------------------


def analyze_page_quality(
    page: Page,
    crawl: CrawlResult,
) -> PageQualityReport:
    """Run all search quality analyses on a single page and return a report."""
    all_pages = crawl.pages

    purpose = classify_page_purpose(page)
    content = classify_content(page)
    reputation = analyze_reputation(page, crawl)
    eeat = analyze_eeat(page)
    originality = analyze_originality(page, all_pages)

    # Spam risk assessment
    spam_risk = "low"
    spam_evidence: list[str] = []
    if originality.thin_content and purpose.confidence == "low":
        spam_risk = "medium"
        spam_evidence.append("thin content with unclear purpose")
    if eeat.deceptive_signals:
        spam_risk = "high"
        spam_evidence.extend([f"deceptive signal: {s}" for s in eeat.deceptive_signals])
    if content.purpose_obscured:
        spam_risk = max(spam_risk, "medium", key=lambda x: {"low": 0, "medium": 1, "high": 2}[x])
        spam_evidence.append("purpose obscured")

    # Quality score (project heuristic)
    quality_score = (
        eeat.overall_score * 0.30
        + originality.originality_score * 0.25
        + originality.added_value_score * 0.20
        + reputation.transparency_score * 0.15
        + (100 if content.main_content_identified else 0) * 0.10
    )

    return PageQualityReport(
        url=page.url,
        purpose=purpose,
        content_classification=content,
        reputation=reputation,
        eeat=eeat,
        originality=originality,
        spam_risk=spam_risk,
        spam_evidence=spam_evidence,
        quality_score=round(quality_score, 2),
        confidence=purpose.confidence,
    )


# ---------------------------------------------------------------------------
# Top-level Search Quality Report
# ---------------------------------------------------------------------------


def analyze_search_quality(
    crawl: CrawlResult,
) -> SearchQualityReport:
    """Run the full search quality analysis on a crawl result."""
    page_reports = [
        analyze_page_quality(page, crawl)
        for page in crawl.pages.values()
    ]

    scaled_content = detect_scaled_content(crawl.pages)

    # Site reputation abuse risk
    site_reputation_risk = "low"
    site_reputation_evidence: list[str] = []
    if scaled_content.detected:
        site_reputation_risk = scaled_content.confidence
        site_reputation_evidence = scaled_content.evidence

    # Overall quality score
    if page_reports:
        overall = sum(p.quality_score for p in page_reports) / len(page_reports)
    else:
        overall = 0.0

    return SearchQualityReport(
        page_reports=page_reports,
        scaled_content=scaled_content,
        site_reputation_abuse_risk=site_reputation_risk,
        site_reputation_evidence=site_reputation_evidence,
        overall_quality_score=round(overall, 2),
        confidence="medium",
    )
