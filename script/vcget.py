#!/usr/bin/env python3
#
#-------------------------------------------------------------------------------

import os
import sys

import simur

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
    reply, _exit_code = simur.run_process(command, True, extra_dir=None,
        as_text=False)

    # Try to work around any http - https redirecting
    if reply.startswith(b'Redirecting to URL'):
        temp = bytearray(reply)
        slicer = temp.index(b'\r\n') + 2
        reply = temp[slicer:]

    return reply


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def handle_local_git(reporoot, revision):
    # Make a pushd to the git dir
    curr_dir = os.getcwd()
    os.chdir(reporoot)
    command = f'git show {revision}'
    reply, _exit_code = simur.run_process(command, True, extra_dir=reporoot,
        as_text=False)
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
        reply, _exit_code = simur.run_process(command, True, extra_dir=git_dir,
            as_text=False)
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
    if len(sys.argv) < 5:
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
        print(f'Cannot handle {vcs}, only svn and git\n')
        usage()
        return 3

    sys.stdout.buffer.write(reply)

    return 0


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
sys.exit(main())
