import sqlite3, os, math, webbrowser, platform
from flask import Flask, render_template, request, url_for, abort, session, redirect, send_file, jsonify, flash, get_flashed_messages, send_from_directory
import zipfile
from datetime import datetime
import io, zipfile, time
import shutil
import random
import cv2
from PIL import Image
import socket
from threading import Timer
import db_jobtools as dbj

try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

"""
Project Browser
This script will start a local webserver to visualize the project files
"""


depot_local = os.getenv('DEPOT_ALL')
path_proj = os.getenv('DUMMY_JOBS')
path_rend = os.getenv('DUMMY_REND')
path_db = os.getenv('DUMMY_DB')
file_sqlite = 'jobs.sqlite3'
db_table_proj = 'projects'
#path_db_json = os.path.join(path_db, 'json')
path_db_sqlite = os.path.join(path_db, 'sqlite', file_sqlite)

# Logo and database table configuration
path_base_media = os.path.join(depot_local, 'assetdepot', 'media')
file_logo_sqr = 'foxlito.png'
path_logo_sqr = os.path.join(path_base_media, 'dummy', 'thumbnails', file_logo_sqr)
list_db_tables = ['media_proj', 'media_arch']

#PER_PAGE = 10  # Number of items per page for pagination
CNT_ITEMS_VIEW_TABLE = 100  # Number of rows per page for table view
CNT_ITEMS_VIEW_GRID = 30  # Number of items per page for grid view
CNT_TOP_TOPICS = 20  # Number of top topics to display in word cloud`

# Note: This module can work as a standalone Flask app OR have its routes
# registered with another Flask app (e.g., mediabrowser)
app = Flask(__name__, static_folder=depot_local)
app.secret_key = 'your_secret_key_here'  # Set secret key for session

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


@app.route('/production', methods=['GET', 'POST'])
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


@app.route('/api/projects_by_year', methods=['GET'])
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


@app.route('/api/apps_by_project', methods=['GET'])
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


@app.route('/api/subdirs_by_app', methods=['GET'])
def api_subdirs_by_app():
    """API endpoint to get subdirectories for a selected app"""
    app = request.args.get('app')
    
    if not app:
        return jsonify({'error': 'App parameter required'}), 400
    
    # Get subdirectories from db_jobtools.dict_apps
    subdirs = dbj.dict_apps.get(app, [])
    
    return jsonify({'subdirs': subdirs})


@app.route('/api/open_app_directory', methods=['POST'])
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


@app.route('/api/action_jobactive_query', methods=['POST'])
def api_action_jobactive_query():
    """Query the database for a selected job by name or path and return full row."""
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


@app.route('/api/action_jobactive_dashboard_populate', methods=['POST'])
def api_action_jobactive_dashboard_populate():
    """Return the subset of job fields used to populate the Project Selection display."""
    # Reuse query logic
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
    fields = ['job_name',
              'job_alias',
              'job_state',
              'job_year',
              'job_path_job',
              'job_path_rnd',
              'job_user_id',
              'job_user_name',
              'job_edit_user_id',
              'job_edit_user_name',
              'job_edit_date',
              'job_date_start',
              'job_date_due',
              'job_charge1',
              'job_charge2',
              'job_charge3',
              'job_notes',
              'job_tags']
    job_out = {f: job.get(f, '') for f in fields}

    return jsonify({'success': True, 'job': job_out}), 200


def db_get_connection():
    
    """Connect to SQLite database and return connection with row factory enabled"""
    
    # Connects to the database and sets row_factory to sqlite3.Row 
    # to access columns by name (like a dictionary)
    # note that db table has the following columns:

    conn = sqlite3.connect(path_db_sqlite)
    conn.row_factory = sqlite3.Row 
    return conn


def register_routes(flask_app):
    """
    Register projectbrowser routes with an existing Flask app.
    This allows mediabrowser to host production routes.
    
    Args:
        flask_app: Flask application instance to register routes with
    """
    flask_app.add_url_rule('/production', 'page_production', page_production, methods=['GET', 'POST'])
    flask_app.add_url_rule('/api/projects_by_year', 'api_projects_by_year', api_projects_by_year, methods=['GET'])
    flask_app.add_url_rule('/api/apps_by_project', 'api_apps_by_project', api_apps_by_project, methods=['GET'])
    flask_app.add_url_rule('/api/subdirs_by_app', 'api_subdirs_by_app', api_subdirs_by_app, methods=['GET'])
    flask_app.add_url_rule('/api/open_app_directory', 'api_open_app_directory', api_open_app_directory, methods=['POST'])
    flask_app.add_url_rule('/api/action_jobactive_query', 'api_action_jobactive_query', api_action_jobactive_query, methods=['POST'])
    flask_app.add_url_rule('/api/action_jobactive_dashboard_populate', 'api_action_jobactive_dashboard_populate', api_action_jobactive_dashboard_populate, methods=['POST'])

