import os
import prepPDB
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
    if not os.path.exists(root):
        print(f'Sorry, the directory {root} does not exist')
        return 3

    pdbs = list_all_files(root, ".pdb")
    if len(pdbs) == 0:
        print(f'No PDB:s fond in directory {root}')
        return 3

    outcome = 0
    cache_file = os.path.join(root, 'vcs_cache.json')
    vcs_cache = simur.load_json_data(cache_file)
    # Should verify or update the cache before using it! - But it takes time
    # vcs_cache = prepPDB.verify_cache_data(vcs_cache)

    for pdb in pdbs:
        print(f'---\nProcessing {pdb}')
        outcome += prepPDB.do_the_job(pdb, srcsrv, vcs_cache, debug_level)
        print(f'---\n')
    simur.store_json_data(cache_file, vcs_cache)

    return outcome

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())