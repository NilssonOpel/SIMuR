import hashlib
import os
import shutil
import subprocess
import sys


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def usage():
    print(f'{sys.argv[0]} vcs reporoot relpath revision')
    print(f'  e.g. {sys.argv[0]} svn https://barbar/svn/SVNrepo trunk/main.c 3')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def run_process(command, do_check, extra_dir):
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
def handle_svn(reporoot, relpath, revision):
    url = reporoot + '/' + relpath
    command = f'svn cat {url}@{revision}'
    reply = run_process(command, True, None)

    return reply

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def handle_local_git(reporoot, revision):
    # Make a pushd to the git dir
    curr_dir = os.getcwd()
    os.chdir(reporoot)
    command = f'git show {revision}'
    reply = run_process(command, True, reporoot)
    os.chdir(curr_dir)

    return reply

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
def handle_remote_git(reporoot, revision):
    # Take in the cache directory through an environment variable since vcget
    # may be called spontaneous from all kind of debugging tools
    cache_dir = os.getenv('SIMUR_CACHE', 'C:\simur_repo')
    local_repo = my_mkdir(cache_dir)

    reporoot_as_bytes = reporoot.encode() # default utf-8
    repo_dir = hashlib.sha1(reporoot_as_bytes).hexdigest()
    subdir = os.path.join(local_repo, repo_dir)
    local_repo = my_mkdir(subdir)

    # Save a dictionary of reporoot and the sha1 so we can have a 'presoak'
    # that updates all the current repos off-line.  It can be tedious if vcget
    # should do all the clone:ing and pull:ing while a debugger is running

    curr_dir = os.getcwd()
    os.chdir(local_repo)

    if os.path.exists('.git'):
        command = 'git pull'
    else:
        command = f'git clone {reporoot}'
    reply = run_process(command, True, local_repo)

    # find a .git directory for GitHub
    git_dir = get_the_git_dir(local_repo, '.git')
    if not git_dir:
        reply  = f'Could not find a .git dir from {reporoot}\n'
        reply += f'when looking in {local_repo}'
    else:
        os.chdir(git_dir)
        command = f'git show {revision}'
        reply = run_process(command, True, git_dir)

    os.chdir(curr_dir)
    return reply

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def handle_git(reporoot, relpath, revision):
    if os.path.exists(reporoot):
        reply = handle_local_git(reporoot, revision)

    else:
        reply = handle_remote_git(reporoot, revision)

    return reply

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def main():
    if len(sys.argv) < 4:
        print("Too few arguments")
        usage()
        return 3

    vcs = sys.argv[1]
    reporoot = sys.argv[2]
    relpath  = sys.argv[3]
    revision = sys.argv[4]

    if vcs == 'svn':
        reply = handle_svn(reporoot, relpath, revision)
    elif vcs == 'git':
        reply = handle_git(reporoot, relpath, revision)
    else:
        print(f'(Cannot handle {vcs}')
        usage()
        return 3

    print(reply, end='')

    return 0


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
sys.exit(main())
