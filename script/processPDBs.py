import os
import prepPDB
import shutil
import simur
import sys

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def usage():
    the_script = os.path.basename(sys.argv[0])
    print(f'usage: {the_script} pdb-dir srcsrv-dir')
    print(f'  e.g. {the_script} RelWithDebInfo C:\WinKits\10\Debuggers\x64\srcsrv')
    print( '    process all the PDB:s in the pdb-dir and sub directories')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def list_all_files(dir, ext):
    the_chosen_files = []

    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.endswith(ext):
                the_chosen_files.append(os.path.join(root, file))

    return the_chosen_files

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def make_log(srcsrv):
    bins_used = [
        sys.executable,
        os.path.join(srcsrv,'srctool.exe'),
        os.path.join(srcsrv,'pdbstr.exe'),
        shutil.which('git.exe'),
        shutil.which('svn.exe')
    ]
    print(f'Executed by      : {os.getenv("USERNAME")}')
    print(f' on machine      : {os.getenv("COMPUTERNAME")}')
    print(f' SIMUR_LOCAL_REPO: {os.getenv("SIMUR_LOCAL_REPO")}')
    print('Script:')
    print(os.path.realpath(sys.argv[0]))
    print('Using binaries:')
    for the_exe in bins_used:
        the_exe = os.path.join(srcsrv, the_exe)
        print(f'  {the_exe}:')
        props = simur.getFileProperties(the_exe)
        if props:
            print(f'    {props["StringFileInfo"]["FileVersion"]}')
            print(f'    {props["FileVersion"]}')


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def main():
    debug_level = 0
    if len(sys.argv) < 2:
        print("Too few arguments")
        usage()
        exit(3)
    root = sys.argv[1]
    srcsrv = 'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\srcsrv'
    if len(sys.argv) > 2:
        srcsrv = sys.argv[2]
    if prepPDB.check_winkits(srcsrv):
        return 3

    pdbs = list_all_files(root, ".pdb")
    if len(pdbs) == 0:
        print(f'No PDB:s found in directory {root}')
        return 3

    outcome = 0
    cache_file = os.path.join(root, 'vcs_cache.json')
    vcs_cache = simur.load_json_data(cache_file)
    # Should verify or update the cache before using it! - But it takes time
    # vcs_cache = prepPDB.verify_cache_data(vcs_cache)

    svn_cache = {}
    git_cache = {}

    for pdb in pdbs:
        print(f'---\nProcessing {pdb}')
        outcome += prepPDB.do_the_job(pdb,
            srcsrv,
            vcs_cache,
            svn_cache,
            git_cache,
            debug_level)
        print(f'---\n')
    simur.store_json_data(cache_file, vcs_cache)

    make_log(srcsrv)
    return outcome

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
