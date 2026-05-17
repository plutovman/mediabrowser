"""
This utility edits the existing sqlite archive to include the following new fields:
file_state = 'active'
file_state_date = current date in 'YYYY-MM-DD' format
file_date = current date in 'YYYY-MM-DD' format
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

import db_jobtools as dbj
import vpr_jobtools as vpr
import db_mediatools as dbm


# ============================================================================
# CONFIGURATION & GLOBALS
# ============================================================================

depot_local = os.getenv('DEPOT_ALL')
if not depot_local:
    raise EnvironmentError("DEPOT_ALL environment variable must be set")


path_base_media = os.path.join(depot_local, 'assetdepot', 'media')
path_base_thumbs = os.path.join(path_base_media, 'dummy', 'thumbnails')
path_base_archive = os.path.join(path_base_media, 'archive')

file_sqlite_media = 'media_dummy.sqlite'
path_db_media = os.path.join(depot_local, 'assetdepot', 'media', 'dummy', 'db')
path_db = os.path.join(path_db_media, file_sqlite_media)

# Database tables
db_table_proj = 'media_proj'
db_table_arch = 'media_arch'
list_tables = [db_table_proj, db_table_arch]

list_archive_extensions = ['mp4']

file_date = 'file_date'
file_state = 'file_state'
file_state_date = 'file_state_date'


def add_column_if_not_exists(cursor, table_name, column_name, column_type, default_value):
    try:
        # Check if column already exists
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        if column_name not in columns:
            # Add the column
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            print(f"Added column '{column_name}' to table '{table_name}'")
            # Initialize the column with default value
            cursor.execute(f"UPDATE {table_name} SET {column_name} = ?", (default_value,))
            print(f"Initialized column '{column_name}' in table '{table_name}' with default value '{default_value}'")
        else:
            print(f"Column '{column_name}' already exists in table '{table_name}'")
    except sqlite3.OperationalError as e:
        print(f"ERROR: Could not add column '{column_name}' to table '{table_name}': {e}")


def copy_values_from_column(cursor, table, file_date, file_state_date):
    """
    Copy values row-by-row from file_date into file_state_date.
    Intended to be run as a separate step.
    """
    try:
        # Validate that both columns exist
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]

        if file_date not in columns:
            print(f"ERROR: Column '{file_date}' not found in table '{table}'")
            return
        if file_state_date not in columns:
            print(f"ERROR: Column '{file_state_date}' not found in table '{table}'")
            return

        # Copy source values into destination
        cursor.execute(
            f"UPDATE {table} SET {file_state_date} = {file_date} "
            f"WHERE {file_date} IS NOT NULL"
        )
        print(
            f"Copied values from '{file_date}' to '{file_state_date}' "
            f"in table '{table}' ({cursor.rowcount} rows affected)"
        )

    except sqlite3.OperationalError as e:
        print(f"ERROR: Could not copy values in table '{table}': {e}")

# ============================================================================
# EXECUTE ARCHIVE UPDATE
# ============================================================================

if __name__ == "__main__":
    print("\\n" + "="*60)
    print("MEDIA ARCHIVE UPDATE UTILITY")
    print("="*60)
    print(f"Source Database: {path_db}")
    print(f"Table Proj:    {db_table_proj}")
    print(f"Table Arch:    {db_table_arch}")
    print("="*60 + "\\n")
    
    # Verify database exists before starting
    if not os.path.exists(path_db):
        print(f"ERROR: Database not found at {path_db}")
        exit(1)
    # Connect to the database
    conn = sqlite3.connect(path_db)
    cursor = conn.cursor()

    # Get current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    past_date = '2026-05-01'  # Example past date for testing

    # Function to add columns if they don't exist
    # Add and initialize columns for each table
    #for table in list_tables:
    #    add_column_if_not_exists(cursor, table, file_date, "TEXT", past_date)
    #    add_column_if_not_exists(cursor, table, file_state, "TEXT", "active")
    #    add_column_if_not_exists(cursor, table, file_state_date, "TEXT", current_date)

    # Run this separately when you want to backfill file_state_date from file_date.
    for table in list_tables:
        copy_values_from_column(cursor, table, file_date, file_state_date)

    # Commit changes and close the connection
    conn.commit()
    conn.close()

    print("\nDatabase update complete!")
    print("="*60)