"""
This utility populates an archive directory with media files copied from a media SQLite database.
It organizes files into subdirectories based on their file types
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

list_archive_extensions = ['mp4']

# ============================================================================
# EXECUTE ARCHIVE MIGRATION
# ============================================================================

if __name__ == "__main__":
    print("\\n" + "="*60)
    print("MEDIA ARCHIVE MIGRATION UTILITY")
    print("="*60)
    print(f"Source Database: {path_db}")
    print(f"Source Table:    {db_table_proj}")
    print(f"Target Table:    {db_table_arch}")
    print(f"Archive Path:    {path_base_archive}")
    print("="*60 + "\\n")
    
    # Verify database exists before starting
    if not os.path.exists(path_db):
        print(f"ERROR: Database not found at {path_db}")
        exit(1)
    
    # Execute the migration
    print("Starting migration process...\\n")
    stats = dbm.db_sqlite_tablea_copy_to_tableb(
        db_path=path_db,
        table_a=db_table_proj,
        table_b=db_table_arch,
        path_target=path_base_archive,
        list_exts=list_archive_extensions
    )
    
    # Report any errors in detail
    if stats['errors']:
        print("\\n" + "="*60)
        print("ERRORS ENCOUNTERED:")
        print("="*60)
        for i, error in enumerate(stats['errors'], 1):
            print(f"{i}. {error}")
        print("="*60)
    
    # Exit with appropriate code
    if stats['failed_copies'] > 0:
        print("\\nMigration completed with errors.")
        exit(1)
    else:
        print("\\nMigration completed successfully!")
        exit(0)