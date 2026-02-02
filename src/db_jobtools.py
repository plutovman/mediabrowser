
import random, string, re, pathlib, datetime
import os, inspect, json
import sqlite3

job_mode_active = 'active'
job_mode_archvd = 'archvd'
job_mode_delete = 'delete'

file_job_env = 'local.env'
file_jobs_txt = 'pe_jobs_lnx.tcsh'
file_jobs_json = 'db_jobs.json'
file_jobs_legacy = 'pe_jobs_lnx.tcsh'

list_dirs_apps = ['adobe', 'audio', 'data', 'houdini', 'maya', 'microsoft', 'movies', 'nuke', 'python']
list_dirs_adobe = ['afterfx', 'illustrator', 'photoshop', 'premiere']
list_dirs_audio = ['src', 'out']
list_dirs_hou = ['bgeo', 'hip', 'hrender', 'otl']
list_dirs_maya = ['mel', 'obj', 'scenes', 'sourceimages', 'textures']
list_dirs_ms = ['excel', 'ppt', 'word']
list_dirs_movies = ['src', 'out']
list_dirs_nuke = []
list_dirs_python = []
list_dirs_data = []

dict_apps = {
    'adobe': list_dirs_adobe,
    'audio': list_dirs_audio,
    'data' : list_dirs_data,
    'houdini': list_dirs_hou,
    'maya': list_dirs_maya,
    'microsoft': list_dirs_ms,
    'movies': list_dirs_movies,
    'nuke': list_dirs_nuke,
    'python': list_dirs_python,
}


list_db_jobs_columns = ['job_id',
                        'job_name', 
                        'job_alias',
                        'job_state',
                        'job_year',
                        'job_user_id',
                        'job_user_name',
                        'job_edit_user_id',
                        'job_edit_user_name',
                        'job_edit_date',
                        'job_notes',
                        'job_tags',
                        'job_date_created',
                        'job_date_due',
                        'job_charge1',
                        'job_charge2',
                        'job_charge3',
                        'job_path_job',
                        'job_path_rnd',
                        'job_apps']

###############################################################################
###############################################################################
def db_job_dict():

    """
    Docstring for db_job_dict
    """
    dict_job_apps = {'adobe': list_dirs_adobe,
                     'audio': list_dirs_audio,
                     'data' : list_dirs_data,
                     'houdini': list_dirs_hou,
                     'maya': list_dirs_maya,
                     'microsoft': list_dirs_ms,
                     'movies': list_dirs_movies,
                     'nuke': list_dirs_nuke,
                     'python': list_dirs_python,
                    }
    dict_job = {
        'job_id' : '',
        'job_name' : '',
        'job_alias' : '',
        'job_state' : job_mode_active,
        'job_year' : '',
        'job_user_id' : '',
        'job_user_name' : '',
        'job_edit_user_id' : '',
        'job_edit_user_name' : '',
        'job_edit_date' : '',
        'job_notes' : '',
        'job_tags' : '',
        'job_date_created' : '',
        'job_date_due' : '',
        'job_charge1' : '',
        'job_charge2' : '',
        'job_charge3' : '',
        'job_path_job' : '',
        'job_path_rnd' : '',
        'job_apps' : dict_job_apps,

    }
    return (dict_job)

# end of def db_job_dict():

###############################################################################
###############################################################################
def db_job_id_create_temp(list_id: list):

    """
    create a unique id for a new job entry that is not in list_id
    """

    '''
    job_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    while job_id in list_id:
        job_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return job_id
    '''

    job_id = db_token_generator()
    while job_id in list_id:
        job_id = db_token_generator()
    return job_id

# end of def db_job_id_create_temp(list_id: list):

def db_id_create(db_sqlite_path: str, db_table: str, id_column: str):

    """
    create a unique id for a new file entry in the sqlite database
    """

    conn = sqlite3.connect(db_sqlite_path)
    cursor = conn.cursor()

    # Generate a unique file_id
    file_id = db_token_generator()
    
    # Check if file_id already exists in the database
    cursor.execute(f"SELECT COUNT(*) FROM {db_table} WHERE {id_column} = ?", (file_id,))
    count = cursor.fetchone()[0]
    
    # Regenerate until we get a unique ID
    while count > 0:
        file_id = db_token_generator()
        cursor.execute(f"SELECT COUNT(*) FROM {db_table} WHERE {id_column} = ?", (file_id,))
        count = cursor.fetchone()[0]

    conn.close()
    return file_id

# end of def db_id_create(db_sqlite_path: str):

def db_token_generator(token_length=12):
    """
    generate a random token of ascii characters and digits of length token_length
    """
    letters = string.ascii_lowercase
    token = ''.join(random.choice(letters) for i in range(token_length) )
    return token

###############################################################################
###############################################################################
def db_jobname_clean(jobname:str, jobname_char_max: int):
    """
    clean job name to acceptable characters and length
    """
    # strip out all spaces
    jobname = re.sub(r'\s+', '', jobname)
    # strip out digits from beginning of job name
    jobname = re.sub(r'^[0-9]+', '', jobname)
    # strip out digits from end of job name
    jobname = re.sub(r'[0-9]+$', '', jobname)
    # strip out non-alphanumeric characters 
    jobname = re.sub(r'[\x00-\X1F\x21-\x2F\x3A-\x40\x5B-\x60\x7B-\xFF]+', '', jobname)
    # chop at char_max
    jobname = jobname[0:jobname_char_max].lower()

    return jobname

#  end of def db_jobname_clean(jobname:str, jobname_char_max: int):

###############################################################################
###############################################################################
def db_jobs_legacy_to_json(db_path_legacy, db_path_json, file_jobs_txt, file_jobs_json):
 
    """
    convert legacy jobs txt file to json file
    note that the format of file_jobs_txt looks something like this:

    # misc26 created by vss on Sun Jan 11 19:52:16 PST 2026

    alias   misc26 "cd $JOBS_LNX/2026/26_misc_a;source local.env"
    set     misc26 = $JOBS_LNX/2026/26_misc_a 

    In the lines above, here is how the words positionally break down:
    job_alias = misc26
    job_name = 26_misc_a
    job_user_id = vss
    job_year = 2026
    job_notes = ''
    job_path_job = $JOBS_LNX/2026/26_misc_a

    """
    
    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    path_jobs_txt = os.path.join(db_path_legacy, file_jobs_txt)
    path_jobs_json = os.path.join(db_path_json, file_jobs_json)

    dict_jobs_txt = {}
    dict_jobs_alias = {}

    with open ( path_jobs_txt, 'r') as f:
        list_lines = f.readlines()
        # step through the document only lookin at 'set' lines
        for line in list_lines:
            list_words = re.split(r'\s+', line)
            if line.startswith('set'):
                job_alias = list_words[1]
                job_path_job = list_words[3]
                job_path_obj = pathlib.Path(job_path_job)
                job_name = job_path_obj.name
                job_path_rnd = job_path_job.replace('JOBS_LNX', 'RND_LNX')
                dict_job = db_job_dict()
                dict_job['job_alias'] = job_alias
                dict_job['job_path_job'] = job_path_job
                dict_job['job_path_rnd'] = job_path_rnd
                # append to dictionaries
                dict_jobs_txt[job_name] = dict_job
                dict_jobs_alias[job_alias] = job_name
        # step through the document again only looking at '#' lines
        for line in list_lines:
            list_words = line.split()
            if line.startswith('#'):
                job_alias = list_words[1]
                job_user_id = list_words[4]
                date_month = list_words[7]
                date_day = list_words[8]
                date_year = list_words[11]
                date_hour = list_words[9]
                date_string_in = '{} {} {} {}'.format(date_month, date_day, date_year, date_hour)
                format_in = '%b %d %Y %H:%M:%S'
                format_out = '%Y-%m-%d %H:%M:%S'
                date_object = datetime.datetime.strptime(date_string_in, format_in)
                date_string_out = date_object.strftime(format_out)
                job_name = dict_jobs_alias[job_alias]
                dict_job = dict_jobs_txt[job_name]
                dict_job['job_user_id'] = job_user_id
                dict_job['job_date_created'] = date_string_out
                dict_job['job_edit_date'] = date_string_out

    f.close()
    with open ( path_jobs_json, 'w') as f_json:
        json.dump(dict_jobs_txt, f_json, indent=4)
    f_json.close()

# end of def db_jobs_legacy_to_json(db_path, file_jobs_txt, file_jobs_json):

###############################################################################
###############################################################################
def db_jobs_legacy_migrate():

    """
    migrate legacy jobs txt file to json file
    """
    import os

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    path_db_legacy = '/mnt/x/projectdepot/db/navigation/lnx'
    path_db_json = '/mnt/x/assetdepot/db/json/jobs'
    path_jobs_txt = os.path.join(path_db_legacy, file_jobs_txt)
    path_jobs_json = os.path.join(path_db_json, file_jobs_json)

    if os.path.exists(path_jobs_txt):
        db_jobs_legacy_to_json(path_db_legacy, path_db_json, file_jobs_txt, file_jobs_json)
        print (dbh + f'Migrated {path_jobs_txt} to {path_jobs_json}')
    else:
        print (dbh + f'No legacy jobs txt file found: {path_jobs_txt}.') 

def db_jobdirs_get(depot_current: str, job_year: str, job_name: str):

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    path_dummy = os.path.join(depot_current, 'assetdepot', 'jobs_dummy')
    path_db = os.path.join(path_dummy, 'db', 'json')
    path_proj = os.path.join(path_dummy, 'projectdepot') 
    path_rend = os.path.join(path_dummy, 'renderdepot')
    path_job = os.path.join(path_proj, job_year, job_name)
    path_rnd = os.path.join(path_rend, job_year, job_name)
    job_name_parts = job_name.split('_')
    job_base = '_'.join(job_name_parts[-1])

    dict_jobdirs = {
        'path_db': path_db,
        'path_proj': path_proj,
        'path_rend': path_rend,
        'path_job': path_job,
        'path_rnd': path_rnd,
        'job_base': job_base
    }
    return dict_jobdirs


def db_sqlite_table_jobs_create(db_path: str, table_name: str):

    '''
    create sqlite table for jobs if it doesn't exist

    '''

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY,
            job_id TEXT NOT NULL,
            job_name TEXT NOT NULL,
            job_alias TEXT NOT NULL,
            job_state TEXT NOT NULL,
            job_year TEXT NOT NULL,
            job_user_id TEXT NOT NULL,
            job_user_name TEXT NOT NULL,
            job_edit_user_id TEXT NOT NULL,
            job_edit_user_name TEXT NOT NULL,
            job_edit_date TEXT NOT NULL,
            job_notes TEXT NOT NULL,
            job_tags TEXT NOT NULL,
            job_date_created TEXT NOT NULL,
            job_date_due TEXT NOT NULL,
            job_charge1 TEXT NOT NULL,
            job_charge2 TEXT NOT NULL,
            job_charge3 TEXT NOT NULL,
            job_path_job TEXT NOT NULL,
            job_path_rnd TEXT NOT NULL,
            job_apps TEXT NOT NULL,
            UNIQUE(job_id, job_name)
                   
        )
    ''')

    conn.commit()
    #conn.close()
    return conn

#db_jobs_legacy_migrate()