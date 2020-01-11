from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import simur
import subprocess
import sys
import urllib

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def usage():
    print(f'{sys.argv[0]} pdb-file srcsrv-dir')
    print(f'  e.g. {sys.argv[0]} RelWithDebInfo\TestGitCat.pdb C:\WinKits\10\Debuggers\x64\srcsrv')

#-------------------------------------------------------------------------------
# --- Routines for extracting the data from the pdb and associated vcs:s ---
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_indexed(root, srcsrv):
    pdbstr = os.path.join(srcsrv, 'pdbstr.exe')
    commando = f'{pdbstr} -r -p:{root} -s:srcsrv'
    # Looks like pdbstr return -1 if not indexed, and 0 if indexed (?)
    reply = simur.run_process(commando, False)

    # I will look at an empty reply as a test
    if len(reply):
        return True
    return False

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def split_url(url):
#    print(f'url: {url}')
    #https://tools.ietf.org/pdf/rfc3986.pdf
    parsed = urllib.parse.urlparse(url)
    reporoot = f'{parsed.scheme}://'
    if parsed.username:
        reporoot += f'{parsed.username}@'
        if parsed.password:
            reporoot += parsed.password
    reporoot += parsed.netloc
    if parsed.port:
        reporoot += f':{parsed.port}'

    relpath = parsed.path
    return reporoot, relpath

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_non_indexed(root, srcsrv):
    srctool = os.path.join(srcsrv, 'srctool.exe')
    commando = f'{srctool} -r {root}'
    # srctool returns the number of files - not an exit code
    filestring = simur.run_process(commando, False)
    all_files = filestring.splitlines()
    files = []
    for file in all_files:
        canonical_path = os.path.realpath(file)
        if os.path.isfile(canonical_path):
            files.append(canonical_path)

    return files

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_in_svn(file, data):
    commando = f'svn info "{file}"'
    reply = simur.run_process(commando, True)
    if len(reply) < 2:
        print(f'svn info returned: {reply}')
        return False

    lines = reply.splitlines()
    hits = 0
    for line in lines:
#        print(line)
        url = re.match('^URL: (.*)$', line)
        if url:
            root, rel = split_url(url.group(1))
            data['reporoot'] = root
            data['relpath']  = rel
            hits += 1
            continue
        rev = re.match('^Revision: (.*)$', line)
        if rev:
            data['revision'] = rev.group(1)
            hits += 1
            continue
        sha1 = re.match('^Checksum: ([a-f0-9]+)$', line)
        if sha1:
            data['sha1']  = sha1.group(1)
            hits += 1
            continue

    if hits != 3:
        return False

    data['vcs'] = 'svn'
    return True

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_git_dir(path):
    # Add a cache for those directories that are not git-ish
    # and also for those that are
    dir = os.path.dirname(path)

    curr_dir = os.path.realpath(dir)
    while True:
#        print(f'Looking at {curr_dir}')
        a_git = os.path.join(curr_dir, '.git')
        if os.path.exists(a_git):
            break
        next_dir = os.path.split(curr_dir)[0]
        if next_dir == curr_dir:
            return None
        curr_dir = next_dir

    return curr_dir

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def was_in_git(file, data):
    report_fail = lambda dir, command: \
        f'When executing in directory: {dir}\n>{command} failed'

    git_dir = get_git_dir(file)
    if git_dir == None:
        return False
    # Make a pushd to the git dir
    curr_dir = os.getcwd()
    os.chdir(git_dir)

    # srctool may return in all lower case and that is not OK with git
    as_on_disk = Path(file).resolve()
    commando = f'git ls-files -s "{as_on_disk}"'
    reply = simur.run_process(commando, True)
    if len(reply) == 0:
        os.chdir(curr_dir)
        return False
    if reply.startswith('fatal'): # fatal: not a git repository ...
#        report_fail(curr_dir, commando)    so it is not a fail
        os.chdir(curr_dir)
        return False
    reply = reply.rstrip()
#    print(f'GIT: |{reply}|')
    repo = re.match('^(\d+)\s*([a-fA-F0-9]+)\s*(\d+)\s*(.+)$', reply)
    if repo:
        data['revision'] = repo.group(2)
        data['relpath']  = repo.group(4)
        data['reporoot'] = git_dir
        data['local']    = git_dir
    else:
        print(report_fail(git_dir, commando))
        print(f'When executing in directory: {git_dir}')
        print(f'>{commando} failed')
        os.chdir(curr_dir)
        return False

    #Look for remote:s
    commando = 'git remote -v'
    reply = simur.run_process(commando, True)
    lines = reply.splitlines()
    for line in lines:
        remote = re.match('^origin\s*(.+)\s+\(fetch\)$', line)
        if remote:
            data['reporoot'] = remote.group(1)
            data['remote']   = remote.group(1)

    data['vcs'] = 'git'

    os.chdir(curr_dir)
    return True

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_in_git(file, data):
    report_fail = lambda dir, command: \
        f'When executing in directory: {dir}\n>{command} failed'

    dir = os.path.dirname(file)
    git_dir = os.path.realpath(dir)
    if git_dir == None:
        return False
    # Make a pushd to the git dir
    curr_dir = os.getcwd()
    os.chdir(git_dir)

    # srctool may return in all lower case and that is not OK with git
    as_on_disk = Path(file).resolve()
    commando = f'git ls-files -s "{as_on_disk}"'
    reply = simur.run_process(commando, False) # False since git may complain
    if len(reply) == 0:                        # if it is not a repo
        os.chdir(curr_dir)
        return False
    if reply.startswith('fatal'): # fatal: not a git repository ...
#        report_fail(curr_dir, commando)    so it is not a fail
        os.chdir(curr_dir)
        return False
    reply = reply.rstrip()
#    print(f'GIT: |{reply}|')
    repo = re.match('^(\d+)\s*([a-fA-F0-9]+)\s*(\d+)\s*(.+)$', reply)
    if repo:
        data['revision'] = repo.group(2)
        data['relpath']  = repo.group(4)
        data['reporoot'] = git_dir
        data['local']    = git_dir
    else:
        print(report_fail(git_dir, commando))
        print(f'When executing in directory: {git_dir}')
        print(f'>{commando} failed')
        os.chdir(curr_dir)
        return False

    #Look for remote:s
    commando = 'git remote -v'
    reply = simur.run_process(commando, True)
    lines = reply.splitlines()
    for line in lines:
        remote = re.match('^origin\s*(.+)\s+\(fetch\)$', line)
        if remote:
            data['reporoot'] = remote.group(1)
            data['remote']   = remote.group(1)

    data['vcs'] = 'git'

    os.chdir(curr_dir)
    return True

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_vcs_information(files, vcs_cache):
    data = {}
    no_vcs = 'no-vcs'

    for file in files:
        if file in vcs_cache.keys():
            cached = vcs_cache[file]
            if no_vcs in cached.keys():
                continue
            data[file] = vcs_cache[file]
        else:
            response = {}
            if is_in_svn(file, response):
                data[file] = response
                vcs_cache[file] = response
                continue
            if is_in_git(file, response):
                data[file] = response
                vcs_cache[file] = response
                continue
            response[no_vcs] = "true"
            vcs_cache[file] = response

    return data

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def dump_vcsdata(vcs_information):
    for file in vcs_information:
        print()
        print(file)
        what = vcs_information[file]
        for key in what:
            print(f'  {key} : {what[key]}')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def report_vcsdata(vcs_information):
    vcses = {}
    for file in vcs_information:
        what = vcs_information[file]
        vcs = what['vcs']
        if vcs in vcses:
            vcses[vcs] += 1
        else:
            vcses[vcs] = 1

    for key in vcses:
        print(f'Found {vcses[key]} files using {key}')

    return vcses

#-------------------------------------------------------------------------------
# --- Routines for inserting the data into the pdb ---
# See https://docs.microsoft.com/en-us/windows/win32/debug/source-server-and-source-indexing
#-------------------------------------------------------------------------------

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def init_the_stream_text(vcs_information):
    stream = []
    # init
    stream.append('SRCSRV: ini -----------------------------------------------')
    stream.append('VERSION=1')
    stream.append('VERCTL=SvnGit')
    instant = datetime.today().isoformat()
    stream.append(f'DATETIME={instant}')

    # variables
    stream.append('SRCSRV: variables -----------------------------------------')
    # How to buid the target path for the extracted file
    stream.append('SRCSRVTRG=%vcget_target%')
    # How to build the command to extract file from source control
    stream.append('SRCSRVCMD=%vcget_command%')

    # fnbksl - replace forward slashes with backward ditos
    # fnfile - extract filename (basename)
    # targ   - is the temp dir where the debugger roots its contents
    stream.append('VCGET_TARGET=' +
        '%targ%\\%fnbksl%(%var4%)\\%var5%\\%fnfile%(%var1%)')
    # How to build the command to extract file from source control
    stream.append('VCGET_COMMAND=' +
        'cmd /c vcget.cmd %var2% "%var3%" "%var4%" %var5% > "%vcget_target%"')

    # our data
    #  VAR2 VAR3       VAR4      VAR5
    # 'svn'*<reporoot>*<relpath>*revision
    # 'git'*<reporoot>*<relpath>*sha
    stream.append('SRCSRV: source files --------------------------------------')
    for file in vcs_information:
        what = vcs_information[file]
        our_data = file + '*'
        our_data += f'{what["vcs"]}*'
        our_data += f'{what["reporoot"]}*'
        our_data += f'{what["relpath"]}*'
        our_data += f'{what["revision"]}'
        stream.append(our_data)

    stream.append('SRCSRV: end -----------------------------------------------')
    return stream

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def dump_stream_data(stream):
    for line in stream:
        print(line)

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def make_backup_file(src_file, extension):
    dst_file = src_file + extension
    if os.path.exists(dst_file):
        return dst_file

    shutil.copyfile(src_file, dst_file)
    return dst_file

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def make_stream_file(pdb_file, stream):
    tempfile = os.path.basename(pdb_file)
    tempfile = tempfile + '.stream'
    if os.path.exists(tempfile):
        os.remove(tempfile)

    with open(tempfile, 'w+t') as f:
        for line in stream:
            f.write(line+'\n')

    return tempfile

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def dump_stream_to_pdb(pdb_file, srcsrv, stream):
    tempfile = make_stream_file(pdb_file, stream)
# To restore the pdb:s
# for %%I in (*.*.orig) do (
#   del %%~nI
#   ren %%I %%~nI
# )
    make_backup_file(pdb_file, '.orig')
    pdbstr = os.path.join(srcsrv, 'pdbstr.exe')
    commando = f'{pdbstr} -w -s:srcsrv -p:{pdb_file} -i:{tempfile}'
    reply = simur.run_process(commando, True)

    os.remove(tempfile)                 # Or keep it for debugging

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def update_presoak_file(vcs_data):
    presoak_file = simur.get_presoak_file()
    data = simur.load_json_data(presoak_file)

    for file in vcs_data:
        what = vcs_data[file]
        if what['vcs'] == 'git':
            remote = what['remote']
            if remote:
                if not remote in data:
                    data[remote] = 'presoak'

    simur.store_json_data(presoak_file, data)

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def check_paths(root, srcsrv):
    if not os.path.exists(srcsrv):
        print(f'Sorry, the WinKits directory {srcsrv} does not exist')
        return 3
    if not os.path.exists(root):
        print(f'Sorry, the pdb {root} does not exist')
        return 3
    if not os.path.isfile(root):
        print(f'Sorry, {root} is not a file')
        return 3

    return 0

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def check_requirements(root, srcsrv):
    if check_paths(root, srcsrv):
        return 3
    if is_indexed(root, srcsrv):
        print(f'Sorry, {root} is already indexed or has no debug information')
        ext = Path(root).suffix
        if ext != '.pdb':
            print(f'  (debug information usually has extension .pdb, not {ext})')
        return 1

    return 0

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def do_the_job(root, srcsrv, vcs_cache, debug=0):
    failing_requirements = check_requirements(root, srcsrv)
    if failing_requirements:
        return failing_requirements

    if debug > 3:
        print('prepPDB START')

    files = get_non_indexed(root, srcsrv)
    if not files:
        print(f'No files to index in {root}')
        return 0
    else:
        print(f'Found {len(files)} source files')

    if debug > 3:
        print(files)

    root_dir = os.path.dirname(root)

    vcs_data = get_vcs_information(files, vcs_cache)
    if not vcs_data:
        print(f'No version controlled files in {root}')
    else:
        if debug > 3:
            dump_vcsdata(vcs_data)

        stream = init_the_stream_text(vcs_data)
        if debug > 3:
            dump_stream_data(stream)
        dump_stream_to_pdb(root, srcsrv, stream)
        update_presoak_file(vcs_data)
        report_vcsdata(vcs_data)
    if debug > 3:
        print('prepPDB END')

    return 0

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def verify_cache_data(vcs_cache):
    # turned out to be cheaper to update than verify
    new_data = {}
    no_vcs = 'no-vcs'

    files = vcs_cache.keys()
    for file in files:
        cached = vcs_cache[file]
        if 'vcs' in cached.keys():
            vcs_system = cached["vcs"]
            if vcs_system == 'svn':
                response = {}
                if is_in_svn(file, response):
                    new_data[file] = response
                else:
                    print(f'svn:{file} removed from cache')
                continue
            if vcs_system == 'git':
                response = {}
                if is_in_git(file, response):
                    new_data[file] = response
                else:
                    print(f'git:{file} removed from cache')
                continue
            eprint(f'verify_cache_data: unhandled vcs {vcs_system}')
            continue
        # How to verify no-vcs cheaply ?
        print(f'non-vcs:{file} removed from cache')

    return new_data

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Too few arguments")
        usage()
        exit(3)
    debug = 0
    root = sys.argv[1]
    srcsrv = sys.argv[2]

    dummy_cache = {}
    outcome = do_the_job(root, srcsrv, dummy_cache, debug)
    return outcome

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
