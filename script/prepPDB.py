from datetime import datetime
import os
import re
import shutil
import simur
import subprocess
import sys

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
        repo = re.match('^Repository Root: (.*)$', line)
        if repo:
            data['reporoot'] = repo.group(1)
            hits += 1
            continue
        url = re.match('^URL: (.*)$', line)
        if url:
            data['url'] = url.group(1)
            hits += 1
            continue
        rev = re.match('^Revision: (.*)$', line)
        if rev:
            data['revision'] = rev.group(1)
            hits += 1
            continue
        rel = re.match('^Relative URL: \^/(.*)$', line)
        if rel:
            data['relpath']  = rel.group(1)
            hits += 1
            continue
        sha1 = re.match('^Checksum: ([a-f0-9]+)$', line)
        if sha1:
            data['sha1']  = sha1.group(1)
            hits += 1
            continue

    if hits != 5:
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
def is_in_git(file, data):
    git_dir = get_git_dir(file)
    if git_dir == None:
        return False
    # Make a pushd to the git dir
    curr_dir = os.getcwd()
    os.chdir(git_dir)

    commando = f'git ls-files -s "{file}"'
    reply = simur.run_process(commando, True)
    if reply.startswith('fatal'):
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
        print(f'When executing in directory: {git_dir}')
        print(f'>{commando} failed')
#        os.chdir(curr_dir) stay at the fail
        exit(3)

    #Look for remote:s
    commando = 'git remote -v'
    reply = simur.run_process(commando, True)
    lines = reply.splitlines()
    for line in lines:
        remote = re.match('^origin\s*(.+)\s*\(fetch\)$', line)
        if remote:
            data['reporoot'] = remote.group(1)
            data['remote']   = remote.group(1)

    data['vcs'] = 'git'

    os.chdir(curr_dir)
    return True

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_vcs_information(files):
    data = {}
    for file in files:
        response = {}
        if is_in_svn(file, response):
            data[file] = response
            continue
        if is_in_git(file, response):
            data[file] = response
            continue

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
        '%targ%\\%var5%\\%fnbksl%(%var4%)')
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

    make_backup_file(pdb_file, '.orig')
    pdbstr = os.path.join(srcsrv, 'pdbstr.exe')
    commando = f'{pdbstr} -w -s:srcsrv -p:{pdb_file} -i:{tempfile}'
    reply = simur.run_process(commando, True)

    os.remove(tempfile)                 # Or keep it for debugging

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def update_presoak_file(vcs_data):
    data = simur.load_presoak_data()

    for file in vcs_data:
        what = vcs_data[file]
        if what['vcs'] == 'git':
            remote = what['remote']
            if remote:
                if not remote in data:
                    data[remote] = 'presoak'

    simur.store_presoak_data(data)

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

    return 0

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def check_requirements(root, srcsrv):
    if check_paths(root, srcsrv):
        return 3
    if is_indexed(root, srcsrv):
        print(f'Sorry, {root} is already indexed')
        return 1

    return 0

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def do_the_job(root, srcsrv, debug=0):
    failing_requirements = check_requirements(root, srcsrv)
    if failing_requirements:
        return failing_requirements

    if debug > 3:
        print('prepPDB START')

    files = get_non_indexed(root, srcsrv)
    if not files:
        print(f'No files to index in {root}')
        return 0
    if debug > 3:
        print(files)

    vcs_data = get_vcs_information(files)
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
    if debug > 3:
        print('prepPDB END')

    return 0


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

    outcome = do_the_job(root, srcsrv, debug)
    return outcome

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
