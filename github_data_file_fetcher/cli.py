"""CLI commands for skill collection."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Collect files from GitHub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "results",
        help="Output directory for results",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # fetch-file-paths subcommand
    fetch_parser = subparsers.add_parser(
        "fetch-file-paths",
        help="Fetch file paths matching query",
    )
    fetch_parser.add_argument(
        "query",
        help="Search query (e.g., filename:SKILL.md)",
    )
    fetch_parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Database path (default: results/files.db)",
    )
    fetch_parser.add_argument(
        "--skip-cache",
        action="store_true",
        help="Skip reading from cache (still writes to cache)",
    )

    # fetch-file-content subcommand
    content_parser = subparsers.add_parser(
        "fetch-file-content",
        help="Fetch content for collected file paths",
    )
    content_parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Database path (default: results/files.db)",
    )
    content_parser.add_argument(
        "--content-dir",
        type=Path,
        default=None,
        help="Directory to store content (default: results/content)",
    )
    content_parser.add_argument(
        "--graphql",
        action="store_true",
        help="Use GraphQL batch API (separate rate limit pool, ~50x faster)",
    )
    content_parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Files per GraphQL query (default: 50, requires --graphql)",
    )
    content_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Stop after downloading N files (default: no limit)",
    )

    # fetch-repo-metadata subcommand
    meta_parser = subparsers.add_parser(
        "fetch-repo-metadata",
        help="Fetch repository metadata (stars, forks, etc.)",
    )
    meta_parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Database path (default: results/files.db)",
    )
    meta_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output JSON file (default: results/repo_metadata.json)",
    )
    meta_parser.add_argument(
        "--graphql",
        action="store_true",
        help="Use GraphQL batch API (separate rate limit pool, ~50x faster)",
    )
    meta_parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Repos per GraphQL query (default: 50, requires --graphql)",
    )
    meta_parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Retry cached errors (e.g. repos that previously 404'd)",
    )

    # fetch-file-history subcommand
    history_parser = subparsers.add_parser(
        "fetch-file-history",
        help="Fetch commit history for skill files",
    )
    history_parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Database path (default: results/files.db)",
    )
    history_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output JSON file (default: results/file_history.json)",
    )
    history_parser.add_argument(
        "--graphql",
        action="store_true",
        help="Use GraphQL batch API (separate rate limit pool, ~50x faster)",
    )
    history_parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Files per GraphQL query (default: 5, requires --graphql)",
    )
    history_parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Retry cached errors (e.g. files that previously 404'd)",
    )

    # api subcommand
    api_parser = subparsers.add_parser(
        "api",
        help="Make a generic cached GitHub API call",
    )
    api_parser.add_argument(
        "endpoint",
        help="API endpoint path (e.g., repos/owner/repo/contents/path)",
    )
    api_parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Query parameter (repeatable, e.g., --param per_page=100)",
    )
    api_parser.add_argument(
        "--method",
        default="GET",
        help="HTTP method (default: GET)",
    )
    api_parser.add_argument(
        "--skip-cache",
        action="store_true",
        help="Skip cache for this call",
    )
    api_parser.add_argument(
        "--graphql",
        action="store_true",
        help="Treat endpoint as GraphQL (use --query instead of positional endpoint)",
    )
    api_parser.add_argument(
        "--query",
        default=None,
        help="GraphQL query string (requires --graphql)",
    )

    # search-repos subcommand
    repos_parser = subparsers.add_parser(
        "search-repos",
        help="Search repositories (find ready-made projects to reuse)",
    )
    repos_parser.add_argument("query", nargs="?", default="", help="Free-text search terms")
    repos_parser.add_argument("--language", help="Filter by primary language")
    repos_parser.add_argument(
        "--topic", action="append", default=[], metavar="TOPIC",
        help="Require a topic (repeatable)",
    )
    repos_parser.add_argument("--min-stars", type=int, help="Minimum star count")
    repos_parser.add_argument("--pushed-after", metavar="YYYY-MM-DD", help="Pushed on/after date")
    repos_parser.add_argument("--created-after", metavar="YYYY-MM-DD", help="Created on/after date")
    repos_parser.add_argument("--license", dest="license_filter", help="SPDX license key, e.g. mit")
    repos_parser.add_argument("--in", dest="in_fields", metavar="FIELDS",
                              help="Where to match, e.g. name,description,readme")
    repos_parser.add_argument("--sort", default="stars",
                              choices=["stars", "forks", "updated", "help-wanted-issues", "best-match"])
    repos_parser.add_argument("--order", default="desc", choices=["desc", "asc"])
    repos_parser.add_argument("--limit", type=int, default=30, help="Max repos to return (<=1000)")
    repos_parser.add_argument("--include-forks", action="store_true")
    repos_parser.add_argument("--include-archived", action="store_true")
    repos_parser.add_argument("--skip-cache", action="store_true")
    repos_parser.add_argument("--table", action="store_true", help="Human-readable table instead of JSON")

    # search-code subcommand
    code_parser = subparsers.add_parser(
        "search-code",
        help="Search source code and group matches by repository",
    )
    code_parser.add_argument("query", help="Search term (required by GitHub code search)")
    code_parser.add_argument("--language", help="Filter by language")
    code_parser.add_argument("--filename", help="Match a specific filename")
    code_parser.add_argument("--extension", help="Match a file extension, e.g. ts")
    code_parser.add_argument("--path", help="Restrict to a path prefix")
    code_parser.add_argument("--repo", help="Restrict to owner/name")
    code_parser.add_argument("--org", help="Restrict to an organization")
    code_parser.add_argument("--user", help="Restrict to a user")
    code_parser.add_argument("--in", dest="in_fields", metavar="FIELDS",
                             help="Where to match, e.g. file,path")
    code_parser.add_argument("--limit", type=int, default=50, help="Max file matches to collect (<=1000)")
    code_parser.add_argument("--no-metadata", action="store_true",
                             help="Skip repo metadata enrichment (faster, no stars)")
    code_parser.add_argument("--sort", dest="sort_repos_by", default="stars",
                             choices=["stars", "matches"])
    code_parser.add_argument("--skip-cache", action="store_true")
    code_parser.add_argument("--table", action="store_true", help="Human-readable table instead of JSON")

    args = parser.parse_args()

    if args.command == "fetch-file-paths":
        from .fetch_file_paths import fetch_file_paths

        db_path = args.db or (args.output_dir / "files.db")
        fetch_file_paths(args.query, db_path=db_path, skip_cache=args.skip_cache)
    elif args.command == "fetch-file-content":
        from .db import get_file_count, get_files_without_content, init_db

        db_path = args.db or (args.output_dir / "files.db")
        init_db(db_path)
        urls = get_files_without_content(db_path)
        total = get_file_count(db_path)
        content_dir = args.content_dir or (args.output_dir / "content")

        if not urls:
            print(f"All {total:,} files already have content status. Nothing to fetch.")
        else:
            print(f"Fetching content for {len(urls):,} URLs ({total - len(urls):,} already done) to {content_dir}")

            if args.graphql:
                from .fetch_file_content import fetch_file_content_graphql

                stats = fetch_file_content_graphql(
                    urls, content_dir, db_path=db_path,
                    batch_size=args.batch_size, limit=args.limit,
                )
                print(
                    f"\nDone: {stats['fetched']} fetched, {stats['errors']} errors, "
                    f"{stats['truncated_rest']} REST fallback, {stats['queries']} queries"
                )
            else:
                from .fetch_file_content import fetch_file_content

                stats = fetch_file_content(urls, content_dir, db_path=db_path, limit=args.limit)
                print(f"\nDone: {stats['fetched']} fetched, {stats['errors']} errors")
    elif args.command == "fetch-repo-metadata":
        db_path = args.db or (args.output_dir / "files.db")

        if args.graphql:
            from .fetch_repo_metadata import fetch_repo_metadata_graphql

            stats = fetch_repo_metadata_graphql(db_path=db_path, batch_size=args.batch_size)
            print(
                f"\nDone: {stats['fetched']} fetched, {stats['errors']} errors, "
                f"{stats['queries']} queries"
            )
        else:
            from .fetch_repo_metadata import fetch_repo_metadata

            stats = fetch_repo_metadata(db_path=db_path, retry_errors=args.retry_errors)
            print(f"\nDone: {stats['fetched']} fetched, {stats['errors']} errors")
    elif args.command == "fetch-file-history":
        db_path = args.db or (args.output_dir / "files.db")

        if args.graphql:
            from .fetch_file_history import fetch_file_history_graphql

            stats = fetch_file_history_graphql(db_path=db_path, batch_size=args.batch_size)
            print(
                f"\nDone: {stats['fetched']} fetched, {stats['errors']} errors, "
                f"{stats['queries']} queries"
            )
        else:
            from .fetch_file_history import fetch_file_history

            stats = fetch_file_history(db_path=db_path, retry_errors=args.retry_errors)
            print(f"\nDone: {stats['fetched']} fetched, {stats['errors']} errors")
    elif args.command == "api":
        import json
        import sys

        if args.graphql:
            from . import graphql as graphql_mod

            query_str = args.query or args.endpoint
            gql = graphql_mod.GraphQLClient()
            try:
                result = gql.graphql(query_str)
                json.dump(result, sys.stdout, indent=2)
                sys.stdout.write("\n")
            finally:
                gql.close()
        else:
            from . import generic_client

            params = {}
            for p in args.param:
                k, _, v = p.partition("=")
                params[k] = v

            client = generic_client.get_generic_client(skip_cache=args.skip_cache)
            resp = client.api(args.endpoint, params=params or None, method=args.method)
            json.dump(resp.body, sys.stdout, indent=2)
            sys.stdout.write("\n")
    elif args.command == "search-repos":
        from .search import search_repositories

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
        _emit_search(result, args.table)
    elif args.command == "search-code":
        from .search import search_code

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
    else:
        parser.print_help()


def _emit_search(result: dict, as_table: bool) -> None:
    """Write a search result to stdout as JSON (default) or a compact table."""
    import json
    import sys

    if "error" in result:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(1)

    if not as_table:
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    if result["kind"] == "repositories":
        print(f"{result['returned']} of ~{result['total_count']:,} repos for: {result['query']}\n")
        for r in result["results"]:
            stars = r["stars"] if r["stars"] is not None else "?"
            meta = " | ".join(filter(None, [
                f"★{stars}", r["language"], r["license"], f"pushed {(r['pushed_at'] or '')[:10]}",
            ]))
            print(f"{r['full_name']}  ({meta})")
            if r["description"]:
                print(f"    {r['description']}")
            print(f"    {r['url']}")
        return

    print(f"{result['returned_repos']} repos, {result['returned_files']} files for: {result['query']}\n")
    for r in result["repos"]:
        stars = r.get("stars", "?")
        print(f"{r['full_name']}  (★{stars} | {r['match_count']} match(es) | {r.get('language') or '?'})")
        if r.get("description"):
            print(f"    {r['description']}")
        for m in r["matches"][:5]:
            print(f"    - {m['path']}")


if __name__ == "__main__":
    main()
