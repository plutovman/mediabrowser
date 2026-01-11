import sqlite3, os, math, webbrowser
from flask import Flask, render_template, request, url_for, abort, session, redirect, send_file, jsonify
import zipfile
from datetime import datetime
import io, zipfile, time
import shutil
import random
import cv2
from PIL import Image
import socket
from threading import Timer


try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

depot_local = os.getenv('DEPOT_ALL')
#path_base_media = os.path.join(depot_local, 'assetdepot', 'media', 'people', 'ig')
path_base_media = os.path.join(depot_local, 'assetdepot', 'media')
path_base_thumbs = os.path.join(path_base_media, 'dummy', 'thumbnails')
path_base_archive = os.path.join(path_base_media, 'archive')

#PER_PAGE = 10  # Number of items per page for pagination
CNT_ITEMS_VIEW_TABLE = 100  # Number of rows per page for table view
CNT_ITEMS_VIEW_GRID = 30  # Number of items per page for grid view
CNT_TOP_TOPICS = 20  # Number of top topics to display in word cloud`

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

list_db_tables = ['media']
#list_file_types = ['mp4', 'jpg', 'psd', 'prproj','docx', 'xlsx', 'pptx', 'hip', 'nk', 'obj', 'other0', 'other1', 'other2', 'other3', 'other4']
list_file_types = ['mp4', 'jpg', 'psd', 'prproj','docx', 'xlsx', 'pptx', 'hip', 'nk', 'obj']
#list_genres = ['action', 'adventure', 'comedy', 'drama', 'fantasy', 'horror', 'mystery', 'romance', 'sci-fi', 'thriller']
list_genres = ['noir', 'modern', 'vintage', 'abstract', 'realism', 'fantasy', 'sci-fi']

file_logo_sqr = 'foxlito.png'
path_logo_sqr = os.path.join(path_base_media, 'dummy', 'thumbnails', file_logo_sqr)

def enrich_media_paths(item):
    
    """Enrich media item with absolute/relative paths and thumbnail paths for Flask serving"""
    
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

def db_get_connection():
    
    """Connect to SQLite database and return connection with row factory enabled"""
    
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

def db_item_add_from_dict(item_dict: dict, db_table: str = 'media'):
    """
    Adds a new media item to the database from a dictionary.
    
    Args:
        item_dict: Dictionary containing media item fields
        db_table: Database table name (default: 'media')
    """
    # Validate table name
    if db_table not in list_db_tables:
        db_table = 'media'
    
    conn = db_get_connection()
    columns = ', '.join(item_dict.keys())
    placeholders = ', '.join('?' for _ in item_dict)
    sql = f'INSERT INTO {db_table} ({columns}) VALUES ({placeholders})'
    conn.execute(sql, tuple(item_dict.values()))
    conn.commit()
    conn.close()

def category_get_dict(category: str, top_n: int, db_table: str = 'media') -> dict:
    """
    Returns a dictionary of {category_value: count} for the top N occurrences.
    
    Args:
        category: Column name to query (e.g., 'genre', 'subject', 'tags')
        top_n: Number of top results to return
        db_table: Database table name (default: 'media')
        
    Returns:
        Dictionary mapping category values to their counts
        Example: {'space': 10, 'air': 7}
    """
    conn = db_get_connection()
    
    # Validate category to prevent SQL injection
    allowed_categories = ['file_type', 'genre', 'subject', 'category', 'lighting', 'setting', 'tags']
    if category not in allowed_categories:
        conn.close()
        return {}
    
    # Validate table name to prevent SQL injection
    if db_table not in list_db_tables:
        conn.close()
        return {}
    
    # Query to count occurrences of each value in the specified category
    query = f'''
        SELECT {category}, COUNT(*) as count 
        FROM {db_table} 
        WHERE {category} IS NOT NULL AND {category} != ''
        GROUP BY {category}
        ORDER BY count DESC
        LIMIT ?
    '''
    
    results = conn.execute(query, (top_n,)).fetchall()
    conn.close()
    
    # Convert to dictionary
    category_dict = {row[category]: row['count'] for row in results}
    
    return category_dict

def git_get_info():
    """
    Extracts the latest commit information from the Git repository.
    
    Returns:
        dict: Dictionary containing commit hash, date, and message
        Example: {'hash': 'abc123', 'date': '2026-01-01 10:30:00', 'message': 'Initial commit'}
        Returns None if Git is not available or repo not found
    """
    if not GIT_AVAILABLE:
        return None
    
    try:
        # Get the repository root (current directory or parent directories)
        repo = git.Repo(search_parent_directories=True)
        
        # Get the latest commit
        latest_commit = repo.head.commit
        
        # Extract commit information
        commit_info = {
            'hash': latest_commit.hexsha[:7],  # Short hash (first 7 characters)
            'date': datetime.fromtimestamp(latest_commit.committed_date).strftime('%Y-%m-%d %H:%M:%S'),
            'message': latest_commit.message.strip().split('\n')[0]  # First line of commit message
        }
        
        return commit_info
    except (git.InvalidGitRepositoryError, git.GitCommandError):
        # Not a git repository or git command failed
        return None

# ============================================================================
# Flask routines for media browser
# ============================================================================
@app.route('/')
@app.route('/index')
def page_index():
    
    """Render homepage with random media item, word clouds, and search stats"""
    
    # Get db_table parameter (default to 'media')
    db_table = request.args.get('db_table', 'media')
    if db_table not in list_db_tables:
        db_table = 'media'
    
    conn = db_get_connection()

    # Fetch random image for homepage
    random_media = conn.execute(f'SELECT * FROM {db_table} ORDER BY RANDOM() LIMIT 1').fetchone()
    random_image = enrich_media_paths(random_media) if random_media else None

    conn.close()
    
    # Logo relative path for template
    logo_relative = os.path.relpath(path_logo_sqr, path_base_media)
    
    # Get top 20 subjects and genres for word cloud
    top_subjects = category_get_dict('subject', CNT_TOP_TOPICS, db_table)
    top_genres = category_get_dict('genre', CNT_TOP_TOPICS, db_table)
    
    # Get git commit info
    git_info = git_get_info()

    return render_template('index.html', random_image=random_image, logo_path=logo_relative,
                          top_subjects=top_subjects, top_genres=top_genres, 
                          db_tables=list_db_tables, db_table=db_table,
                          file_types=list_file_types, genres=list_genres, top_topics=CNT_TOP_TOPICS,
                          git_info=git_info)

@app.route('/search', methods=['GET', 'POST'])
def page_search():
    
    """Search and filter media with pagination. POST adds items to cart, GET displays results"""
    
    # Get search parameters (from form if POST, else from args)
    search_query = request.form.get('query') or request.args.get('query', '')
    file_type_filter = request.form.get('file_type') or request.args.get('file_type', '')
    genre_filter = request.form.get('genre') or request.args.get('genre', '')
    db_table = request.form.get('db_table') or request.args.get('db_table', 'media')
    view = request.form.get('view') or request.args.get('view', 'grid')
    page_str = request.form.get('page') or request.args.get('page', '1')
    
    # Validate db_table
    if db_table not in list_db_tables:
        db_table = 'media'
    
    try:
        page = int(page_str)
    except ValueError:
        abort(404)

    # Dynamic PER_PAGE based on view
    CNT_ITEMS_PER_PAGE = {'table': CNT_ITEMS_VIEW_TABLE, 'grid': CNT_ITEMS_VIEW_GRID}.get(view, 10)
    offset = (page - 1) * CNT_ITEMS_PER_PAGE

    if request.method == 'POST':
        selected = request.form.getlist('selected')
        if 'cart' not in session:
            session['cart'] = []
        session['cart'].extend(selected)
        session['cart'] = list(set(session['cart']))  # unique

    conn = db_get_connection()

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
        
        sql_query = f'SELECT * FROM {db_table} WHERE {where_clause} ORDER BY file_id ASC LIMIT ? OFFSET ?'
        params.extend([CNT_ITEMS_PER_PAGE, offset])
        
        count_sql = f'SELECT COUNT(*) FROM {db_table} WHERE {where_clause}'
        count_params = params[:]
        count_params = count_params[:-(2)]  # Remove LIMIT and OFFSET params
        
        media = conn.execute(sql_query, params).fetchall()
        total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
        total_pages = math.ceil(total_media_count / CNT_ITEMS_PER_PAGE)
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
        sql_query = f'SELECT * FROM {db_table} WHERE {where_clause} ORDER BY file_id ASC LIMIT ? OFFSET ?'
        params.extend([CNT_ITEMS_PER_PAGE, offset])
        count_sql = f'SELECT COUNT(*) FROM {db_table} WHERE {where_clause}'
        count_params = params[:-2]  # Exclude LIMIT and OFFSET
        media = conn.execute(sql_query, params).fetchall()
        total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
        total_pages = math.ceil(total_media_count / CNT_ITEMS_PER_PAGE)
    else:
        # Default: show all
        sql_query = f'SELECT * FROM {db_table} ORDER BY file_id ASC LIMIT ? OFFSET ?'
        params = (CNT_ITEMS_PER_PAGE, offset)
        count_sql = f'SELECT COUNT(*) FROM {db_table}'
        count_params = ()
        media = conn.execute(sql_query, params).fetchall()
        total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
        total_pages = math.ceil(total_media_count / CNT_ITEMS_PER_PAGE)

    # Process media to compute relative paths for static serving
    media_list = [enrich_media_paths(item) for item in media]

    conn.close()

    if total_pages > 0 and (page > total_pages or page < 1):
        abort(404)
    
    # Logo relative path for template
    logo_relative = os.path.relpath(path_logo_sqr, path_base_media)
    
    # Get git commit info
    git_info = git_get_info()

    return render_template(
        'search.html', 
        media=media_list,
        page=page,
        total_pages=total_pages,
        total_media_count=total_media_count,
        search_query=search_query,
        file_type_filter=file_type_filter,
        genre_filter=genre_filter,
        db_table=db_table,
        file_types=list_file_types,
        genres=list_genres,
        db_tables=list_db_tables,
        view=view,
        random_image=None,
        logo_path=logo_relative,
        git_info=git_info
    )

@app.route('/cart')
def page_cart():
    
    """Display cart page with selected media items from session"""
    
    # Store referrer URL for back navigation
    referrer = request.referrer
    if referrer and '/search' in referrer:
        session['last_search_url'] = referrer
    
    cart_ids = session.get('cart', [])
    media_list = []
    if cart_ids:
        placeholders = ','.join('?' for _ in cart_ids)
        #query = f'SELECT * FROM media WHERE file_name IN ({placeholders})'
        query = f'SELECT * FROM media WHERE file_id IN ({placeholders})'
        conn = db_get_connection()
        media = conn.execute(query, cart_ids).fetchall()
        for item in media:
            media_list.append(enrich_media_paths(item))
        conn.close()
    
    # Logo relative path for template
    logo_relative = os.path.relpath(path_logo_sqr, path_base_media)
    
    # Get back URL - default to search page if no previous search
    back_url = session.get('last_search_url', url_for('page_search'))
    
    # Get git commit info
    git_info = git_get_info()
    
    return render_template('cart.html', media=media_list, logo_path=logo_relative, back_url=back_url, git_info=git_info)

@app.route('/clear_cart')
def cart_clear():
    
    """Clear all items from cart session and redirect to cart page"""
    
    session.pop('cart', None)
    return redirect(url_for('page_cart'))

@app.route('/download_cart', methods=['POST'])
def cart_download():
    
    """Create and download a ZIP file of selected cart items"""
    
    selected_ids = request.form.getlist('selected')
    
    if not selected_ids:
        return redirect(url_for('page_cart'))
    
    # Get file paths from database
    placeholders = ','.join('?' for _ in selected_ids)
    query = f'SELECT * FROM media WHERE file_id IN ({placeholders})'
    conn = db_get_connection()
    media = conn.execute(query, selected_ids).fetchall()
    conn.close()
    
    if not media:
        return redirect(url_for('page_cart'))
    
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
        return redirect(url_for('page_cart'))
    
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
def cart_items_update():
    
    """Update metadata fields for cart items (requires password authentication)"""
    
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
    
    conn = db_get_connection()
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

@app.route('/prune_cart_items', methods=['POST'])
def cart_items_prune():
    
    """Delete items from database by file_id (requires password authentication)"""
    
    data = request.get_json()
    file_ids = data.get('file_ids', [])
    provided_password = data.get('password', '')
    
    # Check password
    correct_password = os.getenv('MEDIA_SQLITE_KEY')
    if not correct_password:
        return {'success': False, 'error': 'Database password not configured on server'}
    
    if provided_password != correct_password:
        return {'success': False, 'error': 'Incorrect password'}
    
    if not file_ids:
        return {'success': False, 'error': 'No items selected'}
    
    conn = db_get_connection()
    deleted_count = 0
    
    try:
        for file_id in file_ids:
            sql = 'DELETE FROM media WHERE file_id = ?'
            conn.execute(sql, (file_id,))
            deleted_count += 1
            
            # Remove from session cart if present
            if 'cart' in session and file_id in session['cart']:
                session['cart'].remove(file_id)
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'deleted': deleted_count}
    except Exception as e:
        conn.close()
        return {'success': False, 'error': str(e)}

# ============================================================================
# MEDIA ARCHIVE ROUTES - Flask-based media processing workflow
# ============================================================================

@app.route('/archive')
def page_archive():
    
    """Media archive interface for adding files to database"""
    
    # Get db_table parameter (default to 'media')
    db_table = request.args.get('db_table', 'media')
    if db_table not in list_db_tables:
        db_table = 'media'
    
    # Store in session for use in submit
    session['target_db_table'] = db_table
    
    # Get processing queue from session
    queue = session.get('processing_queue', [])
    current_index = session.get('current_index', 0)
    
    # Initialize processed files cache if not exists
    if 'processed_files' not in session:
        session['processed_files'] = {}
    
    current_item = queue[current_index] if queue and current_index < len(queue) else None
    
    # Logo relative path
    logo_relative = os.path.relpath(path_logo_sqr, path_base_media)
    
    # Get git commit info
    git_info = git_get_info()
    
    return render_template('archive.html',
                          queue=queue,
                          current_item=current_item,
                          current_index=current_index,
                          total_items=len(queue),
                          file_types=list_file_types,
                          genres=list_genres,
                          logo_path=logo_relative,
                          path_base_media=path_base_media,
                          db_table=db_table,
                          db_tables=list_db_tables,
                          processed_files=session.get('processed_files', {}),
                          git_info=git_info)

@app.route('/api/archive/upload_files', methods=['POST'])
def api_archive_upload_files():
    
    """Upload files to archive folder and add to processing queue"""
    
    try:
        uploaded_files = request.files.getlist('files')
        
        if not uploaded_files:
            return jsonify({'success': False, 'error': 'No files uploaded'})
        
        # Ensure archive directory exists
        os.makedirs(path_base_archive, exist_ok=True)
        
        # Initialize or get existing queue
        queue = session.get('processing_queue', [])
        copied_files = []
        
        # Save uploaded files to archive
        for file in uploaded_files:
            if file.filename == '':
                continue
            
            file_name = file.filename
            dest_path = os.path.join(path_base_archive, file_name)
            
            # Handle duplicate filenames
            if os.path.exists(dest_path):
                base, ext = os.path.splitext(file_name)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(path_base_archive, f"{base}_{counter}{ext}")
                    counter += 1
            
            # Save uploaded file
            file.save(dest_path)
            
            # Add to queue
            if dest_path not in queue:
                queue.append(dest_path)
                copied_files.append(dest_path)
        
        session['processing_queue'] = queue
        session['current_index'] = 0
        
        return jsonify({
            'success': True, 
            'count': len(queue),
            'copied': len(copied_files)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/archive/get_processed', methods=['POST'])
def api_archive_get_processed():
    
    """Get cached processed file data if exists"""
    
    try:
        file_path = request.json.get('file_path')
        processed_files = session.get('processed_files', {})
        
        if file_path in processed_files:
            return jsonify({'success': True, 'data': processed_files[file_path], 'cached': True})
        else:
            return jsonify({'success': True, 'cached': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/archive/save_processed', methods=['POST'])
def api_archive_save_processed():
    
    """Save processed file data to session"""
    
    try:
        file_path = request.json.get('file_path')
        data = request.json.get('data')
        
        if 'processed_files' not in session:
            session['processed_files'] = {}
        
        session['processed_files'][file_path] = data
        session.modified = True
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/archive/extract_metadata', methods=['POST'])
def api_archive_extract_metadata():
    
    """Extract metadata from media file"""
    
    try:
        file_path = request.json.get('file_path')
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'File not found'})
        
        # Extract metadata
        metadata = extract_media_metadata(file_path)
        
        # Get file info
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lstrip('.')
        
        metadata['file_name'] = file_name
        metadata['file_type'] = file_ext.lower()
        metadata['source_path'] = file_path
        
        return jsonify({'success': True, 'metadata': metadata})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/archive/copy_file', methods=['POST'])
def api_archive_copy_file():
    
    """Copy file to repository with progress tracking"""
    
    try:
        data = request.json
        source_path = data.get('source_path')
        file_type = data.get('file_type')
        
        # Determine destination folder
        if file_type in ['mp4', 'mov', 'avi', 'mkv']:
            dest_folder = os.path.join(path_base_media, 'videos')
        elif file_type in ['jpg', 'jpeg', 'png', 'psd']:
            dest_folder = os.path.join(path_base_media, 'images')
        else:
            dest_folder = os.path.join(path_base_media, 'other')
        
        os.makedirs(dest_folder, exist_ok=True)
        
        # Generate destination path
        file_name = os.path.basename(source_path)
        dest_path = os.path.join(dest_folder, file_name)
        
        # Check if file already exists
        if os.path.exists(dest_path):
            base, ext = os.path.splitext(file_name)
            counter = 1
            while os.path.exists(dest_path):
                dest_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
                counter += 1
        
        # Copy file
        copy_id = f"copy_{int(time.time()*1000)}"
        session[f'copy_progress_{copy_id}'] = {'percent': 0, 'status': 'copying'}
        
        # Perform copy in chunks for progress tracking
        total_size = os.path.getsize(source_path)
        copied = 0
        
        with open(source_path, 'rb') as src, open(dest_path, 'wb') as dst:
            while True:
                chunk = src.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                dst.write(chunk)
                copied += len(chunk)
                percent = int((copied / total_size) * 100)
                session[f'copy_progress_{copy_id}'] = {'percent': percent, 'status': 'copying'}
        
        session[f'copy_progress_{copy_id}'] = {'percent': 100, 'status': 'complete'}
        
        # Convert to $DEPOT_ALL format
        rel_path = dest_path.replace(depot_local, '$DEPOT_ALL')
        
        # Auto-generate thumbnail for video files
        if file_type in ['mp4', 'mov', 'avi', 'mkv']:
            try:
                # Generate thumbnail at 1 second mark (or 25% through video)
                cap = cv2.VideoCapture(dest_path)
                if cap.isOpened():
                    # Try 1 second in, or 25% if video is shorter than 4 seconds
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    if fps > 0:
                        duration = frame_count / fps
                        seek_time = 1.0 if duration > 4 else duration * 0.25
                        cap.set(cv2.CAP_PROP_POS_MSEC, seek_time * 1000)
                    
                    ret, frame = cap.read()
                    cap.release()
                    
                    if ret:
                        # Save thumbnail in same directory as video
                        base_name = os.path.splitext(os.path.basename(dest_path))[0]
                        thumb_path = os.path.join(dest_folder, f"{base_name}.jpg")
                        cv2.imwrite(thumb_path, frame)
            except Exception as e:
                # Don't fail the copy operation if thumbnail generation fails
                print(f"Warning: Could not auto-generate thumbnail: {e}")
        
        # Cache the destination path for this source file
        source_path = data.get('source_path')
        if 'file_copy_cache' not in session:
            session['file_copy_cache'] = {}
        session['file_copy_cache'][source_path] = dest_path
        session.modified = True
        
        return jsonify({'success': True, 'dest_path': rel_path, 'copy_id': copy_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/archive/copy_progress/<copy_id>')
def api_archive_copy_progress(copy_id):
    
    """Get file copy progress"""
    
    progress = session.get(f'copy_progress_{copy_id}', {'percent': 0, 'status': 'unknown'})
    return jsonify(progress)

@app.route('/api/archive/generate_thumbnails', methods=['POST'])
def api_archive_generate_thumbnails():
    
    """Generate a single thumbnail at the current playhead position"""
    
    try:
        file_path = request.json.get('file_path')
        current_time = request.json.get('current_time', 0)  # Current playhead position in seconds
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': 'File not found'})
        
        # Generate thumbnail at current position
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return jsonify({'success': False, 'error': 'Could not open video file'})
        
        # Seek to current time
        cap.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return jsonify({'success': False, 'error': 'Could not capture frame'})
        
        # Save thumbnail in videos directory
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        dest_folder = os.path.join(path_base_media, 'videos')
        os.makedirs(dest_folder, exist_ok=True)
        thumb_path = os.path.join(dest_folder, f"{base_name}.jpg")
        
        # Write thumbnail
        cv2.imwrite(thumb_path, frame)
        
        return jsonify({'success': True, 'thumbnail': thumb_path, 'time': current_time})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/archive/submit', methods=['POST'])
def api_archive_submit():
    
    """Submit metadata to database"""
    
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['file_id', 'file_name', 'file_path', 'file_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'Missing required field: {field}'})
        
        # Get target table from session
        db_table = session.get('target_db_table', 'media')
        
        # Insert into database
        db_item_add_from_dict(data, db_table)
        
        # Move to next item in queue
        current_index = session.get('current_index', 0)
        session['current_index'] = current_index + 1
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/archive/clear_queue', methods=['POST'])
def api_archive_clear_queue():
    
    """Clear processing queue and reset session cache"""
    
    session.pop('processing_queue', None)
    session.pop('processed_files', None)
    session.pop('file_copy_cache', None)
    session['current_index'] = 0
    return jsonify({'success': True})

@app.route('/api/archive/update_queue', methods=['POST'])
def api_archive_update_queue():
    
    """Update processing queue for skip/remove operations"""
    
    try:
        queue = request.json.get('queue', [])
        session['processing_queue'] = queue
        session.modified = True
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/archive/serve_file')
def api_archive_serve_file():
    
    """Serve file for preview from any filesystem location"""
    
    try:
        file_path = request.args.get('path', '')
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        # Security check - ensure file is readable
        if not os.path.isfile(file_path):
            return jsonify({'error': 'Not a file'}), 400
        
        return send_file(file_path)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Helper functions for media archive
def extract_media_metadata(file_path):
    
    """Extract resolution and duration metadata from video files using OpenCV"""
    
    metadata = {}
    file_ext = os.path.splitext(file_path)[1].lstrip('.').lower()
    
    try:
        if file_ext in ['mp4', 'mov', 'avi', 'mkv']:
            # Extract video metadata
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                metadata['file_resolution'] = f"{width}x{height}"
                
                # Calculate duration in seconds
                if fps > 0:
                    duration_seconds = frame_count / fps
                    # Format as MM:SS or HH:MM:SS
                    hours = int(duration_seconds // 3600)
                    minutes = int((duration_seconds % 3600) // 60)
                    seconds = int(duration_seconds % 60)
                    if hours > 0:
                        metadata['file_duration'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    else:
                        metadata['file_duration'] = f"{minutes:02d}:{seconds:02d}"
                
                cap.release()
    except Exception as e:  
        print(f"Error extracting video metadata: {e}")

    return metadata

def generate_video_thumbnails(video_path, intervals=4):
    
    """Generate video thumbnails at equal intervals (default: 25%, 50%, 75%, 100%)"""
    
    thumbnails = []
    
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return thumbnails
        
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Generate thumbnail directory path
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        thumb_dir = os.path.join(path_base_thumbs, 'video_previews')
        os.makedirs(thumb_dir, exist_ok=True)
        
        # Generate thumbnails at 25%, 50%, 75%, 100% positions
        for i in range(1, intervals + 1):
            frame_pos = int((frame_count * i) / intervals) - 1
            frame_pos = max(0, min(frame_pos, frame_count - 1))
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
            ret, frame = cap.read()
            
            if ret:
                thumb_path = os.path.join(thumb_dir, f"{base_name}_{i*25}pct.jpg")
                cv2.imwrite(thumb_path, frame)
                thumbnails.append(thumb_path)
        
        cap.release()
    
    except Exception as e:
        print(f"Error generating thumbnails: {e}")
    
    return thumbnails

def open_browser(url):
    
    """Open a URL in the default web browser, with WSL support"""
    
    try:
        # Check if running in WSL (Windows Subsystem for Linux)
        is_wsl = 'microsoft' in os.uname().release.lower() or 'wsl' in os.uname().release.lower()
        
        if is_wsl:
            # Use Windows command to open browser from WSL
            import subprocess
            subprocess.run(['cmd.exe', '/c', 'start', url], check=False)
        else:
            # Use standard webbrowser module for native environments
            webbrowser.open(url)
    except Exception as e:
        print(f"Error opening browser: {e}")

def is_port_available(host, port):
    
    """Check if a port is available on the given host"""
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False

def find_available_port(host='127.0.0.1', start_port=5000, max_attempts=10):
    
    """Find next available port by checking sequential ports from start_port"""
    
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(host, port):
            return port
    return None

def main(debug=True, host='127.0.0.1', port=5000, open_browser_on_start=True):
    """
    Main entry point for the MediaBrowser application.
    
    Args:
        debug (bool): Enable Flask debug mode. Default is True.
        host (str): Host to bind to. Default is '127.0.0.1' (accessible from WSL/Windows).
        port (int): Port to bind to. Default is 5000.
        open_browser_on_start (bool): Automatically open browser. Default is True.
    """
    # Find an available port if the requested one is in use
    if not is_port_available(host, port):
        print(f"Port {port} is already in use, searching for available port...")
        available_port = find_available_port(host, port, max_attempts=10)
        if available_port:
            port = available_port
            print(f"Using port {port} instead")
        else:
            print(f"Could not find an available port in range {port}-{port+9}")
            return
    
    # Build the URL for browser (0.0.0.0 is not browsable, use 127.0.0.1)
    browser_host = '127.0.0.1' if host == '0.0.0.0' else host
    url = f"http://{browser_host}:{port}"
    print(f"Starting MediaBrowser at {url}")
    
    # Open browser after a delay to allow Flask to start
    # In debug mode, Flask uses a reloader that starts twice, so we need a longer delay
    if open_browser_on_start:
        delay = 3.0 if debug else 1.5
        Timer(delay, lambda: open_browser(url)).start()
    
    app.run(debug=debug, host=host, port=port, use_reloader=False)

if __name__ == '__main__':
    main()
