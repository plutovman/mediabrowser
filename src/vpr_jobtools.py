import os, platform, inspect, subprocess
import db_jobtools as dbj 
import datetime

def vpr_file_parts_get(file_name: str):
    """
    split file_name by '_' and return a list of parts
    """
    list_parts = file_name.split('_')
    return list_parts

# end of def vpr_file_parts_get(file_name: str):

def vpr_dir_synchronize(path_local: str, path_netwk: str, direction: str):
    """
    OS-aware directory synchronization using rsync (Linux/macOS/WSL) or robocopy (Windows).
    
    Args:
        path_local: Local directory path
        path_netwk: Network directory path
        direction: 'LOCAL TO NETWK' or 'NETWK TO LOCAL'
    
    Returns:
        bool: True if synchronization succeeded, False otherwise
    
    Notes:
        - Ignores hidden files/directories (starting with '.')
        - Ignores common temporary and system files
        - Uses archive mode to preserve permissions and timestamps
        - Deletes files in destination that don't exist in source
    """

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    # Detect operating system
    system = platform.system()
    
    # Determine source and destination based on direction
    if direction == 'LOCAL TO NETWK':
        source = path_local
        destination = path_netwk
    elif direction == 'NETWK TO LOCAL':
        source = path_netwk
        destination = path_local
    else:
        print(dbh + ' Invalid direction: {}'.format(direction))
        return False
    
    # Validate paths exist
    if not os.path.exists(source):
        print(dbh + ' Source path does not exist: {}'.format(source))
        return False
    
    # Create destination if it doesn't exist
    if not os.path.exists(destination):
        try:
            os.makedirs(destination, exist_ok=True)
            print(dbh + ' Created destination directory: {}'.format(destination))
        except Exception as e:
            print(dbh + ' Failed to create destination: {}'.format(e))
            return False

    # Build command based on OS
    if system == 'Windows':
        # Use robocopy for Windows
        # /MIR = Mirror (copy all, delete extras)
        # /XA:SH = Exclude system and hidden files
        # /XD = Exclude directories
        # /XF = Exclude files
        # /R:3 = Retry 3 times on failure
        # /W:5 = Wait 5 seconds between retries
        # /MT:8 = Use 8 threads for faster copying
        # /NFL = No file list (reduce output)
        # /NDL = No directory list
        # /NP = No progress percentage
        # /LOG = Log to file (optional)
        
        cmd = [
            'robocopy',
            source,
            destination,
            '/MIR',                    # Mirror directory tree
            '/R:3',                    # Retry 3 times
            '/W:5',                    # Wait 5 seconds between retries
            '/MT:8',                   # Multi-threaded (8 threads)
            '/XA:SH',                  # Exclude system and hidden files
            '/XD',                     # Exclude these directories:
            '.*',                      # Hidden directories (starting with .)
            '__pycache__',
            'node_modules',
            '.git',
            '.svn',
            '.DS_Store',
            'Thumbs.db',
            '/XF',                     # Exclude these files:
            '.*',                      # Hidden files (starting with .)
            '*.tmp',
            '*.temp',
            '*.log',
            '*.swp',
            '*.swo',
            '*~',
            'desktop.ini',
            '.DS_Store',
            'Thumbs.db'
        ]
        
        print(dbh + ' Executing robocopy: {} -> {}'.format(source, destination))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            # Robocopy return codes: 0-7 are success, 8+ are errors
            if result.returncode < 8:
                print(dbh + ' Robocopy completed successfully (exit code: {})'.format(result.returncode))
                return True
            else:
                print(dbh + ' Robocopy failed with exit code: {}'.format(result.returncode))
                print(dbh + ' Error output: {}'.format(result.stderr))
                return False
        except Exception as e:
            print(dbh + ' Robocopy command failed: {}'.format(e))
            return False
            
    else:
        # Use rsync for Linux, macOS, and WSL
        # -a = archive mode (recursive, preserve permissions, times, etc.)
        # -v = verbose
        # -h = human-readable output
        # --delete = delete files in dest that don't exist in source
        # --exclude = exclude patterns
        # --progress = show progress during transfer
        
        # Ensure paths end with / for rsync
        if not source.endswith('/'):
            source += '/'
        if not destination.endswith('/'):
            destination += '/'
        
        cmd = [
            'rsync',
            '-avh',                    # Archive, verbose, human-readable
            '--delete',                # Delete extraneous files from dest
            '--progress',              # Show progress
            '--exclude=.*',            # Exclude hidden files/dirs (starting with .)
            '--exclude=__pycache__',
            '--exclude=node_modules',
            '--exclude=*.pyc',
            '--exclude=*.pyo',
            '--exclude=*.tmp',
            '--exclude=*.temp',
            '--exclude=*.log',
            '--exclude=*.swp',
            '--exclude=*.swo',
            '--exclude=*~',
            '--exclude=.DS_Store',
            '--exclude=Thumbs.db',
            '--exclude=desktop.ini',
            source,
            destination
        ]
        
        print(dbh + ' Executing rsync: {} -> {}'.format(source, destination))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(dbh + ' Rsync completed successfully')
                return True
            else:
                print(dbh + ' Rsync failed with exit code: {}'.format(result.returncode))
                print(dbh + ' Error output: {}'.format(result.stderr))
                return False
        except FileNotFoundError:
            print(dbh + ' rsync command not found. Please install rsync.')
            return False
        except Exception as e:
            print(dbh + ' Rsync command failed: {}'.format(e))
            return False

# end of def vpr_dir_synchronize(path_local: str, path_netwk: str, direction: str):

def vpr_job_base_is_valid(job_base: str):
    """
    verify the legality of job_base from a set of rules
    Returns: (bool, str) - (is_valid, reason/job_base)
    """

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    # rules: 
    # 1. only lowercase letters, numbers, and underscores
    # 2. must start with a letter
    # 3. no consecutive underscores
    # 4. max length 8 characters
    # 5. no special characters
    # 6. no spaces
    # 7. cannot end in a number

    import re
    len_min = 4
    len_max = 10
    # Check minimum length (at least len_min characters for start and end with letter)
    if len(job_base) < len_min:
        return False, f'Job base must be at least {len_min} characters long'
    
    # Check maximum length (8 characters)
    if len(job_base) > len_max:
        return False, f'Job base cannot exceed {len_max} characters'
    
    # Check for only lowercase letters, numbers, and underscores (check this early)
    if not re.match(r'^[a-z0-9_]+$', job_base):
        return False, 'Job base can only contain lowercase letters, numbers, and underscores'
    
    # Check if it starts with a letter
    if not re.match(r'^[a-z]', job_base):
        return False, 'Job base must start with a lowercase letter'
    
    # Check if it ends with a letter (cannot end in a number or underscore)
    if not re.search(r'[a-z]$', job_base):
        return False, 'Job base must end with a lowercase letter'
    
    # Check for consecutive underscores
    if '__' in job_base:
        return False, 'Job base cannot contain consecutive underscores'
    
    # All rules passed
    return True, job_base

# end of def vpr_job_base_verify(job_base: str):

def vpr_job_rev_set(job_rev: str):

    """
    set revision letter for job_name
    """

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    # take job_rev and increment to next letter
    # Increment revision letter
    if job_rev == '':
        job_rev_new = 'a'
    elif job_rev.isalpha() and job_rev.islower():
        job_rev_new = chr(ord(job_rev) + 1) if job_rev != 'z' else 'a'
    else:
        print (dbh + 'Invalid job_rev: {}'.format(job_rev))
        return None

    return job_rev_new

def vpr_job_name_create(job_base: str, job_revision: str):
    """
    create job_name from year, job_base, and revision
    """

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    is_valid, reason = vpr_job_base_is_valid(job_base)
    #if is_valid:
    #    revision = vpr_job_rev_set(job_base=job_base)

    if not is_valid:
        print (dbh + 'Invalid job_base: {} - {}'.format(job_base, reason))
        return None
    
    year = datetime.datetime.now().strftime('%Y')
    year_short = year[-2:]  # get last two digits of year
    job_name = '_'.join([year_short, job_base, job_revision])
    job_alias = ''.join([job_base, year_short])
    return job_name, job_alias

# end of def vpr_job_name_create(job_base: str, revision: str):

def vpr_job_create_directories(job_name: str, path_job: str, path_rnd: str):
    """
    Create job directories for given job_name under path_job and path_rnd.
    path_job and path_rnd should be the parent directories where job_name will be created.
    """

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    path_job_parent = path_job.replace(job_name, '')
    path_rnd_parent = path_rnd.replace(job_name, '')

    #path_job_full = os.path.join(path_job, job_name)
    #path_rnd_full = os.path.join(path_rnd, job_name)

    # Check write access to parent directories
    for path in [path_job_parent, path_rnd_parent]:
        if not os.path.exists(path):
            print (dbh + 'Parent path does not exist: {}'.format(path))
            success = False
            return success
        if not os.access(path, os.W_OK):
            print (dbh + 'No write access to path: {}'.format(path))
            success = False
            return success
    dict_job = dbj.db_job_dict()

    # creating job directories using dict_apps from db_jobtools
    for app, list_subdirs in dbj.dict_apps.items():
        path_app = os.path.join(path_job, app)
        if not(os.path.exists(path_app)):
            os.makedirs(path_app, 0o755)
            # Create subdirectories for each app based on dict_apps
            for subdir in list_subdirs:
                path_subdir = os.path.join(path_app, subdir)
                if not(os.path.exists(path_subdir)):
                    print (dbh + 'Creating directory: {}'.format(path_subdir))
                    os.makedirs(path_subdir, 0o755)
                    
    # creating rnd directory
    if not(os.path.exists(path_rnd)):
        os.makedirs(path_rnd, 0o755)
    success = True
    return success


# end of def vpr_job_create_directories(job_name: str, path_job: str, path_rnd: str):


def vpr_jobs_dummy_create():

    '''
    creating dummy job database
    '''

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    depot_local = os.getenv('DEPOT_ALL')
    path_proj_netwk = os.getenv('DUMMY_JOBS_NETWK')
    path_rend_netwk = os.getenv('DUMMY_REND_NETWK')
    
    path_db = os.getenv('DUMMY_DB')
    file_sqlite = 'jobs.sqlite3'
    #path_db_json = os.path.join(path_db, 'json')
    path_db_sqlite = os.path.join(path_db, 'sqlite', file_sqlite)
    dict_job = dbj.db_job_dict()
    job_apps = ', '.join(list(dict_job['job_apps'].keys()))

    db_table = 'projects'

    list_job_ids = []

    #file_db_jobs = os.path.join(path_db_json, 'jobs.json')
    conn = dbj.db_sqlite_table_jobs_create(db_path=path_db_sqlite, table_name=db_table)
    list_years = ['2022', '2023', '2024', '2025', '2026']
    list_jobs_base = ['apple', 'banana', 'cherry', 'date', 'guava']
    for year in list_years:
        # get last two digits of year
        year_short = year[-2:]
        base_rev = 'a'
        for job in list_jobs_base:
            job_id = dbj.db_job_id_create_temp(list_id=list_job_ids)
            job_name = '_'.join([year_short, job, base_rev])
            job_alias = ''.join([job, year_short])
            job_user_id = 'dummy_user'
            job_user_name = 'TBD'
            job_notes = 'dummy notes for {}'.format(job_name)
            job_tags = 'tag1, tag2'
            job_date_created = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            job_year = year
            job_date_due = job_date_created
            job_charge1 = 'charge1'
            job_charge2 = 'charge2'
            job_charge3 = 'charge3'
            job_state = 'active'
            job_path_job = os.path.join(path_proj_netwk, year, job_name)
            job_path_job_symbolic = job_path_job.replace(depot_local, '$DEPOT_ALL')
            job_path_rnd = os.path.join(path_rend_netwk, year, job_name)
            job_path_rnd_symbolic = job_path_rnd.replace(depot_local, '$DEPOT_ALL')
            print (dbh + 'Creating job: {}'.format(job_name))

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
            sql_insert = f'INSERT INTO {db_table} ({columns}) VALUES ({placeholders})'
            print (dbh + 'SQL: {}'.format(sql_insert))
            conn.execute(sql_insert, tuple(job_data.values()))
            conn.commit()

            path_job_year = os.path.join(path_proj_netwk, year)
            path_rnd_year = os.path.join(path_rend_netwk, year)

            if not os.path.exists(path_job_year):
                os.makedirs(path_job_year, 0o755)
            if not os.path.exists(path_rnd_year):
                os.makedirs(path_rnd_year, 0o755)

            vpr_job_create_directories(job_name=job_name, path_job=job_path_job, path_rnd=job_path_rnd)
            list_job_ids.append(job_id)

    conn.close()

    

###############################################################################
###############################################################################


#vpr_jobs_dummy_create()