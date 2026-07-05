"""Search GitHub for reusable repositories and source code.

Built on the project's cached, throttled, rate-limited clients:
  - REST search via ``get_generic_client().api()``
  - repo metadata enrichment via ``GraphQLClient.fetch_metadata_batch()``

Both entry points return plain JSON-serializable dicts so a Claude Code agent
can consume the output directly.
"""

import httpx

from ..generic_client import get_generic_client
from ..models import GITHUB_SEARCH_RESULT_LIMIT

PER_PAGE = 100
MAX_PAGES = 10  # GitHub caps search pagination at 10 pages * 100 = 1000 results
DEFAULT_REPO_LIMIT = 30
DEFAULT_CODE_LIMIT = 50
METADATA_BATCH_SIZE = 50

_VALID_REPO_SORTS = {"stars", "forks", "updated", "help-wanted-issues", "best-match"}
_VALID_ORDERS = {"asc", "desc"}


def _quote(value: str) -> str:
    """Wrap a qualifier value in quotes if it contains whitespace."""
    return f'"{value}"' if any(c.isspace() for c in value) else value


def _build_query(base: str, qualifiers: list[str]) -> str:
    """Combine free-text with qualifier clauses into a single search string."""
    parts = [base.strip()] if base and base.strip() else []
    parts.extend(q for q in qualifiers if q)
    return " ".join(parts).strip()


def _paginate(endpoint: str, params: dict, limit: int, skip_cache: bool) -> dict:
    """Page through a search endpoint until ``limit`` items or exhaustion.

    Returns ``{"items", "total_count", "incomplete"}`` or ``{"error", "status"}``.
    Honors GitHub's 1000-result ceiling using ``>=`` boundary checks.
    """
    client = get_generic_client()
    capped_limit = min(limit, GITHUB_SEARCH_RESULT_LIMIT)
    items: list[dict] = []
    total_count = 0
    incomplete = False

    page = 1
    while page <= MAX_PAGES:
        page_params = {**params, "per_page": PER_PAGE, "page": page}
        try:
            resp = client.api(endpoint, params=page_params, skip_cache=skip_cache)
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            try:
                message = e.response.json().get("message", str(e))
            except Exception:
                message = str(e)
            return {"error": message, "status": status}

        body = resp.body if isinstance(resp.body, dict) else {}
        total_count = body.get("total_count", total_count)
        incomplete = incomplete or bool(body.get("incomplete_results"))
        page_items = body.get("items", [])
        items.extend(page_items)

        # Stop once we have enough, hit the API ceiling, or drained the results.
        if len(items) >= capped_limit:
            break
        if len(page_items) < PER_PAGE:
            break
        if len(items) >= GITHUB_SEARCH_RESULT_LIMIT:
            break
        page += 1

    return {
        "items": items[:capped_limit],
        "total_count": total_count,
        "incomplete": incomplete,
    }


def _shape_repo(item: dict) -> dict:
    """Project a REST repository object down to the fields agents care about."""
    lic = item.get("license") or {}
    spdx = lic.get("spdx_id") if isinstance(lic, dict) else None
    return {
        "full_name": item.get("full_name"),
        "url": item.get("html_url"),
        "description": item.get("description"),
        "stars": item.get("stargazers_count"),
        "forks": item.get("forks_count"),
        "language": item.get("language"),
        "topics": item.get("topics", []),
        "license": spdx if spdx not in (None, "NOASSERTION") else None,
        "open_issues": item.get("open_issues_count"),
        "archived": item.get("archived", False),
        "is_fork": item.get("fork", False),
        "homepage": (item.get("homepage") or None),
        "pushed_at": item.get("pushed_at"),
        "updated_at": item.get("updated_at"),
        "created_at": item.get("created_at"),
        "default_branch": item.get("default_branch"),
    }


def search_repositories(
    query: str = "",
    *,
    language: str | None = None,
    topics: list[str] | None = None,
    min_stars: int | None = None,
    pushed_after: str | None = None,
    created_after: str | None = None,
    license_filter: str | None = None,
    in_fields: str | None = None,
    sort: str | None = "stars",
    order: str = "desc",
    limit: int = DEFAULT_REPO_LIMIT,
    include_forks: bool = False,
    include_archived: bool = False,
    skip_cache: bool = False,
) -> dict:
    """Search repositories -- the primary tool for finding ready-made projects.

    ``query`` is free text; the keyword args add search qualifiers. Results are
    ranked by stars by default and returned already shaped for consumption.
    """
    qualifiers: list[str] = []
    if in_fields:
        qualifiers.append(f"in:{in_fields}")
    if language:
        qualifiers.append(f"language:{_quote(language)}")
    for topic in topics or []:
        qualifiers.append(f"topic:{topic}")
    if min_stars is not None:
        qualifiers.append(f"stars:>={min_stars}")
    if pushed_after:
        qualifiers.append(f"pushed:>={pushed_after}")
    if created_after:
        qualifiers.append(f"created:>={created_after}")
    if license_filter:
        qualifiers.append(f"license:{license_filter}")
    if not include_archived:
        qualifiers.append("archived:false")

    q = _build_query(query, qualifiers)
    if not q:
        return {"kind": "repositories", "error": "empty query: provide text or qualifiers"}

    if sort is not None and sort not in _VALID_REPO_SORTS:
        return {"kind": "repositories", "error": f"invalid sort: {sort}"}
    if order not in _VALID_ORDERS:
        return {"kind": "repositories", "error": f"invalid order: {order}"}

    params: dict = {"q": q, "order": order}
    if sort and sort != "best-match":
        params["sort"] = sort

    page = _paginate("search/repositories", params, limit, skip_cache)
    if "error" in page:
        return {"kind": "repositories", "query": q, **page}

    results = [_shape_repo(it) for it in page["items"]]
    if not include_forks:
        results = [r for r in results if not r["is_fork"]]

    return {
        "kind": "repositories",
        "query": q,
        "total_count": page["total_count"],
        "returned": len(results),
        "incomplete_results": page["incomplete"],
        "results": results,
    }


def _enrich_repos(repo_keys: list[str]) -> dict[str, dict]:
    """Fetch stars/topics/license/pushed_at for each ``owner/repo`` via GraphQL."""
    from ..graphql import GraphQLClient

    gql = GraphQLClient()
    metadata: dict[str, dict] = {}
    try:
        for start in range(0, len(repo_keys), METADATA_BATCH_SIZE):
            batch = repo_keys[start : start + METADATA_BATCH_SIZE]
            for result in gql.fetch_metadata_batch(batch):
                if result.metadata:
                    metadata[result.repo_key] = result.metadata
    finally:
        gql.close()
    return metadata


def search_code(
    query: str,
    *,
    language: str | None = None,
    filename: str | None = None,
    extension: str | None = None,
    path: str | None = None,
    repo: str | None = None,
    org: str | None = None,
    user: str | None = None,
    in_fields: str | None = None,
    limit: int = DEFAULT_CODE_LIMIT,
    with_metadata: bool = True,
    sort_repos_by: str = "stars",
    skip_cache: bool = False,
) -> dict:
    """Search source code and group matches by repository.

    Use this to find repositories that already implement a specific pattern.
    Matched files are grouped per repo and (by default) enriched with metadata
    so results can be ranked by stars.
    """
    qualifiers: list[str] = []
    if in_fields:
        qualifiers.append(f"in:{in_fields}")
    if language:
        qualifiers.append(f"language:{_quote(language)}")
    if filename:
        qualifiers.append(f"filename:{_quote(filename)}")
    if extension:
        qualifiers.append(f"extension:{extension}")
    if path:
        qualifiers.append(f"path:{_quote(path)}")
    if repo:
        qualifiers.append(f"repo:{repo}")
    if org:
        qualifiers.append(f"org:{org}")
    if user:
        qualifiers.append(f"user:{user}")

    q = _build_query(query, qualifiers)
    if not query or not query.strip():
        return {"kind": "code", "error": "code search requires a non-empty search term"}

    page = _paginate("search/code", {"q": q}, limit, skip_cache)
    if "error" in page:
        return {"kind": "code", "query": q, **page}

    grouped: dict[str, dict] = {}
    for item in page["items"]:
        repo_obj = item.get("repository") or {}
        full_name = repo_obj.get("full_name")
        if not full_name:
            continue
        entry = grouped.setdefault(
            full_name,
            {
                "full_name": full_name,
                "url": repo_obj.get("html_url"),
                "description": repo_obj.get("description"),
                "is_fork": repo_obj.get("fork", False),
                "matches": [],
            },
        )
        entry["matches"].append({"path": item.get("path"), "url": item.get("html_url")})

    if with_metadata and grouped:
        metadata = _enrich_repos(list(grouped.keys()))
        for full_name, entry in grouped.items():
            meta = metadata.get(full_name)
            if not meta:
                continue
            entry["stars"] = meta.get("stars")
            entry["forks"] = meta.get("forks")
            entry["language"] = meta.get("language")
            entry["topics"] = meta.get("topics", [])
            entry["license"] = meta.get("license")
            entry["pushed_at"] = meta.get("pushed_at")
            if not entry.get("description"):
                entry["description"] = meta.get("description")

    repos = list(grouped.values())
    for entry in repos:
        entry["match_count"] = len(entry["matches"])

    if sort_repos_by == "stars":
        repos.sort(key=lambda r: (r.get("stars") or -1, r["match_count"]), reverse=True)
    else:
        repos.sort(key=lambda r: r["match_count"], reverse=True)

    return {
        "kind": "code",
        "query": q,
        "total_count": page["total_count"],
        "returned_files": sum(r["match_count"] for r in repos),
        "returned_repos": len(repos),
        "incomplete_results": page["incomplete"],
        "repos": repos,
    }
