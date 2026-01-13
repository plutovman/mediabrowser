import os, platform, inspect
import db_jobtools as dbj 

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
    """

    func_name = inspect.stack()[0][3]
    dbh = '[{}]'.format(func_name)

    path_job_parent = path_job.replace(job_name, '')
    path_rnd_parent = path_rnd.replace(job_name, '')

    path_job_full = os.path.join(path_job, job_name)
    path_rnd_full = os.path.join(path_rnd, job_name)

    #os.makedirs(path_job_full, exist_ok=True)
    #os.makedirs(path_rnd_full, exist_ok=True)
    for path in [path_job_parent, path_rnd_parent]:
        if not(os.access(path, os.F_OK)):
            print (dbh + 'No write access to path: {}'.format(path))
            success = False
            return success
    dict_job = dbj.db_job_dict()
    dict_job_dirs = dict_job['job_dirs']

    # creating job directories
    for app in dict_job_dirs.keys():
        path_app = os.path.join(path_job_full, app)
        if not(os.path.exists(path_app)):
            os.makedirs(path_app, 0o755)
            if (app == 'adobe'):
                list_adobe_dirs = dbj.list_dirs_adobe
                for adobe_dir in list_adobe_dirs:
                    path_adobe_sub = os.path.join(path_app, adobe_dir)
                    if not(os.path.exists(path_adobe_sub)):
                        print (dbh + 'Creating directory: {}'.format(path_adobe_sub))
                        os.makedirs(path_adobe_sub, 0o755)
            if (app == 'houdini'):
                list_hou_dirs = dbj.list_dirs_hou
                for hou_dir in list_hou_dirs:
                    path_hou_sub = os.path.join(path_app, hou_dir)
                    if not(os.path.exists(path_hou_sub)):
                        print (dbh + 'Creating directory: {}'.format(path_hou_sub))
                        os.makedirs(path_hou_sub, 0o755)
            if (app == 'maya'):
                list_maya_dirs = dbj.list_dirs_maya
                for maya_dir in list_maya_dirs:
                    path_maya_sub = os.path.join(path_app, maya_dir)
                    if not(os.path.exists(path_maya_sub)):
                        print (dbh + 'Creating directory: {}'.format(path_maya_sub))
                        os.makedirs(path_maya_sub, 0o755)
            if (app == 'microsoft'):
                list_ms_dirs = dbj.list_dirs_ms
                for ms_dir in list_ms_dirs:
                    path_ms_sub = os.path.join(path_app, ms_dir)
                    if not(os.path.exists(path_ms_sub)):
                        print (dbh + 'Creating directory: {}'.format(path_ms_sub))
                        os.makedirs(path_ms_sub, 0o755)
                    
    # creating rnd directory
    if not(os.path.exists(path_rnd_full)):
        os.makedirs(path_rnd_full, 0o755)
    success = True
    return success


# end of def vpr_job_create_directories(job_name: str, path_job: str, path_rnd: str):




###############################################################################
###############################################################################
path_dummy_job = '/tmp/dummy/jobs'
path_dummy_rnd = '/tmp/dummy/rnd'
job_name_dummy = 'job_test_001'
vpr_job_create_directories(job_name_dummy, path_dummy_job, path_dummy_rnd)