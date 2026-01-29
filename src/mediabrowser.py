"""
MediaBrowser Routes Module
==========================
Contains all routes and functionality for search, archive, and cart operations.
This module provides register_mediabrowser_routes() which adds all mediabrowser
routes to a Flask app instance.

Routes provided:
- / (index): Homepage with random media and word clouds
- /search: Search and filter media with pagination
- /archive: Media archive interface for adding files to database
- /cart: Display and manage cart items
- /clear_cart: Clear cart items
- /download_cart: Download selected cart items as ZIP
- /update_cart_items: Update metadata for cart items
- /prune_cart_items: Delete items from database
- /api/archive/*: Archive API endpoints for file operations
"""

import sqlite3
import os
import math
import random
import cv2
import io
import zipfile
import time
import shutil
from datetime import datetime
from flask import render_template, request, url_for, abort, session, redirect, send_file, jsonify, flash, send_from_directory
from PIL import Image

try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

# ============================================================================
# CONFIGURATION & GLOBALS
# ============================================================================

depot_local = os.getenv('DEPOT_ALL')
if not depot_local:
    raise EnvironmentError("DEPOT_ALL environment variable must be set")

path_base_media = os.path.join(depot_local, 'assetdepot', 'media')
path_base_thumbs = os.path.join(path_base_media, 'dummy', 'thumbnails')
path_base_archive = os.path.join(path_base_media, 'archive')

path_db_media = os.path.join(depot_local, 'assetdepot', 'media', 'dummy', 'db')
file_media_sqlite = 'media_dummy.sqlite'
path_db_media = os.path.join(path_db_media, file_media_sqlite)

# Pagination settings
CNT_ITEMS_VIEW_TABLE = 100  # Number of rows per page for table view
CNT_ITEMS_VIEW_GRID = 30  # Number of items per page for grid view
CNT_TOP_TOPICS = 20  # Number of top topics to display in word cloud

# Database tables
db_table_proj = 'media_proj'
db_table_arch = 'media_arch'
list_db_tables = [db_table_proj, db_table_arch]

# File types and genres
list_file_types = ['mp4', 'jpg', 'psd', 'prproj', 'docx', 'xlsx', 'pptx', 'hip', 'nk', 'obj']
list_genres = [f"genre_{i:03d}" for i in range(100)]

# Thumbnail mappings
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

# Logo configuration
file_logo_sqr = 'foxlito.png'
path_logo_sqr = os.path.join(path_base_media, 'dummy', 'thumbnails', file_logo_sqr)

# ============================================================================
# HELPER FUNCTIONS - CART MANAGEMENT
# ============================================================================

def cart_init():
    """Initialize cart as a dictionary if it doesn't exist or is not a dict"""
    if 'cart' not in session or not isinstance(session.get('cart'), dict):
        session['cart'] = {}

def cart_get_items(db_table):
    """Get cart items for a specific db_table"""
    cart_init()
    return session['cart'].get(db_table, [])

def cart_add_items(db_table, item_ids):
    """Add items to cart for a specific db_table"""
    cart_init()
    if db_table not in session['cart']:
        session['cart'][db_table] = []
    session['cart'][db_table].extend(item_ids)
    session['cart'][db_table] = list(set(session['cart'][db_table]))  # unique
    session.modified = True

def cart_get_count(db_table):
    """Get count of items in cart for a specific db_table"""
    return len(cart_get_items(db_table))

def cart_clear_table(db_table):
    """Clear cart items for a specific db_table"""
    cart_init()
    if db_table in session['cart']:
        session['cart'].pop(db_table)
        session.modified = True

# ============================================================================
# HELPER FUNCTIONS - DATABASE & MEDIA
# ============================================================================

def db_get_connection():
    """Connect to SQLite database and return connection with row factory enabled"""
    conn = sqlite3.connect(path_db_media)
    conn.row_factory = sqlite3.Row
    return conn

def db_item_add_from_dict(item_dict: dict, db_table: str = None):
    """
    Adds a new media item to the database from a dictionary.
    
    Args:
        item_dict: Dictionary containing media item fields
        db_table: Database table name (default: first table in list)
    """
    # Use default table if not specified
    if db_table is None:
        db_table = list_db_tables[0]
    
    # Validate table name
    if db_table not in list_db_tables:
        db_table = list_db_tables[0]
    
    # Define all expected fields with default values
    all_fields = {
        'file_id': 'unknown',
        'file_name': 'unknown',
        'file_path': 'unknown',
        'file_type': 'unknown',
        'file_format': 'unknown',
        'file_resolution': 'unknown',
        'file_duration': 'unknown',
        'shot_size': 'unknown',
        'shot_type': 'unknown',
        'source': 'unknown',
        'source_id': 'unknown',
        'genre': 'unknown',
        'subject': 'unknown',
        'category': 'unknown',
        'lighting': 'unknown',
        'setting': 'unknown',
        'tags': 'unknown',
        'captions': 'unknown',
    }
    
    # Merge item_dict into all_fields, overwriting defaults with actual values
    for key, value in item_dict.items():
        if key in all_fields:
            all_fields[key] = value
    
    conn = db_get_connection()
    columns = ', '.join(all_fields.keys())
    placeholders = ', '.join('?' for _ in all_fields)
    sql = f'INSERT INTO {db_table} ({columns}) VALUES ({placeholders})'
    conn.execute(sql, tuple(all_fields.values()))
    conn.commit()
    conn.close()

def enrich_media_paths(item):
    """Enrich media item with absolute/relative paths and thumbnail paths for Flask serving"""
    
    item_dict = dict(item)
    full_path = item_dict['file_path']
    if full_path.startswith('$DEPOT_ALL'):
        full_path = full_path.replace('$DEPOT_ALL', depot_local)
    item_dict['absolute_path'] = full_path
    relative_path = os.path.relpath(full_path, depot_local)
    thumbs_other_relative_path = os.path.relpath(path_base_thumbs, depot_local)
    item_dict['relative_path'] = relative_path

    ext_is_matched = False
    ext_is_viewable = False
    thumb_relative_path = relative_path

    # logic for displaying thumbnails when loading mp4 files
    if item_dict.get('file_type', '').lower() == 'mp4':
        ext_is_matched = True
        ext_is_viewable = True
        base, _ = os.path.splitext(relative_path)
        for ext in ('.jpg', '.png'):
            candidate = base + ext
            if os.path.exists(os.path.join(depot_local, candidate)):
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

def category_get_dict(category: str, top_n: int, db_table: str = None) -> dict:
    """
    Returns a dictionary of {category_value: count} for the top N occurrences.
    
    Args:
        category: Column name to query (e.g., 'genre', 'subject', 'tags')
        top_n: Number of top results to return
        db_table: Database table name (default: first table in list)
        
    Returns:
        Dictionary mapping category values to their counts
    """
    if db_table is None:
        db_table = list_db_tables[0]
    
    conn = db_get_connection()
    
    # Validate category to prevent SQL injection
    allowed_categories = ['file_type', 'genre', 'subject', 'category', 'lighting', 'setting', 'tags']
    if category not in allowed_categories:
        conn.close()
        return {}
    
    # Validate table name
    if db_table not in list_db_tables:
        conn.close()
        return {}
    
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
    
    category_dict = {row[category]: row['count'] for row in results}
    return category_dict

def git_get_info():
    """Extract the latest commit information from the Git repository"""
    if not GIT_AVAILABLE:
        return None
    
    try:
        repo = git.Repo(search_parent_directories=True)
        latest_commit = repo.head.commit
        
        commit_info = {
            'hash': latest_commit.hexsha[:7],
            'date': datetime.fromtimestamp(latest_commit.committed_date).strftime('%Y-%m-%d %H:%M:%S'),
            'message': latest_commit.message.strip().split('\n')[0]
        }
        
        return commit_info
    except (git.InvalidGitRepositoryError, git.GitCommandError):
        return None

def extract_media_metadata(file_path):
    """Extract resolution and duration metadata from video files using OpenCV"""
    
    metadata = {}
    file_ext = os.path.splitext(file_path)[1].lstrip('.').lower()
    
    try:
        if file_ext in ['mp4', 'mov', 'avi', 'mkv']:
            cap = cv2.VideoCapture(file_path)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                metadata['file_resolution'] = f"{width}x{height}"
                
                if fps > 0:
                    duration_seconds = frame_count / fps
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

# ============================================================================
# ROUTE REGISTRATION FUNCTION
# ============================================================================

def register_mediabrowser_routes(app):
    """
    Register all mediabrowser routes to the provided Flask app instance.
    
    Args:
        app: Flask application instance
    """
    
    # ========================================================================
    # FLASK CONTEXT PROCESSORS
    # ========================================================================
    
    @app.context_processor
    def inject_cart_count():
        """Make cart count available to all templates based on current db_table"""
        db_table = request.form.get('db_table') or request.args.get('db_table', list_db_tables[0])
        if db_table not in list_db_tables:
            db_table = list_db_tables[0]
        
        count = cart_get_count(db_table)
        return {'cart_count': count, 'current_db_table': db_table, 'db_table': db_table}
    
    # ========================================================================
    # ROUTES - STATIC RESOURCES
    # ========================================================================
    
    @app.route('/resources/<path:filename>')
    def serve_resources(filename):
        """Serve files from the resources directory (e.g., favicon)"""
        resources_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
        return send_from_directory(resources_dir, filename)
    
    # ========================================================================
    # ROUTES - MAIN PAGES
    # ========================================================================
    
    @app.route('/')
    @app.route('/index')
    def page_index():
        """Render homepage with random media item, word clouds, and search stats"""
        
        db_table = request.args.get('db_table', list_db_tables[0])
        if db_table not in list_db_tables:
            db_table = list_db_tables[0]
        
        conn = db_get_connection()
        random_media = conn.execute(f'SELECT * FROM {db_table} ORDER BY RANDOM() LIMIT 1').fetchone()
        random_image = enrich_media_paths(random_media) if random_media else None
        conn.close()
        
        logo_relative = os.path.relpath(path_logo_sqr, depot_local)
        top_subjects = category_get_dict('subject', CNT_TOP_TOPICS, db_table)
        top_genres = category_get_dict('genre', CNT_TOP_TOPICS, db_table)
        git_info = git_get_info()
    
        return render_template('index.html', random_image=random_image, logo_path=logo_relative,
                              top_subjects=top_subjects, top_genres=top_genres,
                              db_tables=list_db_tables, db_table=db_table,
                              file_types=list_file_types, genres=list_genres, top_topics=CNT_TOP_TOPICS,
                              git_info=git_info)
    
    @app.route('/search', methods=['GET', 'POST'])
    def page_search():
        """Search and filter media with pagination. POST adds items to cart, GET displays results"""
        
        search_query = request.form.get('query') or request.args.get('query', '')
        file_type_filter = request.form.get('file_type') or request.args.get('file_type', '')
        genre_filter = request.form.get('genre') or request.args.get('genre', '')
        db_table = request.form.get('db_table') or request.args.get('db_table', list_db_tables[0])
        view = request.form.get('view') or request.args.get('view', 'grid')
        page_str = request.form.get('page') or request.args.get('page', '1')
        
        if db_table not in list_db_tables:
            db_table = list_db_tables[0]
        
        try:
            page = int(page_str)
        except ValueError:
            abort(404)
    
        CNT_ITEMS_PER_PAGE = {'table': CNT_ITEMS_VIEW_TABLE, 'grid': CNT_ITEMS_VIEW_GRID}.get(view, 10)
        offset = (page - 1) * CNT_ITEMS_PER_PAGE
    
        if request.method == 'POST':
            selected = request.form.getlist('selected')
            cart_add_items(db_table, selected)
    
        conn = db_get_connection()
    
        # Build complex query searching across multiple fields
        if search_query:
            where_clause = "(genre LIKE ? OR category LIKE ? OR subject LIKE ? OR tags LIKE ?)"
            params = ['%' + search_query + '%'] * 4
            
            if file_type_filter:
                where_clause += " AND file_type = ?"
                params.append(file_type_filter)
            
            if genre_filter:
                where_clause += " AND genre = ?"
                params.append(genre_filter)
            
            sql_query = f'SELECT * FROM {db_table} WHERE {where_clause} ORDER BY file_id ASC LIMIT ? OFFSET ?'
            params.extend([CNT_ITEMS_PER_PAGE, offset])
            
            count_sql = f'SELECT COUNT(*) FROM {db_table} WHERE {where_clause}'
            count_params = params[:-(2)]
            
            media = conn.execute(sql_query, params).fetchall()
            total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
            total_pages = math.ceil(total_media_count / CNT_ITEMS_PER_PAGE)
        elif file_type_filter or genre_filter:
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
            count_params = params[:-2]
            media = conn.execute(sql_query, params).fetchall()
            total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
            total_pages = math.ceil(total_media_count / CNT_ITEMS_PER_PAGE)
        else:
            sql_query = f'SELECT * FROM {db_table} ORDER BY file_id ASC LIMIT ? OFFSET ?'
            params = (CNT_ITEMS_PER_PAGE, offset)
            count_sql = f'SELECT COUNT(*) FROM {db_table}'
            count_params = ()
            media = conn.execute(sql_query, params).fetchall()
            total_media_count = conn.execute(count_sql, count_params).fetchone()[0]
            total_pages = math.ceil(total_media_count / CNT_ITEMS_PER_PAGE)
    
        media_list = [enrich_media_paths(item) for item in media]
        conn.close()
    
        if total_pages > 0 and (page > total_pages or page < 1):
            abort(404)
        
        logo_relative = os.path.relpath(path_logo_sqr, depot_local)
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
    
    @app.route('/archive')
    def page_archive():
        """Media archive interface for adding files to database"""
        
        db_table = db_table_arch
        session['target_db_table'] = db_table
        
        queue = session.get('processing_queue', [])
        
        # Check for index in URL parameter first, then session
        current_index = request.args.get('index', type=int)
        if current_index is None:
            current_index = session.get('current_index', 0)
        
        # Ensure index is within bounds
        if current_index >= len(queue):
            current_index = len(queue) - 1 if queue else 0
        
        # Save to session for subsequent requests
        session['current_index'] = current_index
        
        if 'processed_files' not in session:
            session['processed_files'] = {}
        
        current_item = queue[current_index] if queue and current_index < len(queue) else None
        
        logo_relative = os.path.relpath(path_logo_sqr, depot_local)
        git_info = git_get_info()
        
        return render_template('archive.html',
                              queue=queue,
                              current_item=current_item,
                              current_index=current_index,
                              total_items=len(queue),
                              file_types=list_file_types,
                              genres=list_genres,
                              logo_path=logo_relative,
                              depot_local=depot_local,
                              path_base_media=path_base_media,
                              db_table=db_table,
                              db_tables=list_db_tables,
                              processed_files=session.get('processed_files', {}),
                              git_info=git_info)
    
    # ========================================================================
    # ROUTES - CART
    # ========================================================================
    
    @app.route('/cart')
    def page_cart():
        """Display cart page with selected media items from session"""
        
        db_table = request.form.get('db_table') or request.args.get('db_table', list_db_tables[0])
        if db_table not in list_db_tables:
            db_table = list_db_tables[0]
        
        referrer = request.referrer
        if referrer and '/search' in referrer:
            session['last_search_url'] = referrer
        
        cart_ids = cart_get_items(db_table)
        media_list = []
        if cart_ids:
            placeholders = ','.join('?' for _ in cart_ids)
            query = f'SELECT * FROM {db_table} WHERE file_id IN ({placeholders})'
            conn = db_get_connection()
            media = conn.execute(query, cart_ids).fetchall()
            for item in media:
                media_list.append(enrich_media_paths(item))
            conn.close()
        
        logo_relative = os.path.relpath(path_logo_sqr, depot_local)
        back_url = session.get('last_search_url', url_for('page_search'))
        git_info = git_get_info()
        
        return render_template('cart.html', media=media_list, logo_path=logo_relative, 
                              back_url=back_url, git_info=git_info, db_table=db_table, 
                              db_tables=list_db_tables, genres=list_genres)
    
    @app.route('/clear_cart')
    def cart_clear():
        """Clear items from cart for specific db_table and redirect to cart page"""
        
        db_table = request.args.get('db_table', list_db_tables[0])
        if db_table not in list_db_tables:
            db_table = list_db_tables[0]
        
        cart_clear_table(db_table)
        return redirect(url_for('page_cart', db_table=db_table))
    
    @app.route('/download_cart', methods=['POST'])
    def cart_download():
        """Create and download a ZIP file of selected cart items"""
        
        db_table = request.form.get('db_table') or request.args.get('db_table', list_db_tables[0])
        if db_table not in list_db_tables:
            db_table = list_db_tables[0]
        
        selected_ids = request.form.getlist('selected')
        
        if not selected_ids:
            flash('No files selected for download', 'error')
            return redirect(url_for('page_cart'))
        
        placeholders = ','.join('?' for _ in selected_ids)
        query = f'SELECT * FROM {db_table} WHERE file_id IN ({placeholders})'
        conn = db_get_connection()
        media = conn.execute(query, selected_ids).fetchall()
        conn.close()
        
        if not media:
            flash('Selected files not found in database', 'error')
            return redirect(url_for('page_cart'))
        
        memory_file = io.BytesIO()
        files_added = 0
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in media:
                item_dict = dict(item)
                full_path = item_dict['file_path']
                if full_path.startswith('$DEPOT_ALL'):
                    full_path = full_path.replace('$DEPOT_ALL', depot_local)
                
                if os.path.exists(full_path):
                    arcname = os.path.basename(full_path)
                    zf.write(full_path, arcname)
                    files_added += 1
        
        if files_added == 0:
            flash(f'No valid file paths found on disk ({len(media)} files missing)', 'error')
            return redirect(url_for('page_cart'))
        
        memory_file.seek(0)
        
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
        db_table = data.get('db_table', list_db_tables[0])
        if db_table not in list_db_tables:
            db_table = list_db_tables[0]
        
        changes = data.get('changes', [])
        provided_password = data.get('password', '')
        
        correct_password = os.getenv('MEDIA_SQLITE_KEY')
        if not correct_password:
            return jsonify({'success': False, 'error': 'Database password not configured on server'})
        
        if provided_password != correct_password:
            return jsonify({'success': False, 'error': 'Incorrect password'})
        
        if not changes:
            return jsonify({'success': False, 'error': 'No changes provided'})
        
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
                    
                sql = f'UPDATE {db_table} SET {field} = ? WHERE file_id = ?'
                cursor = conn.execute(sql, (value, file_id))
                updated_count += cursor.rowcount
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'updated': updated_count})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/prune_cart_items', methods=['POST'])
    def cart_items_prune():
        """Delete items from database by file_id (requires password authentication)"""
        
        data = request.get_json()
        db_table = data.get('db_table', list_db_tables[0])
        if db_table not in list_db_tables:
            db_table = list_db_tables[0]
        
        file_ids = data.get('file_ids', [])
        provided_password = data.get('password', '')
        
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
                sql = f'DELETE FROM {db_table} WHERE file_id = ?'
                conn.execute(sql, (file_id,))
                deleted_count += 1
                
                cart_init()
                if db_table in session.get('cart', {}) and file_id in session['cart'][db_table]:
                    session['cart'][db_table].remove(file_id)
                    session.modified = True
            
            conn.commit()
            conn.close()
            
            return {'success': True, 'deleted': deleted_count}
        except Exception as e:
            conn.close()
            return {'success': False, 'error': str(e)}
    
    # ========================================================================
    # ROUTES - ARCHIVE API
    # ========================================================================
    
    @app.route('/api/archive/upload_files', methods=['POST'])
    def api_archive_upload_files():
        """Upload files to archive folder and add to processing queue"""
        
        try:
            uploaded_files = request.files.getlist('files')
            
            if not uploaded_files:
                return jsonify({'success': False, 'error': 'No files uploaded'})
            
            os.makedirs(path_base_archive, exist_ok=True)
            
            queue = session.get('processing_queue', [])
            copied_files = []
            
            for file in uploaded_files:
                if file.filename == '':
                    continue
                
                file_name = file.filename
                dest_path = os.path.join(path_base_archive, file_name)
                
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(file_name)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(path_base_archive, f"{base}_{counter}{ext}")
                        counter += 1
                
                file.save(dest_path)
                dest_path = dest_path.replace('\\', '/')
                
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
            
            metadata = extract_media_metadata(file_path)
            
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_name)[1].lstrip('.')
            
            metadata['file_name'] = file_name
            metadata['file_type'] = file_ext.lower()
            metadata['source_path'] = file_path
            metadata['file_format'] = metadata.get('file_format', 'info_tbd')
            metadata['source'] = metadata.get('source', 'info_tbd')
            metadata['source_id'] = metadata.get('source_id', 'info_tbd')
            
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
            
            if file_type in ['mp4', 'mov', 'avi', 'mkv']:
                dest_folder = os.path.join(path_base_archive, 'videos')
            elif file_type in ['jpg', 'jpeg', 'png', 'psd']:
                dest_folder = os.path.join(path_base_archive, 'images')
            else:
                dest_folder = os.path.join(path_base_archive, 'other')
            
            os.makedirs(dest_folder, exist_ok=True)
            
            file_name = os.path.basename(source_path)
            dest_path = os.path.join(dest_folder, file_name)
            
            if os.path.exists(dest_path):
                base, ext = os.path.splitext(file_name)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
                    counter += 1
            
            copy_id = f"copy_{int(time.time()*1000)}"
            session[f'copy_progress_{copy_id}'] = {'percent': 0, 'status': 'copying'}
            
            total_size = os.path.getsize(source_path)
            copied = 0
            
            with open(source_path, 'rb') as src, open(dest_path, 'wb') as dst:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
                    copied += len(chunk)
                    percent = int((copied / total_size) * 100)
                    session[f'copy_progress_{copy_id}'] = {'percent': percent, 'status': 'copying'}
            
            session[f'copy_progress_{copy_id}'] = {'percent': 100, 'status': 'complete'}
            
            rel_path = dest_path.replace(depot_local, '$DEPOT_ALL').replace('\\', '/')
            
            # Auto-generate thumbnail for video files
            if file_type in ['mp4', 'mov', 'avi', 'mkv']:
                try:
                    cap = cv2.VideoCapture(dest_path)
                    if cap.isOpened():
                        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        if fps > 0:
                            duration = frame_count / fps
                            seek_time = 1.0 if duration > 4 else duration * 0.25
                            cap.set(cv2.CAP_PROP_POS_MSEC, seek_time * 1000)
                        
                        ret, frame = cap.read()
                        cap.release()
                        
                        if ret:
                            base_name = os.path.splitext(os.path.basename(dest_path))[0]
                            thumb_path = os.path.join(dest_folder, f"{base_name}.jpg")
                            cv2.imwrite(thumb_path, frame)
                except Exception as e:
                    print(f"Warning: Could not auto-generate thumbnail: {e}")
            
            if 'file_copy_cache' not in session:
                session['file_copy_cache'] = {}
            session['file_copy_cache'][source_path] = dest_path
            session.modified = True
            
            dest_path_abs = dest_path.replace('\\', '/')
            return jsonify({'success': True, 'dest_path_rel': rel_path, 'dest_path_abs': dest_path_abs, 'copy_id': copy_id})
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
            current_time = request.json.get('current_time', 0)
            
            if not os.path.exists(file_path):
                return jsonify({'success': False, 'error': 'File not found'})
            
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return jsonify({'success': False, 'error': 'Could not open video file'})
            
            cap.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000)
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                return jsonify({'success': False, 'error': 'Could not capture frame'})
            
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            dest_folder = os.path.join(path_base_archive, 'videos')
            os.makedirs(dest_folder, exist_ok=True)
            thumb_path = os.path.join(dest_folder, f"{base_name}.jpg")
            
            cv2.imwrite(thumb_path, frame)
            
            return jsonify({'success': True, 'thumbnail': thumb_path, 'time': current_time})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/archive/submit', methods=['POST'])
    def api_archive_submit():
        """Submit metadata to database"""
        
        try:
            data = request.json
            
            required_fields = ['file_id', 'file_name', 'file_path', 'file_type']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'error': f'Missing required field: {field}'})
            
            db_table = session.get('target_db_table', db_table_arch)
            
            db_item_add_from_dict(data, db_table)
            
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
            
            if not os.path.isfile(file_path):
                return jsonify({'error': 'Not a file'}), 400
            
            return send_file(file_path)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    print("✓ Registered mediabrowser routes (search, archive, cart, API)")
