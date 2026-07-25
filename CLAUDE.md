# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

mediabrowser is a SQLite-driven app for media and production-project management. It targets a
**media production environment** for animation, video, and graphics work: every "job" (project) has
a standard on-disk directory structure and a corresponding row in a jobs database, and every media
asset (image/video/audio) has a row in a media database. The app gives production staff a browser-based
way to search/tag/archive media and to create, browse, and sync production jobs, while the underlying
Python modules are designed to be reusable outside the GUI (e.g. from other scripts/pipelines).

- **Frontend**: server-rendered Jinja2/HTML templates (`src/templates/`) styled as a single dark-themed
  UI, with **vanilla JavaScript** (no React/Vue/jQuery) driving `fetch()` calls against JSON `/api/*`
  endpoints. There is no build step/bundler — templates are edited directly.
- **Backend**: a Flask app (no ORM, raw `sqlite3`) serving both the pages and the JSON APIs.
- **Cross-platform**: intended to run on Windows/WSL, Linux, and macOS, with the primary production
  emphasis on Windows and Linux. OS-aware branches exist for things like opening a file browser,
  launching a sync terminal, and detecting the current user.
- **Two launch modes**: a CLI Flask server (`app_flask.py`) and a desktop GUI launcher (`launchpad.py`,
  built with `customtkinter`) that embeds the same Flask app in-process and can be frozen into a
  standalone executable via PyInstaller.

### Development history

This project was originally built out with **GitHub Copilot**, and a fair amount of that design
history is preserved in the repo itself rather than in this file:

- `docs/CODE_REVIEW.md`, `docs/CACHING_STRATEGY.md`, `docs/PERFORMANCE_INDEXES.md` — targeted
  deep-dives (production portal cleanup ideas, SQLite/connection caching design and rationale, index
  strategy for large network-hosted DBs). Still broadly accurate; consult them for depth on those
  specific topics rather than duplicating that detail here.
- `docs/production_redesign.md` — writeup of the legacy→consolidated nav bar redesign in
  `production.html` (see Production nav bar redesign below), written to be portable to a similar
  project.
- `docs/CODE_CITATIONS.md` — Copilot's attribution log for borrowed snippets (e.g. modal CSS).

Two Copilot-era docs that had drifted into actively misleading territory —
`.github/copilot-instructions.md` (described a pre-split, single-file `mediabrowser.py` app that no
longer exists) and `PROCESSOR_README.md` (described a superseded `/processor` design; the real
equivalent is the `/archive` + `/api/archive/*` workflow) — have been retired. This CLAUDE.md is now
the current architecture reference.

When making non-trivial changes, it's worth skimming the relevant doc above for rationale before
assuming something is accidental — but verify against the actual code, since these docs drift.

## Architecture

### Module map (`src/`)

| Module | Role |
|---|---|
| `app_flask.py` | CLI launcher / composition root. Creates the single `Flask` app, registers routes from `mediabrowser.py` and `projectbrowser.py`, serves `/static/<path>` from `$DEPOT_ALL` and `/resources/<path>` from `src/resources/`, handles port selection, browser-opening (with WSL support), DB index bootstrapping, and the `main()` CLI entrypoint (`--port`, `--host`, `--debug`, `--no-browser`). |
| `mediabrowser.py` | Media search/archive/cart routes. Exposes `register_routes(app)`; no standalone `Flask()` instance of its own. |
| `projectbrowser.py` | Production/job-management routes (`/production`, `/api/*` job & sync endpoints). Also exposes `register_routes(flask_app)`. |
| `launchpad.py` | `customtkinter` desktop GUI launcher. Runs the **same Flask app in-process** on a background thread (not a subprocess), TCP-probes the port for readiness, offers RESEARCH/ARCHIVE/PRODUCTION buttons that open the OS browser, and auto-closes after an idle countdown reset by any HTTP request or GUI interaction. |
| `app_launchpad_build.py` / `app_launchpad.spec` | PyInstaller packaging for `launchpad.py` → standalone executable. |
| `vpr_jobtools.py` | The **production-environment/OS conventions** layer: job-name validation, job directory creation, local↔network directory sync (rsync/robocopy), git-repo metadata lookup, current-user/file-owner lookup, and the shared `$DEPOT_ALL` path expand/contract helpers. Depends on `db_jobtools.py`. |
| `db_jobtools.py` | The **job database schema and constants** layer: per-app directory structure tables (`dict_apps`), the jobs SQLite schema (`list_db_jobs_columns`), ID/token generation, legacy tcsh-nav-file↔JSON↔SQLite migration helpers, shared taxonomy lists (genres, sources, subjects, etc. — the extension-classification lists were removed as dead code, see Recommendations #3), and the shared `SqliteThreadConnection` class used by both route modules' connection managers. No dependency on `vpr_jobtools.py`. |
| `db_mediatools.py` | Media-file-centric toolkit: archive table-to-table migration, media copy/transcode (ffmpeg), video thumbnailing (OpenCV), MP4 metadata (mutagen). Not imported by the live GUI app (`mediabrowser.py`/`projectbrowser.py`), but **not dead code either** — it's the library backing the local infrastructure scripts `util_sqlite_build_archive.py` / `util_sqlite_edit_archive.py` (see below), a second deliberate consumer of the shared layer alongside the app. |
| `src/old/xglobalsub.py` | Retired bulk path-substitution maintenance script, kept for reference. |

**Dependency graph**: `launchpad.py` → embeds `app_flask.py`'s Flask app → registers routes from
`mediabrowser.py` + `projectbrowser.py` → both import `db_jobtools as dbj` and `vpr_jobtools as vpr`
for shared domain logic (taxonomy lists, job validation/creation, directory sync, git info). `vpr_jobtools.py`
imports `db_jobtools.py`; `db_jobtools.py` has no reverse dependency. `db_mediatools.py` is not reachable
from the running GUI app, but is reachable from — and required by — the local infrastructure utilities
below, which are a second, separate entry point into the same shared library layer.

### Local testing / infrastructure utilities (`util_*.py`)

These five scripts are **not part of the GUI app's import graph** (nothing in `app_flask.py`,
`mediabrowser.py`, `projectbrowser.py`, or `launchpad.py` imports them, and they're never run by the
app) — but they are not dead/orphaned code either. They're standalone command-line tools a developer
runs directly for local testing and infrastructure setup: seeding a job without going through the
browser, building or migrating the archive database, converting rendered frames outside the app. Most
of them exercise the same shared `vpr_jobtools.py` / `db_jobtools.py` / `db_mediatools.py` calls the
live routes use, so they double as a way to test those shared modules in isolation, and as executable
reference examples of the intended calling pattern.

| Script | Role |
|---|---|
| `util_job_make.py` | Interactive CLI that creates a job (DB row + directories + `local.env` + nav alias) via the same `db_jobtools`/`vpr_jobtools` calls behind the `/api/job_new_create` route. Useful for seeding local dev/test jobs, or validating changes to those two modules, without running Flask at all. |
| `util_sqlite_build_archive.py` | Builds/populates the `media_arch` table + archive directory tree from `media_proj`, via `db_mediatools.db_sqlite_tablea_copy_to_tableb()`. The only current consumer of `db_mediatools.py`. |
| `util_sqlite_edit_archive.py` | One-off/rerunnable schema migration + backfill (`file_state`, `file_state_date`, `file_date`) on the media tables, also via `db_mediatools`. |
| `util_imgseq_to_mp4.py` | PNG image sequence → MP4 with optional title slate (ffmpeg/ffprobe). Unlike the other four, this is a production **pipeline** tool (used on real render output), not local-test-only — and it reimplements its own `JOB_DIR`/`WF_IMG_DIR` env-var reads rather than reusing `vpr_jobtools`/`db_jobtools` conventions (see Recommendations). |
| `util_frange_to_list.py` | Small standalone helper — `frange_to_list()` parses a frame-range string (`"1-3,5"`) into `list[int]`. No CLI entrypoint and no dependency on the shared libraries; general-purpose, not depot/job-aware. |

`util_sqlite_build_archive.py` and `util_sqlite_edit_archive.py` both raise `EnvironmentError` at
**import time** if `$DEPOT_ALL` isn't set (module-level env reads, not inside `if __name__ ==
'__main__':`), so they can only be run as scripts, not imported — this is fine for their role as
one-off local tools but means they can't be reused as libraries as-is.

### Data layer

Two independent SQLite databases, no ORM, no migrations framework:

- **Media DB**: `$DEPOT_ALL/assetdepot/media/dummy/db/media_dummy.sqlite`, tables `media_proj` (working)
  and `media_arch` (archived) — same schema, used as a soft-lifecycle pair (`file_state` column).
  Owned by `mediabrowser.py`.
- **Jobs DB**: `$DUMMY_DB/sqlite/db_projects.sqlite3`, table `projects` — schema defined by
  `db_jobtools.db_sqlite_table_jobs_create()`. Owned by `projectbrowser.py`.

Both route modules get their thread-local persistent connection from a shared
`db_jobtools.SqliteThreadConnection` class (each module instantiates its own — `_media_db` in
`mediabrowser.py`, `_jobs_db` in `projectbrowser.py` — since `threading.local()` is per-instance,
independent instances never collide). Each instance applies its own PRAGMA tuning on connect
(`journal_mode=DELETE`, `cache_size`, `synchronous=NORMAL`, `temp_store=MEMORY`, `busy_timeout`)
specifically to mitigate latency on network-hosted (Samba/NFS) DB files — see `docs/CACHING_STRATEGY.md`.
MediaBrowser is configured with a much larger `cache_size` (100MB) than ProjectBrowser (32MB), since
its media table is far larger than the jobs table — that's now an explicit constructor argument
(`cache_size_kb=`) rather than duplicated magic numbers. Both modules also run their own
`functools.lru_cache` read-cache layer with matching `cache_invalidate_runtime()` calls after
writes, and get `sqlite3.Row` row factories for dict-like access from the shared class.

**`$DEPOT_ALL` path convention**: paths stored in either DB use the literal placeholder string
`$DEPOT_ALL` instead of a real filesystem path, so the DB stays portable across machines/mount
points. `vpr_jobtools.vpr_env_depot_expand(path, depot_local=None)` substitutes the real depot
root in on read; `vpr_jobtools.vpr_env_depot_symbolize(path, depot_local=None)` substitutes it back
out (and normalizes `\` to `/`) before writing to the DB, so a Windows-built local path still ends
up stored the same way as one built on Linux/macOS. Both default `depot_local` to the `DEPOT_ALL`
env var if not passed explicitly. All read/write call sites across `mediabrowser.py`,
`projectbrowser.py`, `db_mediatools.py`, and `util_job_make.py` go through these two functions.

SQL is built with f-string interpolation of table/column names, safety coming entirely from
allowlists (`list_db_tables`, `list_columns_editable`) rather than parameterization of identifiers;
values themselves are correctly parameterized with `?`.

### Production directory hierarchy

A **job** lives at `<path_proj_netwk>/<job_year>/<job_name>/` (e.g. `.../2026/26_myjob_a/`) with
per-creative-app subdirectories defined in `db_jobtools.dict_apps` (adobe, audio, data, houdini,
maya, microsoft, movies, nuke, python, …), plus a parallel render tree under `path_rend_netwk`.

- `job_name` = `<YY>_<job_base>_<revision>` (e.g. `26_myjob_a`); `job_base` must be 4–10 lowercase
  alnum/underscore chars, start/end with a letter, no double underscore; `revision` cycles `a`…`z`,
  then `a1`, `b1`, ….
- `job_alias` = `<job_base><YY>`, used as a tcsh shell alias/env-var name.
- Job creation writes a per-job `local.env` (tcsh `setenv` lines: `JOB_YEAR`, `JOB_NAME`, `JOB_DIR`,
  `IMAGE_NAME`, `VDROP`, `JOB_ARCH_SEQ`, `JOB_ARCH_VID`, `WF_IMG_DIR`, `MAYA_PROJECT`, …) and a nav/alias
  entry in a generated tcsh file, for downstream shell tooling outside the web app.
- Note: `util_imgseq_to_mp4.py` expects `movies/source` and an undocumented `logo/` directory that
  don't match `dict_apps`' `movies/{src,out}` — a real drift between the documented schema and at
  least one consumer; verify before relying on either.

### Web layer

- `base.html` is the shared layout (dark theme, `#242424`/`#f0f0f0`) providing one shared
  lightbox/preview modal wired via `data-open-image` / `data-open-video` / `data-open-audio` /
  `data-download-file` attributes — child templates opt in just by adding those attributes.
- Page templates (`index.html`, `search.html`, `archive.html`, `production.html`, `cart.html`) each
  `{% extends "base.html" %}` and fill in a handful of blocks (`title`, `extra_styles`, `content`,
  `extra_scripts`, …).
- All client interactivity is vanilla JS `fetch()` against `/api/*` JSON endpoints — no framework.
  `production.html` is the largest single script block (~1000+ lines), implementing the cascading
  Year → Project → App → Subdir navigation, sync confirmation, and job dashboard/create forms.
- `production.html` currently ships **two nav bars side by side**: the original
  `JOB SET/JOB SYNC/JOB NEW` bar, and a newer consolidated `JOB OPS/JOB:` bar built on top of the
  same underlying functions/endpoints (kept alongside the original for direct comparison, not yet a
  replacement). See `docs/production_redesign.md` for the full design writeup.
- Route naming: page routes are prefixed `page_*`, JSON API routes `api_*`; nearly every `/api/*`
  handler wraps its body in `try/except Exception as e: return jsonify({'success': False, 'error': str(e)})`.
- Password-gated write endpoints (cart edit/prune, job creation) compare a client-submitted value
  against the `MEDIA_SQLITE_KEY` env var — a shared static password, adequate only because this is a
  localhost-bound internal tool, not a real auth system.

### Environment variables

| Variable | Required by | Purpose |
|---|---|---|
| `DEPOT_ALL` | `app_flask.py`, `mediabrowser.py`, `projectbrowser.py`, most `util_*` scripts | Root of the storage depot; real path substituted for the `$DEPOT_ALL` placeholder stored in the DBs. |
| `DUMMY_DB` | `projectbrowser.py`, `util_job_make.py` | Base path to the jobs SQLite/JSON DB directory. |
| `DUMMY_JOBS_NETWK` / `DUMMY_REND_NETWK` | `vpr_jobtools.py`, `projectbrowser.py`, `util_job_make.py` | Network-side job / render directory roots. |
| `DUMMY_JOBS_LOCAL` / `DUMMY_REND_LOCAL` | `projectbrowser.py`, `util_job_make.py` | Local-mirror job / render directory roots (used for the sync feature). |
| `MEDIA_SQLITE_KEY` | `mediabrowser.py`, `projectbrowser.py` | Shared password gating destructive/edit write endpoints. Optional but effectively required for write access. |
| `JOB_DIR`, `WF_IMG_DIR` | `util_imgseq_to_mp4.py` | Per-job working directories for the image-sequence-to-MP4 utility. |
| `USER` / `LOGNAME` / `USERNAME` | `vpr_jobtools.py` (current-user detection) | POSIX/Windows current-user fallback chain. |
| `PYTHON_VENVS` | `.vscode/settings.json` | Points at the venv used for local dev (`$PYTHON_VENVS/venv_vpr`). |

The `DUMMY_*` naming throughout (env vars, `vpr_jobs_dummy_create()`, `db_jobdirs_get()`'s hardcoded
`assetdepot/jobs_dummy` path) suggests final production env-var names haven't been settled — see
Recommendations.

## Coding style — match existing conventions

The user has asked that future work stay as consistent as possible with the existing style,
**particularly `vpr_jobtools.py`, `db_jobtools.py`, and `db_mediatools.py`** (the reusable
"library" layer, as opposed to the Flask route modules). Conventions observed there:

- **Naming**: `snake_case` everywhere. Domain-prefixed function names: `vpr_*` for
  production-environment/OS operations, `db_*` for database/schema operations, `db_media_*` for
  media-file operations within `db_mediatools.py`. Path variables are always `path_*`; constant
  lists/dicts are `list_*` / `dict_*`. Private helpers use a leading underscore.
- **Section banners**: functions in `vpr_jobtools.py` and `db_jobtools.py` are separated by
  `###############################################################################` banner
  comments, often with a trailing `# end of def foo(...):` comment — a distinctive, consistent
  visual convention specific to those two files. The Flask route modules instead use
  `# ====...====` banners around logical sections (e.g. "ROUTES - CART", "HELPER FUNCTIONS - DATABASE").
  Match whichever convention the file you're editing already uses.
- **Docstrings**: triple-quoted, present on almost every function. Newer/more careful functions use
  structured `Args:` / `Returns:` / `Notes:` / `Examples:` blocks (Google-style-ish); match that
  standard for any new function rather than the older bare one-liners.
- **Debug/status output**: `vpr_jobtools.py` and `db_jobtools.py` use a recurring
  `func_name = inspect.stack()[0][3]; dbh = '[{}]'.format(func_name)` prefix idiom before `print()`
  statements, in place of the `logging` module (which is not used anywhere in the codebase). Match
  this in those files rather than introducing `logging` unilaterally.
- **Error handling — two coexisting patterns, pick based on file**:
  - `vpr_jobtools.py` / `db_jobtools.py`: mostly print-and-return (`print(...); return False`/`None`)
    rather than raising.
  - `db_mediatools.py` and the Flask route modules: return a `dict` with `success`/`error` keys.
  - Newer standalone scripts (`util_job_make.py`, `util_frange_to_list.py`) raise real exceptions
    (`ValueError`, `EnvironmentError`) for invalid input/missing config.
  - When adding a function to an existing module, follow that module's existing pattern rather than
    picking your own — this is inconsistent across the codebase already; don't add a fourth style.
- **Paths**: always `os.path.join()` / `os.path.relpath()` / `os.path.splitext()`, never string
  concatenation, for real filesystem paths. The `$DEPOT_ALL` placeholder substitution uses
  `str.replace()` by convention (see Data layer above).
- **Type hints**: partial and inconsistent — present on some newer functions (including PEP 604
  `str | None` unions), largely absent in `vpr_jobtools.py`/`db_jobtools.py`. Adding hints to new
  code is fine and consistent with the newer parts of the codebase; don't feel obligated to
  retrofit old functions as a drive-by.
- **Module docstrings**: each Flask route module opens with a triple-quoted header enumerating its
  routes — treat this as living documentation and keep it updated when routes change.

## Recommendations for future development

The app currently has solid, working core functionality (search, archive ingestion, cart, job
creation/navigation/sync). Rough edges worth addressing before adding significant new capability:

1. **[Known design issue, deferred] Settle the `DUMMY_*` naming.** Env vars, function names
   (`vpr_jobs_dummy_create`), and a hardcoded `assetdepot/jobs_dummy` path
   (`db_jobtools.db_jobdirs_get()`) all read as placeholder/dev naming baked into what's actually
   the primary job-creation path. Renaming these to final production names (and removing the
   hardcoded dummy path) would reduce confusion for anyone extending the job-management flow. Not
   being actioned now — flagged here so it isn't mistaken for accidental/unintentional when
   encountered later.
2. ~~**Deduplicate the DB connection/caching boilerplate.**~~ — done: both route modules now get
   their thread-local connection from `db_jobtools.SqliteThreadConnection`, parameterized per
   module (`_media_db`/`_jobs_db`) with their own `cache_size_kb` — MediaBrowser intentionally
   larger (100MB) than ProjectBrowser (32MB) since its media table is much bigger; that rationale
   is now a code comment next to the constant instead of an undocumented discrepancy. The
   `functools.lru_cache` read-cache layers remain separate per module (they cache different data
   shapes) and weren't merged.
2b. ~~**Factor out the `$DEPOT_ALL` substitution helper.**~~ — done: added
   `vpr_jobtools.vpr_env_depot_expand()` / `vpr_env_depot_symbolize()` and switched all ~11 call
   sites across `mediabrowser.py`, `projectbrowser.py`, `db_mediatools.py`, `util_job_make.py`, and
   `vpr_jobtools.py` itself to use them (removing `projectbrowser.py`'s private, file-local
   `expand_depot_path()` in favor of the shared version). `db_mediatools.py` gained its first
   dependency on `vpr_jobtools.py` as a result. The contract direction now always normalizes `\` to
   `/`, which fixes a latent inconsistency where most write sites didn't normalize separators but
   one (`mediabrowser.py`'s upload handler) did.
3. ~~**Reconcile the diverging extension-classification lists.**~~ — done, but not by reconciling:
   `db_jobtools.py`'s copies (`list_ext_geometry`/`images`/`videos`/`audio`/`docs`/`others`) turned
   out to be **dead code** — grepped the whole `src/` tree and found zero call sites for
   `dbj.list_ext_*` anywhere, including inside `db_jobtools.py` itself. Only `db_mediatools.py`'s
   versions were ever live (used in exactly one place, `db_sqlite_tablea_copy_to_tableb()`, called
   only by `util_sqlite_build_archive.py`), so there was never a real two-live-systems divergence
   risk — just one used list and one orphaned, disagreeing copy. Removed the six unused constants
   from `db_jobtools.py` (`db_jobtools.list_file_extensions`, the unrelated flat list `mediabrowser.py`
   actually uses for its search-filter dropdown, was untouched).
4. ~~**Decide the fate of `db_mediatools.py`.**~~ — resolved by clarification, not by code change:
   it's not dead weight. It's confirmed to be the library backing `util_sqlite_build_archive.py` /
   `util_sqlite_edit_archive.py`, standalone local infrastructure tools for building/migrating the
   archive DB outside the GUI app. It remains a second, independent implementation of archive-copy
   logic alongside `mediabrowser.py`'s own (`db_tables_sync_field()` etc.) — worth keeping the two in
   sync as either evolves, but there's no more open question of whether to wire it in or delete it.
5. ~~**Remove orphaned code**~~ — done: deleted `mediabrowser_addons.py`, `templates/cart_addons.html`,
   the unused `Flask()` instance in `projectbrowser.py`, and `launchpad.py`'s unused
   `get_python_executable()` helper (and their now-dead imports, `Flask`/`sys`).
6. ~~**Harden the write-gated endpoints**~~ — done, all four sub-items:
   - `app.secret_key` hardcoded — fixed: `app_flask.py` now generates a fresh
     `secrets.token_hex(32)` key per app run instead of a fixed literal, with a comment explaining
     what it's for (signs the session cookie — cart, archive queue, etc. — so the browser can't
     tamper with it). A restart now invalidates old session cookies, consistent with the cart
     already being documented as clearing on restart.
   - Missing `conn.rollback()` on write-loop exceptions — fixed: added to both
     `cart_items_update` and `cart_items_prune` in `mediabrowser.py`, so a mid-loop exception no
     longer leaves earlier `UPDATE`/`DELETE` statements applied without the later ones.
   - `MEDIA_SQLITE_KEY` password check used plain `==` — fixed: all three check sites
     (`mediabrowser.py` ×2, `projectbrowser.py` ×1) now use `hmac.compare_digest()`, closing the
     timing side-channel.
   - `/api/archive/serve_file`'s unconfined `send_file(path)` — fixed: now resolves the requested
     path with `os.path.realpath()` (catches both `..` traversal and symlink escapes) and checks
     `os.path.commonpath([real_path, real_depot]) == real_depot` before serving, returning 403
     otherwise. Deliberately scoped to all of `depot_local`, not just `path_base_archive`, since
     `serve_file` previews files from anywhere in the depot during archive ingestion, not just the
     archive subfolder. Verified live: files inside the depot still serve (200); both `../../etc/passwd`
     traversal and a direct `/etc/passwd` request are rejected (403).
   Related and fixed alongside this: `app_flask.py`'s `--debug` CLI flag was discovered to be a
   no-op (`action='store_true', default=True` can never be `False`), meaning debug mode — which
   exposes Werkzeug's interactive in-browser debugger, i.e. arbitrary code execution from any
   unhandled exception — stayed on even if `--host` were widened past `127.0.0.1`. `main()` now
   force-disables debug mode whenever `host != '127.0.0.1'`, regardless of the `--debug` flag's
   value, with a `[SECURITY]` log line when it kicks in. Verified live with `--host 0.0.0.0`.
7. ~~**Rewrite or retire `.github/copilot-instructions.md` and `PROCESSOR_README.md`**~~ — done:
   both retired (deleted); this CLAUDE.md is the current architecture reference.
8. ~~**Add a test suite.**~~ — done, all four tiers. `pytest` scaffolding: `pytest.ini` at the repo
   root (`pythonpath = src`, since `src/` is a flat script directory with no `__init__.py` and needs
   to be put on the import path explicitly for tests to `import vpr_jobtools` the same way
   `mediabrowser.py` does). `pytest` is listed directly in `requirements.txt` (no separate dev
   requirements file). Run with `pytest` from the repo root — 62 tests, all passing, verified stable
   across repeated runs.
   - `test_vpr_jobtools.py` — `vpr_job_base_is_valid`, `vpr_job_rev_set`, the
     `vpr_env_depot_expand`/`vpr_env_depot_symbolize` round-trip (including a Windows-separator case).
   - `test_db_jobtools.py` — `db_tags_verify`, `db_jobname_clean`, `db_token_generator`,
     `db_sqlite_table_jobs_create`, `db_id_create` (including its collision-retry loop, forced via
     `monkeypatch`). Writing the `db_jobname_clean` tests surfaced a real bug — its regex had `\X1F`
     (invalid escape, capital X) instead of `\x1F`, which crashed on Python 3.14 whenever the
     function ran; harmless in practice since it's dead code today (unused anywhere in the app), but
     fixed alongside its test.
   - `test_sqlite_thread_connection.py` — the `SqliteThreadConnection` class itself: same-connection
     reuse within a thread, `release()` not closing the cached connection but closing others,
     per-instance `cache_size` isolation, and genuine thread-local behavior verified with a real
     `threading.Thread`.
   - `test_util_frange_to_list.py` — lifted from the function's own docstring examples.
   - `test_routes_mediabrowser.py` / `test_routes_projectbrowser.py` — Flask integration tests
     (index/search/cart filtering, cart add/clear, job-name validation and revision-incrementing,
     `/api/projects_by_year` filtering) via `conftest.py` fixtures that build a fully-composed test
     app (both `mediabrowser.register_routes()` and `projectbrowser.register_routes()` on one Flask
     instance, matching how `app_flask.py` actually composes the real app — necessary because shared
     templates like `base.html` cross-reference endpoints from either module, e.g. the header link to
     `page_index` even when rendering a `projectbrowser.py` page) against a seeded temp SQLite DB.
     `conftest.py` sets `DEPOT_ALL`/`DUMMY_DB` and builds that temp DB at *module* level (not inside a
     fixture), since pytest imports test files during collection, before any fixture runs, and both
     app modules raise `EnvironmentError` at import time otherwise — and it unconditionally overrides
     those env vars even if already set in the shell, so tests never touch a developer's real depot.
     The cleanup fixtures also call each module's own `cache_invalidate_runtime()` after reseeding
     data, since several routes are wrapped in `functools.lru_cache` and raw SQL seeding (bypassing
     the app's normal write path) wouldn't otherwise invalidate them between tests.
9. ~~**Clean up stray root-level files**~~ — done: removed the stray `1` file and moved
   `# Code Citations.md` to `docs/CODE_CITATIONS.md` (out of the repo root, alongside any future
   reference-only docs).

## Build & test

No build step (server-rendered templates, no bundler). A `pytest` suite exists (see Recommendations
#8 above) covering the pure-function library layer, `SqliteThreadConnection`, and Flask route
integration tests for both `mediabrowser.py` and `projectbrowser.py`. There are also manual
local-testing/infrastructure entry points — see `util_*.py` below.

**Setup**:
```bash
pip install -r requirements.txt   # Flask, customtkinter, tkinterdnd2, opencv-python, python-vlc, GitPython, Pillow, PyInstaller, mutagen, pytest
```

**Run tests** (from the repo root):
```bash
pytest
```

**Run (CLI, dev)**:
```bash
export DEPOT_ALL=/path/to/depot        # required
export DUMMY_DB=/path/to/dummy/db      # required for the production portal
export MEDIA_SQLITE_KEY=...            # optional, gates write endpoints
python src/app_flask.py --port 5000    # see --help for --host/--debug/--no-browser
```

**Run (desktop GUI launcher)**:
```bash
python src/launchpad.py
```

**Package the desktop launcher** (PyInstaller):
```bash
python src/app_launchpad_build.py
```

**Local testing / infrastructure utilities** (same `DEPOT_ALL`/`DUMMY_DB` env as above; see the
Architecture section above for what each does):
```bash
python src/util_job_make.py               # interactively seed a job (DB row + dirs + env + nav alias)
python src/util_sqlite_build_archive.py    # build/populate the media_arch archive DB + directory tree
python src/util_sqlite_edit_archive.py     # migrate/backfill media table columns
python src/util_imgseq_to_mp4.py --help    # PNG sequence -> MP4 (production pipeline tool)
```

The Python interpreter used by this project's VS Code config is `$PYTHON_VENVS/venv_vpr/bin/python3`
(macOS); the default integrated terminal is `tcsh`.
