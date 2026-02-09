"""
ProjectBrowser Routes Module
============================
Contains all routes and functionality for project management operations.
This module provides register_routes() which adds all projectbrowser
routes to a Flask app instance.

Routes provided:
- /production: Project dashboard and management interface
- /api/projects_by_year: Fetch projects organized by year
- /api/apps_by_project: Fetch applications for a project
- /api/subdirs_by_app: Fetch subdirectories for an application
- /api/open_app_directory: Open application directory in OS file manager
- /api/action_jobactive_query: Query active job status
- /api/action_jobactive_dashboard_populate: Fetch job data for dashboard
- /api/action_jobactive_dashboard_update: Update job database entry
"""

import sqlite3
import os
import platform
import subprocess
import time
from flask import Flask, render_template, request, jsonify
from datetime import datetime
import db_jobtools as dbj
import vpr_jobtools as vpr

# Git info is now handled by vpr_jobtools.git_get_info()

# ============================================================================
# CONFIGURATION & GLOBALS
# ============================================================================

depot_local = os.getenv('DEPOT_ALL')
if not depot_local:
    raise EnvironmentError("DEPOT_ALL environment variable must be set")

path_proj_netwk = os.getenv('DUMMY_JOBS_NETWK')
path_rend_netwk = os.getenv('DUMMY_REND_NETWK')
path_proj_local = os.getenv('DUMMY_JOBS_LOCAL')
path_rend_local = os.getenv('DUMMY_REND_LOCAL')

path_db = os.getenv('DUMMY_DB')
if not path_db:
    raise EnvironmentError("DUMMY_DB environment variable must be set")
file_sqlite = 'db_projects.sqlite3'
file_projects_aliases = 'db_projects.tcsh'
file_project_env = 'project_env.tcsh'
file_git_info = 'repo_info.json'

db_table_proj = 'projects'
path_db_sqlite = os.path.join(path_db, 'sqlite', file_sqlite)
path_db_aliases = os.path.join(path_db, 'tcsh', file_projects_aliases)

# Logo and database table configuration
path_base_media = os.path.join(depot_local, 'assetdepot', 'media')
file_logo_sqr = 'foxlito.png'
path_logo_sqr = os.path.join(path_base_media, 'dummy', 'thumbnails', file_logo_sqr)
list_db_tables = ['media_proj', 'media_arch']

# Git repository information (defined once at module level)
path_repo = os.path.dirname(os.path.abspath(__file__))
path_git_info = os.path.join(path_repo, file_git_info)
git_info = vpr.git_get_info(path_repo=path_repo, path_json=path_git_info)

path_resources = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
path_project_env_in = os.path.join(path_resources, file_project_env)
storage_local = 'LOCAL'
storage_netwk = 'NETWK'
list_storage_src = [storage_local, storage_netwk]

# Ensure list_storage_src always has at least one item
if not list_storage_src:
    list_storage_src = [storage_netwk]

sync_local_to_netwk = 'LOCAL TO NETWK'
sync_netwk_to_local = 'NETWK TO LOCAL'
list_sync_directions = [sync_local_to_netwk, sync_netwk_to_local]

# View configuration
CNT_ITEMS_VIEW_TABLE = 100  # Number of rows per page for table view
CNT_ITEMS_VIEW_GRID = 30  # Number of items per page for grid view
CNT_TOP_TOPICS = 20  # Number of top topics to display in word cloud

# Note: This module can work as a standalone Flask app OR have its routes
# registered with another Flask app (e.g., mediabrowser)
app = Flask(__name__, static_folder=depot_local)
app.secret_key = 'your_secret_key_here'  # Set secret key for session

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def expand_depot_path(path):
    """
    Replace $DEPOT_ALL placeholder with actual depot path.
    
    Args:
        path (str): Path that may contain $DEPOT_ALL placeholder
        
    Returns:
        str: Path with $DEPOT_ALL replaced by actual depot_local value
    """
    if path and '$DEPOT_ALL' in path:
        return path.replace('$DEPOT_ALL', depot_local)
    return path

def is_wsl():
    """
    Detect if running in Windows Subsystem for Linux (WSL).
    
    Returns:
        bool: True if running in WSL, False otherwise
    """
    try:
        with open('/proc/version', 'r') as f:
            version_info = f.read().lower()
            return 'microsoft' in version_info or 'wsl' in version_info
    except:
        return False

def convert_path_for_wsl(linux_path):
    """
    Convert Linux path to Windows path using wslpath utility.
    
    Args:
        linux_path (str): Linux-style path to convert
        
    Returns:
        str: Windows-style path, or None if conversion fails
    """
    try:
        result = subprocess.run(['wslpath', '-w', linux_path], 
                              capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def event_jobactive_navigate_to_app_dir(job_path_job, app, subdir=None, storage_source=None):
    """
    OS-aware routine to open an explorer/finder window to the specified job app directory.
    Replaces $DEPOT_ALL with actual path and opens the directory in the system file browser.
    
    Args:
        job_path_job: Job path (may contain $DEPOT_ALL variable)
        app: Application directory name (e.g., 'data', 'maya', 'houdini'), or None for project level
        subdir: Optional subdirectory within app (e.g., 'afterfx' within 'adobe')
        storage_source: Storage location (e.g., 'LOCAL' or 'NETWK'), defaults to None (uses global setting)
    
    Returns:
        dict: {'success': bool, 'message': str, 'path': str}
    """
    # Replace $DEPOT_ALL with actual path
    job_path_job = expand_depot_path(job_path_job)

    # Use passed storage_source parameter, or fall back to network storage
    active_storage = storage_source if storage_source is not None else storage_netwk
    
    if (active_storage == storage_local):
        if path_proj_netwk and path_proj_local:
            job_path_job = job_path_job.replace(path_proj_netwk, path_proj_local)

    if not os.path.exists(job_path_job):
        return {'success': False, 'message': f'Path does not exist: {job_path_job}', 'path': job_path_job}
        
    # Build full path to directory
    if app is None:
        # Open at project level
        full_path = job_path_job
    elif subdir:
        full_path = os.path.join(job_path_job, app, subdir)
    else:
        full_path = os.path.join(job_path_job, app)
    
    # Check if path exists
    if not os.path.exists(full_path):
        return {'success': False, 'message': f'Directory does not exist: {full_path}', 'path': full_path}
    
    # Detect OS and open appropriate file browser
    system = platform.system()
    time.sleep(1)

    try:
        if system == 'Darwin':  # macOS
            os.system(f'open "{full_path}"')
        elif system == 'Windows':
            os.system(f'explorer "{full_path}"')
        elif system == 'Linux':
            # Check if running in WSL
            if is_wsl():
                # Convert Linux path to Windows path for Explorer
                windows_path = convert_path_for_wsl(full_path)
                if windows_path:
                    os.system(f'explorer.exe "{windows_path}"')
                else:
                    return {'success': False, 'message': f'Failed to convert path for WSL: {full_path}', 'path': full_path}
            else:
                # Native Linux
                os.system(f'xdg-open "{full_path}"')
        else:
            return {'success': False, 'message': f'Unsupported OS: {system}', 'path': full_path}
        
        return {'success': True, 'message': f'Opened directory: {full_path}', 'path': full_path}
    except Exception as e:
        return {'success': False, 'message': f'Error opening directory: {str(e)}', 'path': full_path}


# Routes are now defined inside register_routes() function below


def db_get_connection():
    """Connect to SQLite database and return connection with row factory enabled"""
    # Connects to the database and sets row_factory to sqlite3.Row 
    # to access columns by name (like a dictionary)
    conn = sqlite3.connect(path_db_sqlite)
    conn.row_factory = sqlite3.Row 
    return conn


# ============================================================================
# ROUTE REGISTRATION FUNCTION
# ============================================================================

def register_routes(flask_app):
    """
    Register all projectbrowser routes to the provided Flask app instance.
    
    Args:
        flask_app: Flask application instance to register routes with
    """
    
    # ========================================================================
    # ROUTES - MAIN PAGES
    # ========================================================================
    
    @flask_app.route('/production', methods=['GET', 'POST'])
    def page_production():
        """Production interface with cascading dropdowns for years, projects, and apps"""
        # Production uses 'projects' table
        db_table = db_table_proj
        
        # Logo relative path for template
        logo_relative = os.path.relpath(path_logo_sqr, depot_local)
        
        # Get all available years
        conn = db_get_connection()
        cursor = conn.cursor()
        cursor.execute(f'SELECT DISTINCT job_year FROM {db_table} ORDER BY job_year DESC')
        years = [row['job_year'] for row in cursor.fetchall()]
        conn.close()
        
        # Only show sync menu if we have more than one storage source
        show_sync_menu = len(list_storage_src) > 1
        
        return render_template('production.html',
                              logo_path=logo_relative,
                              db_table=db_table,
                              db_tables=list_db_tables,
                              git_info=git_info,
                              years=years,
                              storage_sources=list_storage_src,
                              sync_directions=list_sync_directions,
                              show_sync_menu=show_sync_menu)
    
    # ========================================================================
    # ROUTES - API ENDPOINTS
    # ========================================================================
    
    @flask_app.route('/api/projects_by_year', methods=['GET'])
    def api_projects_by_year():
        """API endpoint to get projects for a selected year"""
        year = request.args.get('year')
        
        if not year:
            return jsonify({'error': 'Year parameter required'}), 400
        
        conn = db_get_connection()
        cursor = conn.cursor()
        cursor.execute(f'SELECT job_name, job_path_job FROM {db_table_proj} WHERE job_year = ? ORDER BY job_name', (year,))
        projects = [{'name': row['job_name'], 'path': row['job_path_job']} for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({'projects': projects})
    
    @flask_app.route('/api/apps_by_project', methods=['GET'])
    def api_apps_by_project():
        """API endpoint to get apps for a selected project"""
        project_name = request.args.get('project')
        
        if not project_name:
            return jsonify({'error': 'Project parameter required'}), 400
        
        conn = db_get_connection()
        cursor = conn.cursor()
        cursor.execute(f'SELECT job_apps, job_path_job FROM {db_table_proj} WHERE job_name = ?', (project_name,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Project not found'}), 404
        
        # Parse job_apps (comma-separated string)
        apps = [app.strip() for app in row['job_apps'].split(',')]
        
        return jsonify({'apps': apps, 'job_path_job': row['job_path_job']})
    
    @flask_app.route('/api/subdirs_by_app', methods=['GET'])
    def api_subdirs_by_app():
        """API endpoint to get subdirectories for a selected app"""
        app = request.args.get('app')
        
        if not app:
            return jsonify({'error': 'App parameter required'}), 400
        
        # Get subdirectories from db_jobtools.dict_apps
        subdirs = dbj.dict_apps.get(app, [])
        
        return jsonify({'subdirs': subdirs})
    
    @flask_app.route('/api/sync_directory', methods=['POST'])
    def api_sync_directory():
        """API endpoint to synchronize directories by launching terminal window"""
        import platform
        import shlex
        
        data = request.get_json()
        job_path_job = data.get('job_path_job')
        app = data.get('app')  # Can be None for project-level sync
        subdir = data.get('subdir')  # Optional subdirectory
        sync_direction = data.get('sync_direction')  # 'LOCAL TO NETWK' or 'NETWK TO LOCAL'
        storage_source = data.get('storage_src', storage_netwk)  # Default to network
        
        if not job_path_job:
            return jsonify({'success': False, 'message': 'job_path_job parameter required'}), 400
        
        if not sync_direction or sync_direction not in list_sync_directions:
            return jsonify({'success': False, 'message': 'Invalid sync_direction'}), 400
        
        # Replace $DEPOT_ALL with actual path
        job_path_job = expand_depot_path(job_path_job)
        
        # Build full path to directory
        if app is None:
            # Sync at project level
            target_path = job_path_job
        elif subdir:
            target_path = os.path.join(job_path_job, app, subdir)
        else:
            target_path = os.path.join(job_path_job, app)
        
        # Determine local and network paths based on target
        # Network path is the target_path as stored in DB
        path_netwk = target_path
        
        # Local path is derived by replacing network base with local base
        if path_proj_netwk and path_proj_local:
            path_local = target_path.replace(path_proj_netwk, path_proj_local)
        else:
            return jsonify({'success': False, 'message': 'Local/Network paths not configured'}), 500
        
        # Determine source and destination based on direction
        if sync_direction == sync_local_to_netwk:
            source = path_local
            destination = path_netwk
        else:  # NETWK TO LOCAL
            source = path_netwk
            destination = path_local
        
        # Validate source path exists
        if not os.path.exists(source):
            return jsonify({'success': False, 'message': f'Source path does not exist: {source}'}), 400
        
        # Create destination if it doesn't exist
        if not os.path.exists(destination):
            try:
                os.makedirs(destination, exist_ok=True)
            except Exception as e:
                return jsonify({'success': False, 'message': f'Failed to create destination: {e}'}), 500
        
        # Detect OS and launch appropriate terminal
        system = platform.system()
        
        try:
            if system == 'Darwin':  # macOS
                # Ensure paths end with / for rsync
                src = source if source.endswith('/') else source + '/'
                dst = destination if destination.endswith('/') else destination + '/'
                
                # Build rsync command
                rsync_cmd = (
                    f"rsync -avh --progress "
                    f"--exclude='.*' --exclude='__pycache__' --exclude='node_modules' "
                    f"--exclude='*.pyc' --exclude='*.pyo' --exclude='*.tmp' --exclude='*.temp' "
                    f"--exclude='*.log' --exclude='*.swp' --exclude='*.swo' --exclude='*~' "
                    f"--exclude='.DS_Store' --exclude='Thumbs.db' --exclude='desktop.ini' "
                    f"'{src}' '{dst}'"
                )
                
                # AppleScript to open Terminal with rsync command
                terminal_script = f'''
tell application "Terminal"
    do script "echo 'Synchronizing: {sync_direction}'; echo 'Source: {source}'; echo 'Destination: {destination}'; echo ''; {rsync_cmd}; echo ''; echo 'Sync completed. Press any key to close...'; read -n 1"
    activate
end tell
'''
                
                subprocess.Popen(['osascript', '-e', terminal_script])
                
                return jsonify({
                    'success': True,
                    'message': f'Sync started in Terminal window - {sync_direction}',
                    'path_local': path_local,
                    'path_netwk': path_netwk
                }), 200
                
            elif system == 'Linux':
                # Check if running in WSL
                if is_wsl():
                    # WSL: Use Windows robocopy via cmd.exe
                    # Convert Linux paths to Windows paths using wslpath
                    source_win = convert_path_for_wsl(source)
                    destination_win = convert_path_for_wsl(destination)
                    
                    if not source_win or not destination_win:
                        return jsonify({
                            'success': False,
                            'message': 'Failed to convert paths for WSL. Ensure wslpath is available.'
                        }), 500
                    
                    # Build robocopy command with timestamp handling
                    robocopy_cmd = (
                        f'robocopy "{source_win}" "{destination_win}" /MIR /R:3 /W:5 /MT:8 '
                        f'/DCOPY:DAT /COPY:DAT /TIMFIX '
                        f'/XA:SH '
                        f'/XD ".*" "__pycache__" "node_modules" ".git" ".svn" '
                        f'/XF ".*" "*.tmp" "*.temp" "*.log" "*.swp" "*.swo" "*~" "desktop.ini" ".DS_Store" "Thumbs.db" '
                        f'& echo. & echo Sync completed. Press any key to close... & pause'
                    )
                    
                    # Launch Windows Command Prompt from WSL
                    subprocess.Popen(
                        ['cmd.exe', '/c', 'start', 'cmd', '/k',
                         f'echo Synchronizing: {sync_direction} & '
                         f'echo Source: {source_win} & '
                         f'echo Destination: {destination_win} & '
                         f'echo. & '
                         f'{robocopy_cmd}'],
                        shell=False
                    )
                    
                    return jsonify({
                        'success': True,
                        'message': f'Sync started in Command Prompt window (WSL) - {sync_direction}',
                        'path_local': path_local,
                        'path_netwk': path_netwk
                    }), 200
                else:
                    # Native Linux: Use rsync
                    # Ensure paths end with / for rsync
                    src = source if source.endswith('/') else source + '/'
                    dst = destination if destination.endswith('/') else destination + '/'
                    
                    # Build rsync command
                    rsync_cmd = (
                        f"rsync -avh --progress "
                        f"--exclude='.*' --exclude='__pycache__' --exclude='node_modules' "
                        f"--exclude='*.pyc' --exclude='*.pyo' --exclude='*.tmp' --exclude='*.temp' "
                        f"--exclude='*.log' --exclude='*.swp' --exclude='*.swo' --exclude='*~' "
                        f"--exclude='.DS_Store' --exclude='Thumbs.db' --exclude='desktop.ini' "
                        f"'{src}' '{dst}'"
                    )
                    
                    bash_cmd = (
                        f"echo 'Synchronizing: {sync_direction}'; "
                        f"echo 'Source: {source}'; "
                        f"echo 'Destination: {destination}'; "
                        f"echo ''; "
                        f"{rsync_cmd}; "
                        f"echo ''; "
                        f"echo 'Sync completed. Press Enter to close...'; "
                        f"read"
                    )
                    
                    # Try gnome-terminal first, fallback to xterm
                    terminal_cmd = None
                    try:
                        subprocess.run(['which', 'gnome-terminal'], 
                                     capture_output=True, check=True)
                        terminal_cmd = ['gnome-terminal', '--', 'bash', '-c', bash_cmd]
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        try:
                            subprocess.run(['which', 'xterm'], 
                                         capture_output=True, check=True)
                            terminal_cmd = ['xterm', '-hold', '-e', 'bash', '-c', bash_cmd]
                        except (subprocess.CalledProcessError, FileNotFoundError):
                            try:
                                subprocess.run(['which', 'konsole'], 
                                             capture_output=True, check=True)
                                terminal_cmd = ['konsole', '--hold', '-e', 'bash', '-c', bash_cmd]
                            except (subprocess.CalledProcessError, FileNotFoundError):
                                pass
                    
                    if terminal_cmd:
                        subprocess.Popen(terminal_cmd)
                        return jsonify({
                            'success': True,
                            'message': f'Sync started in terminal window - {sync_direction}',
                            'path_local': path_local,
                            'path_netwk': path_netwk
                        }), 200
                    else:
                        return jsonify({
                            'success': False,
                            'message': 'No terminal emulator found (tried gnome-terminal, xterm, konsole)'
                        }), 500
                    
            elif system == 'Windows':
                # Build robocopy command with timestamp handling to prevent 1980 date issue
                robocopy_cmd = (
                    f'robocopy "{source}" "{destination}" /MIR /R:3 /W:5 /MT:8 '
                    f'/DCOPY:DAT /COPY:DAT /TIMFIX '  # Copy Data, Attributes, Timestamps and fix timestamps
                    f'/XA:SH '
                    f'/XD ".*" "__pycache__" "node_modules" ".git" ".svn" '
                    f'/XF ".*" "*.tmp" "*.temp" "*.log" "*.swp" "*.swo" "*~" "desktop.ini" ".DS_Store" "Thumbs.db" '
                    f'& echo. & echo Sync completed. Press any key to close... & pause'
                )
                
                # Launch Command Prompt with robocopy
                subprocess.Popen(
                    ['cmd', '/c', 'start', 'cmd', '/k', 
                     f'echo Synchronizing: {sync_direction} & '
                     f'echo Source: {source} & '
                     f'echo Destination: {destination} & '
                     f'echo. & '
                     f'{robocopy_cmd}'],
                    shell=True
                )
                
                return jsonify({
                    'success': True,
                    'message': f'Sync started in Command Prompt window - {sync_direction}',
                    'path_local': path_local,
                    'path_netwk': path_netwk
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': f'Unsupported operating system: {system}'
                }), 500
                
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error launching terminal: {str(e)}'
            }), 500
    
    @flask_app.route('/api/get_sync_paths', methods=['POST'])
    def api_get_sync_paths():
        """API endpoint to get the actual local and network paths for sync preview"""
        data = request.get_json()
        job_path_job = data.get('job_path_job')
        app = data.get('app')
        subdir = data.get('subdir')
        
        if not job_path_job:
            return jsonify({'success': False, 'message': 'job_path_job parameter required'}), 400
        
        # Replace $DEPOT_ALL with actual path
        job_path_job = expand_depot_path(job_path_job)
        
        # Build full path to directory
        if app is None:
            target_path = job_path_job
        elif subdir:
            target_path = os.path.join(job_path_job, app, subdir)
        else:
            target_path = os.path.join(job_path_job, app)
        
        # Determine local and network paths
        path_netwk = target_path
        
        if path_proj_netwk and path_proj_local:
            path_local = target_path.replace(path_proj_netwk, path_proj_local)
        else:
            return jsonify({'success': False, 'message': 'Local/Network paths not configured'}), 500
        
        return jsonify({
            'success': True,
            'path_local': path_local,
            'path_netwk': path_netwk
        }), 200
    
    @flask_app.route('/api/open_app_directory', methods=['POST'])
    def api_open_app_directory():
        """API endpoint to open a job app directory in the system file browser"""
        data = request.get_json()
        job_path_job = data.get('job_path_job')
        app = data.get('app')  # Can be None for project-level opening
        subdir = data.get('subdir')  # Optional subdirectory
        storage_source = data.get('storage_src')  # Optional storage source
        
        if not job_path_job:
            return jsonify({'error': 'job_path_job parameter required'}), 400
        
        result = event_jobactive_navigate_to_app_dir(job_path_job, app, subdir, storage_source)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
    
    @flask_app.route('/api/action_jobactive_query', methods=['POST'])
    def api_action_jobactive_query():
        """Query the database for a selected job by name or path and return full row"""
        data = request.get_json() or {}
        job_name = data.get('job_name')
        job_path_job = data.get('job_path_job')

        if not job_name and not job_path_job:
            return jsonify({'success': False, 'message': 'job_name or job_path_job required'}), 400

        conn = db_get_connection()
        cursor = conn.cursor()

        if job_name:
            cursor.execute(f"SELECT * FROM {db_table_proj} WHERE job_name = ?", (job_name,))
            row = cursor.fetchone()
        else:
            cursor.execute(f"SELECT * FROM {db_table_proj} WHERE job_path_job = ?", (job_path_job,))
            row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({'success': False, 'message': 'Job not found'}), 404

        job = {k: row[k] for k in row.keys()}
        conn.close()
        return jsonify({'success': True, 'job': job}), 200
    
    @flask_app.route('/api/action_jobactive_dashboard_populate', methods=['POST'])
    def api_action_jobactive_dashboard_populate():
        """Return the subset of job fields used to populate the Project Selection display"""
        data = request.get_json() or {}
        job_name = data.get('job_name')
        job_path_job = data.get('job_path_job')

        if not job_name and not job_path_job:
            return jsonify({'success': False, 'message': 'job_name or job_path_job required'}), 400

        conn = db_get_connection()
        cursor = conn.cursor()

        if job_name:
            cursor.execute(f"SELECT * FROM {db_table_proj} WHERE job_name = ?", (job_name,))
            row = cursor.fetchone()
        else:
            cursor.execute(f"SELECT * FROM {db_table_proj} WHERE job_path_job = ?", (job_path_job,))
            row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({'success': False, 'message': 'Job not found'}), 404

        job = {k: row[k] for k in row.keys()}
        conn.close()

        # Choose fields to expose for display
        fields = ['job_name', 'job_alias', 'job_state', 'job_year', 'job_path_job', 
                  'job_path_rnd', 'job_user_id', 'job_user_name', 'job_date_created',
                  'job_edit_user_id', 'job_edit_user_name', 'job_edit_date',
                  'job_date_due', 'job_charge1', 'job_charge2', 'job_charge3',
                  'job_apps', 'job_notes', 'job_tags']
        job_out = {f: job.get(f, '') for f in fields}

        return jsonify({'success': True, 'job': job_out}), 200
    
    @flask_app.route('/api/action_jobactive_dashboard_update', methods=['POST'])
    def api_action_jobactive_dashboard_update():
        """Update job data in the database from the dashboard form"""
        data = request.get_json() or {}
        job_name = data.get('job_name')
        
        if not job_name:
            return jsonify({'success': False, 'message': 'job_name required'}), 400
        
        # Get updateable fields (exclude job_name since it's readonly and used as key)
        #list_columns_editable = [
        #    'job_alias', 'job_state', 'job_year', 'job_user_id', 'job_user_name',
        #    'job_date_created', 'job_edit_user_id', 'job_edit_user_name', 'job_edit_date',
        #    'job_date_due', 'job_charge1', 'job_charge2', 'job_charge3',
        #    'job_path_job', 'job_path_rnd', 'job_apps', 'job_tags', 'job_notes'
        #]
        list_columns_editable = [
            'job_date_due', 'job_charge1', 'job_charge2', 'job_charge3', 'job_tags', 'job_notes'
        ]
        
        # Automatically set edit tracking fields
        user_info = vpr.get_user_info_current()
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Build UPDATE query dynamically
        set_clauses = []
        values = []
        for field in list_columns_editable:
            if field in data:
                value = data[field]
                
                # Special handling for job_tags: remove duplicates
                if field == 'job_tags':
                    value = dbj.db_tags_verify(value)
                
                set_clauses.append(f"{field} = ?")
                values.append(value)
        
        # Add edit tracking fields (always updated on edit)
        set_clauses.append("job_edit_date = ?")
        values.append(current_date)
        set_clauses.append("job_edit_user_id = ?")
        values.append(user_info['user_id'])
        set_clauses.append("job_edit_user_name = ?")
        values.append(user_info['user_name'])
        
        if not set_clauses:
            return jsonify({'success': False, 'message': 'No fields to update'}), 400
        
        values.append(job_name)  # For WHERE clause
        
        try:
            conn = db_get_connection()
            cursor = conn.cursor()
            query = f"UPDATE {db_table_proj} SET {', '.join(set_clauses)} WHERE job_name = ?"
            cursor.execute(query, values)
            conn.commit()
            
            if cursor.rowcount == 0:
                conn.close()
                return jsonify({'success': False, 'message': 'Job not found'}), 404
            
            conn.close()  # Close connection to flush changes
            
            # Reopen connection to ensure SELECT sees committed data (important for Windows)
            conn = db_get_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {db_table_proj} WHERE job_name = ?", (job_name,))
            row = cursor.fetchone()
            updated_job = dict(row) if row else None
            
            conn.close()
            return jsonify({
                'success': True, 
                'message': 'Job updated successfully',
                'job': updated_job
            }), 200
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @flask_app.route('/api/job_name_validate', methods=['POST'])
    def api_job_name_validate():
        """Validate job base and generate job_name and job_alias"""
        data = request.get_json() or {}
        job_base = data.get('job_base', '').strip()
        
        if not job_base:
            return jsonify({'valid': False, 'reason': 'Job base cannot be empty'}), 200
        
        # Validate job_base using vpr_jobtools
        is_valid, reason = vpr.vpr_job_base_is_valid(job_base)
        
        if not is_valid:
            return jsonify({'valid': False, 'reason': reason}), 200

        year = datetime.now().strftime('%Y')
        year_short = year[-2:]  # get last two digits of year
        job_partial = '{}_{}'.format(year_short, job_base)

        # Query the database for any job_name that matches pattern: [yy]_[job_base]_[letter]
        job_revision_current = ''
        try:
            conn = db_get_connection()
            cursor = conn.cursor()
            # Match pattern: job_partial followed by underscore and single character (%)
            cursor.execute(f"SELECT job_name FROM {db_table_proj} WHERE job_name LIKE ?", (job_partial + '_%',))
            matching_jobs = cursor.fetchall()
            conn.close()
            
            # Extract revision letters from matching jobs
            revisions = []
            for row in matching_jobs:
                job_name = row['job_name']
                # Extract last part after final underscore
                parts = job_name.split('_')
                if len(parts) >= 3:  # [yy]_[job_base]_[rev]
                    rev = parts[-1]
                    # Check if it's a single lowercase letter
                    if len(rev) == 1 and rev.isalpha() and rev.islower():
                        revisions.append(rev)
            
            # Find highest revision letter
            if revisions:
                job_revision_current = max(revisions)
        except Exception as e:
            print(f"Error querying database for revisions: {e}")
            job_revision_current = ''

        job_revision_next = vpr.vpr_job_rev_set(job_rev=job_revision_current)
        # Generate job_name and job_alias
        result = vpr.vpr_job_name_create(job_base, job_revision_next)
        
        if result is None:
            return jsonify({'valid': False}), 200
        
        job_name, job_alias = result
        
        # Generate job path (using path_proj_netwk from config)
        job_path = os.path.join(path_proj_netwk, job_name) if path_proj_netwk else ''

        # replace depot_local with $DEPOT_ALL for symbolic path
        job_path = job_path.replace(depot_local, '$DEPOT_ALL')
        
        return jsonify({
            'valid': True,
            'job_name': job_name,
            'job_alias': job_alias,
            'job_path': job_path
        }), 200
    
    @flask_app.route('/api/job_new_create', methods=['POST'])
    def api_job_new_create():

        """Create a new job in the database and filesystem"""
        

        data = request.get_json() or {}

        # generate a new job_id
        job_id = dbj.db_id_create(db_sqlite_path=path_db_sqlite, db_table=db_table_proj, id_column='job_id')
        
        # Get pre-validated data from api_job_name_validate
        job_name = data.get('job_name', '').strip()
        job_alias = data.get('job_alias', '').strip()

        if not job_name or not job_alias:
            return jsonify({'success': False, 'message': 'job_name and job_alias required'}), 400

        job_state = 'active'
        job_year = datetime.now().strftime('%Y')
        # Get current year and user info
        job_user_id = os.getenv('USER', 'unknown')
        job_user_name = 'TBD' #user_id  # Could be enhanced to get full name
        job_date_created = datetime.now().strftime('%Y-%m-%d')
        job_notes = ''
        job_tags = ''
        job_date_due = job_date_created
        job_charge1 = ''
        job_charge2 = ''
        job_charge3 = ''
        job_apps = ','.join(dbj.list_dirs_apps)  # Default apps from db_jobtools
        
        # Generate paths
        job_path_job = os.path.join(path_proj_netwk, job_year, job_name) if path_proj_netwk else ''
        job_path_rnd = os.path.join(path_rend_netwk, job_year, job_name) if path_rend_netwk else ''
        
        job_path_job_symbolic = job_path_job.replace(depot_local, '$DEPOT_ALL')
        job_path_rnd_symbolic = job_path_rnd.replace(depot_local, '$DEPOT_ALL')
        
        
        # Check if job already exists in database
        try:
            conn = db_get_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT job_name FROM {db_table_proj} WHERE job_name = ?", (job_name,))
            existing = cursor.fetchone()
            
            if existing:
                conn.close()
                return jsonify({'success': False, 'message': f'Job {job_name} already exists'}), 409
            

            ##########
            job_data = {
                'job_id': job_id,
                'job_name': job_name,
                'job_alias': job_alias,
                'job_state': job_state,
                'job_year': job_year,
                'job_user_id': job_user_id,
                'job_user_name': job_user_name,
                'job_edit_user_id': job_user_id,
                'job_edit_user_name': job_user_name,
                'job_edit_date': job_date_created,
                'job_notes': job_notes,
                'job_tags': job_tags,
                'job_date_created': job_date_created,
                'job_date_due': job_date_due,
                'job_charge1': job_charge1,
                'job_charge2': job_charge2,
                'job_charge3': job_charge3,
                'job_path_job': job_path_job_symbolic,
                'job_path_rnd': job_path_rnd_symbolic,
                'job_apps': job_apps
            }

            columns = ', '.join(job_data.keys())
            placeholders = ', '.join('?' for _ in job_data)
            sql_insert = f'INSERT INTO {db_table_proj} ({columns}) VALUES ({placeholders})'
            #print (dbh + 'SQL: {}'.format(sql_insert))
            conn.execute(sql_insert, tuple(job_data.values()))
            conn.commit()
            ##########

            conn.commit()
            conn.close()
            
            # Create directories if paths are configured
            if job_path_job and job_path_rnd:
                try:
                    vpr.vpr_job_create_directories(job_name=job_name, 
                                                   path_job=job_path_job, 
                                                   path_rnd=job_path_rnd)
                except Exception as dir_error:
                    # Job created in DB but directories failed - still return success
                    return jsonify({
                        'success': True, 
                        'job_name': job_name,
                        'warning': f'Job created but directory creation failed: {str(dir_error)}'
                    }), 200
                
                # edit job environment file
                try:
                    vpr.vpr_job_edit_environment(job_name=job_name, 
                                                 path_job=job_path_job, 
                                                 path_job_env=path_project_env_in, 
                                                 job_year=job_year)
                except Exception as env_error:
                    # Job created in DB and directories created but environment file edit failed - still return success
                    return jsonify({
                        'success': True, 
                        'job_name': job_name,
                        'warning': f'Job created but environment file edit failed: {str(env_error)}'
                    }), 200
                
                # create nav file
                try:
                    dbj.db_jobs_nav_create(db_path=path_db_sqlite,
                                           db_table=db_table_proj,
                                           nav_path=job_path_job,
                                           nav_file=path_db_aliases)
                except Exception as nav_error:
                    # Job created in DB and directories created but nav file creation failed - still return success
                    return jsonify({
                        'success': True, 
                        'job_name': job_name,
                        'warning': f'Job created but nav file creation failed: {str(nav_error)}'
                    }), 200
                
            return jsonify({
                'success': True,
                'job_name': job_name,
                'job_alias': job_alias,
                'job_path': job_path_job,
                'job_data': {
                    'job_name': job_name,
                    'job_alias': job_alias,
                    'job_state': job_state,
                    'job_year': job_year,
                    'job_user_id': job_user_id,
                    'job_user_name': job_user_name,
                    'job_date_created': job_date_created,
                    'job_edit_user_id': '',
                    'job_edit_user_name': '',
                    'job_edit_date': '',
                    'job_date_due': '',
                    'job_charge1': '',
                    'job_charge2': '',
                    'job_charge3': '',
                    'job_path_job': job_path_job_symbolic,
                    'job_path_rnd': job_path_rnd_symbolic,
                    'job_tags': '',
                    'job_notes': ''
                }
            }), 200
            
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
    
    print("[+] Registered projectbrowser routes (production dashboard, job management API)")

