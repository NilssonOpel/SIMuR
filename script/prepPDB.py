#!/usr/bin/env python3
#
#----------------------------------------------------------------------

from datetime import datetime
import os
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

    file_dir = os.path.dirname(file)
    for skip_dir in skipping_dirs:
        if file_dir.startswith(skip_dir):
            return True

    for skip_dir in dir_contains:
        if skip_dir in file_dir:
            return True

    _filename, extension = os.path.splitext(file)
    for skip_ext in skipping_extensions:
        if extension in skip_ext:
            return True

    return False

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_indexed(root, srcsrv, options):
    pdbstr = os.path.join(srcsrv, 'pdbstr.exe')
    # read the pdb and dump its 'srcsrv' stream
    # - if there is a stream then it is indexed
    # Use a list to avoid whitespace problems in paths
    commando = [pdbstr, '-r', f'-p:{root}', '-s:srcsrv']
    reply, exit_code = simur.run_process(commando, False)
    if options.debug_level > 3:
        print(f'{commando} returned {exit_code = }')
        print(f'{reply = }')

    # I will look at an empty reply as not indexed
    if len(reply) == 0:
        return False

    if not options.quiet:
        print(f'Sorry, {root} is already indexed or has no debug information')
    return True

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_non_indexed_files(root, srcsrv, options):
    srctool = os.path.join(srcsrv, 'srctool.exe')
    commando = [srctool, '-r', root]
    # srctool returns the number of files - not an exit code
    filestring, exit_code = simur.run_process(commando, False)
    if options.debug_level > 3:
        print(f'{commando} returned {exit_code = }')
        print(filestring)

    all_files = filestring.splitlines()[:-1]  # Last line is no source file
    files = []
    for file in all_files:
        if file[0] == '*':
            # Do not know what this is, but lines starting with a star ('*')
            # seems to refer to non-existing .inj files in the object directory
            continue;
        absolute_path = os.path.abspath(file)
        files.append(absolute_path)

    return files

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_in_svn(file, data, svn_cache, options):
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

    svn_dir = get_svn_dir(file)
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
    commando = 'svn info -R'
    reply, _exit_code = simur.run_process(commando, True)
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
                    print("No url")
                if not path:
                    print("No path")
                if not rev:
                    print("No rev")
                if not sha:
                    print("No sha")

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
                    print('cannot handle the path')
                # Incapacitate in case we encounter them in the future
                path = 'throw_on_path'
                key  = 'throw_on_key'
                hits = 0
                node_kind = 'exception'

            if node_kind == 'file':
                key = str(key)  # json cannot have WindowsPath as key
                if options.lower_case_pdb:
                    key = key.lower()
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
def is_in_svn_raw(file, data, _dummy, _options):
    debug_level = 0
    svn_dir = get_svn_dir(file)
    if svn_dir is None:
        return False

    # Make a pushd to the svn dir
    curr_dir = os.getcwd()
    os.chdir(svn_dir)

    commando = 'svn info --show-item url .'
    reply, _exit_code = simur.run_process(commando, True)
    reporoot = reply.strip()
    disk_rel = os.path.relpath(file)
    url_rel  = disk_rel.replace('\\', '/')

    commando = f'svn info "{file}"'
    reply, _exit_code = simur.run_process(commando, True)
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
    path_dir = os.path.dirname(path)
    curr_dir = os.path.abspath(path_dir)
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
    debug_level = 0
    if debug_level > 4:
        print('Looking for a .git directory')
    return get_root_dir(path, '.git')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_svn_dir(path):
    debug_level = 0
    if debug_level > 4:
        print('Looking for a .svn directory')
    return get_root_dir(path, '.svn')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def copy_cache_response(data, response):  # why do I need to do this ?
    for key in response.keys():
        data[key] = response[key]

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def is_in_git(file, data, git_cache, options):
    debug_level = 0
    report_fail = lambda dir, command: \
        f'When executing in directory: {dir}\n>{command} failed'

    for cached_dir in git_cache.keys():          # dict on git roots
        if file.startswith(cached_dir):
            git_content = git_cache[cached_dir]  # dict on abs path file
            if file in git_content.keys():
                copy_cache_response(data, git_content[file])
                return True
            if debug_level > 4:
                print(f'in cached directory {cached_dir}:')
                print(f'  {file} was not found')
            # Do not return False here - it could be a WC further down the path

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
    reply, _exit_code = simur.run_process(commando, True)
    lines = reply.splitlines()
    for line in lines:
        remote = re.match(r'^origin\s*(.+)\s+\(fetch\)$', line)
        if remote:
            git_remote = remote.group(1)
        # No else - you cannot know if there is a remote

    if git_remote is None:
        print(f'Warning: {git_dir} has no remote')

    # Get the commit-sha
    commando = 'git log -1 --format=%H'
    reply, _exit_code = simur.run_process(commando, True)
    commit_id = reply

    # Get the contents of the repository
    commando = 'git ls-files -s'
    reply, _exit_code = simur.run_process(commando, True)
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
            # Make the key, i.e. that is the file path
            key = os.path.join(git_dir, rel_key)
            try:
                key = os.path.abspath(key)
            except Exception:
                if debug_level > 4:
                    print(f'cannot handle {line}')
                continue
            key = str(key)  # json cannot have WindowsPath as key
            if options.lower_case_pdb:
                key = key.lower()
            dir_cache[key] = {}
            cache_entry = dir_cache[key]
            cache_entry['reporoot'] = git_remote
            cache_entry['relpath']  = rel_key
            cache_entry['revision'] = revision
            cache_entry['sha1']     = commit_id
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
def is_in_git_raw(file, data, _dummy, _options):
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
    reply, _exit_code = simur.run_process(commando, False)  # git may complain
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
    reply, _exit_code = simur.run_process(commando, True)
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
def get_vcs_information(files, vcs_cache, vcs_imports, svn_cache, git_cache,
    options):
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
            if is_in_svn(file, response, svn_cache, options):
                data[file] = response
                vcs_cache[file] = response
                continue
            if is_in_git(file, response, git_cache, options):
                data[file] = response
                vcs_cache[file] = response
                continue
            if file in vcs_imports.keys():
                cached = vcs_imports[file]
                vcs_cache[file] = cached    # This is just a cache
                if no_vcs in cached:
                    continue                # Nothing to use
                data[file] = cached         # This is used index the PDB
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
def plural_files(no_of_files):
    if no_of_files == 1:
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
    # How to build the target path for the extracted file
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
    # for git sha1 is the commit ID
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
    common_root, _ext = os.path.splitext(pdb_file)
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

    with open(tempfile, 'w+t') as fh:
        for line in stream:
            fh.write(line + '\n')

    return tempfile

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def dump_stream_to_pdb(pdb_file, srcsrv, stream, options):
    tempfile = make_stream_file(pdb_file, stream)
    '''
    To restore the pdb:s their .orig's
    ---
    for /R %%I in (*.*.orig) do call :doit %%I %%~nI %%~pI
    goto :EOF
    :doit
    pushd %3
    del %2
    ren %1 %2
    popd
    ---
    '''
    if options.backup:
        make_backup_file(pdb_file, '.orig')
    pdbstr = os.path.join(srcsrv, 'pdbstr.exe')
    commando = [pdbstr, '-w', '-s:srcsrv', f'-p:{pdb_file}', f'-i:{tempfile}']
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
def check_winkits(srcsrv, options):
    if not os.path.exists(srcsrv):
        print(f'Sorry, the WinKits directory {srcsrv} does not exist')
        return 3
    fail = False
    srctool = os.path.join(srcsrv, 'srctool.exe')
    pdbstr = os.path.join(srcsrv, 'pdbstr.exe')
    if not os.path.exists(srctool):
        print(f'Sorry, {srctool} is required')
        fail = True
    if not os.path.exists(pdbstr):
        print(f'Sorry, {pdbstr} is required')
        fail = True
    if fail:
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
    vcs_cache.update(lib_data)

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def make_time_stamp(text, options):
    if not options.debug_level:
        return
    instant = datetime.today().strftime("%H:%M:%S:%f")
    print(f'{instant}: {text}')

#-------------------------------------------------------------------------------
# Handle a PDB for executables (*.exe, *.dll)
#-------------------------------------------------------------------------------
def prep_exe_pdb(the_pdb_file, srcsrv,
    vcs_cache, vcs_imports, svn_cache, git_cache, options):
    already_indexed = is_indexed(the_pdb_file, srcsrv, options)
    if already_indexed:
        return 0

    failing_requirements = check_paths(the_pdb_file)
    if failing_requirements:
        return failing_requirements

    make_time_stamp('prep_exe_pbd START', options)
    if options.debug_level > 3:
        print('prep_exe_pbd START')

    make_time_stamp('get_non_indexed_files', options)
    files = get_non_indexed_files(the_pdb_file, srcsrv, options)
    if len(files) == 0:
        print(f'No files to index in {the_pdb_file}')
        return 0

    print(f'Found {len(files)} source {plural_files(len(files))}')

    if options.debug_level > 3:
        for file in files:
            print(file)

    make_time_stamp('get_vcs_information', options)
    vcs_data = get_vcs_information(files, vcs_cache, vcs_imports,
        svn_cache, git_cache, options)
    if not vcs_data:
        print(f'No version controlled files in {the_pdb_file}')
    else:
        if options.debug_level > 3:
            make_time_stamp('dump_vcsdata', options)
            dump_vcsdata(vcs_data)

        make_time_stamp('init_the_stream_text', options)
        stream = init_the_stream_text(vcs_data)
        if options.debug_level > 3:
            dump_stream_data(stream)
        make_time_stamp('dump_stream_to_pdb', options)
        dump_stream_to_pdb(the_pdb_file, srcsrv, stream, options)
        make_time_stamp('update_presoak_file', options)
        update_presoak_file(vcs_data)
        make_time_stamp('report_vcsdata', options)
        report_vcsdata(vcs_data)
    if options.debug_level > 3:
        print('prep_exe_pbd END')
    make_time_stamp('prep_exe_pbd END', options)

    return 0


#-------------------------------------------------------------------------------
# Handle PDB:s for static libraries (*.lib)
#-------------------------------------------------------------------------------
def prep_lib_pdb(the_pdb_file, srcsrv, cvdump, vcs_cache, vcs_imports,
    svn_cache, git_cache, options):
    debug = 0
    # See if we already have cached data (in a *.simur.json file)
    lib_data_file = check_indexed_lib(the_pdb_file)
    if len(lib_data_file):
        # OK, so add data from that file to our current understanding
        print(f'{the_pdb_file} already indexed - taking cached data from {lib_data_file}')
        merge_vcs_data(vcs_cache, lib_data_file)
        return 0

    # Otherwise extract the data
    make_time_stamp('prep_lib_pbd START', options)
    files = libSrcTool.get_lib_source_files(the_pdb_file, cvdump, srcsrv, options)
    if len(files) == 0:
        print(f'No files to index in {the_pdb_file} for static lib')
        return 0

    print(f'Found {len(files)} source {plural_files(len(files))}')

    if debug > 3:
        for file in files:
            print(file)

    make_time_stamp('get_vcs_information', options)
    vcs_data = get_vcs_information(files, vcs_cache, vcs_imports,
        svn_cache, git_cache, options)
    if not vcs_data:
        print(f'No version controlled files in {the_pdb_file}')
    else:
        if debug > 3:
            dump_vcsdata(vcs_data)
        write_cache_file(the_pdb_file, vcs_data)
        report_vcsdata(vcs_data)

    if debug > 3:
        print('prep_lib_pbd END')
    make_time_stamp('prep_lib_pbd END', options)

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
def main():
    '''Just as processPDBs only that as the first argument give the PDB of
    interest
    Example:
    prepPDB.py armLibSupport.pdb . //ExternalAccess/WinKit10Debuggers/srcsrv
    '''
    if len(sys.argv) < 2:
        print("Too few arguments")
        usage()
        sys.exit(3)
    the_pdb = sys.argv[1]
    root = sys.argv[2]
    cvdump = 'cvdump.exe'
    srcsrv = 'C:\\Program Files (x86)\\Windows Kits\\10\\Debuggers\\x64\\srcsrv'
    if len(sys.argv) > 3:
        srcsrv = sys.argv[3]
    if len(sys.argv) > 4:
        cvdump = sys.argv[4]

    cvdump = libSrcTool.check_cvdump(cvdump, srcsrv)

    # Invoke indexPDBs.py as its own process to keep the distance
    this_dir = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(this_dir, 'indexPDBs.py')
    commando = ['python', script, '-u', the_pdb, '-t', root, '-s', srcsrv, '-c', cvdump]
    outputs, exit_code = simur.run_process(commando, True)
    print(outputs)

    return exit_code

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
