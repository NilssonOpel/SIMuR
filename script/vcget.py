import hashlib
import os
import shutil
import simur
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
def handle_svn(reporoot, relpath, revision):
    url = reporoot + '/' + relpath
    command = f'svn cat {url}@{revision}'
    reply = simur.run_process(command, True, None)

    return reply

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def handle_local_git(reporoot, revision):
    # Make a pushd to the git dir
    curr_dir = os.getcwd()
    os.chdir(reporoot)
    command = f'git show {revision}'
    reply = simur.run_process(command, True, reporoot)
    os.chdir(curr_dir)

    return reply

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def handle_remote_git(reporoot, revision):
    # Take in the cache directory through an environment variable since vcget
    # may be called from all kind of debugging tools
    local_repo = simur.get_local_cache_dir()

    reporoot_as_bytes = reporoot.encode() # default utf-8
    repo_dir = hashlib.sha1(reporoot_as_bytes).hexdigest()
    subdir = os.path.join(local_repo, repo_dir)
    local_repo = simur.my_mkdir(subdir)

    git_dir = simur.find_and_update_git(local_repo, reporoot)

    if not git_dir:
        reply  = f'Could not find a .git dir from {reporoot}\n'
        reply += f'when looking in {local_repo}'
    else:
        curr_dir = os.getcwd()
        os.chdir(git_dir)
        command = f'git show {revision}'
        reply = simur.run_process(command, True, git_dir)
        os.chdir(curr_dir)

    return reply

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def handle_git(reporoot, revision):
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
        reply = handle_git(reporoot, revision)
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
