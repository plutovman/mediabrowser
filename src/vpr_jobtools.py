import os, platform, inspect, subprocess
import db_jobtools as dbj 
import datetime
import json

try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

###############################################################################
###############################################################################
def git_get_info(path_repo=None, path_json=None):
    """
    Extracts the latest commit information from the Git repository.
    Falls back to reading from JSON file if git module is unavailable.
    
    Args:
        path_repo: Path to search for git repository (defaults to current directory)
        path_json: Path to JSON file for storing/reading commit info
    
    Returns:
        dict: Dictionary containing commit hash, date, and message
        Example: {'hash': 'abc123', 'date': '2026-01-01 10:30:00', 'message': 'Initial commit'}
        Returns None if neither git nor JSON file is available
    
    Notes:
        - In development: Uses git module and writes to path_json
        - In production (frozen app): Reads from path_json
    """
    # Try to use git module if available
    if GIT_AVAILABLE:
        try:
            # Get the repository root (current directory or parent directories)
            if path_repo:
                repo = git.Repo(path_repo, search_parent_directories=True)
            else:
                repo = git.Repo(search_parent_directories=True)
            
            # Get the latest commit
            latest_commit = repo.head.commit
            
            # Extract commit information
            commit_info = {
                'hash': latest_commit.hexsha[:7],  # Short hash (first 7 characters)
                'date': datetime.datetime.fromtimestamp(latest_commit.committed_date).strftime('%Y-%m-%d %H:%M:%S'),
                'message': latest_commit.message.strip().split('\n')[0]  # First line of commit message
            }
            
            # Write to JSON file if path provided
            if path_json:
                try:
                    os.makedirs(os.path.dirname(path_json), exist_ok=True)
                    with open(path_json, 'w') as f:
                        json.dump(commit_info, f, indent=2)
                except (OSError, IOError) as e:
                    print(f"Warning: Could not write git info to {path_json}: {e}")
            
            return commit_info
            
        except (git.InvalidGitRepositoryError, git.GitCommandError) as e:
            print(f"Git error: {e}")
            # Fall through to JSON fallback
    
    # Fallback: Try to read from JSON file
    if path_json and os.path.exists(path_json):
        try:
            with open(path_json, 'r') as f:
                commit_info = json.load(f)
                return commit_info
        except (OSError, IOError, json.JSONDecodeError) as e:
            print(f"Error reading git info from {path_json}: {e}")
    
    # No git and no JSON file available
    return None

# end of def git_get_info(path_repo=None, path_json=None):

###############################################################################
###############################################################################
def get_user_info_current(user_id=None):
    """
    Get current user information in an OS-aware manner.
    Works on macOS, Linux, WSL, and Windows.
    
    Args:
        user_id (str, optional): User ID to look up. If not provided, detects current user.
    
    Returns:
        dict: Dictionary containing 'user_id' and 'user_name'
    """
    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)
    
    system = platform.system()
    user_name = 'Unknown User'
    
    try:
        if system in ['Linux', 'Darwin']:  # Linux or macOS
            # If user_id not provided, try environment variables first
            if user_id is None:
                user_id = os.getenv('USER') or os.getenv('LOGNAME')
            
            # Get full name from pwd module
            try:
                import pwd
                if user_id:
                    pw_record = pwd.getpwnam(user_id)
                else:
                    pw_record = pwd.getpwuid(os.getuid())
                    user_id = pw_record.pw_name
                # Extract full name from GECOS field
                gecos = pw_record.pw_gecos
                if gecos:
                    user_name = gecos.split(',')[0].strip()
                if not user_name or user_name == '':
                    user_name = user_id.capitalize()
            except (ImportError, KeyError, OSError):
                # Fall back to username only
                if user_id:
                    user_name = user_id.capitalize()
                    
        elif system == 'Windows':
            # Windows-specific user detection
            if user_id is None:
                user_id = os.getenv('USERNAME')
            
            # Try to get full name from Windows
            if user_id:
                try:
                    result = subprocess.run(
                        ['wmic', 'useraccount', 'where', f'name="{user_id}"', 'get', 'fullname'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        if len(lines) > 1:
                            full_name = lines[1].strip()
                            if full_name:
                                user_name = full_name
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    pass
            
            # Fallback: try net user command
            if user_name == 'Unknown User' and user_id:
                try:
                    result = subprocess.run(
                        ['net', 'user', user_id],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'Full Name' in line:
                                parts = line.split(None, 2)
                                if len(parts) >= 3:
                                    user_name = parts[2].strip()
                                    break
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    pass
            
            # Final fallback for Windows
            if user_name == 'Unknown User' and user_id:
                user_name = user_id.replace('.', ' ').title()
        
        # Generic fallbacks
        if not user_id:
            user_id = os.getenv('USER') or os.getenv('USERNAME') or os.getenv('LOGNAME') or 'unknown_user'
        
        if user_name == 'Unknown User':
            user_name = user_id.replace('_', ' ').replace('.', ' ').title()
            
    except Exception as e:
        print(dbh + f' Error getting user info: {e}')
        if not user_id:
            user_id = 'unknown_user'
    
    return {
        'user_id': user_id,
        'user_name': user_name
    }

# end of def get_user_info_current():

###############################################################################
###############################################################################
def get_user_info_from_file(path_file: str):
    """
    Get user ownership info from a specified file in an OS-aware manner.
    Works on macOS, Linux, WSL, and Windows.
    
    Args:
        path_file: Path to file to get ownership information from
        
    Returns:
        dict: Dictionary containing 'user_id' and 'user_name'
    """
    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)
    
    system = platform.system()
    user_id = 'unknown_user'
    user_name = 'Unknown User'
    
    if not os.path.exists(path_file):
        print(dbh + f' File does not exist: {path_file}')
        return {'user_id': user_id, 'user_name': user_name}
    
    try:
        stat_info = os.stat(path_file)
        
        if system in ['Linux', 'Darwin']:  # Linux or macOS
            try:
                import pwd
                uid = stat_info.st_uid
                pw_record = pwd.getpwuid(uid)
                user_id = pw_record.pw_name
                
                # Extract full name from GECOS field
                gecos = pw_record.pw_gecos
                if gecos:
                    user_name = gecos.split(',')[0].strip()
                if not user_name or user_name == '':
                    user_name = user_id.capitalize()
                    
            except (ImportError, KeyError, OSError) as e:
                print(dbh + f' Error using pwd module: {e}')
                # Try to get UID at least
                try:
                    uid = stat_info.st_uid
                    user_id = str(uid)
                    user_name = f'UID {uid}'
                except Exception:
                    pass
                    
        elif system == 'Windows':
            # Windows file ownership detection
            try:
                import ctypes
                from ctypes import wintypes
                
                # Windows API structures and functions
                PSECURITY_DESCRIPTOR = ctypes.c_void_p
                PSID = ctypes.c_void_p
                
                advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
                
                # Get file security info
                security_descriptor = PSECURITY_DESCRIPTOR()
                owner_sid = PSID()
                
                result = advapi32.GetNamedSecurityInfoW(
                    path_file,
                    1,  # SE_FILE_OBJECT
                    1,  # OWNER_SECURITY_INFORMATION
                    ctypes.byref(owner_sid),
                    None, None, None,
                    ctypes.byref(security_descriptor)
                )
                
                if result == 0:  # Success
                    # Convert SID to account name
                    name_size = wintypes.DWORD(0)
                    domain_size = wintypes.DWORD(0)
                    sid_type = wintypes.DWORD()
                    
                    # Get required buffer sizes
                    advapi32.LookupAccountSidW(
                        None, owner_sid, None, ctypes.byref(name_size),
                        None, ctypes.byref(domain_size), ctypes.byref(sid_type)
                    )
                    
                    if name_size.value > 0:
                        name_buffer = ctypes.create_unicode_buffer(name_size.value)
                        domain_buffer = ctypes.create_unicode_buffer(domain_size.value)
                        
                        success = advapi32.LookupAccountSidW(
                            None, owner_sid, name_buffer, ctypes.byref(name_size),
                            domain_buffer, ctypes.byref(domain_size), ctypes.byref(sid_type)
                        )
                        
                        if success:
                            user_id = name_buffer.value
                            # Try to get full name
                            try:
                                result = subprocess.run(
                                    ['wmic', 'useraccount', 'where', f'name="{user_id}"', 'get', 'fullname'],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if result.returncode == 0:
                                    lines = result.stdout.strip().split('\n')
                                    if len(lines) > 1:
                                        full_name = lines[1].strip()
                                        if full_name:
                                            user_name = full_name
                            except Exception:
                                pass
                            
                            if user_name == 'Unknown User':
                                user_name = user_id.replace('.', ' ').title()
                    
                    # Free security descriptor
                    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                    kernel32.LocalFree(security_descriptor)
                    
            except Exception as e:
                print(dbh + f' Error getting Windows file owner: {e}')
                # Fallback: use current user
                user_id = os.getenv('USERNAME', 'unknown_user')
                user_name = user_id.replace('.', ' ').title()
        
    except Exception as e:
        print(dbh + f' Error getting user info from file {path_file}: {e}')
    
    return {
        'user_id': user_id,
        'user_name': user_name
    }
    
# end of def get_user_info_from_file(path_file: str):

###############################################################################
###############################################################################
def vpr_file_parts_get(file_name: str):
    """
    split file_name by '_' and return a list of parts
    """
    list_parts = file_name.split('_')
    return list_parts

# end of def vpr_file_parts_get(file_name: str):

###############################################################################
###############################################################################
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

###############################################################################
###############################################################################
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

###############################################################################
###############################################################################
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

###############################################################################
###############################################################################
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

###############################################################################
###############################################################################
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

###############################################################################
###############################################################################
def vpr_job_edit_environment(job_name: str, path_job: str, path_job_env: str, job_year: str):
    
    import db_jobtools as dbj
    import shutil

    """
    edit job environment variables in job_dict
    """
    #path_job_symbolic = job_dict['job_path_job']
    #path_job: str, path_rnd: str, job_year: str#path_rnd_symbolic = job_dict['job_path_rnd']
    #path_job_literal = path_job_symbolic.replace('$DEPOT_ALL', os.getenv('DEPOT_ALL'))
    #path_rnd_literal = path_rnd_symbolic.replace('$DEPOT_ALL', os.getenv('DEPOT_ALL')) 

    #path_job_generic = '/replace/with/dir'
    #path_rnd_generic = '/replace/with/dir'

    file_proj_env = 'local.env'

    # ger path to current python file
    #path_script = os.path.dirname(os.path.realpath(__file__))
    #path_job_env: str,
    #path_resources = os.path.join(path_script, 'resources')
    #path_job_env_in = os.path.join(path_resources, file_proj_env)
    path_job_env_out = os.path.join(path_job, file_proj_env)

    if (os.path.exists(path_job_env) and os.path.exists(path_job)):
        shutil.copy2(path_job_env, path_job_env_out)
    else:
        print ('[vpr_job_edit_environment] Missing path: {} or {}'.format(path_job_env, path_job))
        return False

    text_jobmisc = 'Last modified on 05/25/05'	
    text_jobyear = 'JOB_YEAR generic'
    text_jobname = 'JOB_NAME generic'
    text_jobsdir = 'JOBS_DIR /replace/with/dir'
    text_imgname = 'IMAGE_NAME generic'
    text_jobdir = 'JOB_DIR /replace/with/dir'
    text_vdrop = 'VDROP /replace/with/dir'
    text_job_arch_seq = 'JOB_ARCH_SEQ /replace/with/dir'
    text_job_arch_vid = 'JOB_ARCH_VID /replace/with/dir'
    text_wf_img_dir = 'WF_IMG_DIR /replace/with/dir'
    text_maya_proj = 'MAYA_PROJECT /default'
    text_maya_scripts = 'path_maya_scripts = /default'
    
    list_lines = []
    # read in job.env
    with open (path_job_env_out) as filein:
        list_lines = filein.readlines()
    filein.close()
    # modify lines
    job_name_parts = vpr_file_parts_get(job_name)
    job_base = job_name_parts[1]
    job_shr = f'{job_base}_shr'
    job_seq = f'{job_base}_seq'
    job_vid = f'{job_base}_vid'
    with open (path_job_env_out, 'w') as fileout:
        for line in list_lines:
            if text_jobyear in line:
                line = f'setenv JOB_YEAR {job_year}\n'
            elif text_jobname in line:
                line = f'setenv JOB_NAME {job_name}\n'
            elif text_jobsdir in line:
                line = f'setenv JOBS_DIR $JOBS_LNX/{job_year}\n'
            elif text_imgname in line:
                line = f'setenv IMAGE_NAME $REND_LNX/{job_year}/{job_name}\n'
            elif text_jobdir in line:
                line = f'setenv JOB_DIR $JOBS_LNX/{job_year}/{job_name}\n'
            elif text_vdrop in line:
                line = f'setenv VDROP $DROP_ALL/{job_year}/{job_shr}\n'
            elif text_job_arch_seq in line:
                line = f'setenv JOB_ARCH_SEQ $ARCH_IMGSEQ/{job_year}/{job_seq}\n'
            elif text_job_arch_vid in line:
                line = f'setenv JOB_ARCH_VID $ARCH_VIDEOS/{job_year}/{job_vid}\n'
            elif text_wf_img_dir in line:
                line = f'setenv WF_IMG_DIR $REND_LNX/{job_year}/{job_name}\n'
            elif text_maya_proj in line:
                line = f'setenv MAYA_PROJECT $JOBS_LNX/{job_year}/{job_name}/maya\n'
            elif text_maya_scripts in line:
                line = f'set path_maya_scripts = $MAYA_SCRIPT_PATH/:$JOBS_LNX/{job_year}/{job_name}/maya/mel\n'
            fileout.write(line)
    fileout.close()
    return True

# end of def vpr_job_edit_environment(job_dict: dict[str|str], 

###############################################################################
###############################################################################
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
###############################################################################
###############################################################################
# TRANSITORY EXECUTION CODE

#vpr_jobs_dummy_create()