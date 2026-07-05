"""Standalone `search` entry point for `uvx --from git+... search <mode> <query>`.

Exposes two modes:
  search repos "<terms>"   -- find ready-made projects, ranked by stars
  search code  "<terms>"   -- find repos implementing a pattern

Reuses the shared output formatter from the main CLI.
"""

import argparse

from ..cli import _emit_search
from .search import search_code, search_repositories


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--language", help="Filter by language")
    parser.add_argument("--in", dest="in_fields", metavar="FIELDS", help="Where to match")
    parser.add_argument("--limit", type=int, default=30, help="Max results (<=1000)")
    parser.add_argument("--skip-cache", action="store_true")
    parser.add_argument("--table", action="store_true", help="Human-readable table instead of JSON")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="search",
        description="Search GitHub for reusable repositories and source code (JSON output).",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    repos = sub.add_parser("repos", help="Find ready-made projects (ranked by stars)")
    repos.add_argument("query", nargs="?", default="", help="Free-text search terms")
    _add_common(repos)
    repos.add_argument("--topic", action="append", default=[], metavar="TOPIC",
                       help="Require a topic (repeatable)")
    repos.add_argument("--min-stars", type=int, help="Minimum star count")
    repos.add_argument("--pushed-after", metavar="YYYY-MM-DD", help="Pushed on/after date")
    repos.add_argument("--created-after", metavar="YYYY-MM-DD", help="Created on/after date")
    repos.add_argument("--license", dest="license_filter", help="SPDX key, e.g. mit")
    repos.add_argument("--sort", default="stars",
                       choices=["stars", "forks", "updated", "help-wanted-issues", "best-match"])
    repos.add_argument("--order", default="desc", choices=["desc", "asc"])
    repos.add_argument("--include-forks", action="store_true")
    repos.add_argument("--include-archived", action="store_true")

    code = sub.add_parser("code", help="Find repos implementing a pattern (grouped by repo)")
    code.add_argument("query", help="Search term (required by GitHub code search)")
    _add_common(code)
    code.add_argument("--filename", help="Match a specific filename")
    code.add_argument("--extension", help="Match a file extension, e.g. ts")
    code.add_argument("--path", help="Restrict to a path prefix")
    code.add_argument("--repo", help="Restrict to owner/name")
    code.add_argument("--org", help="Restrict to an organization")
    code.add_argument("--user", help="Restrict to a user")
    code.add_argument("--no-metadata", action="store_true", help="Skip metadata enrichment")
    code.add_argument("--sort", dest="sort_repos_by", default="stars", choices=["stars", "matches"])

    args = parser.parse_args()

    if args.mode == "repos":
        result = search_repositories(
            args.query,
            language=args.language,
            topics=args.topic,
            min_stars=args.min_stars,
            pushed_after=args.pushed_after,
            created_after=args.created_after,
            license_filter=args.license_filter,
            in_fields=args.in_fields,
            sort=args.sort,
            order=args.order,
            limit=args.limit,
            include_forks=args.include_forks,
            include_archived=args.include_archived,
            skip_cache=args.skip_cache,
        )
    else:
        result = search_code(
            args.query,
            language=args.language,
            filename=args.filename,
            extension=args.extension,
            path=args.path,
            repo=args.repo,
            org=args.org,
            user=args.user,
            in_fields=args.in_fields,
            limit=args.limit,
            with_metadata=not args.no_metadata,
            sort_repos_by=args.sort_repos_by,
            skip_cache=args.skip_cache,
        )

    _emit_search(result, args.table)


if __name__ == "__main__":
    main()
