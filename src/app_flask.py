"""
MediaBrowser Flask Application Launcher
========================================
CLI standalone launcher for the MediaBrowser Flask application.
Initializes Flask app and registers routes from mediabrowser and projectbrowser modules.

Can be run directly: python app_flask.py
For GUI launcher with buttons, use launchpad.py instead.

Environment Requirements:
- DEPOT_ALL: Base depot directory path
- MEDIA_SQLITE_KEY (optional): Password for database modifications
"""

import socket
import webbrowser
import os
import sqlite3
from threading import Timer
from flask import Flask, send_from_directory

# ============================================================================
# CONFIGURATION & GLOBALS
# ============================================================================

depot_local = os.getenv('DEPOT_ALL')
if not depot_local:
    raise EnvironmentError("DEPOT_ALL environment variable must be set")

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================

# Get absolute path to templates directory
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

app = Flask(__name__, 
            static_folder=None,  # Disable automatic static route
            template_folder=template_dir)
app.secret_key = 'your_secret_key_here'  # Set secret key for sessions
app.config['TEMPLATES_AUTO_RELOAD'] = True  # Force template reloading

# Global reference to launchpad app for HTTP activity tracking
launchpad_app_ref = None

@app.before_request
def track_http_activity():
    """Reset launchpad countdown timer on any HTTP request"""
    if launchpad_app_ref is not None and hasattr(launchpad_app_ref, 'time_countdown_reset'):
        launchpad_app_ref.time_countdown_reset()

# ============================================================================
# COMMON RESOURCE ROUTES
# ============================================================================

@app.route('/resources/<path:filename>')
def serve_resources(filename):
    """Serve common resources (favicon, icons) for all modules"""
    resources_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
    return send_from_directory(resources_dir, filename)

# Manually create static route for depot media files
@app.route('/static/<path:filename>')
def static(filename):
    """Serve media files from depot"""
    return send_from_directory(depot_local, filename)

# ============================================================================
# PORT MANAGEMENT UTILITIES
# ============================================================================

def browser_open(url):
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


def port_number_available(host, port):
    """Check if a port is available on the given host"""
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False


def port_find_available(host='127.0.0.1', start_port=5000, max_attempts=10):
    """Find next available port by checking sequential ports from start_port"""
    
    for port in range(start_port, start_port + max_attempts):
        if port_number_available(host, port):
            return port
    return None

# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

def ensure_database_indexes(db_path, table_name, index_definitions):
    """
    Create performance indexes on database tables for faster query execution.
    
    Indexes work like a book's index - SQLite builds a sorted B-tree structure
    for fast lookups instead of reading every row (full table scan).
    
    Performance Impact Example (30k+ records):
    - WITHOUT index: Full table scan = 30,000 rows read (3-5 seconds on network)
    - WITH index: Index lookup = ~10-20 rows read (0.01-0.5 seconds)
    
    Network Storage Considerations:
    - Indexes are even MORE critical with network storage (Samba/NFS)
    - Reduces network I/O by 80-90% after first query (warm cache)
    - Each index adds ~5-15% disk space but eliminates slow network reads
    
    Args:
        db_path (str): Absolute path to SQLite database file
        table_name (str): Name of table to create indexes for
        index_definitions (list): List of tuples (index_name, column_or_columns)
                                 where column_or_columns can be:
                                 - Single column: 'subject'
                                 - Multiple columns: 'file_type, subject'
    
    Example:
        ensure_database_indexes(
            db_path='/path/to/media.sqlite',
            table_name='media_proj',
            index_definitions=[
                ('idx_subject', 'subject'),
                ('idx_type_subject', 'file_type, subject')  # composite index
            ]
        )
    """
    if not os.path.exists(db_path):
        print(f"[!] Database not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path, timeout=60.0)
        cursor = conn.cursor()
        
        created_count = 0
        skipped_count = 0
        
        for index_name, columns in index_definitions:
            # Check if index already exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND name=?
            """, (index_name,))
            
            if cursor.fetchone():
                skipped_count += 1
                continue
            
            # Create index
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({columns})"
            cursor.execute(sql)
            created_count += 1
            print(f"  [+] Created index: {index_name} on {table_name}({columns})")
        
        conn.commit()
        conn.close()
        
        if created_count > 0:
            print(f"✓ Database indexes verified: {created_count} created, {skipped_count} already exist ({table_name})")
        
    except sqlite3.Error as e:
        print(f"[!] Error creating indexes for {table_name}: {e}")
    except Exception as e:
        print(f"[!] Unexpected error creating indexes: {e}")


def ensure_all_indexes():
    """
    Initialize all database indexes for mediabrowser and projectbrowser.
    
    This function is called on application startup to ensure optimal
    query performance for network-shared databases with 30k+ records.
    
    Index Strategy:
    - Single-column indexes: For individual filter fields (subject, genre, etc.)
    - Composite indexes: For common multi-field queries (type + subject)
    - Covers all columns used in WHERE clauses in search routes
    """
    print("\n[Database Index Initialization]")
    
    # MediaBrowser indexes (media_proj and media_arch tables)
    depot_local = os.getenv('DEPOT_ALL')
    if depot_local:
        media_db_path = os.path.join(depot_local, 'assetdepot', 'media', 'dummy', 'db', 'media_dummy.sqlite')
        
        # Common filter fields used in /search route
        media_indexes = [
            ('idx_subject', 'subject'),
            ('idx_genre', 'genre'),
            ('idx_setting', 'setting'),
            ('idx_lighting', 'lighting'),
            ('idx_file_type', 'file_type'),
            ('idx_category', 'category'),
            # Composite indexes for common search combinations
            ('idx_type_subject', 'file_type, subject'),
            ('idx_genre_subject', 'genre, subject'),
        ]
        
        # Apply indexes to both tables
        if os.path.exists(media_db_path):
            print(f"\nIndexing: {media_db_path}")
            ensure_database_indexes(media_db_path, 'media_proj', media_indexes)
            ensure_database_indexes(media_db_path, 'media_arch', media_indexes)
        else:
            print(f"  [ℹ] Media database not found: {media_db_path}")
    
    # ProjectBrowser indexes (projects table)
    path_db = os.getenv('DUMMY_DB')
    if path_db:
        projects_db_path = os.path.join(path_db, 'sqlite', 'db_projects.sqlite3')
        
        # Common filter fields used in project queries
        project_indexes = [
            ('idx_job_name', 'job_name'),
            ('idx_job_alias', 'job_alias'),
            ('idx_job_year', 'job_year'),
            ('idx_job_id', 'job_id'),
            # Composite indexes for dashboard queries
            ('idx_year_alias', 'job_year, job_alias'),
        ]
        
        if os.path.exists(projects_db_path):
            print(f"\nIndexing: {projects_db_path}")
            ensure_database_indexes(projects_db_path, 'projects', project_indexes)
        else:
            print(f"  [ℹ] Projects database not found: {projects_db_path}")
    
    print("[Index initialization complete]\n")


def register_routes_mediabrowser():
    """Register mediabrowser routes if module is available"""
    try:
        import mediabrowser as mb
        if hasattr(mb, 'register_routes'):
            mb.register_routes(app)
    except ImportError:
        print("⚠ mediabrowser module not found, search/archive/cart routes not registered")
    except Exception as e:
        print(f"⚠ Error registering mediabrowser routes: {e}")


def register_routes_projectbrowser():
    """Register projectbrowser routes if module is available"""
    try:
        import projectbrowser as pb
        if hasattr(pb, 'register_routes'):
            pb.register_routes(app)
    except ImportError:
        print("ℹ projectbrowser module not found, skipping route registration")
    except Exception as e:
        print(f"⚠ Error registering projectbrowser routes: {e}")


# Attempt to register routes on module load

register_routes_mediabrowser()
register_routes_projectbrowser()

# ============================================================================
# MAIN CLI LAUNCHER
# ============================================================================

def main(debug=True, host='127.0.0.1', port=5000, browser_open_on_start=True):
    """
    Main entry point for the MediaBrowser application.
    
    Args:
        debug (bool): Enable Flask debug mode. Default is True.
        host (str): Host to bind to. Default is '127.0.0.1' (accessible from WSL/Windows).
        port (int): Port to bind to. Default is 5000.
        browser_open_on_start (bool): Automatically open browser. Default is True.
    """
    # Initialize database indexes for optimal performance
    ensure_all_indexes()
    
    # Find an available port if the requested one is in use
    if not port_number_available(host, port):
        print(f"Port {port} is already in use, searching for available port...")
        available_port = port_find_available(host, port, max_attempts=10)
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
    print("Available interfaces:")
    print(f"  • Search:     {url}/search")
    print(f"  • Archive:    {url}/archive")
    print(f"  • Production: {url}/production")
    print(f"  • Cart:       {url}/cart")
    
    # Open browser after a delay to allow Flask to start
    if browser_open_on_start:
        delay = 3.0 if debug else 1.5
        Timer(delay, lambda: browser_open(url)).start()
    
    app.run(debug=debug, host=host, port=port, use_reloader=False)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='MediaBrowser - Flask-based media management')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on (default: 5000)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--debug', action='store_true', default=True, help='Enable debug mode')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    
    args = parser.parse_args()
    
    # Convert --no-browser flag to positive browser_open flag
    should_open_browser = not args.no_browser
    
    main(debug=args.debug, host=args.host, port=args.port, browser_open_on_start=should_open_browser)
