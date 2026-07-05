---
name: find-github-projects
description: >-
  Find existing, ready-to-reuse GitHub repositories or source code for a stated
  goal. Use when the user wants to discover open-source projects, libraries,
  examples, or reference implementations they could adopt instead of building
  from scratch (e.g. "найди проект/библиотеку для X", "есть ли готовое решение
  для Y", "find a repo that does Z", "who already implemented W"). Runs the
  cached `search` CLI over `uvx` — no install, no cloning.
---

# Find ready-made GitHub projects

Turn a reuse goal ("I need a project that does X") into a short, ranked list of
concrete GitHub repositories the user can actually adopt, with a clear rationale
for each.

The tool runs **zero-install via `uvx`** straight from the git repo — nothing is
cloned or `pip install`ed. It prints JSON to stdout, throttles and caches
automatically (cache in `~/.cache/github-data-file-fetcher/`), and authenticates
with the user's `GITHUB_TOKEN`.

## Setup: load the token before every run

The tool needs `GITHUB_TOKEN`, kept in a `.env` file. **Each Bash call is a fresh
shell — environment does NOT persist between calls**, so you must load `.env`
*inline, in the same command* as every run:

```bash
set -a; source .env; set +a; <the uvx command>
```

`.env` must contain `GITHUB_TOKEN=ghp_...`. If it lives outside the current
directory, source it by absolute path (`source /path/to/.env`). If a call returns
`401`/`403`, the token is missing or invalid — tell the user, and never print it.

## The runner

Every invocation is one of these two forms (always prefixed with the `.env` load):

```bash
# Find ready-made projects — ranked by stars (DEFAULT tool)
set -a; source .env; set +a; \
  uvx --from git+https://github.com/master085358/gsearch \
  search repos "<terms>" [flags]

# Find repos that implement a specific thing — grouped by repo, enriched with stars
set -a; source .env; set +a; \
  uvx --from git+https://github.com/master085358/gsearch \
  search code "<terms>" [flags]
```

The first `uvx` run builds the package (~a few seconds); later runs are cached by
uv and start instantly.

## Workflow

1. **Sharpen the goal.** Extract: the capability wanted, language/stack, must-have
   constraints (license, framework, "maintained"), and whether they want a *whole
   project* or a *specific implementation*. If the goal is one vague word, ask one
   clarifying question — otherwise proceed.

2. **Pick the mode:**
   - **`search repos`** — DEFAULT for "find a project/library/tool I can use".
     Ranks by stars, filters by language/topic/activity.
   - **`search code`** — for "find repos that already implement this specific
     pattern / use this API / contain this file". Groups matches by repo and
     enriches with stars so you can still rank.
   Run both when useful (repos for breadth, code for proof-of-implementation).

3. **Query, then narrow.** Start broad, then add qualifiers based on the result
   count and quality. Prefer 1-2 focused queries over many scattered ones.

4. **Evaluate candidates** on the returned metadata (see "Judging"). Drop archived
   repos, low-star noise, and stale projects unless the user wants them.

5. **Deep-dive the top 3-5.** Inspect what a finalist actually is before
   recommending — don't recommend on stars alone. The same package ships a
   `github-fetch` script for raw API reads:
   ```bash
   set -a; source .env; set +a; \
     uvx --from git+https://github.com/master085358/gsearch \
     github-fetch api repos/OWNER/REPO/readme --param accept=raw      # README
   ```
   (Or `search code "<feature>" --repo OWNER/REPO` to confirm a feature exists.)

6. **Recommend.** Present a ranked shortlist. For each: name + link, one-line
   what-it-is, why it fits, stars / language / license / last-pushed, and any
   caveat (archived, heavy deps, wrong license). Respond in the user's language.
   End with a concrete next step (e.g. "склонировать X и взять модуль Y").

## Examples

```bash
set -a; source .env; set +a; uvx --from git+https://github.com/master085358/gsearch \
  search repos "pdf table extraction" --language python --min-stars 200

set -a; source .env; set +a; uvx --from git+https://github.com/master085358/gsearch \
  search repos "" --topic llm-agent --topic rag --min-stars 500 --pushed-after 2025-01-01

set -a; source .env; set +a; uvx --from git+https://github.com/master085358/gsearch \
  search code "createParallelTransform" --language typescript

# Human-readable table instead of JSON
set -a; source .env; set +a; uvx --from git+https://github.com/master085358/gsearch \
  search repos "vector database" --language rust --table
```

### `search repos` flags
`--language`, `--topic` (repeatable), `--min-stars N`, `--pushed-after YYYY-MM-DD`,
`--created-after`, `--license mit`, `--in name,description,readme`,
`--sort stars|forks|updated|best-match`, `--order`, `--limit` (≤1000),
`--include-forks`, `--include-archived`, `--table`, `--skip-cache`.

### `search code` flags
`--language`, `--filename`, `--extension`, `--path`, `--repo owner/name`,
`--org`, `--user`, `--in file,path`, `--limit` (≤1000), `--no-metadata`,
`--sort stars|matches`, `--table`, `--skip-cache`.

## Query-building cheatsheet

Qualifiers can go in the free-text query too — the flags are shortcuts.
- Scope where terms match: `--in name,description,readme` (repos) / `--in file,path` (code).
- "Maintained" = `--pushed-after` a recent date (e.g. last 12 months).
- "Popular / battle-tested" = `--min-stars` (200+ is a reasonable floor; 1000+ for well-known).
- Domain filter: `--topic` (e.g. `cli`, `machine-learning`, `mcp`). Topics are AND-ed.
- Permissive reuse only: `--license mit` / `apache-2.0`.
- Code search needs a real term (not only qualifiers); to search by filename, pass
  the filename both as the term and `--filename`.

## Judging a candidate

From the JSON, weigh: **stars** (traction), **pushed_at** (alive vs abandoned —
flag anything not pushed in >18 months), **archived** (avoid unless asked),
**license** (must allow the user's intended use), **language/topics** (fit the
stack), **is_fork** (prefer upstream; forks are filtered out by default),
**open_issues** and **description** (does it actually claim to do the thing).
`total_count` tells you if you should narrow (thousands) or broaden (zero).

Never recommend a repo you haven't at least skimmed the README/description of.
If nothing fits, say so plainly and suggest a broader/narrower query rather than
forcing a weak match.

## Notes

- Results are cached ~30 days; add `--skip-cache` for a fresh pull.
- GitHub search caps at 1000 results per query; for "the best project" that's
  irrelevant (you want the top of the ranking).
- Pin a version by appending `@<tag-or-sha>` to the git URL if you need
  reproducibility, e.g. `git+https://github.com/master085358/gsearch@v0.1.0`.
