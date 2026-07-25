from datetime import datetime

from conftest import insert_job_row

_YEAR_FULL = datetime.now().strftime('%Y')
_YEAR_SHORT = _YEAR_FULL[-2:]


def test_production_page_loads_with_empty_db(projectbrowser_client, clean_jobs_db):
    resp = projectbrowser_client.get('/production')
    assert resp.status_code == 200


def test_job_name_validate_empty_base(projectbrowser_client, clean_jobs_db):
    resp = projectbrowser_client.post(
        '/api/job_name_validate', json={'job_base': ''})
    assert resp.status_code == 200
    assert resp.get_json()['valid'] is False


def test_job_name_validate_invalid_base(projectbrowser_client, clean_jobs_db):
    resp = projectbrowser_client.post(
        '/api/job_name_validate', json={'job_base': 'ab'})
    data = resp.get_json()
    assert data['valid'] is False
    assert 'at least' in data['reason']


def test_job_name_validate_first_revision(projectbrowser_client, clean_jobs_db):
    resp = projectbrowser_client.post(
        '/api/job_name_validate', json={'job_base': 'newproj'})
    data = resp.get_json()
    assert data['valid'] is True
    assert data['job_name'] == f'{_YEAR_SHORT}_newproj_a'
    assert data['job_alias'] == f'newproj{_YEAR_SHORT}'


def test_job_name_validate_increments_existing_revision(projectbrowser_client, clean_jobs_db):
    insert_job_row({
        'job_id': 'existingid01',
        'job_name': f'{_YEAR_SHORT}_foxlito_a',
        'job_alias': f'foxlito{_YEAR_SHORT}',
        'job_state': 'active',
    })

    resp = projectbrowser_client.post(
        '/api/job_name_validate', json={'job_base': 'foxlito'})
    data = resp.get_json()
    assert data['valid'] is True
    assert data['job_name'] == f'{_YEAR_SHORT}_foxlito_b'


def test_projects_by_year_filters_correctly(projectbrowser_client, clean_jobs_db):
    insert_job_row({'job_id': 'id0000001', 'job_name': f'{_YEAR_SHORT}_foo_a', 'job_year': _YEAR_FULL})
    insert_job_row({'job_id': 'id0000002', 'job_name': '99_bar_a', 'job_year': '1999'})

    resp = projectbrowser_client.get(f'/api/projects_by_year?year={_YEAR_FULL}')
    assert resp.status_code == 200
    names = [p['name'] for p in resp.get_json()['projects']]
    assert f'{_YEAR_SHORT}_foo_a' in names
    assert '99_bar_a' not in names
