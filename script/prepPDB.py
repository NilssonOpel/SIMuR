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
def skip_file(file):
    skipping_dirs = [
        "c:\\program files",
        "C:\\Program Files",
    ]
    dir_contains = [
        "build",
    ]

    dir = os.path.dirname(file)
    for skip_dir in skipping_dirs:
        if dir.startswith(skip_dir):
#            print(f'Skipping {file}')
            return True

    for skip_dir in dir_contains:
        if skip_dir in dir:
#            print(f'Skipping {file}')
            return True

    return False

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
def is_in_svn(file, data, svn_cache):
    as_on_disk = Path(file).resolve()
    as_on_disk = str(as_on_disk)

    for cached_dir in svn_cache.keys():         # dict on svn roots
        if as_on_disk.startswith(cached_dir):
            descended_into_cache_dir = cached_dir
            svn_content = svn_cache[cached_dir] # dict on abs path file
            if as_on_disk in svn_content.keys():
                copy_cache_response(data, svn_content[as_on_disk])
                print(f'SVN-CACHE: {file}')
                return True
            else:
                print(f'in cached directory {cached_dir}:')
                print(f'  {as_on_disk} was not found')
                return False

    svn_dir = get_root_dir(file, '.svn')
    if svn_dir == None:
        return False

    # Make a pushd to the svn dir
    curr_dir = os.getcwd()
    os.chdir(svn_dir)

    commando = f'svn info -R'
    reply = simur.run_process(commando, True)
    if len(reply) < 2:
        print(f'svn info returned: {reply}')
        os.chdir(curr_dir)
        return False

    svn_dir = str(svn_dir)
    svn_cache[svn_dir] = {}
    dir_cache = svn_cache[svn_dir]

    lines = reply.splitlines()
    more_lines = True

    path_str = 'Path: '
    url_str = 'URL: '
    rev_str = 'Revision: '
    sha_str = 'Checksum: '
    # In case of doubt: use brute force
    no_of_lines = len(lines)
    curr_line = 0

    hits = 0
    # Eat the first entry - it is the root dir
    while curr_line < no_of_lines:
        line = lines[curr_line]
        if line.startswith(url_str):
            print(f'REPOROOT: {line}')
            url = line[len(url_str):]   # Get the reporoot
#        print(f'SKIP: {line}')
        if len(line) == 0:
            break
        curr_line += 1

    while curr_line < no_of_lines:
        if hits >= 3:
            # Make the key
            if not url:
                print(f"No url")
            if not path:
                print(f"No path")
            if not rev:
                print(f"No revh")
            if not sha:
                print(f"No sha")
            if not (path and url and rev and sha): # DeMorgan or DeLorean
                print("Something went wrong")
                exit(347)

            key = os.path.join(svn_dir, path)
            try:
                key = Path(key).resolve()
            except:
                print(f'cannot handle {path}')
                hits = 0
                continue
            key = str(key)  # json cannot have WindowsPath as key
            cache_entry = {}
            cache_entry['relpath']  = os.path.relpath(path)
            cache_entry['reporoot'] = url
            cache_entry['revision'] = rev
            cache_entry['sha1']  = sha
            cache_entry['vcs'] = 'svn'
            path = rev = sha = None
            dir_cache[key] = cache_entry
            hits = 0

        line = lines[curr_line]
        print(f'IN: {line}')
        curr_line += 1

        ### Handle IN: 'Node Kind: directory' rather != file
        if line.startswith(path_str):
            path = line[len(path_str):]
            hits += 1
        if line.startswith(rev_str):
            rev = line[len(rev_str):]
            hits += 1
        if line.startswith(sha_str):
            sha = line[len(sha_str):]
            hits += 1

    copy_cache_response(data, dir_cache[as_on_disk])
    os.chdir(curr_dir)
    return True

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_in_svn_raw(file, data, cache):
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
def get_root_dir(path, ext):
    # Add a cache for those directories that are not git-ish
    # and also for those that are
    dir = os.path.dirname(path)

    curr_dir = os.path.realpath(dir)
    while True:
#        print(f'Looking at {curr_dir}')
        a_root = os.path.join(curr_dir, ext)
        if os.path.exists(a_root):
            break
        next_dir = os.path.split(curr_dir)[0]
        if next_dir == curr_dir:
            return None
        curr_dir = next_dir

    return curr_dir

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_git_dir(path):
    return get_root_dir(path, '.git')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def copy_cache_response(data, response):  # why do I need to do this ?
    for key in response.keys():
        data[key] = response[key]

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_in_git(file, data, git_cache):
    report_fail = lambda dir, command: \
        f'When executing in directory: {dir}\n>{command} failed'

    # srctool may return in all lower case and that is not OK with git
    as_on_disk = Path(file).resolve()
    as_on_disk = str(as_on_disk)

    for cached_dir in git_cache.keys():         # dict on git roots
        if as_on_disk.startswith(cached_dir):
            git_content = git_cache[cached_dir] # dict on abs path file
            if as_on_disk in git_content.keys():
                copy_cache_response(data, git_content[as_on_disk])
                return True
            else:
                print(f'in cached directory {cached_dir}:')
                print(f'  {as_on_disk} was not found')
                return False

    git_dir = get_git_dir(file)
    if git_dir == None:
        return False

    # Make a pushd to the git dir
    curr_dir = os.getcwd()
    os.chdir(git_dir)

    #Look for remote:s
    commando = 'git remote -v'
    git_remote = 'none'
    reply = simur.run_process(commando, True)
    lines = reply.splitlines()
    for line in lines:
        remote = re.match('^origin\s*(.+)\s+\(fetch\)$', line)
        if remote:
            git_remote = remote.group(1)
        # No else - you cannot know it there is a remote

    # Get the contents of the repository
    commando = 'git ls-files -s'
    reply = simur.run_process(commando, True)
    if len(reply) == 0:
        os.chdir(curr_dir)
        return False
    if reply.startswith('fatal'): # fatal: not a git repository ...
        os.chdir(curr_dir)         # so it is not a fail
        return False

    git_dir = str(git_dir)
    git_cache[git_dir] = {}
    dir_cache = git_cache[git_dir]
    # Iterate on lines
    for line in reply.splitlines():
    # 100644 2520fa373ff004b2fd4f9fa3e285b0d7d36c9319 0       script/prepPDB.py
        repo = re.match('^\d+\s*([a-fA-F0-9]+)\s*\d+\s*(.+)$', line)
        if repo:
            revision = repo.group(1)
            rel_key  = repo.group(2)
            # Make the key
            key = os.path.join(git_dir, rel_key)
            try:
                key = Path(key).resolve()
            except:
                print(f'cannot handle {line}')
                continue
            key = str(key)  # json cannot have WindowsPath as key
            dir_cache[key] = {}
            cache_entry = dir_cache[key]
            cache_entry['revision'] = revision
            cache_entry['relpath']  = rel_key
            cache_entry['reporoot'] = git_remote
            cache_entry['remote']   = git_remote
            cache_entry['local']    = git_dir
            cache_entry['vcs']      = 'git'
        else:
            print(report_fail(git_dir, commando))
            print(f'When executing in directory: {git_dir}')
            print(f'>{commando} failed')
            os.chdir(curr_dir)
            return False

    copy_cache_response(data, dir_cache[as_on_disk])

    os.chdir(curr_dir)
    return True

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_in_git_raw(file, data, dummy):
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
def get_vcs_information(files, vcs_cache, svn_cache, git_cache):
    data = {}
    no_vcs = 'no-vcs'

    for file in files:
        if skip_file(file):
            continue
        if file in vcs_cache.keys():
            cached = vcs_cache[file]
            if no_vcs in cached.keys():
                continue
            data[file] = vcs_cache[file]
        else:
            response = {}
            if is_in_svn(file, response, svn_cache):
                data[file] = response
                vcs_cache[file] = response
                continue
            if True:
                if is_in_git(file, response, git_cache):
                    key = Path(file).resolve()
                    key = str(key)
                    data[key] = response
                    vcs_cache[file] = response
            else:
                if is_in_old_git(file, response, git_cache):
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
        for key in what.keys():
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

#    os.remove(tempfile)                 # Or keep it for debugging

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
def make_time_stamp(text, debug):
    if not debug:
        return
    instant = datetime.today().strftime("%H:%M:%S:%f")
    print(f'{instant}: {text}')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def do_the_job(root, srcsrv, vcs_cache, svn_cache, git_cache, debug=0):
    failing_requirements = check_requirements(root, srcsrv)
    if failing_requirements:
        return failing_requirements

    make_time_stamp('prepPDB START', debug)
    if debug > 3:
        print('prepPDB START')

    make_time_stamp('get_non_indexed', debug)
    files = get_non_indexed(root, srcsrv)
    if not files:
        print(f'No files to index in {root}')
        return 0
    else:
        print(f'Found {len(files)} source files')

    if debug > 3:
        for file in files:
            print(file)

    root_dir = os.path.dirname(root)

    make_time_stamp('get_vcs_information', debug)
    vcs_data = get_vcs_information(files, vcs_cache, svn_cache, git_cache)
    if not vcs_data:
        print(f'No version controlled files in {root}')
    else:
        if debug > 3:
            make_time_stamp('dump_vcsdata', debug)
            dump_vcsdata(vcs_data)

        make_time_stamp('init_the_stream_text', debug)
        stream = init_the_stream_text(vcs_data)
        if debug > 3:
            dump_stream_data(stream)
        make_time_stamp('dump_stream_to_pdb', debug)
        dump_stream_to_pdb(root, srcsrv, stream)
        make_time_stamp('update_presoak_file', debug)
        update_presoak_file(vcs_data)
        make_time_stamp('report_vcsdata', debug)
        report_vcsdata(vcs_data)
    if debug > 3:
        print('prepPDB END')
    make_time_stamp('prepPDB END', debug)

    return 0

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def verify_cache_data(vcs_cache):
    # turned out to be cheaper to update than verify
    new_data = {}
    svn_cache = {}
    git_cache = {}
    no_vcs = 'no-vcs'

    files = vcs_cache.keys()
    for file in files:
        cached = vcs_cache[file]
        if 'vcs' in cached.keys():
            vcs_system = cached["vcs"]
            if vcs_system == 'svn':
                response = {}
                if is_in_svn(file, response, svn_cache):
                    new_data[file] = response
                else:
                    print(f'svn:{file} removed from cache')
                continue
            if vcs_system == 'git':
                response = {}
                if is_in_git(file, response, git_cache):
                    new_data[file] = response
                else:
                    print(f'git:{file} removed from cache')
                continue
            print(f'verify_cache_data: unhandled vcs {vcs_system}')
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
    svn_cache = {}
    git_cache = {}
    outcome = do_the_job(root, srcsrv, dummy_cache, svn_cache, git_cache, debug)
    dummy_file = 'dummy.json'
#    simur.store_json_data(dummy_file, dummy_cache)
    return outcome

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
