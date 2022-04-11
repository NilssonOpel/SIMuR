#!/usr/bin/env python3
#
#-------------------------------------------------------------------------------

import hashlib
import json
import os
import re
import subprocess
got_win32api = True
try:
    import win32api
except ModuleNotFoundError:
    got_win32api = False

VCS_CACHE_FILE_NAME = 'vcs_cache.simur.json'
VCS_CACHE_PATTERN = '.simur.json'

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
'''Get current code page'''
def ccp():
    try:
        return ccp.codepage
    except AttributeError:
        reply = os.popen('cmd /c CHCP').read()
        cp = re.match(r'^.*:\s+(\d*)$', reply)
        if cp:
            ccp.codepage = cp.group(1)
        else:
            ccp.codepage = 'utf-8'
        return ccp.codepage

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def run_process(command, do_check, extra_dir=os.getcwd(), as_text=True):
    exit_code = 0
    try:
        encoding_used = None
        if as_text:
            encoding_used = ccp()

        status = subprocess.run(command,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=as_text,
                                encoding=encoding_used,  # See https://bugs.python.org/issue27179
                                check=do_check)
        if status.returncode == 0:
            reply = status.stdout
        else:
            reply = status.stdout
            reply += status.stderr
        exit_code = status.returncode

    except Exception as e:
        reply = '\n-start of exception-\n'
        reply += f'The command\n>{command}\nthrew an exception'
        if extra_dir:
            reply += f' (standing in directory {extra_dir})'
        reply += f':\n\n'
        reply += f'type:  {type(e)}\n'
        reply += f'text:  {e}\n'
        reply += '\n-end of exception-\n'
        reply += f'stdout: {e.stdout}\n'
        reply += f'stderr: {e.stderr}\n'
        if as_text == False:
            reply = reply.encode('utf-8')
        exit_code = 3

    return reply, exit_code

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
def get_repo_cache_dir():
    # Take in the cache directory through an environment variable since vcget
    # may be called spontaneous from all kind of debugging tools
    cache_dir = os.getenv('SIMUR_REPO_CACHE', 'C:\\simur_repo')
    canon_dir = os.path.realpath(cache_dir)
    if not os.path.exists(canon_dir):
        print(f'get_repo_cache_dir(): got {canon_dir}')
        canon_dir = cache_dir

    repo_cache = my_mkdir(canon_dir)

    return repo_cache

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_repo_cache_file(name):
    repo_cache = get_repo_cache_dir()
    cache_file = os.path.join(repo_cache, name)

    return cache_file

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_presoak_file():
    presoak_file = get_repo_cache_file('presoak.json')

    return presoak_file

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_presoak_report_file():
    presoak_file = get_repo_cache_file('presoak_report.json')

    return presoak_file

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def load_json_data(file):
    data = {}
    if not os.path.exists(file):
        return data

    with open(file) as fp:
        try:
            data = json.load(fp)
        except json.decoder.JSONDecodeError:
            pass

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
            answer = os.path.abspath(os.path.join(root, find_dir, ".."))
            return answer
    return

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def find_and_update_git_cache(reporoot):
    # Take in the cache directory through an environment variable since vcget
    # may be called from all kind of debugging tools
    exit_code = 0
    reply = ""
    global_repo = get_repo_cache_dir()

    reporoot_as_bytes = reporoot.encode()  # default utf-8
    repo_dir = hashlib.sha1(reporoot_as_bytes).hexdigest()
    subdir = os.path.join(global_repo, repo_dir)
    global_repo = my_mkdir(subdir)

    curr_dir = os.getcwd()
    os.chdir(global_repo)

    git_dir = get_the_git_dir(global_repo, '.git')

    if git_dir:
        os.chdir(git_dir)
        command = 'git pull'
        reply, exit_code = run_process(command, True, git_dir)
        if exit_code:
            print("  pulling failed: ", reply)
    else:
        command = f'git clone {reporoot}'
        reply, exit_code = run_process(command, True, global_repo)
        git_dir = get_the_git_dir(global_repo, '.git')
        if exit_code:
            print("  cloning failed: ", reply)

    # Update the dictionary of reporoot and the sha1 so we can have a 'presoak'
    # that updates all the current repos off-line.  It can be tedious if vcget
    # should do all the clone:ing and pull:ing while a debugger is running
    presoak_file = get_presoak_file()
    presoak = load_json_data(presoak_file)
    if not presoak:     # You may get an empty dictionary
        if presoak[reporoot] == 'presoak':
            presoak[reporoot] = global_repo
            store_json_data(presoak_file, presoak)
        else:
            if presoak[reporoot] != global_repo:
                print(f'internal_error presoaking for {reporoot}:')
                print(f'  {presoak[reporoot]} vs {global_repo}')
    else:  # Add if missing
        presoak[reporoot] = global_repo
        store_json_data(presoak_file, presoak)

    # Store errors in a file that can be monitored
    if exit_code:
        report_file = get_presoak_report_file()
        report = load_json_data(report_file)
        report[reporoot] = reply.splitlines()
        store_json_data(report_file, report)

    os.chdir(curr_dir)

    return git_dir

#-------------------------------------------------------------------------------
# Shamelessly stolen from:
# https://stackoverflow.com/questions/580924/
#         python-windows-file-version-attribute
#-------------------------------------------------------------------------------
def getFileProperties(fname):
    """
    Read all properties of the given file return them as a dictionary.
    """
    if got_win32api is False:
        return None

    propNames = ('Comments', 'InternalName', 'ProductName',
                 'CompanyName', 'LegalCopyright', 'ProductVersion',
                 'FileDescription', 'LegalTrademarks', 'PrivateBuild',
                 'FileVersion', 'OriginalFilename', 'SpecialBuild')

    props = {'FixedFileInfo': None, 'StringFileInfo': None, 'FileVersion': None}

    try:
        # backslash as parm returns dictionary of numeric info
        # corresponding to VS_FIXEDFILEINFO struc
        fixedInfo = win32api.GetFileVersionInfo(fname, '\\')
        props['FixedFileInfo'] = fixedInfo
        props['FileVersion'] = "%d.%d.%d.%d" % (
                               fixedInfo['FileVersionMS'] / 65536,
                               fixedInfo['FileVersionMS'] % 65536,
                               fixedInfo['FileVersionLS'] / 65536,
                               fixedInfo['FileVersionLS'] % 65536
                           )

        # \VarFileInfo\Translation returns list of available
        # (language, codepage) pairs that can be used to retrieve string info.
        # We are using only the first pair.
        lang, codepage = win32api.GetFileVersionInfo(fname,
            '\\VarFileInfo\\Translation')[0]

        # any other must be of the form \StringfileInfo\%04X%04X\parm_name,
        # middle two are language/codepage pair returned from above

        strInfo = {}
        for propName in propNames:
            strInfoPath = u'\\StringFileInfo\\%04X%04X\\%s' % (lang,
                codepage,
                propName)
            # print str_info
            strInfo[propName] = win32api.GetFileVersionInfo(fname, strInfoPath)

        props['StringFileInfo'] = strInfo
    except Exception:
        pass

    return props
