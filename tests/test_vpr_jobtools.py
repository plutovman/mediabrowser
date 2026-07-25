import pytest

import vpr_jobtools as vpr


# --- vpr_job_base_is_valid --------------------------------------------------

def test_job_base_valid():
    assert vpr.vpr_job_base_is_valid('foxlito') == (True, 'foxlito')


def test_job_base_too_short():
    valid, reason = vpr.vpr_job_base_is_valid('abc')
    assert valid is False
    assert 'at least' in reason


def test_job_base_too_long():
    valid, reason = vpr.vpr_job_base_is_valid('a' * 11)
    assert valid is False
    assert 'exceed' in reason


def test_job_base_rejects_double_underscore():
    valid, _ = vpr.vpr_job_base_is_valid('my__job')
    assert valid is False


def test_job_base_must_start_with_letter():
    valid, _ = vpr.vpr_job_base_is_valid('1myjob')
    assert valid is False


def test_job_base_must_end_with_letter():
    valid, _ = vpr.vpr_job_base_is_valid('myjob1')
    assert valid is False


def test_job_base_rejects_uppercase():
    valid, _ = vpr.vpr_job_base_is_valid('MyJob')
    assert valid is False


# --- vpr_job_rev_set ---------------------------------------------------------

@pytest.mark.parametrize('current,expected', [
    ('', 'a'),
    ('a', 'b'),
    ('y', 'z'),
    ('z', 'a1'),
    ('a1', 'b1'),
    ('z1', 'a2'),
    ('z2', 'a3'),
])
def test_job_rev_set(current, expected):
    assert vpr.vpr_job_rev_set(current) == expected


def test_job_rev_set_invalid_returns_none():
    assert vpr.vpr_job_rev_set('Z') is None


# --- vpr_env_depot_expand / vpr_env_depot_symbolize --------------------------

def test_depot_roundtrip():
    depot = '/fake/depot'
    real = '/fake/depot/assetdepot/jobs/2026/26_foo_a'
    symbolic = vpr.vpr_env_depot_symbolize(real, depot)
    assert symbolic == '$DEPOT_ALL/assetdepot/jobs/2026/26_foo_a'
    assert vpr.vpr_env_depot_expand(symbolic, depot) == real


def test_depot_symbolize_normalizes_windows_separators():
    depot_win = r'C:\depotlite'
    real_win = r'C:\depotlite\assetdepot\jobs_dummy\2026\26_foxlito_a'
    assert vpr.vpr_env_depot_symbolize(real_win, depot_win) == \
        '$DEPOT_ALL/assetdepot/jobs_dummy/2026/26_foxlito_a'


def test_depot_expand_leaves_non_symbolic_path_untouched():
    assert vpr.vpr_env_depot_expand('/already/real/path', '/fake/depot') == '/already/real/path'


def test_depot_symbolize_empty_path_untouched():
    assert vpr.vpr_env_depot_symbolize('', '/fake/depot') == ''


def test_depot_symbolize_no_depot_local_untouched(monkeypatch):
    # depot_local=None falls back to os.getenv('DEPOT_ALL'); isolate that
    # explicitly so this test doesn't depend on the ambient shell environment.
    monkeypatch.delenv('DEPOT_ALL', raising=False)
    assert vpr.vpr_env_depot_symbolize('/some/real/path', None) == '/some/real/path'
