# Caching Strategy (Current Implementation)

This document describes the caching behavior currently implemented in this repository, and why these settings were chosen.

## Scope

Caching is implemented at two layers:

1. **SQLite connection/page-cache tuning** for network-hosted database files.
2. **In-process Python read caches** (`functools.lru_cache`) for repeated expensive reads.

No external cache service (Redis/Memcached) is used.

---

## Runtime Model

- Launchpad starts **one Flask app** with both MediaBrowser and ProjectBrowser routes registered.
- Flask runs with `threaded=True`, so request worker threads are created as needed.
- Each module maintains a **thread-local SQLite connection** (persistent for that thread).

Practical effect:
- Connections are not opened/closed on every request.
- SQLite page cache stays warm per thread.
- Memory usage scales with active request threads.

---

## SQLite Settings in Use

Both modules configure SQLite connections with:

- `journal_mode=DELETE`
- `synchronous=NORMAL`
- `temp_store=MEMORY`
- `busy_timeout=30000`
- `timeout=60.0` (Python sqlite connect timeout)
- `check_same_thread=False`

### Why these were chosen

- **`DELETE` journal mode**: safest compatibility choice for shared/network filesystems.
- **`NORMAL` synchronous**: balances durability with reduced network sync overhead.
- **`temp_store=MEMORY`**: avoids temporary-file network I/O.
- **`busy_timeout=30000` + `timeout=60.0`**: tolerates short lock/contention and network latency spikes.
- **Thread-local persistent connections**: reduces connection churn and preserves warm page cache.

---

## Cache Size Choices

### MediaBrowser

- `SQLITE_CACHE_SIZE_KB = -102400`
- Effective target: **~100 MB per thread-local SQLite connection**.

Why:
- MediaBrowser is the heavier workload (search + archive + path enrichment + metadata/thumbnail-related activity).
- Larger page cache reduces repeated network reads and improves warm-query responsiveness.

### ProjectBrowser

- `SQLITE_CACHE_SIZE_KB = -32768`
- Effective target: **~32 MB per thread-local SQLite connection**.

Why:
- ProjectBrowser is primarily DB-centric with lighter/less varied read patterns.
- Smaller cache gives most warm-cache benefit at lower memory cost.

### Note on negative cache size

`PRAGMA cache_size` semantics:
- Positive value = number of pages.
- Negative value = kibibytes (KiB) target.

Negative values are used so memory targets are predictable regardless of SQLite page size.

---

## In-Process Read Caches (Implemented)

### MediaBrowser (`src/mediabrowser.py`)

Implemented `lru_cache` usage:

- `_cached_category_counts(...)` for top-N aggregation queries used by index/dashboard widgets.
- `_cached_media_path_details(...)` for repeated path/thumbnail resolution and file-existence checks.
- `_extract_media_metadata_cached(...)` for media metadata extraction keyed with file mtime.

### ProjectBrowser (`src/projectbrowser.py`)

Implemented `lru_cache` usage:

- `_cached_years()`
- `_cached_projects_by_year(year)`
- `_cached_project_apps(project_name)`
- `_cached_job_by_name(job_name)`
- `_cached_job_by_path(job_path_job)`

These target high-frequency API reads and UI-population calls.

---

## Invalidation Strategy (Implemented)

Read caches are explicitly cleared after write operations.

- **MediaBrowser** invalidates via `cache_invalidate_runtime()` after DB mutations (archive submit/insert, cart metadata updates, prune/deletes).
- **ProjectBrowser** invalidates via `cache_invalidate_runtime()` after dashboard updates and job creation.

This keeps cached reads fast while preventing stale post-write responses.

---

## Observability

Current startup/runtime logging includes cache configuration visibility:

- One-time per-module cache config logs on first DB connection creation.
- Consolidated startup summary printed by `app_flask.print_cache_summary()`.
- Launchpad startup path also calls `print_cache_summary()`.

This allows quick verification of active cache policy at runtime.

---

## Tradeoffs

Benefits:
- Lower network I/O after warmup.
- Better response time for repeated read patterns.
- Reduced connection setup overhead.

Costs:
- Memory scales with number of active request threads.
- Thread-local caches are per-process/per-thread (not shared across processes).
- Explicit invalidation is required after writes (already implemented for current write paths).

---

## Tuning Guidance (for this codebase)

If memory pressure appears:
- First reduce MediaBrowser cache size (e.g., from 100 MB to 64 MB).
- Keep ProjectBrowser smaller unless workload materially changes.

If lock errors appear under concurrent use:
- Revisit write frequency/transaction duration first.
- Increase timeouts only after confirming lock contention is transient.

If stale data is observed:
- Add invalidation in any newly added write endpoint in the same module.

---

## Code References (Current)

### MediaBrowser (`src/mediabrowser.py`)

- SQLite tuning constants: [src/mediabrowser.py#L57-L63](src/mediabrowser.py#L57-L63)
- Connection PRAGMA configuration: [src/mediabrowser.py#L150-L157](src/mediabrowser.py#L150-L157)
- Thread-local connection acquisition: [src/mediabrowser.py#L173-L191](src/mediabrowser.py#L173-L191)
- Public DB connection helper: [src/mediabrowser.py#L194-L196](src/mediabrowser.py#L194-L196)
- Read cache: category counts: [src/mediabrowser.py#L216-L228](src/mediabrowser.py#L216-L228)
- Read cache: media path/thumbnail details: [src/mediabrowser.py#L231-L274](src/mediabrowser.py#L231-L274)
- Read cache: extracted metadata: [src/mediabrowser.py#L277-L314](src/mediabrowser.py#L277-L314)
- Cache invalidation helper: [src/mediabrowser.py#L317-L320](src/mediabrowser.py#L317-L320)

### ProjectBrowser (`src/projectbrowser.py`)

- SQLite tuning constants: [src/projectbrowser.py#L55-L57](src/projectbrowser.py#L55-L57)
- Thread-local DB connection + PRAGMAs: [src/projectbrowser.py#L217-L263](src/projectbrowser.py#L217-L263)
- Read cache: years: [src/projectbrowser.py#L280-L285](src/projectbrowser.py#L280-L285)
- Read cache: projects by year: [src/projectbrowser.py#L288-L293](src/projectbrowser.py#L288-L293)
- Read cache: apps by project: [src/projectbrowser.py#L296-L304](src/projectbrowser.py#L296-L304)
- Read cache: job by name: [src/projectbrowser.py#L307-L315](src/projectbrowser.py#L307-L315)
- Read cache: job by path: [src/projectbrowser.py#L318-L326](src/projectbrowser.py#L318-L326)
- Cache invalidation helper: [src/projectbrowser.py#L328-L334](src/projectbrowser.py#L328-L334)

### Startup / Observability

- Consolidated cache summary function: [src/app_flask.py#L275-L309](src/app_flask.py#L275-L309)
- Startup call in CLI path (`main`): [src/app_flask.py#L326-L327](src/app_flask.py#L326-L327)
- Launchpad startup call: [src/launchpad.py#L256](src/launchpad.py#L256)
