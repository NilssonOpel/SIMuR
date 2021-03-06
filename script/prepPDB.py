from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import sys

import libSrcTool
import simur


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def usage():
    print(f'{sys.argv[0]} pdb-file dir-of-pdbs srcsrv-dir')
    print(f'  e.g. {sys.argv[0]} TestGitCat.pdb RelWithDebInfo C:/WinKits/10/Debuggers/x64/srcsrv')
    print(f'       {sys.argv[0]} armLibSupport.pdb . //ExternalAccess/WinKit10Debuggers/srcsrv')


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
        # "build",
    ]
    skipping_extensions = [
        # ".tmp"
    ]

    dir = os.path.dirname(file)
    for skip_dir in skipping_dirs:
        if dir.startswith(skip_dir):
            return True

    for skip_dir in dir_contains:
        if skip_dir in dir:
            return True

    filename, extension = os.path.splitext(file)
    for skip_ext in skipping_extensions:
        if extension in skip_ext:
            return True

    return False


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_indexed(root, srcsrv):
    pdbstr = os.path.join(srcsrv, 'pdbstr.exe')
    # read the pdb and dump its 'srcsrv' stream
    # - if there is a stream then it is indexed
    commando = f'{pdbstr} -r -p:{root} -s:srcsrv'
    # Looks like pdbstr return -1 if not indexed, and 0 if indexed (?)
    reply = simur.run_process(commando, False)

    # I will look at an empty reply as a test
    if len(reply) == 0:
        return False
    return True


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_non_indexed(root, srcsrv, vcs_cache):
    srctool = os.path.join(srcsrv, 'srctool.exe')
    commando = f'{srctool} -r {root}'
    # srctool returns the number of files - not an exit code
    filestring = simur.run_process(commando, False)
    all_files = filestring.splitlines()
    files = []
    for file in all_files:
        absolute_path = os.path.abspath(file)
        if os.path.isfile(absolute_path):
            files.append(absolute_path)
        if file in vcs_cache.keys():
            files.append(absolute_path)

    return files


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_in_svn(file, data, svn_cache):
    debug_level = 0
    for cached_dir in svn_cache.keys():          # dict on svn roots
        # Since svn may have externals this may fail if we have a narrower root
        if file.startswith(cached_dir):
            svn_content = svn_cache[cached_dir]  # dict on abs path file
            if file in svn_content.keys():
                copy_cache_response(data, svn_content[file])
                if debug_level > 4:
                    print(f'Found in cache: {file}')
                return True

    svn_dir = get_root_dir(file, '.svn')
    if svn_dir is None:
        return False

    if str(svn_dir) in svn_cache.keys():
        if debug_level > 4:
            print(f'Already cached {svn_dir} - {file}')
        return False

    # Make a pushd to the svn dir
    curr_dir = os.getcwd()
    os.chdir(svn_dir)

    if debug_level > 4:
        print(f'svn-caching: {svn_dir} - {file}')
    commando = f'svn info -R'
    reply = simur.run_process(commando, True)
    if len(reply) < 2:
        if debug_level > 4:
            print(f'svn info returned: {reply}')
        os.chdir(curr_dir)
        return False

    svn_dir = str(svn_dir)
    svn_cache[svn_dir] = {}
    dir_cache = svn_cache[svn_dir]

    lines = reply.splitlines()

    path_str = 'Path: '
    url_str = 'URL: '
    rev_str = 'Revision: '
    sha_str = 'Checksum: '
    nod_str = 'Node Kind: '
    # In case of doubt: use brute force
    no_of_lines = len(lines)
    curr_line = 0

    hits = 0
    # Eat the first entry - it is the root dir
    while curr_line < no_of_lines:
        line = lines[curr_line]
        if line.startswith(url_str):
            url = line[len(url_str):]   # Get the repository root
        curr_line += 1
        if len(line) == 0:
            break

    path = rev = sha = node_kind = None
    while curr_line < no_of_lines:
        line = lines[curr_line]
        if debug_level > 4:
            print(f'IN: {hits} {line}')
        curr_line += 1

        if hits >= 3 or curr_line >= no_of_lines or len(line) == 0:
            # Make the key
            if debug_level > 4:
                print(f'hits; {hits}')
                print(f'cnt ; {curr_line}:{no_of_lines}')
                print(f'len ; {len(line)}')
                if not url:
                    print(f"No url")
                if not path:
                    print(f"No path")
                if not rev:
                    print(f"No revh")
                if not sha:
                    print(f"No sha")

            if not path:
                path = 'None'
                node_kind = 'went_wrong'
            if not (url and rev and (sha or node_kind)):  # DeLorean
                node_kind = 'went_wrong'
            try:
                key = os.path.join(svn_dir, path)
                key = os.path.abspath(key)
            except Exception:
                if debug_level > 4:
                    print(f'cannot handle the path')
                # Incapacitate in case we encounter them in the future
                path = 'throw_on_path'
                key  = 'throw_on_key'
                hits = 0
                node_kind = 'exception'

            if node_kind == 'file':
                key = str(key)  # json cannot have WindowsPath as key
                cache_entry = {}
                disk_rel = os.path.relpath(path)
                url_rel = disk_rel.replace('\\', '/')   # since disk_rel is str
                cache_entry['reporoot'] = url
                cache_entry['relpath']  = url_rel
                cache_entry['revision'] = rev
                cache_entry['sha1'] = sha
                cache_entry['vcs'] = 'svn'
                dir_cache[key] = cache_entry
                if debug_level > 4:
                    print(f'Inserts: {key}')
            else:
                if debug_level > 4:
                    print(f'Skips: {node_kind} - {path}')

            path = rev = sha = node_kind = None
            hits = 0

        if line.startswith(path_str):
            path = line[len(path_str):]
            hits += 1
        if line.startswith(rev_str):
            rev = line[len(rev_str):]
            hits += 1
        if line.startswith(sha_str):
            sha = line[len(sha_str):]
            hits += 1
        if line.startswith(nod_str):
            node_kind = line[len(nod_str):]

    os.chdir(curr_dir)
    # We may have looked in this directory but 'file' maybe isn't under VC
    if file in dir_cache.keys():
        copy_cache_response(data, dir_cache[file])
        return True
    return False


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_in_svn_raw(file, data, dummy):
    debug_level = 0
    svn_dir = get_root_dir(file, '.svn')
    if svn_dir is None:
        return False

    # Make a pushd to the svn dir
    curr_dir = os.getcwd()
    os.chdir(svn_dir)

    commando = 'svn info --show-item url .'
    reply = simur.run_process(commando, True)
    reporoot = reply.strip()
    disk_rel = os.path.relpath(file)
    url_rel  = disk_rel.replace('\\', '/')

    commando = f'svn info "{file}"'
    reply = simur.run_process(commando, True)
    if len(reply) < 2:
        print(f'svn info returned: {reply}')
        os.chdir(curr_dir)
        return False

    lines = reply.splitlines()
    hits = 0
    for line in lines:
        if debug_level > 4:
            print(line)
        # Just check if we get an URL: but we ignore what it says
        url = line.startswith('URL: ')
        if url:
            data['reporoot'] = reporoot
            data['relpath']  = url_rel
            hits += 1
            continue
        rev = re.match(r'^Revision: (.*)$', line)
        if rev:
            data['revision'] = rev.group(1)
            hits += 1
            continue
        sha1 = re.match(r'^Checksum: ([a-fA-F0-9]+)$', line)
        if sha1:
            data['sha1'] = sha1.group(1)
            hits += 1
            continue

    os.chdir(curr_dir)
    if hits != 3:
        return False

    data['vcs'] = 'svn'
    return True


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_root_dir(path, ext):
    debug_level = 0
    # Add a cache for those directories that are not git-ish
    # and also for those that are
    dir = os.path.dirname(path)
    curr_dir = os.path.abspath(dir)
    while True:
        if debug_level > 4:
            print(f'Looking at {curr_dir}')
        a_root = os.path.join(curr_dir, ext)
        if os.path.exists(a_root):
            break
        next_dir = os.path.split(curr_dir)[0]
        if next_dir == curr_dir:
            return None
        curr_dir = next_dir

    curr_dir = os.path.abspath(curr_dir)
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
    debug_level = 0
    report_fail = lambda dir, command: \
        f'When executing in directory: {dir}\n>{command} failed'

    for cached_dir in git_cache.keys():          # dict on git roots
        if file.startswith(cached_dir):
            git_content = git_cache[cached_dir]  # dict on abs path file
            if file in git_content.keys():
                copy_cache_response(data, git_content[file])
                return True
            else:
                if debug_level > 4:
                    print(f'in cached directory {cached_dir}:')
                    print(f'  {file} was not found')

    git_dir = get_git_dir(file)
    if git_dir is None:
        return False

    # Make a pushd to the git dir
    curr_dir = os.getcwd()
    os.chdir(git_dir)

    if debug_level > 4:
        print(f'git-caching: {git_dir}')

    #Look for remote:s
    commando = 'git remote -v'
    git_remote = None
    reply = simur.run_process(commando, True)
    lines = reply.splitlines()
    for line in lines:
        remote = re.match(r'^origin\s*(.+)\s+\(fetch\)$', line)
        if remote:
            git_remote = remote.group(1)
        # No else - you cannot know if there is a remote

    if git_remote is None:
        print(f'Warning: {git_dir} has no remote')

    # Get the contents of the repository
    commando = 'git ls-files -s'
    reply = simur.run_process(commando, True)
    if len(reply) == 0:
        os.chdir(curr_dir)
        return False
    if reply.startswith('fatal'):  # fatal: not a git repository ...
        os.chdir(curr_dir)         # so it is not a fail
        return False

    git_dir = str(git_dir)
    git_cache[git_dir] = {}
    dir_cache = git_cache[git_dir]
    # Iterate on lines
    for line in reply.splitlines():
        # 100644 2520fa373ff004b2fd4f9fa3e285b0d7d36c9319 0   script/prepPDB.py
        repo = re.match(r'^\d+\s*([a-fA-F0-9]+)\s*\d+\s*(.+)$', line)
        if repo:
            revision = repo.group(1)
            rel_key  = repo.group(2)
            # Make the key
            key = os.path.join(git_dir, rel_key)
            try:
                key = os.path.abspath(key)
            except Exception:
                if debug_level > 4:
                    print(f'cannot handle {line}')
                continue
            key = str(key)  # json cannot have WindowsPath as key
            dir_cache[key] = {}
            cache_entry = dir_cache[key]
            cache_entry['reporoot'] = git_remote
            cache_entry['relpath']  = rel_key
            cache_entry['revision'] = revision
            cache_entry['sha1']     = revision
            cache_entry['local']    = git_dir
            cache_entry['remote']   = git_remote
            cache_entry['vcs']      = 'git'
        else:
            print(report_fail(git_dir, commando))
            print(f'When executing in directory: {git_dir}')
            print(f'>{commando} failed')
            os.chdir(curr_dir)
            return False

    os.chdir(curr_dir)
    # We may have looked in this directory but 'file' maybe isn't under VC
    if file in dir_cache.keys():
        copy_cache_response(data, dir_cache[file])
        return True

    return False


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_in_git_raw(file, data, dummy):
    debug_level = 0
    report_fail = lambda dir, command: \
        f'When executing in directory: {dir}\n>{command} failed'

    git_dir = get_git_dir(file)
    if git_dir is None:
        return False

    # Make a pushd to the git dir
    curr_dir = os.getcwd()
    os.chdir(git_dir)

    commando = f'git ls-files -s "{file}"'
    reply = simur.run_process(commando, False)  # False since git may complain
    if len(reply) == 0:                         # if it is not a repo
        os.chdir(curr_dir)
        return False
    if reply.startswith('fatal'):  # fatal: not a git repository ...
        if debug_level > 4:
            print(report_fail(curr_dir, commando))  # so it is not a fail
        os.chdir(curr_dir)
        return False
    reply = reply.rstrip()
    if debug_level > 4:
        print(f'GIT: |{reply}|')
    repo = re.match(r'^(\d+)\s*([a-fA-F0-9]+)\s*(\d+)\s*(.+)$', reply)
    if repo:
        data['reporoot'] = str(git_dir)
        data['relpath']  = repo.group(4)
        data['revision'] = repo.group(2)
        data['sha1']     = repo.group(2)
        data['local']    = str(git_dir)
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
        remote = re.match(r'^origin\s*(.+)\s+\(fetch\)$', line)
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
        # Restore correct case-ing to satisfy git (and me)
        file = os.path.abspath(file)
        file = str(file)
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
            if is_in_git(file, response, git_cache):
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
def plural_files(no):
    if no == 1:
        return 'file'
    return 'files'


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
        print(f'Found {vcses[key]} {plural_files(vcses[key])} using {key}')

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
    stream.append('VCGET_TARGET='
                  '%targ%\\%fnbksl%(%var4%)\\%var6%\\%fnfile%(%var1%)')
    # How to build the command to extract file from source control
    stream.append('VCGET_COMMAND='
                  'cmd /c vcget.cmd %var2% "%var3%" "%var4%" %var5%'
                  ' > "%vcget_target%"')

    # our data
    #  VAR2 VAR3       VAR4      VAR5     VAR6
    # 'svn'*<reporoot>*<relpath>*revision*sha1
    # 'git'*<reporoot>*<relpath>*revision*sha1
    # for git revision and sha1 is the same
    stream.append('SRCSRV: source files --------------------------------------')
    for file in vcs_information:
        what = vcs_information[file]
        our_data = file + '*'
        our_data += f'{what["vcs"]}*'
        our_data += f'{what["reporoot"]}*'
        our_data += f'{what["relpath"]}*'
        our_data += f'{what["revision"]}*'
        our_data += f'{what["sha1"]}'
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
def make_cache_file(pdb_file):
    common_root, ext = os.path.splitext(pdb_file)
    cache_file = common_root + '.simur.json'
    return cache_file


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
            f.write(line + '\n')

    return tempfile


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def dump_stream_to_pdb(pdb_file, srcsrv, stream):
    debug_level = 0
    tempfile = make_stream_file(pdb_file, stream)
# To restore the pdb:s
#---
#for /R %%I in (*.*.orig) do call :doit %%I %%~nI %%~pI
#goto :EOF
#:doit
#pushd %3
#del %2
#ren %1 %2
#popd
#---
    if debug_level > 4:
        make_backup_file(pdb_file, '.orig')
    pdbstr = os.path.join(srcsrv, 'pdbstr.exe')
    commando = f'{pdbstr} -w -s:srcsrv -p:{pdb_file} -i:{tempfile}'
    simur.run_process(commando, True)

    os.remove(tempfile)                 # Or keep it for debugging


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def write_cache_file(pdb_file, vcs_data):
    cache_file = make_cache_file(pdb_file)
    simur.store_json_data(cache_file, vcs_data)

    pdb_access_time  = os.path.getatime(pdb_file)
    pdb_mod_time  = os.path.getmtime(pdb_file)
    os.utime(cache_file, times=(pdb_access_time, pdb_mod_time))

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
def check_winkits(srcsrv):
    if not os.path.exists(srcsrv):
        print(f'Sorry, the WinKits directory {srcsrv} does not exist')
        return 3
    return 0


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def check_paths(root):
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
def check_indexed(root, srcsrv):
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
def check_indexed_lib(pdb):
    # Heuristic: is there a 'cache file' that is newer than the base.pdb
    composed_prep = make_cache_file(pdb)
    if os.path.exists(composed_prep):
        prep_mod_time = os.path.getmtime(composed_prep)
        pdb_mod_time  = os.path.getmtime(pdb)
        if prep_mod_time >= pdb_mod_time:
            lib_data_file = composed_prep
            return lib_data_file

    return ""


#-------------------------------------------------------------------------------
# Insert VCS data from static library
#-------------------------------------------------------------------------------
def merge_vcs_data(vcs_cache, lib_data_file):
    lib_data = simur.load_json_data(lib_data_file)
    # Should we check if we overwrite anything?  But how do we know which one is
    # correct when getting data from a static library
#    print(f'Merge from {lib_data_file}')
#    dump_vcsdata(lib_data)
    vcs_cache.update(lib_data)
#    print(f'Outcome:')
#    dump_vcsdata(vcs_cache)


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def check_requirements(root, srcsrv):
    if check_paths(root):
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
# Handle PDB:s for executables (*.exe, *.dll)
#-------------------------------------------------------------------------------
def prep_exe_pdb(root, srcsrv, vcs_cache, svn_cache, git_cache, debug=0):
    already_indexed = check_indexed(root, srcsrv)
    if already_indexed:
        return 0

    failing_requirements = check_paths(root)
    if failing_requirements:
        return failing_requirements

    make_time_stamp('prep_exe_pbd START', debug)
    if debug > 3:
        print('prep_exe_pbd START')

    make_time_stamp('get_non_indexed', debug)
    files = get_non_indexed(root, srcsrv, vcs_cache)
    if len(files) == 0:
        print(f'No files to index in {root}')
        return 0

    print(f'Found {len(files)} source {plural_files(len(files))}')

    if debug > 3:
        for file in files:
            print(file)

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
        print('prep_exe_pbd END')
    make_time_stamp('prep_exe_pbd END', debug)

    return 0


#-------------------------------------------------------------------------------
# Handle PDB:s for static libraries (*.lib)
#-------------------------------------------------------------------------------
def prep_lib_pdb(root, srcsrv, cvdump, vcs_cache, svn_cache, git_cache, debug=0):
    lib_data_file = check_indexed_lib(root)
    if len(lib_data_file):
        # OK, so add data from that file to our current understanding
        print(f'{root} already indexed - taking cached data from {lib_data_file}')
        merge_vcs_data(vcs_cache, lib_data_file)
        return 0

    make_time_stamp('prep_lib_pbd START', debug)
    files = libSrcTool.get_lib_source_files(root, cvdump, srcsrv)
    if len(files) == 0:
        print(f'No files to index in {root} for static lib')
        return 0

    print(f'Found {len(files)} source {plural_files(len(files))}')

    if debug > 3:
        for file in files:
            print(file)

    make_time_stamp('get_vcs_information', debug)
    vcs_data = get_vcs_information(files, vcs_cache, svn_cache, git_cache)
    if not vcs_data:
        print(f'No version controlled files in {root}')
    else:
        if debug > 3:
            dump_vcsdata(vcs_data)

        write_cache_file(root, vcs_data)
        report_vcsdata(vcs_data)

    if debug > 3:
        print('prep_lib_pbd END')
    make_time_stamp('prep_lib_pbd END', debug)

    return 0


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def extract_repo_roots(the_cache):
    roots = []
    for the_dir in the_cache.keys():
        roots.append(the_dir)

    return roots


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def verify_cache_data(vcs_cache):
    # turned out to be cheaper to update than verify
    new_data = {}
    svn_cache = {}
    git_cache = {}

    files = vcs_cache.keys()
    for file in files:
        cached = vcs_cache[file]
        if 'vcs' in cached.keys():
            vcs_system = cached["vcs"]
            if vcs_system == 'svn':
                response = {}
                if is_in_svn_raw(file, response, svn_cache):
                    new_data[file] = response
                else:
                    print(f'svn:{file} removed from cache')
                continue
            if vcs_system == 'git':
                response = {}
                if is_in_git_raw(file, response, git_cache):
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
def do_the_job(the_pdb, root, srcsrv, cvdump, dummy_cache, svn_cache, git_cache,
    debug_level):
    import processPDBs as processPDBs

    pdbs = processPDBs.list_all_files(root, ".pdb")
    if len(pdbs) == 0:
        print(f'No PDB:s found in directory {root}')
        return 3

    # If there is no cvdump, then we won't filter out an lib_pdbs either
    lib_pdbs, exe_pdbs = processPDBs.filter_pdbs(pdbs, cvdump, srcsrv)

    outcome = 0
    cache_file = os.path.join(root, 'vcs_cache.json')
    # vcs_cache = simur.load_json_data(cache_file)
    # Should verify or update the cache before using it! - But it takes time
    # vcs_cache = prepPDB.verify_cache_data(vcs_cache)
    vcs_cache = {}
    svn_cache = {}
    git_cache = {}

    for lib_pdb in lib_pdbs:
        print(f'---\nProcessing library {lib_pdb}')
        outcome += prep_lib_pdb(lib_pdb,
                                        srcsrv,
                                        cvdump,
                                        vcs_cache,
                                        svn_cache,
                                        git_cache,
                                        debug_level)

    for exe_pdb in exe_pdbs:
        if not the_pdb in exe_pdb:
            print(f'---\nSkipping {exe_pdb}')
            continue
        print(f'---\nProcessing executable {exe_pdb}')
        outcome += prep_exe_pdb(exe_pdb,
                                        srcsrv,
                                        vcs_cache,
                                        svn_cache,
                                        git_cache,
                                        debug_level)

    if debug_level > 4:
        simur.store_json_data(cache_file, vcs_cache)
    # Store the directories where we found our 'roots'
    # This can be used for checking if we have un-committed changes
    roots = {}
    roots["svn"] = extract_repo_roots(svn_cache)
    roots["git"] = extract_repo_roots(git_cache)
    repo_file = os.path.join(root, 'repo_roots.json')
    simur.store_json_data(repo_file, roots)

    if debug_level > 4:
        svn_file = os.path.join(root, 'svn_cache.json')
        simur.store_json_data(svn_file, svn_cache)
        git_file = os.path.join(root, 'git_cache.json')
        simur.store_json_data(git_file, git_cache)

    return outcome

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def main():
    '''Just as processPDBs only that as the first argument give the PDB of
    interest
    Example:
    prepPDB.py armLibSupport.pdb . //ExternalAccess/WinKit10Debuggers/srcsrv
    '''
    debug_level = 6
    if len(sys.argv) < 2:
        print("Too few arguments")
        usage()
        exit(3)
    the_pdb = sys.argv[1]
    root = sys.argv[2]
    cvdump = 'cvdump.exe'
    srcsrv = 'C:\\Program Files (x86)\\Windows Kits\\10\\Debuggers\\x64\\srcsrv'
    if len(sys.argv) > 3:
        srcsrv = sys.argv[3]
    if check_winkits(srcsrv):
        return 3

    if len(sys.argv) > 4:
        cvdump = sys.argv[4]
    cvdump = libSrcTool.check_cvdump(cvdump)

    dummy_cache = {}
    svn_cache = {}
    git_cache = {}
    outcome = do_the_job(the_pdb, root, srcsrv, cvdump, dummy_cache, svn_cache,
        git_cache, debug_level)
#    dummy_file = 'dummy.json'
#    simur.store_json_data(dummy_file, dummy_cache)
    return outcome


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
