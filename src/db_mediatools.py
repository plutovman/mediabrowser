import os, sqlite3


list_ext_geometry = ['blend', 'stl', 'obj', 'fbx', '3mf', 'ply', 'geo', 'bgeo', 'gltf', 'glb', 'ma', 'mb', 'abc']
list_ext_images = ['exr', 'hdr', 'jpg', 'jpeg', 'png', 'tif', 'tiff', 'bmp']
list_ext_videos = ['mp4', 'mov', 'avi', 'mkv', 'wmv', 'flv', 'webm']
list_ext_audio = ['mp3', 'wav', 'flac', 'aac', 'ogg']
list_ext_documents = ['aep', 'ai', 'csv', 'nk', 'pdf', 'psb', 'psd', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'xls', 'xlsx']
list_ext_others = ['bzip','tar', 'tgz', 'zip']  # any other file extensions not in the above lists
                   
###############################################################################
###############################################################################
def db_sqlite_tablea_copy_to_tableb(db_path: str, table_a: str, table_b: str, path_target: str, list_exts: list = None):
    '''
    Copy data from sqlite table_a to table_b and organize files into archive structure.
    
    Args:
        db_path: Path to SQLite database
        table_a: Source table name (e.g., 'media_proj')
        table_b: Destination table name (e.g., 'media_arch')
        path_target: Base path for archive directory (e.g., '/path/to/archive')
        list_exts: Optional list of file extensions to filter (e.g., ['mp4', 'mov']). 
                   If None, all file types will be archived.
    
    Returns:
        dict: Statistics about the migration process
    '''
    
    stats = {
        'total_records': 0,
        'skipped_existing': 0,
        'skipped_extension': 0,
        'copied_records': 0,
        'copied_files': 0,
        'failed_copies': 0,
        'thumbnails_created': 0,
        'errors': []
    }
    
    # 1. Verify that db_path exists
    if not os.path.exists(db_path):
        error_msg = f"Database path does not exist: {db_path}"
        stats['errors'].append(error_msg)
        print(f"ERROR: {error_msg}")
        return stats
    
    # Make connection to database
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    except sqlite3.Error as e:
        error_msg = f"Failed to connect to database: {e}"
        stats['errors'].append(error_msg)
        print(f"ERROR: {error_msg}")
        return stats
    
    try:
        # 2. Verify that both tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        if table_a not in existing_tables:
            error_msg = f"Source table '{table_a}' does not exist"
            stats['errors'].append(error_msg)
            print(f"ERROR: {error_msg}")
            return stats
        
        if table_b not in existing_tables:
            error_msg = f"Destination table '{table_b}' does not exist"
            stats['errors'].append(error_msg)
            print(f"ERROR: {error_msg}")
            return stats
        
        # Verify both tables have file_id column
        cursor.execute(f"PRAGMA table_info({table_a})")
        table_a_columns = [row[1] for row in cursor.fetchall()]
        cursor.execute(f"PRAGMA table_info({table_b})")
        table_b_columns = [row[1] for row in cursor.fetchall()]
        
        if 'file_id' not in table_a_columns:
            error_msg = f"Source table '{table_a}' missing 'file_id' column"
            stats['errors'].append(error_msg)
            print(f"ERROR: {error_msg}")
            return stats
        
        if 'file_id' not in table_b_columns:
            error_msg = f"Destination table '{table_b}' missing 'file_id' column"
            stats['errors'].append(error_msg)
            print(f"ERROR: {error_msg}")
            return stats
        
        # 3. Get all records from table_a
        cursor.execute(f'SELECT * FROM {table_a}')
        records_a = cursor.fetchall()
        stats['total_records'] = len(records_a)
        
        print(f"Found {stats['total_records']} records in {table_a}")
        
        # Get existing file_ids in table_b for quick lookup
        cursor.execute(f'SELECT file_id FROM {table_b}')
        existing_file_ids = set(row[0] for row in cursor.fetchall())
        
        # 4. Loop through all records in table_a
        for record in records_a:
            file_id = record['file_id']
            
            # Skip if already exists in table_b
            if file_id in existing_file_ids:
                stats['skipped_existing'] += 1
                print(f"Skipping {file_id} - already exists in {table_b}")
                continue
            
            # Get file_path and file_name from record
            file_path = record['file_path'] if 'file_path' in record.keys() else None
            file_name = record['file_name'] if 'file_name' in record.keys() else None
            file_extension = record['file_type'] if 'file_type' in record.keys() else None
            
            if not file_path or not file_name:
                error_msg = f"Record {file_id} missing file_path or file_name"
                stats['errors'].append(error_msg)
                print(f"WARNING: {error_msg}")
                continue
            
            # Filter by list_exts if provided
            if list_exts is not None:
                if file_extension not in list_exts:
                    stats['skipped_extension'] += 1
                    print(f"Skipping {file_id} - extension '{file_extension}' not in filter list")
                    continue
            
            # Extract file extension
            #file_extension = os.path.splitext(file_name)[1].lstrip('.').lower()
            
            # Determine subdirectory based on extension
            if file_extension in list_ext_geometry:
                subdir = 'geometry'
            elif file_extension in list_ext_images:
                subdir = 'images'
            elif file_extension in list_ext_videos:
                subdir = 'videos'
            elif file_extension in list_ext_audio:
                subdir = 'audio'
            elif file_extension in list_ext_documents:
                subdir = 'documents'
            else:
                subdir = 'others'
            
            # Build source path (handle $DEPOT_ALL placeholder)
            path_src = file_path.replace('$DEPOT_ALL', os.getenv('DEPOT_ALL', ''))
            
            # Build destination path
            path_dst = os.path.join(path_target, subdir)
            
            # Copy file to archive
            copy_result = db_media_copy_patha_to_pathb(
                patha=os.path.dirname(path_src),
                pathb=path_dst,
                file_name=file_name,
                file_extension=file_extension
            )
            
            if copy_result['success']:
                # Update file_path to reflect new archive location with symbolic path
                depot_local = os.getenv('DEPOT_ALL', '')
                path_dst_full = os.path.join(path_dst, file_name)
                path_dst_symbolic = path_dst_full.replace(depot_local, '$DEPOT_ALL')
                
                # Convert record to dict and update file_path
                record_dict = dict(record)
                record_dict['file_path'] = path_dst_symbolic
                
                # Copy record to table_b with updated file_path
                column_names = ', '.join(record_dict.keys())
                placeholders = ', '.join(['?' for _ in record_dict.keys()])
                insert_query = f'INSERT INTO {table_b} ({column_names}) VALUES ({placeholders})'
                
                try:
                    cursor.execute(insert_query, tuple(record_dict.values()))
                    conn.commit()
                    conn.commit()
                    stats['copied_records'] += 1
                    stats['copied_files'] += 1
                    
                    if copy_result.get('thumbnail_created'):
                        stats['thumbnails_created'] += 1
                    
                    print(f"Copied {file_id}: {file_name} -> {subdir}/")
                    
                except sqlite3.Error as e:
                    error_msg = f"Failed to insert record {file_id}: {e}"
                    stats['errors'].append(error_msg)
                    print(f"ERROR: {error_msg}")
                    stats['failed_copies'] += 1
            else:
                error_msg = f"Failed to copy file {file_name}: {copy_result.get('error', 'Unknown error')}"
                stats['errors'].append(error_msg)
                print(f"ERROR: {error_msg}")
                stats['failed_copies'] += 1
        
        # Print summary
        print("\n" + "="*60)
        print("ARCHIVE MIGRATION SUMMARY")
        print("="*60)
        print(f"Total records in source:     {stats['total_records']}")
        print(f"Skipped (already archived):  {stats['skipped_existing']}")
        print(f"Skipped (extension filter):  {stats['skipped_extension']}")
        print(f"Records copied to archive:   {stats['copied_records']}")
        print(f"Files copied:                {stats['copied_files']}")
        print(f"Thumbnails created:          {stats['thumbnails_created']}")
        print(f"Failed copies:               {stats['failed_copies']}")
        print(f"Errors encountered:          {len(stats['errors'])}")
        print("="*60)
        
    except Exception as e:
        error_msg = f"Unexpected error during migration: {e}"
        stats['errors'].append(error_msg)
        print(f"ERROR: {error_msg}")
    
    finally:
        conn.close()
    
    return stats

# end of def db_sqlite_tablea_copy_to_tableb(db_path: str, table_a: str, table_b: str, path_target: str):

###############################################################################
###############################################################################
def db_media_copy_patha_to_pathb(patha: str, pathb: str, file_name: str, file_extension: str):
    '''
    Copy media file from patha to pathb with validation and post-processing.
    
    Args:
        patha: Source directory path
        pathb: Destination directory path
        file_name: Name of file to copy
        file_extension: File extension (without dot)
    
    Returns:
        dict: Result with 'success' boolean, optional 'thumbnail_created' boolean, and 'error' message if failed
    '''
    
    result = {
        'success': False,
        'thumbnail_created': False,
        'error': None
    }
    
    try:
        # Extract file extension from file name (normalize)
        file_ext = os.path.splitext(file_name)[1].lstrip('.').lower()
        
        # Build full paths
        file_name_dst = file_name.replace(' ', '_')  # replace spaces with underscores
        path_src = os.path.join(patha, file_name)
        path_dst = os.path.join(pathb, file_name_dst)
        
        # 1. Verify source path exists and is readable
        if not os.path.exists(path_src):
            result['error'] = f"Source file does not exist: {path_src}"
            return result
        
        if not os.path.isfile(path_src):
            result['error'] = f"Source path is not a file: {path_src}"
            return result
        
        if not os.access(path_src, os.R_OK):
            result['error'] = f"Source file is not readable: {path_src}"
            return result
        
        # 2. Verify/create destination directory
        try:
            os.makedirs(pathb, exist_ok=True)
        except OSError as e:
            result['error'] = f"Failed to create destination directory {pathb}: {e}"
            return result
        
        # 3. Copy the file
        try:
            import shutil
            
            # Special handling for video formats that need conversion to MP4
            formats_to_convert = ['wmv', 'mov', 'avi', 'mkv', 'flv', 'webm']
            
            if file_ext in formats_to_convert:
                # Build MP4 output path
                file_name_base = os.path.splitext(file_name_dst)[0]
                file_name_mp4 = f"{file_name_base}.mp4"
                path_dst_mp4 = os.path.join(pathb, file_name_mp4)
                
                # Convert to MP4 using dedicated function
                conversion_success = db_media_video_to_mp4(path_src, file_ext, path_dst_mp4)
                
                if conversion_success:
                    # Update paths for thumbnail generation
                    path_dst = path_dst_mp4
                    file_ext = 'mp4'
                    result['success'] = True
                else:
                    result['error'] = f"Failed to convert {file_ext.upper()} to MP4"
                    return result
            else:
                # Standard copy for all other file types (including native mp4)
                shutil.copy2(path_src, path_dst)  # copy2 preserves metadata
                result['success'] = True
        except (IOError, OSError, shutil.Error) as e:
            result['error'] = f"Failed to copy file: {e}"
            return result
        
        # 4. Post-processing for specific file types
        # For video files (mp4), create a thumbnail image at 25% progress
        if file_ext in ['mp4']:
            try:
                # Build thumbnail path (same name but .png extension)
                file_name_base = os.path.splitext(file_name_dst)[0]
                thumb_name = f"{file_name_base}.png"
                path_thumb = os.path.join(pathb, thumb_name)
                
                # Get video duration to calculate 25% timestamp
                import cv2
                cap = cv2.VideoCapture(path_dst)
                
                if cap.isOpened():
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    cap.release()
                    
                    if fps > 0 and frame_count > 0:
                        duration = frame_count / fps
                        time_at_25_percent = duration * 0.25
                        
                        # Capture thumbnail at 25% mark
                        db_media_thumbnail_capture_video(
                            path_video=path_dst,
                            path_thumb=path_thumb,
                            time_sec=time_at_25_percent
                        )
                        result['thumbnail_created'] = True
                        print(f"  Created thumbnail: {thumb_name}")
                    else:
                        # Fallback to 1 second if we can't determine duration
                        db_media_thumbnail_capture_video(
                            path_video=path_dst,
                            path_thumb=path_thumb,
                            time_sec=1.0
                        )
                        result['thumbnail_created'] = True
                        print(f"  Created thumbnail (1s fallback): {thumb_name}")
                        
            except Exception as e:
                # Don't fail the entire copy if thumbnail creation fails
                print(f"  Warning: Failed to create thumbnail for {file_name}: {e}")
                result['thumbnail_created'] = False
        
        return result
        
    except Exception as e:
        result['error'] = f"Unexpected error: {e}"
        return result 

def db_media_thumbnail_capture_video(path_video: str, path_thumb: str, time_sec: float = 1.0):

    '''
    capture a thumbnail image from a video file at specified time (in seconds)
    '''

    import cv2
    import os


    if not os.path.exists(path_video):
        raise FileNotFoundError(f"Video file not found: {path_video}")

    cap = cv2.VideoCapture(path_video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_number = int(fps * time_sec)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    ret, frame = cap.read()
    if ret:
        cv2.imwrite(path_thumb, frame)
    else:
        raise RuntimeError(f"Failed to capture thumbnail from video: {path_video}")

    cap.release()


def db_media_video_to_mp4(path_src: str, file_ext: str, path_dst_mp4: str) -> bool:
    """
    Convert various video formats to MP4 using ffmpeg.
    
    Supports: mov, avi, mkv, wmv, flv, webm
    
    Args:
        path_src: Source video file path
        file_ext: Source file extension (without dot)
        path_dst_mp4: Destination MP4 file path
    
    Returns:
        bool: True if conversion succeeded, False otherwise
    """
    
    # Validate source file exists
    if not os.path.exists(path_src):
        print(f"ERROR: Source video not found: {path_src}")
        return False
    
    # List of supported formats for conversion
    supported_formats = ['mov', 'avi', 'mkv', 'wmv', 'flv', 'webm']
    
    if file_ext.lower() not in supported_formats:
        print(f"ERROR: Unsupported format for conversion: {file_ext}")
        return False
    
    try:
        import subprocess
        
        # Build ffmpeg command with format-specific optimizations
        cmd = [
            'ffmpeg',
            '-i', path_src,              # Input file
            '-c:v', 'libx264',           # Video codec: H.264
            '-crf', '23',                # Quality (0=lossless, 51=worst, 23=default/good)
            '-preset', 'medium',         # Encoding speed vs compression efficiency
            '-c:a', 'aac',               # Audio codec: AAC
            '-b:a', '128k',              # Audio bitrate
            '-movflags', '+faststart',   # Enable streaming/web playback
            '-y',                        # Overwrite output file without prompting
            path_dst_mp4
        ]
        
        # Execute ffmpeg conversion
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Verify output file was created
        if os.path.exists(path_dst_mp4):
            file_size = os.path.getsize(path_dst_mp4) / (1024 * 1024)  # MB
            print(f"  Converted {file_ext.upper()} to MP4: {os.path.basename(path_dst_mp4)} ({file_size:.2f} MB)")
            return True
        else:
            print(f"ERROR: Conversion completed but output file not found: {path_dst_mp4}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"ERROR: FFmpeg conversion failed for {path_src}")
        print(f"  stderr: {e.stderr}")
        return False
        
    except FileNotFoundError:
        print("ERROR: FFmpeg not found. Install with: brew install ffmpeg")
        return False
        
    except Exception as e:
        print(f"ERROR: Unexpected error during conversion: {e}")
        return False    

def db_media_video_info(file_path: str):
    """
    Retrieve MP4 video metadata via mutagen.mp4
    We want to get title, date, comment, description and encoder info
    return a dictionary with {'status': [suddess/fail], 'data': {metadata dict}}
    """
    from mutagen.mp4 import MP4
    
    result = {
        'status': 'fail',
        'data': {},
        'error': None
    }
    
    try:
        # Verify file exists
        if not os.path.exists(file_path):
            result['error'] = f"File not found: {file_path}"
            return result
        
        # Load MP4 file with mutagen
        video = MP4(file_path)
        
        # Extract metadata tags
        metadata = {}
        
        # Title
        if '\xa9nam' in video.tags:
            metadata['title'] = video.tags['\xa9nam'][0]
        
        # Date
        if '\xa9day' in video.tags:
            metadata['date'] = video.tags['\xa9day'][0]
        
        # Comment
        if '\xa9cmt' in video.tags:
            metadata['comment'] = video.tags['\xa9cmt'][0]
        
        # Description
        if 'desc' in video.tags:
            metadata['description'] = video.tags['desc'][0]
        elif '\xa9des' in video.tags:
            metadata['description'] = video.tags['\xa9des'][0]
        
        # Encoder
        if '\xa9too' in video.tags:
            metadata['encoder'] = video.tags['\xa9too'][0]
        
        result['data'] = metadata
        result['status'] = 'success'
        
    except Exception as e:
        result['error'] = f"Error reading MP4 metadata: {str(e)}"
        result['status'] = 'fail'
    
    return result