"""Graph analysis for the PageRank SEO SDK.

Builds a NetworkX directed graph from a ``CrawlResult`` and computes:

- Standard PageRank (Dangling-node-safe)
- Weighted PageRank (link position + rel-aware weights)
- In/out degree
- Weakly-connected components
- Strongly-connected components
- Orphan detection (in-degree zero)
- Gini coefficient of PageRank distribution
- Top-1 PageRank share

References
----------
- Page, Brin, Motwani, Winograd (1999). "The PageRank Citation Ranking."
  http://ilpubs.stanford.edu:8090/422/1/1999-66.pdf
"""
from __future__ import annotations

from typing import Iterable

import networkx as nx

from pagerank_seo.models import (
    CrawlResult,
    GraphMetrics,
    Link,
    RelType,
    SiteGraph,
)


# ---------------------------------------------------------------------------
# Edge weights
# ---------------------------------------------------------------------------


# Following Google Search Central, nofollow/sponsored/ugc are hint attributes.
# We model them as weight reductions rather than removals.
_REL_WEIGHTS = {
    RelType.DOFOLLOW: 1.0,
    RelType.NOFOLLOW: 0.3,  # hint: still contributes, but reduced
    RelType.SPONSORED: 0.2,
    RelType.UGC: 0.5,
}


def _edge_weight(link: Link) -> float:
    """Compute a single edge's weight from position + rel."""
    base = link.position_weight if link.position_weight > 0 else 0.5
    return base * _REL_WEIGHTS.get(link.rel, 1.0)


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(crawl: CrawlResult) -> nx.DiGraph:
    """Build a directed graph from the crawl result."""
    g = nx.DiGraph()
    for url, page in crawl.pages.items():
        # Add the node even if it has no out-links, so it shows up in metrics.
        g.add_node(url, page=page)
    for link in crawl.edges:
        src = link.source_url
        dst = link.target_url
        # Drop self-loops (they are not informative for site-graphs).
        if src == dst:
            continue
        if src not in g or dst not in g:
            continue
        w = _edge_weight(link)
        # If multiple edges exist between the same nodes, keep the strongest.
        if g.has_edge(src, dst):
            existing = g[src][dst].get("weight", 0.0)
            if w > existing:
                g[src][dst]["weight"] = w
        else:
            g.add_edge(src, dst, weight=w)
    return g


# ---------------------------------------------------------------------------
# PageRank (standard)
# ---------------------------------------------------------------------------


def standard_pagerank(graph: nx.DiGraph, *, alpha: float = 0.85) -> dict[str, float]:
    """Compute standard PageRank with dangling-node handling.

    Dangling nodes (no out-edges) are connected back to every other node
    with equal probability so their PageRank doesn't leak (this is the
    "rank sink" correction from the original PageRank paper §2.4).
    """
    if graph.number_of_nodes() == 0:
        return {}
    return nx.pagerank(graph, alpha=alpha, weight="weight")


def weighted_pagerank(graph: nx.DiGraph, *, alpha: float = 0.85) -> dict[str, float]:
    """Compute weighted PageRank using position+rel weights.

    The "weight" attribute is used for both the standard and weighted
    PageRank — the difference is that the position weights reflect
    observed semantic placement in the DOM, not just a uniform
    per-edge weight. This is documented in methodology.md §2.3 as a
    project-side analytical tool.
    """
    # nx.pagerank already uses the 'weight' attribute; aliasing for clarity.
    return standard_pagerank(graph, alpha=alpha)


# ---------------------------------------------------------------------------
# Centrality + distribution
# ---------------------------------------------------------------------------


def degree_dicts(graph: nx.DiGraph) -> tuple[dict[str, int], dict[str, int]]:
    """Return (in_degree, out_degree) dictionaries."""
    nodes = list(graph.nodes)
    in_deg = {n: graph.in_degree(n) for n in nodes}
    out_deg = {n: graph.out_degree(n) for n in nodes}
    return in_deg, out_deg


def gini(values: Iterable[float]) -> float:
    """Gini coefficient of a non-negative value distribution.

    Returns 0.0 for perfectly equal distributions and approaches 1.0
    for total concentration in one element.
    """
    values = sorted(float(v) for v in values)
    n = len(values)
    if n == 0:
        return 0.0
    if sum(values) == 0:
        return 0.0
    cumulative = 0.0
    for i, v in enumerate(values, start=1):
        cumulative += i * v
    total = sum(values)
    # Standard formula: G = (2 * sum(i*x_i) / (n * sum(x_i))) - (n + 1) / n
    return (2.0 * cumulative) / (n * total) - (n + 1) / n


def weakly_connected_components_count(graph: nx.DiGraph) -> int:
    """Number of weakly connected components."""
    if graph.number_of_nodes() == 0:
        return 0
    return nx.number_weakly_connected_components(graph)


def strongly_connected_components_count(graph: nx.DiGraph) -> int:
    """Number of strongly connected components."""
    if graph.number_of_nodes() == 0:
        return 0
    return nx.number_strongly_connected_components(graph)


def has_cycle(graph: nx.DiGraph) -> bool:
    """True if the graph has at least one directed cycle."""
    if graph.number_of_nodes() == 0:
        return False
    try:
        nx.find_cycle(graph, orientation="original")
        return True
    except nx.NetworkXNoCycle:
        return False


def orphan_pages(graph: nx.DiGraph, *, seed_url: str | None = None) -> list[str]:
    """Pages with in-degree zero (excluding the seed URL if provided).

    The seed URL has in-degree zero by construction in any BFS crawl.
    Excluding it makes the metric interpretable.
    """
    return [
        n for n in graph.nodes
        if graph.in_degree(n) == 0 and n != seed_url
    ]


# ---------------------------------------------------------------------------
# Composite metrics
# ---------------------------------------------------------------------------


def compute_metrics(graph: nx.DiGraph, *, seed_url: str | None = None) -> GraphMetrics:
    """Compute and return all metrics for the graph."""
    pagerank = standard_pagerank(graph)
    weighted = weighted_pagerank(graph)
    in_deg, out_deg = degree_dicts(graph)
    orphans = orphan_pages(graph, seed_url=seed_url)

    total_pr = sum(pagerank.values())
    if total_pr > 0:
        top1 = max(pagerank.values())
        top1_share = top1 / total_pr
    else:
        top1_share = 0.0

    return GraphMetrics(
        node_count=graph.number_of_nodes(),
        edge_count=graph.number_of_edges(),
        pagerank=pagerank,
        weighted_pagerank=weighted,
        in_degree=in_deg,
        out_degree=out_deg,
        weakly_connected_components=weakly_connected_components_count(graph),
        orphan_pages=orphans,
        gini_pagerank=gini(pagerank.values()),
        top1_share=top1_share,
        has_cycle=has_cycle(graph),
        strongly_connected_components=strongly_connected_components_count(graph),
    )


def to_site_graph(crawl: CrawlResult) -> SiteGraph:
    """Build a ``SiteGraph`` from a ``CrawlResult``."""
    g = build_graph(crawl)
    seed = crawl.start_url
    metrics = compute_metrics(g, seed_url=seed)
    return SiteGraph(pages=crawl.pages, metrics=metrics)
