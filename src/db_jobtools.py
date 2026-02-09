
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
list_dirs_data = ['step', 'obj', 'other']
list_dirs_hou = ['bgeo', 'hip', 'hrender', 'otl']
list_dirs_maya = ['mel', 'obj', 'scenes', 'sourceimages', 'textures']
list_dirs_ms = ['excel', 'ppt', 'word']
list_dirs_movies = ['src', 'out']
list_dirs_nuke = []
list_dirs_python = []

sync_local_to_netwk = 'LOCAL TO NETWK'
sync_netwk_to_local = 'NETWK TO LOCAL'
list_sync_directions = [sync_local_to_netwk, sync_netwk_to_local]

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
def db_tags_verify(tag_string: str) -> str:
    """
    Verify and clean tag string by removing duplicates while preserving order.
    Tags must be comma-separated to support multi-word tags.
    Case-insensitive duplicate detection.
    
    Args:
        tag_string: Comma-separated string of tags (supports multi-word tags)
        
    Returns:
        Cleaned tag string with duplicates removed, consistently formatted as 'tag1, tag2, tag3'
        
    Examples:
        'animation, lighting, animation, Lighting' -> 'animation, lighting'
        'character animation, background lighting' -> 'character animation, background lighting'
        'animation,lighting,compositing' -> 'animation, lighting, compositing'
        ',animation,,lighting,' -> 'animation, lighting'
    """
    if not tag_string:
        return ''
    
    # Split by comma only (preserves spaces within multi-word tags)
    tags = [tag.strip() for tag in tag_string.split(',') if tag.strip()]
    
    # Remove duplicates (case-insensitive) while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique_tags.append(tag)
    
    # Always return comma-space separated string for consistency
    return ', '.join(unique_tags)

def db_job_legacy_dict():

    """
    legacy job dict structure for txt file parsing
    """
    dict_job_charge ={'charge1': '',
                     'charge2': '',
                     'charge3': ''}
    dict_job_dirs = {'adobe': list_dirs_adobe,
                     'audio': [],
                     'data' : [],
                     'houdini': list_dirs_hou,
                     'maya': list_dirs_maya,
                     'microsoft': list_dirs_ms,
                     'movies': list_dirs_movies,
                     'nuke': list_dirs_nuke,
                     'python': list_dirs_python
                    }
    dict_job = {
        'job_alias' : '',
        'job_user' : '',
        'job_notes' : '',
        'job_date_start' : '',
        'job_date_due' : '',
        'job_charge' : dict_job_charge,
        'job_state' : job_mode_active,
        'job_path_job' : '',
        'job_path_rnd' : '',
        'job_dirs' : dict_job_dirs,
    }
    return (dict_job)

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

###############################################################################
###############################################################################
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

###############################################################################
###############################################################################
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

# end of db_jobs_legacy_migrate()

###############################################################################
###############################################################################
def db_jobs_sqlite_to_json(db_path_sqlite: str, db_table: str, db_path_json: str, json_file: str):

    """
    migrate sqlite3 table to json file
    """
    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    path_json = os.path.join(db_path_json, json_file)

    conn = sqlite3.connect(db_path_sqlite)
    cursor = conn.cursor()

    cursor.execute(f'SELECT * FROM {db_table}')
    rows = cursor.fetchall()

    dict_data = {}
    for row in rows:
        dict_row = {}
        for idx, col in enumerate(list_db_jobs_columns):
            value = row[idx]
            # Deserialize job_apps if it's stored as JSON string
            if col == 'job_apps' and isinstance(value, str):
                try:
                    dict_row[col] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    dict_row[col] = {}  # Default to empty dict if parsing fails
            else:
                dict_row[col] = value
        job_name = dict_row['job_name']
        dict_data[job_name] = dict_row

    with open ( path_json, 'w') as f_json:
        json.dump(dict_data, f_json, indent=4)
    f_json.close()

    conn.close()
    print (dbh + f'Exported sqlite3 table {db_table} to json file: {path_json}')

# end of def db_jobs_sqlite_to_json(db_path_sqlite: str, db_table: str, db_path_json: str, json_file: str):


###############################################################################
###############################################################################
def db_jobs_jsonlegacy_to_sqlite(db_path_json: str, file_json: str, db_path_sqlite: str, db_table: str):

    """
    migrate legacy jobs json file to sqlite3 table
    """

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    path_json = os.path.join(db_path_json, file_json)

    dict_job = db_job_dict()
    with open ( path_json, 'r') as f_json:
        dict_jobs_legacy = json.load(f_json)
    f_json.close()

    conn = db_sqlite_table_jobs_create(db_path_sqlite, db_table)
    cursor = conn.cursor()


    dict_job = db_job_dict()
    for job_name in dict_jobs_legacy.keys():

        job_id = db_id_create(db_sqlite_path=db_path_sqlite, db_table=db_table, id_column='job_id')
        
        dict_job_legacy = dict_jobs_legacy[job_name]
        dict_job['job_id'] = job_id
        dict_job['job_name'] = job_name
        dict_job['job_alias'] = dict_job_legacy['job_alias']
        dict_job['job_user_id'] = dict_job_legacy['job_user']
        dict_job['job_user_name'] = 'tbd'
        dict_job['job_date_created'] = dict_job_legacy['job_date_start']
        dict_job['job_date_due'] = dict_job_legacy['job_date_due']
        dict_job['job_notes'] = dict_job_legacy['job_notes']
        dict_job['job_state'] = dict_job_legacy['job_state']
        dict_job['job_path_job'] = dict_job_legacy['job_path_job']
        dict_job['job_path_rnd'] = dict_job_legacy['job_path_rnd']
        
        # Map legacy job_charge dict to individual charge fields
        if 'job_charge' in dict_job_legacy and isinstance(dict_job_legacy['job_charge'], dict):
            dict_job['job_charge1'] = dict_job_legacy['job_charge'].get('charge1', '')
            dict_job['job_charge2'] = dict_job_legacy['job_charge'].get('charge2', '')
            dict_job['job_charge3'] = dict_job_legacy['job_charge'].get('charge3', '')
        
        # Map legacy job_dirs to job_apps (serialize to JSON string for SQLite)
        if 'job_dirs' in dict_job_legacy:
            dict_job['job_apps'] = json.dumps(dict_job_legacy['job_dirs'])
        else:
            # If no job_dirs, serialize the default dict_job_apps to JSON string
            dict_job['job_apps'] = json.dumps(dict_job['job_apps'])

        # table insertion
        placeholders = ', '.join(['?'] * len(list_db_jobs_columns))
        columns = ', '.join(list_db_jobs_columns)
        sql = f'INSERT INTO {db_table} ({columns}) VALUES ({placeholders})'
        values = [dict_job[col] for col in list_db_jobs_columns]
        cursor.execute(sql, values)

    conn.commit()
    conn.close()
    print (dbh + f'Imported legacy jobs json file {path_json} to sqlite3 table: {db_table}')

# end of def db_jobs_jsonlegacy_to_sqlite(db_path_json: str, file_json: str, db_path_sqlite: str, db_table: str):

###############################################################################
###############################################################################
def db_jobs_nav_create(db_path: str, db_table: str, nav_path: str, nav_file: str):

    """
    create navigation file for jobs if it doesn't exist
    """

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    path_nav = os.path.join(nav_path, nav_file)
    #if not os.path.exists(path_nav):

    if True:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. query db_table for all jobs
        # 2. create nav_file and for each job, populate as follows:
        #   # [job_name] created by [job_user_name] on [job_date_created]

        #   alias   [job_alias] "cd [job_path_job]; source local.env"
        #   set     [job_alias] = [job_path_job]

        cursor.execute(f'SELECT job_name, job_alias, job_user_name, job_date_created, job_path_job FROM {db_table}')
        rows = cursor.fetchall()
        with open(path_nav, 'w') as f_nav:
            f_nav.write('#!/bin/tcsh\n\n')
            f_nav.write('# Navigation file for jobs\n\n')
            for row in rows:
                job_name = row[0]
                job_alias = row[1]
                job_user_name = row[2]
                job_date_created = row[3]
                job_path_job = row[4]
                f_nav.write('\n')
                f_nav.write(f'# {job_name} created by {job_user_name} on {job_date_created}\n')
                f_nav.write(f'alias   {job_alias} "cd {job_path_job}; source local.env"\n')
                f_nav.write(f'set     {job_alias} = {job_path_job}\n\n')
                f_nav.write('\n')
            f_nav.close()

        conn.close()
        print (dbh + f'Created navigation database table: {path_nav}')

# end of def db_jobs_nav_create(db_path: str, db_table: str, nav_path: str, nav_file: str):

###############################################################################
###############################################################################
def db_jobdirs_get(depot_current: str, job_year: str, job_name: str):

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    path_dummy = os.path.join(depot_current, 'assetdepot', 'jobs_dummy')
    path_db = os.path.join(path_dummy, 'db', 'json')
    path_proj_netwk = os.path.join(path_dummy, 'projectdepot') 
    path_rend_netwk = os.path.join(path_dummy, 'renderdepot')
    path_job = os.path.join(path_proj_netwk, job_year, job_name)
    path_rnd = os.path.join(path_rend_netwk, job_year, job_name)
    job_name_parts = job_name.split('_')
    job_base = '_'.join(job_name_parts[-1])

    dict_jobdirs = {
        'path_db': path_db,
        'path_proj_netwk': path_proj_netwk,
        'path_rend_netwk': path_rend_netwk,
        'path_job': path_job,
        'path_rnd': path_rnd,
        'job_base': job_base
    }
    return dict_jobdirs

###############################################################################
###############################################################################
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
            job_tags VARCHAR(500) NOT NULL,
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
