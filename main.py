import sqlite3
import os
import math
from flask import Flask, render_template, request, url_for, abort

depot_local = os.getenv('DEPOT_ALL')
#path_base_photo = os.path.join(depot_local, 'assetdepot', 'photo', 'people', 'ig')
path_base_photo = os.path.join(depot_local, 'assetdepot', 'photo')

PER_PAGE = 10  # Number of items per page for pagination

app = Flask(__name__, static_folder=path_base_photo)

def get_db_connection():
    # Connects to the database and sets row_factory to sqlite3.Row 
    # to access columns by name (like a dictionary)
    depot_local = os.getenv('DEPOT_ALL')
    path_base_photo = os.path.join(depot_local,'assetdepot', 'photo')
    path_db_photo = os.path.join(path_base_photo, 'db') 
    file_media_sqlite = 'db_media.sqlite3'
    path_db_media = os.path.join(path_db_photo, file_media_sqlite)
    conn = sqlite3.connect(path_db_media)
    conn.row_factory = sqlite3.Row 
    return conn

@app.route('/')
@app.route('/index')
def index():
    conn = get_db_connection()
    # Execute the query and fetch all results

    '''
    Note that the database schema for 'photos' table is as follows:
        dict_media = {
        'file' : '',
        'path' : '',
        'medium': '',
        'format': [],
        'resolution': [],
        'genre' : [],
        'category' : [],
        'shot_size' : [],
        'shot_type' : [],
        'lighting' : [],
        'setting' : [],
        'people' : [],
        'social_id': [],
        'tags' : [],
        'caption' : [],
    }
    '''
    #photos = conn.execute('SELECT * FROM photos').fetchall()
    ig_name = 'snohaalegra'
    #sql = 'SELECT * FROM photos WHERE social_id = ?'
    #photos = conn.execute(sql, (ig_name,)).fetchall()
    #conn.close()

    '''
    # we need to do some processing to expand the $DEPOT_ALL variable in the path
    photos_abs = []
    for photo in photos:
        photo_dict = dict(photo)
        photo_path = photo_dict['path']
        if photo_path.startswith('$DEPOT_ALL'):
            photo_path = photo_path.replace('$DEPOT_ALL', depot_local)
        photo_dict['absolute_path'] = photo_path
        photos_abs.append(photo_dict)
    '''

    # 1. Determine the current page number
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        # If the page parameter is not a valid integer, return a 404
        abort(404)

    # Calculate OFFSET: how many records to skip
    offset = (page - 1) * PER_PAGE
    
    # 2. Query the database using LIMIT and OFFSET
    # We fetch only 10 rows starting from the calculated offset

    ig_name = 'snohaalegra'
    sql0 = 'SELECT COUNT(*) FROM photos WHERE social_id = ?' 
    sql = 'SELECT * FROM photos WHERE social_id = ? ORDER BY id ASC LIMIT ? OFFSET ?' 

    photos = conn.execute(
        sql, (ig_name, PER_PAGE, offset)
    ).fetchall()

    # 3. Calculate total pages for navigation links
    # Get total count of all records
    #total_photos_count = conn.execute('SELECT COUNT(*) FROM photos').fetchone()[0]
    #photos = conn.execute(sql, (ig_name,)).fetchall()
    total_photos_count = conn.execute(sql0, (ig_name,)).fetchone()[0]
    conn.close()

    # Calculate total number of pages needed (ceiling division)
    total_pages = math.ceil(total_photos_count / PER_PAGE)

    # Ensure the user isn't trying to access a page that doesn't exist
    if page > total_pages > 0 or page < 1:
         abort(404)

    return render_template(
        'index.html', 
        photos=photos,
        page=page,
        total_pages=total_pages
    )

    # Pass the query results to the template
    return render_template('index.html', photos=photos)

if __name__ == '__main__':
    app.run(debug=True)
