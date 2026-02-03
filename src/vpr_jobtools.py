import os, platform, inspect
import db_jobtools as dbj 
import datetime

def vpr_file_parts_get(file_name: str):
    """
    split file_name by '_' and return a list of parts
    """
    list_parts = file_name.split('_')
    return list_parts

# end of def vpr_file_parts_get(file_name: str):

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