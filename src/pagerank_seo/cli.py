"""Command-line entrypoint: ``pagerank-seo audit <url>``.

Supports the full audit pipeline with sensible defaults; advanced users
should import ``SiteAuditor`` from ``pagerank_seo.auditor`` instead.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pagerank_seo import __version__
from pagerank_seo.auditor import SiteAuditor
from pagerank_seo.models import AuditConfig
from pagerank_seo.report import to_html, to_json, to_markdown


def _build_config(args: argparse.Namespace) -> AuditConfig:
    return AuditConfig(
        start_url=args.url,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        request_timeout_seconds=args.timeout,
        requests_per_second=args.rate,
        user_agent=args.user_agent,
        respect_robots_txt=not args.ignore_robots,
        follow_external_links=args.follow_external,
        max_document_bytes=args.max_bytes,
    )


def _cmd_audit(args: argparse.Namespace) -> int:
    try:
        config = _build_config(args)
    except ValueError as exc:
        print(f"invalid configuration: {exc}", file=sys.stderr)
        return 2
    auditor = SiteAuditor(
        config,
        progress_callback=(lambda line: print(f"[crawl] {line}", file=sys.stderr)) if args.verbose else None,
    )

    try:
        report = auditor.audit()
    except Exception as exc:
        print(f"audit failed: {exc}", file=sys.stderr)
        return 1

    # Output
    outputs = [o.strip() for o in args.output.split(",")] if args.output else ["markdown"]
    for fmt in outputs:
        if fmt == "json":
            text = to_json(report)
        elif fmt == "html":
            text = to_html(report)
        elif fmt == "markdown":
            text = to_markdown(report)
        else:
            print(f"unknown format: {fmt}", file=sys.stderr)
            return 2

        if args.out_dir:
            out_path = Path(args.out_dir) / f"audit-{_slug(config.start_url)}.{fmt}"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
            print(f"wrote {out_path}", file=sys.stderr)
        else:
            print(text)

    return 0


def _slug(url: str) -> str:
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    host = parts.netloc.replace(":", "_")
    return f"{host}{parts.path.replace('/', '_')}".rstrip("_") or "audit"


def _cmd_version(_args: argparse.Namespace) -> int:
    print(f"pagerank-seo {__version__}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pagerank-seo",
        description="PageRank-oriented SEO audit: turn a website into an information graph "
                    "and produce prioritized, evidence-traceable recommendations.",
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    p_audit = sub.add_parser("audit", help="audit a website")
    p_audit.add_argument("url", help="start URL (http:// or https://)")
    p_audit.add_argument("--max-pages", type=int, default=50, help="maximum pages to crawl (default: 50)")
    p_audit.add_argument("--max-depth", type=int, default=3, help="maximum BFS depth from start URL (default: 3)")
    p_audit.add_argument("--timeout", type=float, default=10.0, help="per-request timeout seconds (default: 10)")
    p_audit.add_argument("--rate", type=float, default=2.0, help="requests per second (default: 2)")
    p_audit.add_argument("--max-bytes", type=int, default=5_000_000, help="max document bytes (default: 5MB)")
    p_audit.add_argument("--user-agent", default="pagerank-seo/0.1 (+https://github.com/kliewerdaniel/pagerank-seo)",
                         help="User-Agent header to send")
    p_audit.add_argument("--ignore-robots", action="store_true",
                         help="ignore robots.txt (off by default — conservative)")
    p_audit.add_argument("--follow-external", action="store_true",
                         help="follow external links (off by default — same-origin only)")
    p_audit.add_argument("--output", default="markdown",
                         help="comma-separated output formats: json,html,markdown (default: markdown)")
    p_audit.add_argument("--out-dir", default=None,
                         help="if set, write outputs to <out-dir>/audit-<slug>.<fmt>")
    p_audit.add_argument("--verbose", "-v", action="store_true", help="print crawl progress to stderr")
    p_audit.set_defaults(func=_cmd_audit)

    args = parser.parse_args(argv)

    if args.version:
        return _cmd_version(args)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
