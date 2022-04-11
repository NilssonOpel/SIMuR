#!/usr/bin/env python3
#
#-------------------------------------------------------------------------------

import argparse
import datetime
import os
import re
import shutil
import sys
import textwrap
import time

import libSrcTool
import prepPDB
import simur

MY_NAME = os.path.basename(__file__)
DEFAULT_SRCSRV = 'C:/Program Files (x86)/Windows Kits/10/Debuggers/x64/srcsrv'

DESCRIPTION = f"""
Index the PDB files in the --target_dir, taking the information from the
    {simur.VCS_CACHE_PATTERN} files found under the --processed_dir:s

  --srcsrv_dir may for example be (if you have it on a server)
      //seupp-s-rptmgr/ExternalAccess/IndexingServices/WinKit10Debuggers/srcsrv
    or (if you have it locally)
      C:/Program Files (x86)/Windows Kits/10/Debuggers/x64/srcsrv
"""
USAGE_EXAMPLE = f"""
Example:
> {MY_NAME} -t D:/src/rl78_trunk/rl78/intermediate/build_Win32_14
            -p D:/src/rl78_trunk/core/ide/lib/Release
            -s //seupp-s-rptmgr/ExternalAccess/IndexingServices/WinKit10Debuggers/srcsrv
"""

#-------------------------------------------------------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(
        MY_NAME,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(DESCRIPTION),
        epilog=textwrap.dedent(USAGE_EXAMPLE)
    )
    add = parser.add_argument
    add('-b', '--backup', action='store_true',
        help='make a backup of the .pdb file as <path>.orig')
    add('-c', '--cvdump_path', metavar='cvdump.exe',
        default='cvdump.exe',
        help='path to cvdump.exe (unless it is in the --srcsrv_dir directory)')
    add('-d', '--debug_level', type=int, default=0, help='set debug level')

    add('-l', '--lower_case_pdb', action='store_true',
        help='handle old PDBs (< VS2019) that stored paths in lower case')
    add('-p', '--processed_dir', metavar='processed-dir1{;dir2;dir4}',
        help='fetch *.simur.json from preprocessed PDB directories')
    add('-q', '--quiet', action='store_true',
        help='be more quiet')
    add('-s', '--srcsrv_dir', metavar='srcsrv',
        default=DEFAULT_SRCSRV,
        help='WinKits srcsrv directory')
    add('-t', '--target_dir', metavar='stage-dir',
        required=True,
        help='root path to index (recursively)')
    add('-u', '--under_test', metavar='the.pdb',
        help='index only this pdb file')
    add('-v', '--verbose', action='store_true',
        help='be more verbose')

    return parser.parse_args()

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def list_all_files(directory, ext):
    the_chosen_files = []

    for root, _dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(ext):
                the_chosen_files.append(os.path.join(root, file))

    return the_chosen_files

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def filter_pdbs(pdbs, cvdump, srcsrv, options):
    lib_pdbs = []
    exe_pdbs = []
    for pdb_file in pdbs:
        # First exclude the default vcNNN.pdb files, they are from the compiler
        internal_pdb = re.match(r'.*\\vc\d+\.pdb$', pdb_file)
        if internal_pdb:
            print(f'Skipping {pdb_file}')
            continue
        # First check if srctool returns anything - then it is NOT a lib-PDB
        exe_files = prepPDB.get_non_indexed_files(pdb_file, srcsrv, options)
        if exe_files:
            exe_pdbs.append(pdb_file)
        elif cvdump:
            commando = [cvdump, pdb_file]
            raw_data, _exit_code = simur.run_process(commando, True)
            files = libSrcTool.process_raw_cvdump_data(raw_data)
            # The .pdb contained source files, append it
            if files:
                lib_pdbs.append(pdb_file)

    return lib_pdbs, exe_pdbs

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def accumulate_processed(options):
    '''
    Look up all files ending with VCS_CACHE_PATTERN ('.simur.json')
    take out the contents and put in vcs_imports dictionary
    '''
    vcs_imports = {}
    caching_files = []
    roots = options.processed_dir.split(';')

    for the_dir in roots:
        simur_files = list_all_files(the_dir, simur.VCS_CACHE_PATTERN)
        caching_files.extend(simur_files)

    for cache_file in caching_files:
        if options.verbose:
            print(f'Take vcs exports from {cache_file}')
        in_data = simur.load_json_data(cache_file)
        vcs_imports.update(in_data)

    return vcs_imports

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_available_bins(bins_in):
    bins_found = []
    bins_not = []
    for the_bin in bins_in:
        reply = shutil.which(the_bin)
        if reply is None:
            # Not in path, try once more in 'this' directory
            this_dir = os.path.dirname(os.path.abspath(__file__))
            reply = shutil.which(the_bin, path=this_dir)

        if reply is None:
            bins_not.append(the_bin)
        else:
            bins_found.append(reply)
    return bins_found, bins_not

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def make_time_string(elapsed):
    if elapsed > 60:
        longer_time = datetime.timedelta(seconds=elapsed)
        return str(longer_time)

    return str(elapsed) + ' secs'

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def make_log(srcsrv, explicit_cvdump, elapsed):
    bins_used = [
        sys.executable,
        os.path.join(srcsrv, 'srctool.exe'),
        os.path.join(srcsrv, 'pdbstr.exe'),
    ]
    maybe_bins = [
        explicit_cvdump,
        'git.exe',
        'svn.exe',
        'hg.exe'
    ]
    found_bins, unfound_bins = get_available_bins(maybe_bins)
    bins_used += found_bins

    print(f'Executed by       : {os.getenv("USERNAME")}')
    print(f'  on machine      : {os.getenv("COMPUTERNAME")}')
    print(f'  SIMUR_REPO_CACHE: {os.getenv("SIMUR_REPO_CACHE")}')
    print(f'  elapsed time    : {make_time_string(elapsed)}')

    codepage, _exit_code = simur.run_process('cmd /c CHCP', False)
    the_cp = re.match(r'^.*:\s+(\d*)$', codepage)
    if the_cp:
        codepage = the_cp.group(1)
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

    if unfound_bins:
        print('Binaries not found/used:')
        for the_exe in unfound_bins:
            print(f'  {the_exe}:')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def main():
    options = parse_arguments()
    start = time.time()

    root = options.target_dir
    cvdump = options.cvdump_path
    srcsrv = options.srcsrv_dir
    debug_level = options.debug_level

    if prepPDB.check_winkits(srcsrv, options):
        return 3
    found_cvdump = libSrcTool.check_cvdump(cvdump, srcsrv)

    pdbs = list_all_files(root, ".pdb")
    if len(pdbs) == 0:
        print(f'No PDB:s found in directory {root}')
        return 3

    # If there is no cvdump, then we won't filter out any lib_pdb:s either
    lib_pdbs, exe_pdbs = filter_pdbs(pdbs, found_cvdump, srcsrv, options)
    # --under_test - only process an explicit pdb file
    if options.under_test:
        if options.under_test in exe_pdbs:
            lib_pdbs = []
            exe_pdbs = [options.under_test]
        else:
            print(f'Could not find {options.under_test} in directory {root}')
            return 3

    outcome = 0
    vcs_cache = {}
    svn_cache = {}
    git_cache = {}
    vcs_imports = {}

    # If anything from options.processed_dir (-p), then take their
    # outputs (vcs_cache) and use as imports
    if options.processed_dir:
        vcs_imports = accumulate_processed(options)

    if found_cvdump:
        for lib_pdb in lib_pdbs:
            print(f'---\nProcessing library {lib_pdb}')
            outcome += prepPDB.prep_lib_pdb(lib_pdb,
                                            srcsrv,
                                            found_cvdump,
                                            vcs_cache,
                                            vcs_imports,
                                            svn_cache,
                                            git_cache,
                                            options)

    for exe_pdb in exe_pdbs:
        print(f'---\nProcessing executable {exe_pdb}')
        outcome += prepPDB.prep_exe_pdb(exe_pdb,
                                        srcsrv,
                                        vcs_cache,
                                        vcs_imports,
                                        svn_cache,
                                        git_cache,
                                        options)

    end = time.time()
    make_log(srcsrv, cvdump, end - start)
    # Store the directories where we found our 'roots'
    # This can be used for checking if we have un-committed changes
    roots = {}
    roots["svn"] = prepPDB.extract_repo_roots(svn_cache)
    roots["git"] = prepPDB.extract_repo_roots(git_cache)
    repo_file = os.path.join(root, 'repo_roots.json')
    simur.store_json_data(repo_file, roots)

    cache_file = os.path.join(root, simur.VCS_CACHE_FILE_NAME)
    simur.store_json_data(cache_file, vcs_cache)

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
