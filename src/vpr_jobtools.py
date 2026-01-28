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
    path_proj = os.getenv('DUMMY_JOBS')
    path_rend = os.getenv('DUMMY_REND')
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
            job_id = dbj.db_job_id_create(list_id=list_job_ids)
            job_name = '_'.join([year_short, job, base_rev])
            job_alias = ''.join([year_short, job])
            job_user = 'dummy_user'
            job_notes = 'dummy notes for {}'.format(job_name)
            job_tags = 'tag1, tag2'
            job_date_start = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            job_year = year
            job_date_due = job_date_start
            job_charge1 = 'charge1'
            job_charge2 = 'charge2'
            job_charge3 = 'charge3'
            job_state = 'active'
            job_path_job = os.path.join(path_proj, year, job_name)
            job_path_job_symbolic = job_path_job.replace(depot_local, '$DEPOT_ALL')
            job_path_rnd = os.path.join(path_rend, year, job_name)
            job_path_rnd_symbolic = job_path_rnd.replace(depot_local, '$DEPOT_ALL')
            print (dbh + 'Creating job: {}'.format(job_name))

            job_data = {
                'job_id': job_id,
                'job_name': job_name,
                'job_alias': job_alias,
                'job_user': job_user,
                'job_notes': job_notes,
                'job_tags': job_tags,
                'job_year': job_year,
                'job_date_start': job_date_start,
                'job_date_due': job_date_due,
                'job_charge1': job_charge1,
                'job_charge2': job_charge2,
                'job_charge3': job_charge3,
                'job_state': job_state,
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

            path_job_year = os.path.join(path_proj, year)
            path_rnd_year = os.path.join(path_rend, year)

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