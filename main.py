import sqlite3
import os
import math
from flask import Flask, render_template, request, url_for, abort

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
    # Execute the query and fetch all results

    '''
    Note that the database schema for 'media' table is as follows:
        dict_media = {
        'file' : '',
        'path' : '',
        'medium': '',
        'format': [],
        'resolution': [],
        'length': '',
        'genre' : [],
        'category' : [],
        'shot_size' : [],
        'shot_type' : [],
        'lighting' : [],
        'setting' : [],
        'people' : [],
        'source' : '',
        'source_id': [],
        'tags' : [],
        'captions' : [],
    }
    '''

    '''
    # we need to do some processing to expand the $DEPOT_ALL variable in the path
    media_abs = []
    for photo in media:
        photo_dict = dict(photo)
        photo_path = photo_dict['path']
        if photo_path.startswith('$DEPOT_ALL'):
            photo_path = photo_path.replace('$DEPOT_ALL', depot_local)
        photo_dict['absolute_path'] = photo_path
        media_abs.append(photo_dict)
    '''

    # 1. Determine the current page number
    search_query = request.args.get('query', '')
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
    # We use a LIKE clause for partial matches in the subject field
    if search_query:
        # The '%' signs are wildcards for the SQL LIKE operator
        sql_query = 'SELECT * FROM media WHERE source_id LIKE ? ORDER BY id ASC LIMIT ? OFFSET ?'
        #sql_query_cnt = 'SELECT COUNT(*) FROM media WHERE source_id LIKE ?'
        # The parameters must be passed as a tuple
        params = ('%' + search_query + '%', PER_PAGE, offset)
        
        count_sql = 'SELECT COUNT(*) FROM media WHERE source_id LIKE ?'
        count_params = ('%' + search_query + '%',)

    else:
        # Default query if no search term is present
        sql_query = 'SELECT * FROM media ORDER BY id ASC LIMIT ? OFFSET ?'
        params = (PER_PAGE, offset)
        
        count_sql = 'SELECT COUNT(*) FROM media'
        count_params = ()

    # Execute main query
    media = conn.execute(sql_query, params).fetchall()

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
    #total_media_count = conn.execute(sql0, (ig_name,)).fetchone()[0]
    total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
    conn.close()

    # Calculate total number of pages needed (ceiling division)
    total_pages = math.ceil(total_media_count / PER_PAGE)

    # Ensure the user isn't trying to access a page that doesn't exist
    #if page > total_pages > 0 or page < 1:
    if total_pages > 0 and (page > total_pages or page < 1):
         abort(404)

    return render_template(
        'index.html', 
        media=media_list,
        page=page,
        total_pages=total_pages,
        search_query=search_query # Pass the query back to the template
    )

    # Pass the query results to the template
    #return render_template('index.html', media=media)

if __name__ == '__main__':
    app.run(debug=True)
