# Agent instructions

This repo ships a **zero-install GitHub search tool** for discovering ready-made
projects and source code to reuse. Agents (opencode, Claude Code, etc.) should use
it via `uvx` straight from git — no cloning, no `pip install`.

## Finding reusable GitHub projects

When the user wants to find an existing project/library/example to reuse
("найди готовый проект для X", "find a repo that does Y"), run the `search` tool.

**Load the token from `.env` inline in the same command** — each shell is fresh,
so exported env does not carry between separate commands:

```bash
# Ready-made projects, ranked by stars (default)
set -a; source .env; set +a; uvx --from git+https://github.com/master085358/gsearch \
  search repos "<terms>" --language <lang> --min-stars 200

# Repos implementing a specific pattern (grouped by repo, enriched with stars)
set -a; source .env; set +a; uvx --from git+https://github.com/master085358/gsearch \
  search code "<terms>" --language <lang>
```

- Output is JSON (add `--table` for a human view).
- `.env` must define `GITHUB_TOKEN=ghp_...`; source it by absolute path if it is
  not in the current directory. On `401`/`403` the token is missing/invalid.
- Deep-dive a candidate's README/layout with the sibling script:
  `... uvx --from git+https://github.com/master085358/gsearch github-fetch api repos/OWNER/REPO/readme --param accept=raw`
- Full method and flag list: `.opencode/skills/find-github-projects/SKILL.md`.

Judge candidates by stars, `pushed_at` (freshness), `archived`, license, and
description before recommending. Present a ranked shortlist with a rationale.
