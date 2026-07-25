import sqlite3
import threading

import pytest

import db_jobtools as dbj


def _make_conn_mgr(tmp_path, name='test.sqlite3', **kwargs):
    return dbj.SqliteThreadConnection(str(tmp_path / name), label='Test', **kwargs)


def test_get_returns_usable_connection(tmp_path):
    mgr = _make_conn_mgr(tmp_path)
    conn = mgr.get()
    # row_factory is sqlite3.Row (set by _configure()), which doesn't compare
    # equal to a plain tuple directly -- cast explicitly.
    assert tuple(conn.execute('SELECT 1').fetchone()) == (1,)


def test_get_returns_same_connection_within_thread(tmp_path):
    mgr = _make_conn_mgr(tmp_path)
    assert mgr.get() is mgr.get()


def test_release_does_not_close_cached_connection(tmp_path):
    mgr = _make_conn_mgr(tmp_path)
    conn = mgr.get()
    mgr.release(conn)
    # still usable after release() -- it's the thread's cached connection,
    # so release() must be a no-op for it, per the "stay warm" design.
    assert tuple(conn.execute('SELECT 1').fetchone()) == (1,)


def test_release_closes_non_cached_connection(tmp_path):
    mgr = _make_conn_mgr(tmp_path)
    mgr.get()  # populate the thread-local cache with a *different* connection
    other_conn = sqlite3.connect(str(tmp_path / 'test.sqlite3'))
    mgr.release(other_conn)
    with pytest.raises(sqlite3.ProgrammingError):
        other_conn.execute('SELECT 1')


def test_cache_size_pragma_applied(tmp_path):
    mgr = _make_conn_mgr(tmp_path, cache_size_kb=-1024)
    conn = mgr.get()
    assert conn.execute('PRAGMA cache_size').fetchone()[0] == -1024


def test_independent_instances_dont_collide(tmp_path):
    # This is the whole rationale behind the class: two instances (e.g. one
    # per database) must never share state or config, even with identically
    # named attributes, since each wraps its own threading.local().
    mgr_a = _make_conn_mgr(tmp_path, name='a.sqlite3', cache_size_kb=-102400)
    mgr_b = _make_conn_mgr(tmp_path, name='b.sqlite3', cache_size_kb=-32768)

    conn_a = mgr_a.get()
    conn_b = mgr_b.get()

    assert conn_a is not conn_b
    assert conn_a.execute('PRAGMA cache_size').fetchone()[0] == -102400
    assert conn_b.execute('PRAGMA cache_size').fetchone()[0] == -32768


def test_connections_are_thread_local(tmp_path):
    mgr = _make_conn_mgr(tmp_path)
    main_conn = mgr.get()

    other_thread_conn = {}

    def worker():
        other_thread_conn['conn'] = mgr.get()

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert other_thread_conn['conn'] is not main_conn
