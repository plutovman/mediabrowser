import sqlite3
import os
import math
from flask import Flask, render_template, request, url_for, abort, session, redirect, send_file
import re
import zipfile
from datetime import datetime
import io

depot_local = os.getenv('DEPOT_ALL')
#path_base_media = os.path.join(depot_local, 'assetdepot', 'media', 'people', 'ig')
path_base_media = os.path.join(depot_local, 'assetdepot', 'media')
path_base_thumbs = os.path.join(path_base_media, 'dummy', 'thumbnails')

PER_PAGE = 10  # Number of items per page for pagination

app = Flask(__name__, static_folder=path_base_media)
app.secret_key = 'your_secret_key_here'  # Set secret key for sessions

dict_thumbs = {
    "afx": "adobe_afx.png",
    "prproj": "adobe_prm.png",
    "psd": "adobe_psd.png",
    "xlsx": "ms_excel.png",
    "pptx": "ms_ppt.png",
    "docx": "ms_word.png",
    "hip": "sidefx_hou.png",
    "other": "thumb_generic.png"
}
list_file_types = ['mp4', 'jpg', 'psd', 'prproj','docx', 'xlsx', 'pptx', 'hip', 'nk', 'obj', 'other0', 'other1', 'other2', 'other3', 'other4']
#list_genres = ['action', 'adventure', 'comedy', 'drama', 'fantasy', 'horror', 'mystery', 'romance', 'sci-fi', 'thriller']
list_genres = ['noir', 'modern', 'vintage', 'abstract', 'realism', 'fantasy', 'sci-fi']

file_logo_sqr = 'foxlito.png'
path_logo_sqr = os.path.join(path_base_media, 'dummy', 'thumbnails', file_logo_sqr)

def enrich_media_paths(item):
    item_dict = dict(item)
    full_path = item_dict['file_path']
    if full_path.startswith('$DEPOT_ALL'):
        full_path = full_path.replace('$DEPOT_ALL', depot_local)
    item_dict['absolute_path'] = full_path
    relative_path = os.path.relpath(full_path, path_base_media)
    thumbs_other_relative_path  = os.path.relpath(path_base_thumbs, path_base_media)
    item_dict['relative_path'] = relative_path

    ext_is_matched = False
    ext_is_viewable = False
    thumb_relative_path = relative_path

    # logic for displaying thumbnails when loading mp4 files
    if item_dict.get('file_type', '').lower() == 'mp4':
        ext_is_matched = True
        ext_is_viewable = True
        base, _ = os.path.splitext(relative_path)
        # note that thumbnail generation can be achieved separately via ffmpeg
        # ffmpeg -ss 00:00:05 -i apod_2023_09_23_0.mp4 -frames:v 1 apod_2023_09_23_0.png
        for ext in ('.jpg', '.png'):
            candidate = base + ext
            if os.path.exists(os.path.join(path_base_media, candidate)):
                thumb_relative_path = candidate
                break
    # for 'jpg', 'jpeg', 'png' files, use the image itself as thumbnail
    elif item_dict.get('file_type', '').lower() in ['jpg', 'jpeg', 'png']:
        ext_is_matched = True
        ext_is_viewable = True
        thumb_relative_path = relative_path

    # for other file types, use predefined thumbnails
    else:
        for file_ext in dict_thumbs.keys():            
            if item_dict.get('file_type', '').lower() == file_ext:
                thumb_relative_path = os.path.join(thumbs_other_relative_path, dict_thumbs[file_ext])
                ext_is_matched = True
                break


    if not ext_is_matched:
        thumb_relative_path = os.path.join(thumbs_other_relative_path, dict_thumbs["other"])
        

    item_dict['thumbnail_relative_path'] = thumb_relative_path
    item_dict['ext_is_viewable'] = ext_is_viewable
    return item_dict

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
    #path_db_media = os.path.join(depot_local, 'assetdepot', 'db', 'sqlite', 'media') 
    path_db_media = os.path.join(depot_local, 'assetdepot', 'media', 'dummy', 'db') 
    #file_media_sqlite = 'db_media.sqlite3'
    file_media_sqlite = 'media_dummy.sqlite'
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
    random_image = enrich_media_paths(random_media) if random_media else None

    conn.close()
    
    # Logo relative path for template
    logo_relative = os.path.relpath(path_logo_sqr, path_base_media)

    return render_template('index.html', random_image=random_image, logo_path=logo_relative)

@app.route('/search', methods=['GET', 'POST'])
def search():
    # Get search parameters (from form if POST, else from args)
    search_query = request.form.get('query') or request.args.get('query', '')
    file_type_filter = request.form.get('file_type') or request.args.get('file_type', '')
    genre_filter = request.form.get('genre') or request.args.get('genre', '')
    view = request.form.get('view') or request.args.get('view', 'grid')
    page_str = request.form.get('page') or request.args.get('page', '1')
    try:
        page = int(page_str)
    except ValueError:
        abort(404)

    # Dynamic PER_PAGE based on view
    PER_PAGE_VIEW = {'table': 10, 'grid': 30}.get(view, 10)
    offset = (page - 1) * PER_PAGE_VIEW

    if request.method == 'POST':
        selected = request.form.getlist('selected')
        if 'cart' not in session:
            session['cart'] = []
        session['cart'].extend(selected)
        session['cart'] = list(set(session['cart']))  # unique

    conn = get_db_connection()

    # Build complex query searching across multiple fields
    if search_query:
        # Search across genre, category, subject, tags
        where_clause = "(genre LIKE ? OR category LIKE ? OR subject LIKE ? OR tags LIKE ?)"
        params = ['%' + search_query + '%'] * 4
        
        # Add file_type filter if selected
        if file_type_filter:
            where_clause += " AND file_type = ?"
            params.append(file_type_filter)
        
        # Add genre filter if selected
        if genre_filter:
            where_clause += " AND genre = ?"
            params.append(genre_filter)
        
        sql_query = f'SELECT * FROM media WHERE {where_clause} ORDER BY file_id ASC LIMIT ? OFFSET ?'
        params.extend([PER_PAGE_VIEW, offset])
        
        count_sql = f'SELECT COUNT(*) FROM media WHERE {where_clause}'
        count_params = params[:]
        count_params = count_params[:-(2)]  # Remove LIMIT and OFFSET params
        
        media = conn.execute(sql_query, params).fetchall()
        total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
        total_pages = math.ceil(total_media_count / PER_PAGE_VIEW)
    elif file_type_filter or genre_filter:
        # Filter by file_type and/or genre only
        where_conditions = []
        params = []
        
        if file_type_filter:
            where_conditions.append("file_type = ?")
            params.append(file_type_filter)
        
        if genre_filter:
            where_conditions.append("genre = ?")
            params.append(genre_filter)
        
        where_clause = " AND ".join(where_conditions)
        sql_query = f'SELECT * FROM media WHERE {where_clause} ORDER BY file_id ASC LIMIT ? OFFSET ?'
        params.extend([PER_PAGE_VIEW, offset])
        count_sql = f'SELECT COUNT(*) FROM media WHERE {where_clause}'
        count_params = params[:-2]  # Exclude LIMIT and OFFSET
        media = conn.execute(sql_query, params).fetchall()
        total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
        total_pages = math.ceil(total_media_count / PER_PAGE_VIEW)
    else:
        # Default: show all
        sql_query = 'SELECT * FROM media ORDER BY file_id ASC LIMIT ? OFFSET ?'
        params = (PER_PAGE_VIEW, offset)
        count_sql = 'SELECT COUNT(*) FROM media'
        count_params = ()
        media = conn.execute(sql_query, params).fetchall()
        total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
        total_pages = math.ceil(total_media_count / PER_PAGE_VIEW)

    # Process media to compute relative paths for static serving
    media_list = [enrich_media_paths(item) for item in media]

    conn.close()

    if total_pages > 0 and (page > total_pages or page < 1):
        abort(404)
    
    # Logo relative path for template
    logo_relative = os.path.relpath(path_logo_sqr, path_base_media)

    return render_template(
        'search.html', 
        media=media_list,
        page=page,
        total_pages=total_pages,
        search_query=search_query,
        file_type_filter=file_type_filter,
        genre_filter=genre_filter,
        file_types=list_file_types,
        genres=list_genres,
        view=view,
        random_image=None,
        logo_path=logo_relative
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
            media_list.append(enrich_media_paths(item))
        conn.close()
    
    # Logo relative path for template
    logo_relative = os.path.relpath(path_logo_sqr, path_base_media)
    
    return render_template('cart.html', media=media_list, logo_path=logo_relative)

@app.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('cart'))

@app.route('/download_cart', methods=['POST'])
def download_cart():
    selected_ids = request.form.getlist('selected')
    
    if not selected_ids:
        return redirect(url_for('cart'))
    
    # Get file paths from database
    placeholders = ','.join('?' for _ in selected_ids)
    query = f'SELECT * FROM media WHERE file_id IN ({placeholders})'
    conn = get_db_connection()
    media = conn.execute(query, selected_ids).fetchall()
    conn.close()
    
    if not media:
        return redirect(url_for('cart'))
    
    # Create zip file in memory
    memory_file = io.BytesIO()
    files_added = 0
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for item in media:
            item_dict = dict(item)
            full_path = item_dict['file_path']
            if full_path.startswith('$DEPOT_ALL'):
                full_path = full_path.replace('$DEPOT_ALL', depot_local)
            
            if os.path.exists(full_path):
                # Use just the filename in the zip
                arcname = os.path.basename(full_path)
                zf.write(full_path, arcname)
                files_added += 1
    
    if files_added == 0:
        return redirect(url_for('cart'))
    
    memory_file.seek(0)
    
    # Generate filename with current date
    today = datetime.now()
    zip_filename = f"media_{today.year:04d}_{today.month:02d}_{today.day:02d}.zip"
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    )

@app.route('/update_cart_items', methods=['POST'])
def update_cart_items():
    data = request.get_json()
    changes = data.get('changes', [])
    provided_password = data.get('password', '')
    
    # Check password
    correct_password = os.getenv('MEDIA_SQLITE_KEY')
    if not correct_password:
        return {'success': False, 'error': 'Database password not configured on server'}
    
    if provided_password != correct_password:
        return {'success': False, 'error': 'Incorrect password'}
    
    if not changes:
        return {'success': False, 'error': 'No changes provided'}
    
    # Validate fields
    allowed_fields = ['subject', 'genre', 'setting', 'captions', 'tags']
    
    conn = get_db_connection()
    updated_count = 0
    
    try:
        for change in changes:
            file_id = change.get('file_id')
            field = change.get('field')
            value = change.get('value', '')
            
            if field not in allowed_fields:
                continue
                
            sql = f'UPDATE media SET {field} = ? WHERE file_id = ?'
            conn.execute(sql, (value, file_id))
            updated_count += 1
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'updated': updated_count}
    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}

if __name__ == '__main__':
    app.run(debug=True)
