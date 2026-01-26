import sqlite3, os, math, webbrowser
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

@app.route('/production', methods=['GET', 'POST'])
def page_production():
    
    """Production interface - minimal page for future functionality"""
    
    # Production uses 'media_proj' table
    db_table = db_table_proj
    
    # Logo relative path for template
    logo_relative = os.path.relpath(path_logo_sqr, depot_local)
    
    # Get git commit info
    git_info = git_get_info()
    
    return render_template('production.html',
                          logo_path=logo_relative,
                          db_table=db_table,
                          db_tables=list_db_tables,
                          git_info=git_info)


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

