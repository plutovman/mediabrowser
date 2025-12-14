import sqlite3
import os
import math
from flask import Flask, render_template, request, url_for, abort, session, redirect
import re

depot_local = os.getenv('DEPOT_ALL')
#path_base_media = os.path.join(depot_local, 'assetdepot', 'media', 'people', 'ig')
path_base_media = os.path.join(depot_local, 'assetdepot', 'media')

PER_PAGE = 10  # Number of items per page for pagination

app = Flask(__name__, static_folder=path_base_media)
app.secret_key = 'your_secret_key_here'  # Set secret key for sessions

def get_db_connection():
    # Connects to the database and sets row_factory to sqlite3.Row 
    # to access columns by name (like a dictionary)
    # note that db table has the following columns:
    '''
        dict_media = {
        'file_id' : '',
        'file_name' : '',
        'file_path' : '',
        'file_type': '',
        'file_format': '',
        'file_resolution': '',
        'file_duration': '',
        'shot_size' : '',
        'shot_type' : '',
        'source' : '',
        'source_id': '',
        'genre' : '',
        'subject' : '',
        'category' : '',
        'lighting' : '',
        'setting' : '',
        'tags' : '',
        'captions' : '',
    }
    '''
    depot_local = os.getenv('DEPOT_ALL')
    path_base_media = os.path.join(depot_local,'assetdepot', 'media')
    path_db_media = os.path.join(path_base_media, 'db') 
    file_media_sqlite = 'db_media.sqlite3'
    path_db_media = os.path.join(path_db_media, file_media_sqlite)
    conn = sqlite3.connect(path_db_media)
    conn.row_factory = sqlite3.Row 
    return conn

@app.route('/')
@app.route('/index')
def index():
    conn = get_db_connection()

    # Fetch random image for homepage
    random_media = conn.execute('SELECT * FROM media ORDER BY RANDOM() LIMIT 1').fetchone()
    random_image = None
    if random_media:
        random_dict = dict(random_media)
        full_path = random_dict['file_path']
        if full_path.startswith('$DEPOT_ALL'):
            full_path = full_path.replace('$DEPOT_ALL', depot_local)
        random_dict['absolute_path'] = full_path
        relative_path = os.path.relpath(full_path, path_base_media)
        random_dict['relative_path'] = relative_path
        random_image = random_dict

    conn.close()

    return render_template('index.html', random_image=random_image)

@app.route('/search', methods=['GET', 'POST'])
def search():
    # Get search parameters (from form if POST, else from args)
    search_query = request.form.get('query') or request.args.get('query', '')
    filter_type = request.form.get('filter') or request.args.get('filter', 'subject')
    page_str = request.form.get('page') or request.args.get('page', '1')
    try:
        page = int(page_str)
    except ValueError:
        abort(404)

    allowed_filters = ['subject', 'captions', 'setting', 'lighting']
    if filter_type not in allowed_filters:
        filter_type = 'subject'

    offset = (page - 1) * PER_PAGE

    if request.method == 'POST':
        selected = request.form.getlist('selected')
        if 'cart' not in session:
            session['cart'] = []
        session['cart'].extend(selected)
        session['cart'] = list(set(session['cart']))  # unique

    conn = get_db_connection()

    # Dynamic SQL Query
    if filter_type == 'captions' and search_query:
        all_media = conn.execute('SELECT * FROM media ORDER BY id ASC').fetchall()
        filtered = []
        for item in all_media:
            captions = item['captions'] or ''
            sentences = [s.strip() for s in captions.split('.') if s.strip()]
            for sentence in sentences:
                if re.search(r'\b' + re.escape(search_query) + r'\b', sentence, re.IGNORECASE):
                    filtered.append(item)
                    break
        total_media_count = len(filtered)
        start = (page - 1) * PER_PAGE
        end = start + PER_PAGE
        media = filtered[start:end]
        total_pages = math.ceil(total_media_count / PER_PAGE)
    elif search_query:
        sql_query = f'SELECT * FROM media WHERE {filter_type} LIKE ? ORDER BY id ASC LIMIT ? OFFSET ?'
        params = ('%' + search_query + '%', PER_PAGE, offset)
        count_sql = f'SELECT COUNT(*) FROM media WHERE {filter_type} LIKE ?'
        count_params = ('%' + search_query + '%',)
        media = conn.execute(sql_query, params).fetchall()
        total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
        total_pages = math.ceil(total_media_count / PER_PAGE)
    else:
        # Default: show all
        sql_query = 'SELECT * FROM media ORDER BY id ASC LIMIT ? OFFSET ?'
        params = (PER_PAGE, offset)
        count_sql = 'SELECT COUNT(*) FROM media'
        count_params = ()
        media = conn.execute(sql_query, params).fetchall()
        total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
        total_pages = math.ceil(total_media_count / PER_PAGE)

    # Process media to compute relative paths for static serving
    media_list = []
    for item in media:
        item_dict = dict(item)
        full_path = item_dict['file_path']
        if full_path.startswith('$DEPOT_ALL'):
            full_path = full_path.replace('$DEPOT_ALL', depot_local)
        item_dict['absolute_path'] = full_path
        relative_path = os.path.relpath(full_path, path_base_media)
        item_dict['relative_path'] = relative_path
        media_list.append(item_dict)

    conn.close()

    if total_pages > 0 and (page > total_pages or page < 1):
        abort(404)

    return render_template(
        'search.html', 
        media=media_list,
        page=page,
        total_pages=total_pages,
        search_query=search_query,
        filter_type=filter_type,
        random_image=None
    )

@app.route('/cart')
def cart():
    cart_ids = session.get('cart', [])
    media_list = []
    if cart_ids:
        placeholders = ','.join('?' for _ in cart_ids)
        #query = f'SELECT * FROM media WHERE file_name IN ({placeholders})'
        query = f'SELECT * FROM media WHERE file_id IN ({placeholders})'
        conn = get_db_connection()
        media = conn.execute(query, cart_ids).fetchall()
        for item in media:
            item_dict = dict(item)
            full_path = item_dict['file_path']
            if full_path.startswith('$DEPOT_ALL'):
                full_path = full_path.replace('$DEPOT_ALL', depot_local)
            item_dict['absolute_path'] = full_path
            relative_path = os.path.relpath(full_path, path_base_media)
            item_dict['relative_path'] = relative_path
            media_list.append(item_dict)
        conn.close()
    return render_template('cart.html', media=media_list)

@app.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('cart'))

if __name__ == '__main__':
    app.run(debug=True)
