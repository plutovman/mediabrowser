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
import time
from flask import Flask, render_template, request, jsonify
from datetime import datetime
import db_jobtools as dbj
import vpr_jobtools as vpr

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

path_proj = os.getenv('DUMMY_JOBS')
path_rend = os.getenv('DUMMY_REND')
path_db = os.getenv('DUMMY_DB')
file_sqlite = 'jobs.sqlite3'
db_table_proj = 'projects'
path_db_sqlite = os.path.join(path_db, 'sqlite', file_sqlite)

# Logo and database table configuration
path_base_media = os.path.join(depot_local, 'assetdepot', 'media')
file_logo_sqr = 'foxlito.png'
path_logo_sqr = os.path.join(path_base_media, 'dummy', 'thumbnails', file_logo_sqr)
list_db_tables = ['media_proj', 'media_arch']

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

def event_jobactive_navigate_to_app_dir(job_path_job, app, subdir=None):
    """
    OS-aware routine to open an explorer/finder window to the specified job app directory.
    Replaces $DEPOT_ALL with actual path and opens the directory in the system file browser.
    
    Args:
        job_path_job: Job path (may contain $DEPOT_ALL variable)
        app: Application directory name (e.g., 'data', 'maya', 'houdini'), or None for project level
        subdir: Optional subdirectory within app (e.g., 'afterfx' within 'adobe')
    
    Returns:
        dict: {'success': bool, 'message': str, 'path': str}
    """
    # Replace $DEPOT_ALL with actual path
    if '$DEPOT_ALL' in job_path_job:
        job_path_job = job_path_job.replace('$DEPOT_ALL', depot_local)
    
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
        
        # Get git commit info
        git_info = git_get_info()
        
        # Get all available years
        conn = db_get_connection()
        cursor = conn.cursor()
        cursor.execute(f'SELECT DISTINCT job_year FROM {db_table} ORDER BY job_year DESC')
        years = [row['job_year'] for row in cursor.fetchall()]
        conn.close()
        
        return render_template('production.html',
                              logo_path=logo_relative,
                              db_table=db_table,
                              db_tables=list_db_tables,
                              git_info=git_info,
                              years=years)
    
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
    
    @flask_app.route('/api/open_app_directory', methods=['POST'])
    def api_open_app_directory():
        """API endpoint to open a job app directory in the system file browser"""
        data = request.get_json()
        job_path_job = data.get('job_path_job')
        app = data.get('app')  # Can be None for project-level opening
        subdir = data.get('subdir')  # Optional subdirectory
        
        if not job_path_job:
            return jsonify({'error': 'job_path_job parameter required'}), 400
        
        result = event_jobactive_navigate_to_app_dir(job_path_job, app, subdir)
        
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
        
        # Build UPDATE query dynamically
        set_clauses = []
        values = []
        for field in list_columns_editable:
            if field in data:
                set_clauses.append(f"{field} = ?")
                values.append(data[field])
        
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
            
            conn.close()
            return jsonify({'success': True, 'message': 'Job updated successfully'}), 200
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
        
        # Generate job path (using path_proj from config)
        job_path = os.path.join(path_proj, job_name) if path_proj else ''

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
        job_path_job = os.path.join(path_proj, job_year, job_name) if path_proj else ''
        job_path_rnd = os.path.join(path_rend, job_year, job_name) if path_rend else ''
        
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
            

            # Insert new job into database
            #cursor.execute(f"""
            #    INSERT INTO {db_table_proj} 
            #    (job_name, job_alias, job_state, job_year, job_user_id, job_user_name, 
            #     job_date_created, job_path_job, job_path_rnd)
            #    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            #""", (job_name, job_alias, 'active', current_year, user_id, user_name, 
            #      date_created, job_path_job, job_path_rnd))

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
                    vpr.vpr_job_create_directories(job_name, job_path_job, job_path_rnd)
                except Exception as dir_error:
                    # Job created in DB but directories failed - still return success
                    return jsonify({
                        'success': True, 
                        'job_name': job_name,
                        'warning': f'Job created but directory creation failed: {str(dir_error)}'
                    }), 200
            
            return jsonify({
                'success': True,
                'job_name': job_name,
                'job_alias': job_alias,
                'job_path': job_path_job,
                'job_data': {
                    'job_name': job_name,
                    'job_alias': job_alias,
                    'job_state': 'active',
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
    
    print("✓ Registered projectbrowser routes (production dashboard, job management API)")

