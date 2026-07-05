"""Unit tests for the search module. HTTP and metadata enrichment are mocked."""

from unittest.mock import MagicMock, patch

import httpx

from github_data_file_fetcher.models import ApiResponse
from github_data_file_fetcher.search import search as search_mod
from github_data_file_fetcher.search import search_code, search_repositories


class FakeClient:
    """Records api() calls and replays queued response bodies by page."""

    def __init__(self, pages):
        # pages: list of body dicts, one per page (1-indexed)
        self._pages = pages
        self.calls = []

    def api(self, endpoint, params=None, skip_cache=False):
        self.calls.append({"endpoint": endpoint, "params": params, "skip_cache": skip_cache})
        page = (params or {}).get("page", 1)
        body = self._pages[page - 1] if page - 1 < len(self._pages) else {"items": [], "total_count": 0}
        return ApiResponse(status=200, body=body)


def _repo_item(full_name, stars=100, fork=False, **extra):
    owner_repo = full_name
    base = {
        "full_name": owner_repo,
        "html_url": f"https://github.com/{owner_repo}",
        "description": f"desc for {owner_repo}",
        "stargazers_count": stars,
        "forks_count": 3,
        "language": "Python",
        "topics": ["cli"],
        "license": {"spdx_id": "MIT"},
        "open_issues_count": 1,
        "archived": False,
        "fork": fork,
        "pushed_at": "2026-01-01T00:00:00Z",
        "default_branch": "main",
    }
    base.update(extra)
    return base


def _use_client(client):
    return patch.object(search_mod, "get_generic_client", return_value=client)


class TestBuildQuery:
    def test_combines_and_quotes(self):
        result = search_mod._build_query("foo bar", ["language:Python", 'filename:"a b.py"'])
        assert result == 'foo bar language:Python filename:"a b.py"'

    def test_quote_helper(self):
        assert search_mod._quote("go") == "go"
        assert search_mod._quote("visual basic") == '"visual basic"'


class TestSearchRepositories:
    def test_query_construction_and_shape(self):
        client = FakeClient([{"items": [_repo_item("a/b", stars=500)], "total_count": 1}])
        with _use_client(client):
            result = search_repositories(
                "web scraper", language="python", topics=["crawler"],
                min_stars=100, license_filter="mit", limit=10,
            )

        assert result["kind"] == "repositories"
        q = client.calls[0]["params"]["q"]
        assert "web scraper" in q
        assert "language:python" in q
        assert "topic:crawler" in q
        assert "stars:>=100" in q
        assert "license:mit" in q
        assert "archived:false" in q  # excluded by default
        assert client.calls[0]["params"]["sort"] == "stars"

        repo = result["results"][0]
        assert repo["full_name"] == "a/b"
        assert repo["stars"] == 500
        assert repo["license"] == "MIT"

    def test_forks_filtered_by_default(self):
        client = FakeClient([{
            "items": [_repo_item("a/b", fork=False), _repo_item("c/d", fork=True)],
            "total_count": 2,
        }])
        with _use_client(client):
            result = search_repositories("x", limit=10)
        names = [r["full_name"] for r in result["results"]]
        assert names == ["a/b"]

    def test_include_forks_and_archived(self):
        client = FakeClient([{"items": [_repo_item("c/d", fork=True)], "total_count": 1}])
        with _use_client(client):
            result = search_repositories("x", include_forks=True, include_archived=True)
        assert "archived:false" not in client.calls[0]["params"]["q"]
        assert result["returned"] == 1

    def test_empty_query_errors(self):
        with _use_client(FakeClient([])):
            result = search_repositories("", include_archived=True)
        assert "error" in result

    def test_pagination_respects_limit(self):
        page1 = {"items": [_repo_item(f"o/r{i}") for i in range(100)], "total_count": 250}
        page2 = {"items": [_repo_item(f"o/s{i}") for i in range(100)], "total_count": 250}
        client = FakeClient([page1, page2])
        with _use_client(client):
            result = search_repositories("x", limit=150, include_forks=True)
        assert result["returned"] == 150
        assert len(client.calls) == 2

    def test_best_match_omits_sort(self):
        client = FakeClient([{"items": [], "total_count": 0}])
        with _use_client(client):
            search_repositories("x", sort="best-match")
        assert "sort" not in client.calls[0]["params"]

    def test_http_error_surfaced(self):
        request = httpx.Request("GET", "https://api.github.com/search/repositories")
        response = httpx.Response(422, json={"message": "Validation Failed"}, request=request)

        client = MagicMock()
        client.api.side_effect = httpx.HTTPStatusError("boom", request=request, response=response)
        with _use_client(client):
            result = search_repositories("x", include_archived=True)
        assert result["error"] == "Validation Failed"
        assert result["status"] == 422


class TestSearchCode:
    def _code_item(self, full_name, path):
        return {
            "path": path,
            "html_url": f"https://github.com/{full_name}/blob/main/{path}",
            "repository": {
                "full_name": full_name,
                "html_url": f"https://github.com/{full_name}",
                "description": None,
                "fork": False,
            },
        }

    def test_groups_and_enriches(self):
        page = {
            "items": [
                self._code_item("a/b", "src/x.py"),
                self._code_item("a/b", "src/y.py"),
                self._code_item("c/d", "main.py"),
            ],
            "total_count": 3,
        }
        client = FakeClient([page])
        meta = {
            "a/b": {"stars": 50, "language": "Python", "topics": [], "license": "MIT",
                    "pushed_at": "2026-01-01", "forks": 1, "description": "AB"},
            "c/d": {"stars": 900, "language": "Go", "topics": [], "license": None,
                    "pushed_at": "2026-01-01", "forks": 2, "description": "CD"},
        }
        with _use_client(client), patch.object(search_mod, "_enrich_repos", return_value=meta):
            result = search_code("transform", language="python")

        assert result["returned_repos"] == 2
        assert result["returned_files"] == 3
        # Sorted by stars desc -> c/d first
        assert result["repos"][0]["full_name"] == "c/d"
        ab = next(r for r in result["repos"] if r["full_name"] == "a/b")
        assert ab["match_count"] == 2
        assert ab["stars"] == 50
        assert "language:python" in client.calls[0]["params"]["q"]

    def test_empty_term_errors(self):
        result = search_code("")
        assert "error" in result

    def test_no_metadata_skips_enrichment(self):
        page = {"items": [self._code_item("a/b", "x.py")], "total_count": 1}
        client = FakeClient([page])
        with _use_client(client), patch.object(search_mod, "_enrich_repos") as enrich:
            result = search_code("term", with_metadata=False)
        enrich.assert_not_called()
        assert result["repos"][0]["match_count"] == 1
