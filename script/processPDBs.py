import os
import prepPDB
import sys

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
    srcsrv = 'C:/WinKits/10/Debuggers/x64/srcsrv'
    if len(sys.argv) > 2:
        srcsrv = sys.argv[2]
    if prepPDB.check_paths(root, srcsrv):
        return 3


    pdbs = list_all_files(root, ".pdb")

    outcome = 0
    for pdb in pdbs:
        print(f'---\nProcessing {pdb}')
        outcome += prepPDB.do_the_job(pdb, srcsrv, debug_level)
        print(f'---\n')

    return outcome

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
