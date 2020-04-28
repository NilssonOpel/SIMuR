import os
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
    git_dir = simur.find_and_update_git_cache(reporoot)

    if not git_dir:
        reply  = f'Could not find a .git dir from {reporoot}\n'
        reply += f'when looking in {git_dir}'
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
