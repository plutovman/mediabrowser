#!/usr/bin/env python3
"""
Job Creation Utility
====================
Standalone command-line utility to create new jobs in the project database.
Replicates the behavior of the production 'new job dashboard' web interface.

Usage:
    python util_job_make.py

This utility will:
1. Prompt for a job base name
2. Validate the base name (reject invalid characters)
3. Check the database for existing jobs to determine revision
4. Generate job_name and job_alias
5. Display summary and request confirmation
6. Create job entry in database
7. Create job and render directories
8. Set up environment file
9. Create navigation alias file
"""

import sqlite3
import os
import sys
from datetime import datetime

# Import project modules
import db_jobtools as dbj
import vpr_jobtools as vpr


# ============================================================================
# CONFIGURATION
# ============================================================================

def get_configuration():
    """Load configuration from environment variables"""
    config = {}
    
    # Required environment variables
    config['depot_local'] = os.getenv('DEPOT_ALL')
    if not config['depot_local']:
        raise EnvironmentError("DEPOT_ALL environment variable must be set")
    
    config['path_proj_netwk'] = os.getenv('DUMMY_JOBS_NETWK')
    config['path_rend_netwk'] = os.getenv('DUMMY_REND_NETWK')
    config['path_proj_local'] = os.getenv('DUMMY_JOBS_LOCAL')
    config['path_rend_local'] = os.getenv('DUMMY_REND_LOCAL')
    
    config['path_db'] = os.getenv('DUMMY_DB')
    if not config['path_db']:
        raise EnvironmentError("DUMMY_DB environment variable must be set")
    
    # File and path configuration
    config['file_sqlite'] = 'db_projects.sqlite3'
    config['file_projects_aliases'] = 'db_projects.tcsh'
    config['file_project_env'] = 'project_env.tcsh'
    
    config['db_table_proj'] = 'projects'
    config['path_db_sqlite'] = os.path.join(config['path_db'], 'sqlite', config['file_sqlite'])
    config['path_db_aliases'] = os.path.join(config['path_db'], 'tcsh', config['file_projects_aliases'])
    
    # Resources path
    path_script = os.path.dirname(os.path.abspath(__file__))
    config['path_resources'] = os.path.join(path_script, 'resources')
    config['path_project_env_in'] = os.path.join(config['path_resources'], config['file_project_env'])
    
    return config


def db_get_connection(path_db_sqlite):
    """Connect to SQLite database and return connection with row factory enabled"""
    conn = sqlite3.connect(path_db_sqlite)
    conn.row_factory = sqlite3.Row 
    return conn


# ============================================================================
# JOB VALIDATION & GENERATION
# ============================================================================

def validate_job_base(job_base):
    """
    Validate job base name using vpr_jobtools validation.
    
    Returns:
        tuple: (is_valid, reason)
    """
    if not job_base:
        return False, 'Job base cannot be empty'
    
    return vpr.vpr_job_base_is_valid(job_base)


def get_next_revision(config, job_base):
    """
    Query database for existing jobs and determine next revision letter.
    
    Args:
        config: Configuration dictionary
        job_base: Base name for the job
        
    Returns:
        str: Next revision letter (e.g., 'a', 'b', 'c')
    """
    year = datetime.now().strftime('%Y')
    year_short = year[-2:]  # get last two digits of year
    job_partial = '{}_{}'.format(year_short, job_base)
    
    job_revision_current = ''
    
    try:
        conn = db_get_connection(config['path_db_sqlite'])
        cursor = conn.cursor()
        
        # Match pattern: job_partial followed by underscore and single character
        cursor.execute(
            f"SELECT job_name FROM {config['db_table_proj']} WHERE job_name LIKE ?",
            (job_partial + '_%',)
        )
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
            print(f"   Found existing jobs with revisions: {', '.join(sorted(revisions))}")
            
    except Exception as e:
        print(f"   Warning: Error querying database for revisions: {e}")
        job_revision_current = ''
    
    job_revision_next = vpr.vpr_job_rev_set(job_rev=job_revision_current)
    return job_revision_next


def generate_job_info(config, job_base, revision):
    """
    Generate job_name and job_alias from base name and revision.
    
    Args:
        config: Configuration dictionary
        job_base: Base name for the job
        revision: Revision letter
        
    Returns:
        tuple: (job_name, job_alias) or (None, None) if generation fails
    """
    result = vpr.vpr_job_name_create(job_base, revision)
    
    if result is None:
        return None, None
    
    return result


# ============================================================================
# JOB CREATION
# ============================================================================

def create_job_in_database(config, job_info):
    """
    Create job entry in the database.
    
    Args:
        config: Configuration dictionary
        job_info: Dictionary with job information
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Generate unique job_id
        job_id = dbj.db_id_create(
            db_sqlite_path=config['path_db_sqlite'],
            db_table=config['db_table_proj'],
            id_column='job_id'
        )
        
        # Prepare job data
        job_data = {
            'job_id': job_id,
            'job_name': job_info['job_name'],
            'job_alias': job_info['job_alias'],
            'job_state': job_info['job_state'],
            'job_year': job_info['job_year'],
            'job_user_id': job_info['job_user_id'],
            'job_user_name': job_info['job_user_name'],
            'job_edit_user_id': job_info['job_user_id'],
            'job_edit_user_name': job_info['job_user_name'],
            'job_edit_date': job_info['job_date_created'],
            'job_notes': job_info['job_notes'],
            'job_tags': job_info['job_tags'],
            'job_date_created': job_info['job_date_created'],
            'job_date_due': job_info['job_date_due'],
            'job_charge1': job_info['job_charge1'],
            'job_charge2': job_info['job_charge2'],
            'job_charge3': job_info['job_charge3'],
            'job_path_job': job_info['job_path_job_symbolic'],
            'job_path_rnd': job_info['job_path_rnd_symbolic'],
            'job_apps': job_info['job_apps']
        }
        
        # Check if job already exists
        conn = db_get_connection(config['path_db_sqlite'])
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT job_name FROM {config['db_table_proj']} WHERE job_name = ?",
            (job_info['job_name'],)
        )
        existing = cursor.fetchone()
        
        if existing:
            conn.close()
            print(f"   ERROR: Job '{job_info['job_name']}' already exists in database!")
            return False
        
        # Insert new job
        columns = ', '.join(job_data.keys())
        placeholders = ', '.join('?' for _ in job_data)
        sql_insert = f'INSERT INTO {config["db_table_proj"]} ({columns}) VALUES ({placeholders})'
        
        conn.execute(sql_insert, tuple(job_data.values()))
        conn.commit()
        conn.close()
        
        print(f"   [+] Job added to database (ID: {job_id})")
        return True
        
    except Exception as e:
        print(f"   ERROR: Failed to create job in database: {e}")
        return False


def create_job_directories(config, job_info):
    """
    Create job and render directories on filesystem.
    
    Args:
        config: Configuration dictionary
        job_info: Dictionary with job information
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        vpr.vpr_job_create_directories(
            job_name=job_info['job_name'],
            path_job=job_info['job_path_job'],
            path_rnd=job_info['job_path_rnd']
        )
        print(f"   [+] Created job directory: {job_info['job_path_job']}")
        print(f"   [+] Created render directory: {job_info['job_path_rnd']}")
        return True
    except Exception as e:
        print(f"   WARNING: Failed to create directories: {e}")
        return False


def setup_job_environment(config, job_info):
    """
    Set up job environment file.
    
    Args:
        config: Configuration dictionary
        job_info: Dictionary with job information
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        vpr.vpr_job_edit_environment(
            job_name=job_info['job_name'],
            path_job=job_info['job_path_job'],
            path_job_env=config['path_project_env_in'],
            job_year=job_info['job_year']
        )
        print(f"   [+] Created environment file")
        return True
    except Exception as e:
        print(f"   WARNING: Failed to create environment file: {e}")
        return False


def create_nav_file(config, job_info):
    """
    Create navigation alias file.
    
    Args:
        config: Configuration dictionary
        job_info: Dictionary with job information
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        dbj.db_jobs_nav_create(
            db_path=config['path_db_sqlite'],
            db_table=config['db_table_proj'],
            nav_path=job_info['job_path_job'],
            nav_file=config['path_db_aliases']
        )
        print(f"   [+] Created navigation alias file")
        return True
    except Exception as e:
        print(f"   WARNING: Failed to create navigation file: {e}")
        return False


# ============================================================================
# USER INTERACTION
# ============================================================================

def prompt_for_job_base():
    """
    Prompt user for job base name with validation loop.
    
    Returns:
        str: Valid job base name
    """
    print("\n" + "=" * 70)
    print("JOB CREATION UTILITY")
    print("=" * 70)
    print("\nEnter a job base name (e.g., 'logo_anim', 'product_spot', 'banner_ad')")
    print("Rules:")
    print("  - Only lowercase letters, numbers, and underscores allowed")
    print("  - No spaces or special characters")
    print("  - Must start/end with a letter")
    print("  - Keep it descriptive but concise")
    print()
    
    while True:
        job_base = input("Job base name: ").strip()
        
        if not job_base:
            print("   [!] Job base cannot be empty. Please try again.\n")
            continue
        
        is_valid, reason = validate_job_base(job_base)
        
        if is_valid:
            return job_base
        else:
            print(f"   [!] Invalid: {reason}")
            print("   Please try again.\n")


def display_job_summary(config, job_info):
    """
    Display comprehensive job summary for user review.
    
    Args:
        config: Configuration dictionary
        job_info: Dictionary with job information
    """
    print("\n" + "=" * 70)
    print("JOB SUMMARY")
    print("=" * 70)
    print(f"\nJob Name:      {job_info['job_name']}")
    print(f"Job Alias:     {job_info['job_alias']}")
    print(f"Job Year:      {job_info['job_year']}")
    print(f"Job State:     {job_info['job_state']}")
    print(f"Created By:    {job_info['job_user_name']} ({job_info['job_user_id']})")
    print(f"Date Created:  {job_info['job_date_created']}")
    print(f"\nJob Path:      {job_info['job_path_job']}")
    print(f"Render Path:   {job_info['job_path_rnd']}")
    print(f"\nApplications:  {job_info['job_apps']}")
    print("=" * 70)


def confirm_creation():
    """
    Ask user for confirmation to proceed with job creation.
    
    Returns:
        bool: True if user confirms, False otherwise
    """
    print("\nProceed with job creation?")
    while True:
        response = input("Enter 'yes' to create, 'no' to cancel: ").strip().lower()
        
        if response in ['yes', 'y']:
            return True
        elif response in ['no', 'n']:
            return False
        else:
            print("   Please enter 'yes' or 'no'.")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    try:
        # Load configuration
        config = get_configuration()
        
        # Step 1: Prompt for job base name
        job_base = prompt_for_job_base()
        
        print(f"\n[+] Job base name accepted: '{job_base}'")
        
        # Step 2: Determine revision
        print("\nChecking database for existing jobs...")
        revision = get_next_revision(config, job_base)
        print(f"   Next revision: '{revision}'")
        
        # Step 3: Generate job name and alias
        print("\nGenerating job information...")
        job_name, job_alias = generate_job_info(config, job_base, revision)
        
        if not job_name or not job_alias:
            print("   ERROR: Failed to generate job name and alias")
            sys.exit(1)
        
        print(f"   Job name:  {job_name}")
        print(f"   Job alias: {job_alias}")
        
        # Step 4: Prepare full job information
        year = datetime.now().strftime('%Y')
        job_user_id = os.getenv('USER', 'unknown')
        job_user_name = job_user_id
        job_date_created = datetime.now().strftime('%Y-%m-%d')
        
        # Generate paths
        job_path_job = os.path.join(config['path_proj_netwk'], year, job_name) if config['path_proj_netwk'] else ''
        job_path_rnd = os.path.join(config['path_rend_netwk'], year, job_name) if config['path_rend_netwk'] else ''
        
        job_path_job_symbolic = job_path_job.replace(config['depot_local'], '$DEPOT_ALL')
        job_path_rnd_symbolic = job_path_rnd.replace(config['depot_local'], '$DEPOT_ALL')
        
        job_info = {
            'job_name': job_name,
            'job_alias': job_alias,
            'job_state': 'active',
            'job_year': year,
            'job_user_id': job_user_id,
            'job_user_name': job_user_name,
            'job_date_created': job_date_created,
            'job_notes': '',
            'job_tags': '',
            'job_date_due': job_date_created,
            'job_charge1': '',
            'job_charge2': '',
            'job_charge3': '',
            'job_path_job': job_path_job,
            'job_path_rnd': job_path_rnd,
            'job_path_job_symbolic': job_path_job_symbolic,
            'job_path_rnd_symbolic': job_path_rnd_symbolic,
            'job_apps': ','.join(dbj.list_dirs_apps)
        }
        
        # Step 5: Display summary and get confirmation
        display_job_summary(config, job_info)
        
        if not confirm_creation():
            print("\n[x] Job creation cancelled by user.")
            sys.exit(0)
        
        # Step 6: Create job in database
        print("\n" + "=" * 70)
        print("CREATING JOB")
        print("=" * 70)
        print("\n1. Adding job to database...")
        if not create_job_in_database(config, job_info):
            sys.exit(1)
        
        # Step 7: Create directories
        print("\n2. Creating directories...")
        if job_path_job and job_path_rnd:
            create_job_directories(config, job_info)
        else:
            print("   WARNING: Job or render paths not configured")
        
        # Step 8: Setup environment
        print("\n3. Setting up environment...")
        setup_job_environment(config, job_info)
        
        # Step 9: Create nav file
        print("\n4. Creating navigation file...")
        create_nav_file(config, job_info)
        
        # Success message
        print("\n" + "=" * 70)
        print("[+] JOB CREATION COMPLETE")
        print("=" * 70)
        print(f"\nJob '{job_name}' has been successfully created!")
        print(f"\nJob directory:    {job_path_job}")
        print(f"Render directory: {job_path_rnd}")
        print()
        
    except KeyboardInterrupt:
        print("\n\n[x] Job creation cancelled by user (Ctrl+C).")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n[x] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
