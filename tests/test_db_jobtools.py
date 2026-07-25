import db_jobtools as dbj


# --- db_tags_verify -----------------------------------------------------------

def test_tags_verify_dedupes_case_insensitive():
    assert dbj.db_tags_verify('animation, lighting, animation, Lighting') == 'animation, lighting'


def test_tags_verify_strips_empty_entries():
    assert dbj.db_tags_verify(',animation,,lighting,') == 'animation, lighting'


def test_tags_verify_normalizes_spacing():
    assert dbj.db_tags_verify('animation,lighting,compositing') == 'animation, lighting, compositing'


def test_tags_verify_preserves_multiword_tags():
    assert dbj.db_tags_verify('character animation, background lighting') == \
        'character animation, background lighting'


# --- db_jobname_clean ----------------------------------------------------------

def test_jobname_clean_strips_spaces_and_punctuation():
    assert dbj.db_jobname_clean('  My 2026 Job!! ', 20) == 'my2026job'


def test_jobname_clean_strips_leading_and_trailing_digits_only():
    assert dbj.db_jobname_clean('99project007', 20) == 'project'


def test_jobname_clean_truncates_to_max_length():
    assert dbj.db_jobname_clean('averylongjobname', 6) == 'averyl'


# --- db_token_generator ---------------------------------------------------

def test_token_generator_default_length():
    token = dbj.db_token_generator()
    assert len(token) == 12
    assert token.isalpha()
    assert token.islower()


def test_token_generator_custom_length():
    assert len(dbj.db_token_generator(6)) == 6


# --- db_sqlite_table_jobs_create --------------------------------------------

def test_sqlite_table_jobs_create_columns(tmp_path):
    db_path = str(tmp_path / 'jobs.sqlite3')
    conn = dbj.db_sqlite_table_jobs_create(db_path, 'projects')
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        assert ('projects',) in tables

        columns = [row[1] for row in conn.execute('PRAGMA table_info(projects)').fetchall()]
        # first column is the autoincrement 'id' PK, not part of list_db_jobs_columns
        assert columns[1:] == dbj.list_db_jobs_columns
    finally:
        conn.close()


def test_sqlite_table_jobs_create_is_idempotent(tmp_path):
    db_path = str(tmp_path / 'jobs.sqlite3')
    dbj.db_sqlite_table_jobs_create(db_path, 'projects').close()
    # CREATE TABLE IF NOT EXISTS -- calling again on the same file must not raise
    dbj.db_sqlite_table_jobs_create(db_path, 'projects').close()


# --- db_id_create -------------------------------------------------------------

_JOB_ROW = (
    'job_id', 'job_name', 'job_alias', 'job_state', 'job_year', 'job_user_id',
    'job_user_name', 'job_edit_user_id', 'job_edit_user_name', 'job_edit_date',
    'job_notes', 'job_tags', 'job_date_created', 'job_date_due',
    'job_charge1', 'job_charge2', 'job_charge3', 'job_path_job', 'job_path_rnd', 'job_apps',
)


def _insert_job(conn, job_id, job_name='job'):
    values = {col: '' for col in _JOB_ROW}
    values['job_id'] = job_id
    values['job_name'] = job_name
    columns = ', '.join(values.keys())
    placeholders = ', '.join('?' for _ in values)
    conn.execute(f'INSERT INTO projects ({columns}) VALUES ({placeholders})', tuple(values.values()))
    conn.commit()


def test_id_create_returns_well_formed_token(tmp_path):
    db_path = str(tmp_path / 'jobs.sqlite3')
    dbj.db_sqlite_table_jobs_create(db_path, 'projects').close()

    job_id = dbj.db_id_create(db_path, 'projects', 'job_id')
    assert len(job_id) == 12
    assert job_id.isalpha()
    assert job_id.islower()


def test_id_create_regenerates_on_collision(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'jobs.sqlite3')
    conn = dbj.db_sqlite_table_jobs_create(db_path, 'projects')
    _insert_job(conn, job_id='alreadytaken')
    conn.close()

    # First candidate collides with the row above; db_id_create must retry
    # rather than returning it.
    tokens = iter(['alreadytaken', 'freshuniqueid'])
    monkeypatch.setattr(dbj, 'db_token_generator', lambda *a, **k: next(tokens))

    assert dbj.db_id_create(db_path, 'projects', 'job_id') == 'freshuniqueid'
