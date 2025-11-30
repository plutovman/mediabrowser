import sqlite3
import os
from flask import Flask, render_template

depot_local = os.getenv('DEPOT_ALL')
#path_base_photo = os.path.join(depot_local, 'assetdepot', 'photo', 'people', 'ig')
path_base_photo = os.path.join(depot_local, 'assetdepot', 'photo')
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
    sql = 'SELECT * FROM photos WHERE social_id = ?'
    photos = conn.execute(sql, (ig_name,)).fetchall()
    conn.close()

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
    
    # Pass the query results to the template
    return render_template('index.html', photos=photos)

if __name__ == '__main__':
    app.run(debug=True)
