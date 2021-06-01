import os
# from pathlib import Path
# import re
import shutil
import sys

import simur
import prepPDB


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def about_cvdump():
    print('  You need to have cvdump.exe in your path to index'
          ' static libraries')
    print('  - you can find it here:')
    print('  https://github.com/microsoft/microsoft-pdb/blob/master'
          '/cvdump/cvdump.exe')


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def usage():
    the_script = os.path.basename(sys.argv[0])
    print(f'Usage:')
    print(f'{the_script} lib-pdb-file')
    print(f'  e.g. {the_script} RelWithDebInfo/TestLibCat.lib\n')
    print(f'  this is an attempt at mimicking srctool for PDBs from static')
    print(f'  libraries, since there is none from Microsoft\n')
    about_cvdump()


#-------------------------------------------------------------------------------
# --- Routines for extracting the data from the pdb and associated vcs:s ---
#-------------------------------------------------------------------------------

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
def process_raw_cvdump_data(raw_data):
    files = []
    lines = raw_data.splitlines()
    next_line = False
    for line in lines:
        if next_line:
            file_in_spe = line.strip()
#            print(f'Looking at {file_in_spe}')
            if os.path.isfile(file_in_spe):
                files.append(file_in_spe)
#                print(f'Found {file_in_spe}')
            next_line = False
        if 'LF_STRING_ID' in line:
            next_line = True
            continue

    return files


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_lib_source_files(pdb_file, cvdump, srcsrv):
    # First check if srctool returns anything - then it is NOT a lib-PDB
    srctool_files = prepPDB.get_non_indexed(pdb_file, srcsrv, {})
    if len(srctool_files):
        print(f'{pdb_file} is not a lib-PDB file - skipped')
        return []
    commando = f'{cvdump} {pdb_file}'
    raw_data, exit_code = simur.run_process(commando, True)

    files = process_raw_cvdump_data(raw_data)
    return files


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def check_cvdump(cvdump):
    second_try = cvdump
    cvdump = shutil.which(cvdump)
    if cvdump is None:
        # Not in path, try once more in 'this' directory
        cvdump = shutil.which(second_try,
                              path=os.path.dirname(os.path.abspath(__file__)))
    if cvdump is None:
        about_cvdump()

    return cvdump


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def check_requirements(root, cvdump):
    return_value = 0
    return_value = check_cvdump(cvdump)

    if check_paths(root):
        return_value = 3

    return return_value


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print("Too few arguments")
        usage()
        exit(3)
    root = sys.argv[1]
    cvdump = 'cvdump.exe'
    srcsrv = 'C:\\Program Files (x86)\\Windows Kits\\10\\Debuggers\\x64\\srcsrv'
    if len(sys.argv) > 2:
        srcsrv = sys.argv[2]

    failing_requirements = check_requirements(root, cvdump)
    if failing_requirements:
        return failing_requirements
    if prepPDB.check_winkits(srcsrv):
        return 3

    files = get_lib_source_files(root, cvdump, srcsrv)
    if not files:
        print(f'No source files from static lib found in {root}')
        return 3

    print(f'Found {len(files)} source {plural_files(len(files))}')

    for file in files:
        print(file)

    return 0


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
