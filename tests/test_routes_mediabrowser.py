from conftest import insert_media_row


def _row(file_id, genre='portrait', file_name=None, extra=None):
    row = {
        'file_id': file_id,
        'file_name': file_name or f'{file_id}.jpg',
        'file_path': f'$DEPOT_ALL/assetdepot/media/dummy/proj/{file_id}.jpg',
        'file_extension': 'jpg',
        'genre': genre,
        'file_state': 'active',
    }
    if extra:
        row.update(extra)
    return row


def test_index_with_empty_db(mediabrowser_client, clean_media_db):
    resp = mediabrowser_client.get('/')
    assert resp.status_code == 200


def test_index_with_seeded_item(mediabrowser_client, clean_media_db):
    insert_media_row(_row('img001'))
    resp = mediabrowser_client.get('/')
    assert resp.status_code == 200


def test_search_no_filters_returns_all_active(mediabrowser_client, clean_media_db):
    insert_media_row(_row('img001', genre='portrait'))
    insert_media_row(_row('img002', genre='landscape'))
    resp = mediabrowser_client.get('/search')
    assert resp.status_code == 200
    assert b'img001.jpg' in resp.data
    assert b'img002.jpg' in resp.data


def test_search_filters_by_genre(mediabrowser_client, clean_media_db):
    insert_media_row(_row('img001', genre='portrait'))
    insert_media_row(_row('img002', genre='landscape'))
    resp = mediabrowser_client.get('/search?genre=portrait')
    assert resp.status_code == 200
    assert b'img001.jpg' in resp.data
    assert b'img002.jpg' not in resp.data


def test_search_excludes_inactive_items(mediabrowser_client, clean_media_db):
    insert_media_row(_row('img001', extra={'file_state': 'active'}))
    insert_media_row(_row('img002', extra={'file_state': 'archvd'}))
    resp = mediabrowser_client.get('/search')
    assert resp.status_code == 200
    assert b'img001.jpg' in resp.data
    assert b'img002.jpg' not in resp.data


def test_cart_starts_empty(mediabrowser_client, clean_media_db):
    resp = mediabrowser_client.get('/cart')
    assert resp.status_code == 200


def test_search_post_adds_to_cart_and_cart_shows_it(mediabrowser_client, clean_media_db):
    insert_media_row(_row('img001'))

    post_resp = mediabrowser_client.post('/search', data={
        'db_table': 'media_proj',
        'selected': ['img001'],
    })
    assert post_resp.status_code == 200

    cart_resp = mediabrowser_client.get('/cart')
    assert cart_resp.status_code == 200
    assert b'img001.jpg' in cart_resp.data


def test_clear_cart_empties_it(mediabrowser_client, clean_media_db):
    insert_media_row(_row('img001'))
    mediabrowser_client.post('/search', data={'db_table': 'media_proj', 'selected': ['img001']})

    mediabrowser_client.get('/clear_cart?db_table=media_proj')

    cart_resp = mediabrowser_client.get('/cart')
    assert b'img001.jpg' not in cart_resp.data
