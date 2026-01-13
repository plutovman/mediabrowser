
import random, string, re, pathlib, datetime
import os, inspect, json

job_mode_active = 'active'
job_mode_archvd = 'archvd'
job_mode_delete = 'delete'

file_job_env = 'local.env'
file_jobs_txt = 'pe_jobs_lnx.tcsh'
file_jobs_json = 'db_jobs.json'
file_jobs_legacy = 'pe_jobs_lnx.tcsh'

list_dirs_adobe = ['afterfx', 'illustrator', 'photoshop', 'premiere']
list_dirs_hou = ['bgeo', 'hip', 'hrender', 'otl']
list_dirs_maya = ['mel', 'obj', 'scenes', 'sourceimages', 'textures']
list_dirs_ms = ['excel', 'ppt', 'word']

###############################################################################
###############################################################################
def db_job_dict():

    """
    Docstring for db_job_dict
    """
    dict_job_chg = {'chg1' :'',
                    'chg2' :'',
                    'chg3' :''}

    dict_job_dirs = {'adobe': list_dirs_adobe,
                     'audio': [],
                     'houdini': list_dirs_hou,
                     'maya': list_dirs_maya,
                     'microsoft': list_dirs_ms,
                     'movies': [],
                     'nuke': [],
                     'python': [],
                    }
    dict_job = {
        'job_alias' : '',
        'job_user' : '',
        'job_notes' : '',
        'job_date_start' : '',
        'job_date_end' : '',
        'job_charges' : dict_job_chg,
        'job_state' : job_mode_active,
        'job_path_job' : '',
        'job_path_rnd' : '',
        'job_dirs' : dict_job_dirs,

    }
    return (dict_job)

# end of def db_job_dict():

###############################################################################
###############################################################################
def db_job_id_create(list_id: list):

    """
    create a unique id for a new job entry that is not in list_id
    """
    job_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    while job_id in list_id:
        job_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return job_id

# end of def db_job_id_create(list_id: list):

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
    job_user = vss
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
                job_user = list_words[4]
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
                dict_job['job_user'] = job_user
                dict_job['job_date_start'] = date_string_out

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


#############################################

db_jobs_legacy_migrate()