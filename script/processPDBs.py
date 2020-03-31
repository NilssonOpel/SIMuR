import os
import re
import shutil
import simur
import sys
import time

import libSrcTool
import prepPDB

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def usage():
    the_script = os.path.basename(sys.argv[0])
    print(f'usage: {the_script} pdb-dir srcsrv-dir')
    print(f'  e.g. {the_script} RelWithDebInfo C:/WinKits/10/Debuggers/x64/srcsrv')
    print(f'    process all the PDB:s in the pdb-dir and sub directories')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def list_all_files(directory, ext):
    the_chosen_files = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(ext):
                the_chosen_files.append(os.path.join(root, file))

    return the_chosen_files

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def filter_pdbs(pdbs, cvdump, srcsrv):
    lib_pdbs = []
    exe_pdbs = []
    for pdb_file in pdbs:
        # First exclude the default vcNNN.pdb files, they are from the compiler
        internal_pdb = re.match(r'.*\\vc\d+\.pdb$', pdb_file)
        if internal_pdb:
            print(f'Skipping {pdb_file}')
            continue
        # First check if srctool returns anything - then it is NOT a lib-PDB
        exe_files = prepPDB.get_non_indexed(pdb_file, srcsrv, {})
        if len(exe_files):
            exe_pdbs.append(pdb_file)
        elif cvdump:
            commando = f'{cvdump} {pdb_file}'
            raw_data = simur.run_process(commando, True)

            files = libSrcTool.process_raw_cvdump_data(raw_data)
            if len(files):
                lib_pdbs.append(pdb_file)

    return lib_pdbs, exe_pdbs

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_available_bins(bins_in):
    bins_found = []
    bins_not  = []
    for the_bin in bins_in:
        reply = shutil.which(the_bin)
        if reply == None:
            bins_not.append(the_bin)
        else:
            bins_found.append(reply)
    return bins_found, bins_not

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def make_log(srcsrv, elapsed):
    bins_used = [
        sys.executable,
        os.path.join(srcsrv, 'srctool.exe'),
        os.path.join(srcsrv, 'pdbstr.exe'),
    ]
    maybe_bins = [
        'cvdump.exe',
        'git.exe',
        'svn.exe',
        'hg.exe'
    ]
    found_bins, unfound_bins = get_available_bins(maybe_bins)
    bins_used += found_bins

    print(f'Executed by       : {os.getenv("USERNAME")}')
    print(f'  on machine      : {os.getenv("COMPUTERNAME")}')
    print(f'  SIMUR_REPO_CACHE: {os.getenv("SIMUR_REPO_CACHE")}')
    print(f'  elapsed time    : {elapsed}')

    codepage = simur.run_process('cmd /c CHCP', False)
    cp = re.match(r'^.*:\s+(\d*)$', codepage)
    if cp:
        codepage = cp.group(1)
    print(f'  CodePage        : {codepage}')
    print('Script:')
    print(f'  {os.path.realpath(sys.argv[0])}')
    print('Using binaries:')
    for the_exe in bins_used:
        the_exe = os.path.join(srcsrv, the_exe)
        print(f'  {the_exe}:')
        props = simur.getFileProperties(the_exe)
        if props:
            print(f'    {props["StringFileInfo"]["FileVersion"]}')
            print(f'    {props["FileVersion"]}')

    if len(unfound_bins):
        print('Binaries not found/used:')
        for the_exe in unfound_bins:
            print(f'  {the_exe}:')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def main():
    start = time.time()
    debug_level = 0
    if len(sys.argv) < 2:
        print("Too few arguments")
        usage()
        exit(3)
    root = sys.argv[1]
    cvdump = 'cvdump.exe'
    srcsrv = 'C:\\Program Files (x86)\\Windows Kits\\10\\Debuggers\\x64\\srcsrv'
    if len(sys.argv) > 2:
        srcsrv = sys.argv[2]
    if prepPDB.check_winkits(srcsrv):
        return 3

    if len(sys.argv) > 3:
        cvdump = sys.argv[3]
    cvdump = libSrcTool.check_cvdump(cvdump)

    pdbs = list_all_files(root, ".pdb")
    if len(pdbs) == 0:
        print(f'No PDB:s found in directory {root}')
        return 3

    # If there is no cvdump, then we won't filter out an lib_pdbs either
    lib_pdbs, exe_pdbs = filter_pdbs(pdbs, cvdump, srcsrv)

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
        outcome += prepPDB.prep_lib_pdb(lib_pdb,
            srcsrv,
            cvdump,
            vcs_cache,
            svn_cache,
            git_cache,
            debug_level)

    for exe_pdb in exe_pdbs:
        print(f'---\nProcessing executable {exe_pdb}')
        outcome += prepPDB.prep_exe_pdb(exe_pdb,
            srcsrv,
            vcs_cache,
            svn_cache,
            git_cache,
            debug_level)

    if debug_level > 4:
        simur.store_json_data(cache_file, vcs_cache)
    end = time.time()
    make_log(srcsrv, end-start)
    # Store the directories where we found our 'roots'
    # This can be used for checking if we have un-committed changes
    roots = {}
    roots["svn"] = prepPDB.extract_repo_roots(svn_cache)
    roots["git"] = prepPDB.extract_repo_roots(git_cache)
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
if __name__ == "__main__":
    sys.exit(main())
