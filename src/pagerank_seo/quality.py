"""Public SDK model types — Search Quality extension.

This module extends the core models with the Search Quality Evaluation
Framework derived from publicly documented search-quality concepts
(Google Search Quality Rater Guidelines, General Guidelines v10.1.1,
September 2025 — summarized and cited, not reproduced).

These are project-internal analytical constructs. They do NOT reproduce
Google's proprietary ranking system. See docs/methodology.md §Search Quality
and docs/research/sources.md for the full epistemic framing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Page Purpose
# ---------------------------------------------------------------------------


class PagePurposeType(str, Enum):
    """The apparent primary purpose of a page.

    Derived from the Search Quality Rater Guidelines §2.2: raters are
    instructed to identify the true purpose of a page early in evaluation.
    Our classifier is heuristic — it observes structural signals and
    content patterns, not authorial intent.
    """
    INFORMATIONAL = "informational"
    TRANSACTIONAL = "transactional"
    NAVIGATIONAL = "navigational"
    ENTERTAINMENT = "entertainment"
    COMMUNITY = "community"
    SOFTWARE_TOOL = "software_tool"
    COMMERCE = "commerce"
    PERSONAL_EXPRESSION = "personal_expression"
    REFERENCE = "reference"
    SERVICE = "service"
    UNKNOWN = "unknown"


@dataclass
class PagePurpose:
    """The auditor's assessment of a page's primary purpose.

    ``confidence`` reflects how clearly the signals point to a single
    purpose (high) versus ambiguous signals (low). When confidence is
    low, the analyst should treat the purpose as provisional.
    """
    purpose: PagePurposeType
    confidence: str = "medium"   # high | medium | low
    signals: list[str] = field(default_factory=list)
    target_audience: str = ""
    likely_user_tasks: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Content Classification (MC / SC / Ads)
# ---------------------------------------------------------------------------


@dataclass
class ContentClassification:
    """A heuristic classification of page content into MC/SC/Ads buckets.

    Derived from the Search Quality Rater Guidelines §2.4:
    - Main Content (MC): directly helps the page achieve its purpose
    - Supplementary Content (SC): contributes to UX without being primary
    - Advertisements/Monetization: treated separately

    The guidelines explicitly state that advertising is NOT inherently a
    reason for a low Page Quality rating. We model it as a structural
    observation, not a penalty.
    """
    main_content_identified: bool = True
    main_content_evidence: list[str] = field(default_factory=list)
    supplementary_content_present: bool = False
    advertisements_present: bool = False
    ad_density: str = "none"   # none | low | medium | high
    purpose_obscured: bool = False
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reputation
# ---------------------------------------------------------------------------


class ReputationSignalType(str, Enum):
    """Types of reputation evidence the auditor can observe."""
    HTTPS = "https"
    ABOUT_PAGE = "about_page"
    CONTACT_PAGE = "contact_page"
    LEGAL_PAGE = "legal_page"
    ORGANIZATION_SCHEMA = "organization_schema"
    AUTHOR_INFO = "author_info"
    AUTHOR_SCHEMA = "author_schema"
    EXTERNAL_REFERENCE = "external_reference"
    TRANSPARENCY = "transparency"
    ANONYMOUS = "anonymous"
    SELF_SERVING = "self_serving"


@dataclass
class ReputationSignal:
    """A single piece of reputation evidence."""
    signal_type: ReputationSignalType
    present: bool = False
    evidence: str = ""
    independent: bool = False  # True if from a source other than the site itself


@dataclass
class ReputationAnalysis:
    """The auditor's reputation assessment for a page or site.

    The Search Quality Rater Guidelines §3.3 treat reputation as something
    that requires investigation beyond what a website says about itself —
    independent reviews, references, news articles, etc. Our automated
    analysis can only observe on-site signals; the skill instructs the
    agent to investigate independent sources separately.
    """
    signals: list[ReputationSignal] = field(default_factory=list)
    transparency_score: float = 0.0   # 0-100
    independent_evidence_score: float = 0.0   # 0-100
    self_serving_ratio: float = 0.0   # fraction of claims that are self-serving
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# E-E-A-T
# ---------------------------------------------------------------------------


@dataclass
class EEATAnalysis:
    """Experience, Expertise, Authoritativeness, Trust analysis.

    Derived from the Search Quality Rater Guidelines §3.4. E-E-A-T is
    a framework for evaluating the *evidence* a page provides about its
    creators and their qualifications — not a keyword checklist.

    The auditor looks for observable evidence; absence of evidence is
    recorded as such (not fabricated).
    """
    # Experience
    first_hand_evidence: list[str] = field(default_factory=list)
    demonstrations: list[str] = field(default_factory=list)
    experience_score: float = 0.0   # 0-100

    # Expertise
    credentials_observed: list[str] = field(default_factory=list)
    depth_of_knowledge: str = "unknown"   # high | medium | low | unknown
    technical_accuracy: str = "unknown"
    expertise_score: float = 0.0

    # Authoritativeness
    recognized_authorship: bool = False
    citations: list[str] = field(default_factory=list)
    independent_references: list[str] = field(default_factory=list)
    authoritativeness_score: float = 0.0

    # Trust
    transparency: list[str] = field(default_factory=list)
    accuracy_signals: list[str] = field(default_factory=list)
    responsible_ownership: bool = False
    disclosures: list[str] = field(default_factory=list)
    deceptive_signals: list[str] = field(default_factory=list)
    trust_score: float = 0.0

    # Overall
    overall_score: float = 0.0
    confidence: str = "medium"
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Originality
# ---------------------------------------------------------------------------


@dataclass
class OriginalityAnalysis:
    """Originality and added-value analysis.

    Derived from the Search Quality Rater Guidelines §4.6.5 (Scaled Content
    Abuse) and §4.6.6 (Little Effort / Originality / Added Value). The
    framework distinguishes high-quality content from content that has
    little effort, originality, or added value.

    This is particularly important for an AI-powered SEO agent: the skill
    must explicitly instruct the agent NOT to optimize by mass-producing
    generic content.
    """
    duplicate_content: bool = False
    near_duplicate_pages: list[str] = field(default_factory=list)
    templated_content: bool = False
    excessive_boilerplate: bool = False
    thin_content: bool = False
    source_paraphrasing: bool = False
    missing_original_analysis: bool = False
    missing_primary_evidence: bool = False
    lack_of_differentiation: bool = False
    unique_entities: list[str] = field(default_factory=list)
    unique_facts: list[str] = field(default_factory=list)
    unique_examples: list[str] = field(default_factory=list)
    original_functionality: bool = False
    originality_score: float = 0.0   # 0-100
    added_value_score: float = 0.0   # 0-100
    confidence: str = "medium"
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scaled Content
# ---------------------------------------------------------------------------


@dataclass
class ScaledContentPattern:
    """Potential scaled-content pattern detected across the site.

    Derived from the Search Quality Rater Guidelines §4.6.5. The auditor
    looks for patterns such as hundreds of structurally identical pages,
    minimal variation, programmatic keyword substitution, scraped
    information, and low-information pages.

    The agent should NOT automatically classify a site as spam. Instead
    it produces the pattern with evidence and confidence for human review.
    """
    detected: bool = False
    structurally_identical_count: int = 0
    template_pages: list[str] = field(default_factory=list)
    variation_score: float = 1.0   # 0 = identical, 1 = highly varied
    programmatic_substitution: bool = False
    scraped_content: bool = False
    low_information_pages: list[str] = field(default_factory=list)
    confidence: str = "low"
    evidence: list[str] = field(default_factory=list)
    recommended_action: str = ""


# ---------------------------------------------------------------------------
# Query Intent & Needs Met
# ---------------------------------------------------------------------------


class QueryIntentType(str, Enum):
    """Query intent categories derived from the Search Quality Rater
    Guidelines §12.7 (Understanding User Intent).

    The guidelines categorize different query intents including Know,
    Know Simple, Do, Website, Visit-in-Person, and queries with multiple
    meanings.
    """
    KNOW = "know"
    KNOW_SIMPLE = "know_simple"
    DO = "do"
    WEBSITE = "website"
    VISIT_IN_PERSON = "visit_in_person"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class NeedsMetLevel(str, Enum):
    """Needs Met levels derived from the Search Quality Rater
    Guidelines §13.0.

    The guidelines define Fully Meets, Highly Meets, Moderately Meets,
    Slightly Meets, and Fails to Meet in terms of how helpful a result
    is for user intent. This is a project-internal heuristic, not a
    reproduction of Google's rating system.
    """
    FULLY_MEETS = "fully_meets"
    HIGHLY_MEETS = "highly_meets"
    MODERATELY_MEETS = "moderately_meets"
    SLIGHTLY_MEETS = "slightly_meets"
    FAILS_TO_MEET = "fails_to_meet"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class QueryIntent:
    """The auditor's interpretation of a query's intent."""
    query_text: str
    intent: QueryIntentType = QueryIntentType.UNKNOWN
    confidence: str = "medium"
    possible_intents: list[QueryIntentType] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class NeedsMetAnalysis:
    """Query-page fit analysis.

    Derived from the Search Quality Rater Guidelines §13.0 and §14.0
    (Relationship Between Page Quality and Needs Met).

    Critical distinction: Page Quality is evaluated based on the landing
    page itself. Needs Met depends on the query and user intent. A
    high-quality page can still fail to meet a particular query. A result
    can be topically relevant but untrustworthy and therefore fail the
    user need.
    """
    query: QueryIntent = field(default_factory=lambda: QueryIntent(query_text=""))
    page_relevance: str = "unknown"   # high | medium | low | unknown
    intent_match: bool = False
    topic_match: bool = False
    specificity: str = "unknown"   # high | medium | low
    freshness_requirement: str = "none"   # high | medium | low | none
    freshness_met: bool = True
    prominence: str = "unknown"   # high | medium | low
    needs_met_level: NeedsMetLevel = NeedsMetLevel.NOT_APPLICABLE
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Unified Page Quality
# ---------------------------------------------------------------------------


@dataclass
class PageQualityReport:
    """Unified Page Quality analysis for a single page.

    Derived from the Search Quality Rater Guidelines §3.0 (Overall Page
    Quality). The system does NOT produce one magical number — it produces
    a multidimensional report. The composite score, if present, is
    explicitly labeled as a project heuristic.
    """
    url: str = ""
    purpose: Optional[PagePurpose] = None
    content_classification: Optional[ContentClassification] = None
    reputation: Optional[ReputationAnalysis] = None
    eeat: Optional[EEATAnalysis] = None
    originality: Optional[OriginalityAnalysis] = None
    spam_risk: str = "low"   # high | medium | low
    spam_evidence: list[str] = field(default_factory=list)
    quality_score: float = 0.0   # 0-100, project heuristic
    confidence: str = "medium"
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Search Quality Report (top-level)
# ---------------------------------------------------------------------------


@dataclass
class SearchQualityReport:
    """Top-level search quality analysis combining all frameworks.

    This is the project's unified analytical output. It combines:
    - The information graph (PageRank, link structure, IA)
    - Page Quality (purpose, content, reputation, E-E-A-T, originality)
    - Query Satisfaction (intent, needs met) — when a query is provided
    """
    page_reports: list[PageQualityReport] = field(default_factory=list)
    scaled_content: Optional[ScaledContentPattern] = None
    query_satisfaction: list[NeedsMetAnalysis] = field(default_factory=list)
    site_reputation_abuse_risk: str = "low"
    site_reputation_evidence: list[str] = field(default_factory=list)
    overall_quality_score: float = 0.0   # 0-100, project heuristic
    confidence: str = "medium"
    notes: list[str] = field(default_factory=list)
