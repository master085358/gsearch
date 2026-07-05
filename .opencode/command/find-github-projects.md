---
description: Find ready-made GitHub projects/code to reuse (zero-install via uvx)
---

Find existing GitHub repositories or source code the user could reuse instead of
building from scratch. Goal: $ARGUMENTS

Use the `find-github-projects` skill's method. The tool runs **zero-install via
`uvx`** — do not clone or install anything.

Before every run, load the token from `.env` inline (each shell is fresh, so the
env does not persist between commands):

```bash
# Find ready-made projects (ranked by stars) — the default
set -a; source .env; set +a; uvx --from git+https://github.com/master085358/gsearch \
  search repos "<terms>" --language <lang> --min-stars 200

# Find repos implementing a specific pattern (grouped by repo, enriched with stars)
set -a; source .env; set +a; uvx --from git+https://github.com/master085358/gsearch \
  search code "<terms>" --language <lang>

# Add --table for human-readable output instead of JSON
```

`.env` must contain `GITHUB_TOKEN=ghp_...`. If it is elsewhere, source it by
absolute path. On `401`/`403`, the token is missing/invalid — say so, never print it.

Steps: sharpen the goal → pick `repos` (whole project) vs `code` (specific
implementation) → query then narrow with `--topic`, `--min-stars`,
`--pushed-after`, `--license` → judge candidates by stars, `pushed_at` (freshness),
`archived`, license, and description → deep-dive the top 3-5 (read the README via
`... github-fetch api repos/OWNER/REPO/readme --param accept=raw`) → present a
ranked shortlist with a one-line rationale and a concrete next step. Reply in the
user's language.
