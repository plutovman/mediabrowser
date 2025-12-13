import sqlite3
import os
import math
from flask import Flask, render_template, request, url_for, abort
import re

depot_local = os.getenv('DEPOT_ALL')
#path_base_media = os.path.join(depot_local, 'assetdepot', 'media', 'people', 'ig')
path_base_media = os.path.join(depot_local, 'assetdepot', 'media')

PER_PAGE = 10  # Number of items per page for pagination

app = Flask(__name__, static_folder=path_base_media)

def get_db_connection():
    # Connects to the database and sets row_factory to sqlite3.Row 
    # to access columns by name (like a dictionary)
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

    # Execute the query and fetch all results

    '''
    Note that the database schema for 'media' table is as follows:
        dict_media = {
        'file_name' : '',
        'file_path' : '',
        'file_type': '',
        'file_format': '',
        'file_resolution': '',
        'file_duration': '',
        'shot_size' : '',
        'shot_type' : '',
        'source': '',
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

    # 1. Determine the current page number
    search_query = request.args.get('query', '')
    filter_type = request.args.get('filter', 'subject')
    # Sanitize filter_type
    allowed_filters = ['subject', 'captions', 'setting', 'lighting']
    if filter_type not in allowed_filters:
        filter_type = 'subject'
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        # If the page parameter is not a valid integer, return a 404
        abort(404)

    # Calculate OFFSET: how many records to skip
    offset = (page - 1) * PER_PAGE
    
    # 2. Query the database using LIMIT and OFFSET
    # We fetch only 10 rows starting from the calculated offset
    '''
    ig_name = 'snohaalegra'
    sql0 = 'SELECT COUNT(*) FROM media WHERE source_id = ?' 
    sql = 'SELECT * FROM media WHERE source_id = ? ORDER BY id ASC LIMIT ? OFFSET ?' 

    media = conn.execute(
        sql, (ig_name, PER_PAGE, offset)
    ).fetchall()
    '''

    #######################################
    # --- Dynamic SQL Query ---
    # We use a LIKE clause for partial matches in the selected field
    if filter_type == 'captions' and search_query:
        # Special handling for captions: check if query is in any sentence (case-insensitive)
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
        # The '%' signs are wildcards for the SQL LIKE operator
        sql_query = f'SELECT * FROM media WHERE {filter_type} LIKE ? ORDER BY id ASC LIMIT ? OFFSET ?'
        #sql_query_cnt = 'SELECT COUNT(*) FROM media WHERE source_id LIKE ?'
        # The parameters must be passed as a tuple
        params = ('%' + search_query + '%', PER_PAGE, offset)
        
        count_sql = f'SELECT COUNT(*) FROM media WHERE {filter_type} LIKE ?'
        count_params = ('%' + search_query + '%',)

    else:
        # Default query if no search term is present
        sql_query = 'SELECT * FROM media ORDER BY id ASC LIMIT ? OFFSET ?'
        params = (PER_PAGE, offset)
        
        count_sql = 'SELECT COUNT(*) FROM media'
        count_params = ()

    if not (filter_type == 'captions' and search_query):
        # Execute main query
        media = conn.execute(sql_query, params).fetchall()

        # 3. Calculate total pages for navigation links
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
        # Compute relative path from static folder
        relative_path = os.path.relpath(full_path, path_base_media)
        item_dict['relative_path'] = relative_path
        media_list.append(item_dict)

    #######################################

    # 3. Calculate total pages for navigation links
    # Get total count of all records
    conn.close()

    # Ensure the user isn't trying to access a page that doesn't exist
    #if page > total_pages > 0 or page < 1:
    if total_pages > 0 and (page > total_pages or page < 1):
         abort(404)

    return render_template(
        'index.html', 
        media=media_list,
        page=page,
        total_pages=total_pages,
        search_query=search_query,
        filter_type=filter_type,
        random_image=random_image
    )

    # Pass the query results to the template
    #return render_template('index.html', media=media)

if __name__ == '__main__':
    app.run(debug=True)
