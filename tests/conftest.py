"""
Shared pytest fixtures for the mediabrowser test suite.

mediabrowser.py and projectbrowser.py both raise EnvironmentError at IMPORT
time if DEPOT_ALL/DUMMY_DB aren't set, and pytest imports test modules during
collection -- before any fixture function has a chance to run. So the env
vars (and a seeded temp SQLite DB for each module to find) have to be set up
here at conftest.py *module* level, not inside a fixture: pytest always loads
a directory's conftest.py before collecting/importing the test files in it.

This deliberately overrides DEPOT_ALL/DUMMY_DB even if already set in the
calling shell (common on this project, since they're needed to run the app
directly) -- tests must run against an isolated, disposable depot, never
against whatever real depot a developer happens to have configured.
"""

import os
import sqlite3
import tempfile

import pytest

import db_jobtools as dbj  # noqa: E402  (no DEPOT_ALL/DUMMY_DB requirement at import time)

# Columns mediabrowser.py's cart_item_add_from_dict() expects on the media
# tables (mediabrowser.py: `all_fields` dict) -- not defined by a CREATE
# TABLE anywhere in the app itself, so the test schema is built from that.
MEDIA_COLUMNS = [
    'file_id', 'file_name', 'file_path', 'file_extension', 'file_format',
    'file_resolution', 'file_duration', 'shot_size', 'shot_type',
    'source', 'source_id', 'genre', 'subject', 'category', 'lighting',
    'setting', 'tags', 'captions', 'file_date', 'file_state', 'file_state_date',
]

_TEST_DEPOT = tempfile.mkdtemp(prefix='mediabrowser_test_depot_')
os.environ['DEPOT_ALL'] = _TEST_DEPOT

_MEDIA_DB_DIR = os.path.join(_TEST_DEPOT, 'assetdepot', 'media', 'dummy', 'db')
os.makedirs(_MEDIA_DB_DIR, exist_ok=True)
MEDIA_DB_PATH = os.path.join(_MEDIA_DB_DIR, 'media_dummy.sqlite')

_DUMMY_DB_ROOT = os.path.join(_TEST_DEPOT, 'jobs_dummy_db')
os.makedirs(os.path.join(_DUMMY_DB_ROOT, 'sqlite'), exist_ok=True)
os.environ['DUMMY_DB'] = _DUMMY_DB_ROOT
JOBS_DB_PATH = os.path.join(_DUMMY_DB_ROOT, 'sqlite', 'db_projects.sqlite3')


def _create_media_db():
    conn = sqlite3.connect(MEDIA_DB_PATH)
    columns_sql = ', '.join(f'{col} TEXT' for col in MEDIA_COLUMNS)
    for table in ('media_proj', 'media_arch'):
        conn.execute(f'CREATE TABLE IF NOT EXISTS {table} ({columns_sql})')
    conn.commit()
    conn.close()


def _create_jobs_db():
    conn = dbj.db_sqlite_table_jobs_create(JOBS_DB_PATH, 'projects')
    conn.close()  # db_sqlite_table_jobs_create leaves it open; not our style, close it here


_create_media_db()
_create_jobs_db()

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'src', 'templates')
_RESOURCES_DIR = os.path.join(os.path.dirname(__file__), '..', 'src', 'resources')


def _build_full_app():
    """Mirror app_flask.py's real composition: one Flask app with BOTH
    mediabrowser's and projectbrowser's routes registered, plus the
    serve_resources route app_flask.py defines separately. Templates
    (base.html in particular) freely cross-reference endpoints from either
    module -- e.g. the shared header links to mediabrowser's page_index even
    when rendering a projectbrowser page -- so registering only one module's
    routes 500s on any template render that hits those cross-references.
    """
    from flask import Flask, send_from_directory
    import mediabrowser
    import projectbrowser

    app = Flask(__name__, template_folder=_TEMPLATE_DIR)
    app.secret_key = 'test-secret'

    @app.route('/resources/<path:filename>')
    def serve_resources(filename):
        return send_from_directory(_RESOURCES_DIR, filename)

    mediabrowser.register_routes(app)
    projectbrowser.register_routes(app)
    return app


@pytest.fixture
def mediabrowser_client():
    """Flask test client against the fully-composed app (see _build_full_app)."""
    return _build_full_app().test_client()


@pytest.fixture
def projectbrowser_client():
    """Flask test client against the fully-composed app (see _build_full_app)."""
    return _build_full_app().test_client()


@pytest.fixture
def clean_media_db():
    """Empty both media tables so each test starts from a known, empty state.

    Also clears mediabrowser's lru_cache-based read caches: they're keyed on
    things like (category, top_n, db_table), not on row content, so a stale
    hit from an earlier test would otherwise silently survive this reset.
    """
    conn = sqlite3.connect(MEDIA_DB_PATH)
    for table in ('media_proj', 'media_arch'):
        conn.execute(f'DELETE FROM {table}')
    conn.commit()
    conn.close()

    import mediabrowser
    mediabrowser.cache_invalidate_runtime()


@pytest.fixture
def clean_jobs_db():
    """Empty the jobs table so each test starts from a known, empty state.

    Also clears projectbrowser's lru_cache-based read caches (e.g.
    _cached_projects_by_year), for the same reason as clean_media_db above.
    """
    conn = sqlite3.connect(JOBS_DB_PATH)
    conn.execute('DELETE FROM projects')
    conn.commit()
    conn.close()

    import projectbrowser
    projectbrowser.cache_invalidate_runtime()


def insert_media_row(row):
    """Insert one row into media_proj. `row` may omit columns; blanks fill in."""
    values = {col: '' for col in MEDIA_COLUMNS}
    values.update(row)
    conn = sqlite3.connect(MEDIA_DB_PATH)
    columns = ', '.join(values.keys())
    placeholders = ', '.join('?' for _ in values)
    conn.execute(f'INSERT INTO media_proj ({columns}) VALUES ({placeholders})', tuple(values.values()))
    conn.commit()
    conn.close()


def insert_job_row(row):
    """Insert one row into projects. `row` may omit columns; blanks fill in."""
    values = {col: '' for col in dbj.list_db_jobs_columns}
    values.update(row)
    conn = sqlite3.connect(JOBS_DB_PATH)
    columns = ', '.join(values.keys())
    placeholders = ', '.join('?' for _ in values)
    conn.execute(f'INSERT INTO projects ({columns}) VALUES ({placeholders})', tuple(values.values()))
    conn.commit()
    conn.close()
