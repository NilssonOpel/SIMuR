import json
import os
import subprocess

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def run_process(command, do_check, extra_dir=os.getcwd()):
    try:
        status = subprocess.run(command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=do_check)
        if status.returncode == 0:
            reply = status.stdout
        else:
            reply = status.stdout
            reply += status.stderr

    except Exception as e:
        if extra_dir:
            command = f'At {extra_dir}:\n'
        reply = f'{command} threw an exception:\n'
        reply += f'type: {type(e)}\n'
        reply += f'    : {e}\n'
        reply += '\n-end of exception-\n'

    return reply

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def my_mkdir(the_dir):
    if not os.path.exists(the_dir):
        os.mkdir(the_dir)
    the_dir = os.path.realpath(the_dir)
    return the_dir

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_local_cache_dir():
    # Take in the cache directory through an environment variable since vcget
    # may be called spontaneous from all kind of debugging tools
    cache_dir = os.getenv('SIMUR_CACHE', 'C:\simur_repo')
    local_repo = my_mkdir(cache_dir)

    return local_repo

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_local_cache_file(name):
    local_repo = get_local_cache_dir()
    local_file = os.path.join(local_repo, name)

    return local_file

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def load_local_cache_file(name):
    local_repo = get_local_cache_dir()
    local_file = os.path.join(local_repo, name)

    return local_file

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_presoak_file():
    presoak_file = get_local_cache_file('presoak.json')

    return presoak_file

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def load_json_data(file):
    if not os.path.exists(file):
        return {}

    with open(file) as fp:
        data = json.load(fp)

    return data

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def store_json_data(file, data):
    with open(file, 'w') as fp:
        json.dump(data, fp, indent=2)

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_the_git_dir(start_dir, find_dir):
    # find subdirectory 'find_dir' within 'start_dir'
    for root, dirs, files in os.walk(start_dir):
        if find_dir in dirs:
            return os.path.join(root, find_dir)
    return

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def find_and_update_git(local_repo, reporoot):
    curr_dir = os.getcwd()
    os.chdir(local_repo)

    git_dir = get_the_git_dir(local_repo, '.git')

    if git_dir:
        os.chdir(git_dir)
        command = 'git pull'
        run_process(command, True, git_dir)
    else:
        command = f'git clone {reporoot}'
        reply = run_process(command, True, local_repo)
        git_dir = get_the_git_dir(local_repo, '.git')

    # Update the dictionary of reporoot and the sha1 so we can have a 'presoak'
    # that updates all the current repos off-line.  It can be tedious if vcget
    # should do all the clone:ing and pull:ing while a debugger is running
    presoak_file = get_presoak_file()
    presoak = load_json_data(presoak_file)
    if presoak[reporoot] == 'presoak':
        presoak[reporoot] = local_repo
        store_json_data(presoak_file, presoak)
    else:
        if presoak[reporoot] != local_repo:
            print(f'internal_error presoaking for {reporoot}')

    os.chdir(curr_dir)

    return git_dir
