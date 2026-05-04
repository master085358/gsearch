# github_data_file_fetcher/fetch_file_paths/fetch_file_paths.py

from pathlib import Path

from ..db import (
    get_file_count,
    get_scan_progress,
    init_db,
    insert_files,
    insert_search_hits,
    update_scan_progress,
)
from ..github import get_client
from ..models import GITHUB_SEARCH_RESULT_LIMIT
from .fetch_files import fetch_files

MAX_SIZE = 1_000_000  # 1 MB
DEFAULT_CHUNK_SIZE = 10000
MAX_CONSECUTIVE_EMPTY = 10


def _get_lo(progress: dict) -> int:
    """Совместимость со старыми схемами БД: last_lo или lastlo."""
    for key in ("lastlo", "last_lo", "lo"):
        try:
            val = progress[key]
            if val is not None:
                return int(val)
        except (KeyError, IndexError):
            pass
    return 0


def _get_collected(progress: dict) -> int:
    for key in ("collected",):
        try:
            val = progress[key]
            if val is not None:
                return int(val)
        except (KeyError, IndexError):
            pass
    return 0


def _is_completed(progress: dict) -> bool:
    for key in ("completedat", "completed_at", "completed"):
        try:
            val = progress[key]
            return bool(val)
        except (KeyError, IndexError):
            pass
    return False


def fetch_file_paths(
    query: str,
    db_path: Path | None = None,
    chunk: int = DEFAULT_CHUNK_SIZE,
    skip_cache: bool = False,
) -> dict:
    """
    Collect file paths matching a search query using linear scanning with
    adaptive chunks. Stores results in SQLite.
    """
    init_db(db_path)
    client = get_client(skip_cache=skip_cache)

    # ── Resume support ──────────────────────────────────────────────────────
    progress = get_scan_progress(db_path, query)
    if progress is not None and _is_completed(progress) and not skip_cache:
        total = get_file_count(db_path)
        print(
            f"Scan already completed ({_get_collected(progress):,} files). "
            "Use --skip-cache to rescan.",
            flush=True,
        )
        return {"collected": _get_collected(progress), "total": total}

    if progress is not None and _get_lo(progress) > 0 and not skip_cache:
        lo = _get_lo(progress)
        collected = _get_collected(progress)
        total = collected
        print(f"Resuming scan from size:{lo}", flush=True)
    else:
        lo = 0
        collected = 0
        total = get_file_count(db_path)

    consecutive_empty = 0

    while lo <= MAX_SIZE:
        hi = min(lo + chunk - 1, MAX_SIZE)

        count = client.search_code(
            f"{query} size:{lo}..{hi}", per_page=1, page=1
        ).get("total_count", 0)

        # ── CASE 1: empty range ──────────────────────────────────────────
        if count == 0:
            print(f"  size:{lo}..{hi} = 0 (skipping)", flush=True)
            consecutive_empty += 1
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                print(
                    f"  {consecutive_empty} consecutive empty ranges, stopping",
                    flush=True,
                )
                break
            lo = hi + 1
            chunk = min(chunk * 2, MAX_SIZE)
            continue

        consecutive_empty = 0

        # ── CASE 2: range is too dense → narrow ─────────────────────────
        if count > GITHUB_SEARCH_RESULT_LIMIT:
            print(f"  size:{lo}..{hi} = {count:,} (narrowing)", flush=True)

            # ╔══════════════════════════════════════════════════════════╗
            # ║  FIX: lo == hi  →  1-байтовый диапазон, сужать некуда.  ║
            # ║  Собираем до лимита API и принудительно двигаем lo вперёд║
            # ╚══════════════════════════════════════════════════════════╝
            if lo == hi:
                full_query = f"{query} size:{lo}..{hi}"
                files = fetch_files(full_query)
                new_count = insert_files(db_path, files)
                insert_search_hits(
                    db_path,
                    [
                        {
                            "url": f["html_url"],
                            "query": full_query,
                            "size_min": lo,
                            "size_max": hi,
                        }
                        for f in files
                    ],
                )
                collected += new_count
                total += new_count
                print(
                    f"  size:{lo}..{lo} ceiling — stored {new_count} new "
                    f"(API reported {count:,}, fetched {len(files)}), "
                    f"collected={collected:,}, total={total:,}",
                    flush=True,
                )
                lo = hi + 1
                chunk = min(max(chunk * 2, 2), MAX_SIZE)
                update_scan_progress(db_path, query, lo, MAX_SIZE, collected)
                continue

            # Обычное сужение: делим chunk пополам, lo не меняем
            chunk = max(chunk // 2, 1)
            continue

        # ── CASE 3: collectible range ────────────────────────────────────
        print(f"  size:{lo}..{hi} = {count:,} (collecting)", flush=True)
        full_query = f"{query} size:{lo}..{hi}"
        files = fetch_files(full_query)

        insert_search_hits(
            db_path,
            [
                {
                    "url": f["html_url"],
                    "query": full_query,
                    "size_min": lo,
                    "size_max": hi,
                }
                for f in files
            ],
        )
        new_count = insert_files(db_path, files)
        collected += new_count
        total += new_count

        # Если fetch вернул >= 1000 несмотря на count <= 1000 — сужаем
        if len(files) >= GITHUB_SEARCH_RESULT_LIMIT and lo < hi:
            print(f"  hit ceiling {len(files)}, narrowing", flush=True)
            chunk = max(chunk // 2, 1)
            continue

        print(
            f"  stored {new_count} new, collected={collected:,}, total={total:,}",
            flush=True,
        )
        lo = hi + 1
        chunk = min(chunk * 2, MAX_SIZE)
        update_scan_progress(db_path, query, lo, MAX_SIZE, collected)

    update_scan_progress(db_path, query, lo, MAX_SIZE, collected, completed=True)
    print(f"\nCollected {collected:,} total.", flush=True)
    return {"collected": collected, "total": total}