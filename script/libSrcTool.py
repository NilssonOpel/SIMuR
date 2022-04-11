#!/usr/bin/env python3
#
#----------------------------------------------------------------------

import os
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
    ''' See if we can find any source files in the .pdb of the static lib
    raw_data looks like this:
    0x2702 : Length = 118, Leaf = 0x1605 LF_STRING_ID
    C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\VC\Tools\MSVC\14.29.30133\include\functional
    No sub string
    '''
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
def get_lib_source_files(pdb_file, cvdump, srcsrv, options):
    # First check if srctool returns anything - then it is NOT a lib-PDB
    srctool_files = prepPDB.get_non_indexed_files(pdb_file, srcsrv, options)
    if srctool_files:
        print(f'{pdb_file} is not a lib-PDB file - skipped')
        return []
    commando = [cvdump, pdb_file]
    raw_data, _exit_code = simur.run_process(commando, True)

    files = process_raw_cvdump_data(raw_data)
    return files

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def check_cvdump(cvdump, srcsrv):
    # Got an absolute path
    if os.path.exists(cvdump):
        return cvdump

    # Check if in path
    return_path = shutil.which(cvdump)
    if return_path:
        return return_path

    # Not in path, try in 'this' directory
    return_path = shutil.which(cvdump,
        path=os.path.dirname(os.path.abspath(__file__)))
    if return_path:
        return return_path

    # Finally try in 'srcsrv' directory
    return_path = os.path.join(srcsrv, cvdump)
    if os.path.exists(return_path):
        return return_path

    about_cvdump()  # Give an heads-up
    return None

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def check_requirements(root, cvdump, srcsrv):
    return_value = 0
    return_value = check_cvdump(cvdump, srcsrv)

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
        sys.exit(3)
    root = sys.argv[1]
    cvdump = 'cvdump.exe'
    srcsrv = 'C:\\Program Files (x86)\\Windows Kits\\10\\Debuggers\\x64\\srcsrv'
    if len(sys.argv) > 2:
        srcsrv = sys.argv[2]

    failing_requirements = check_requirements(root, cvdump, srcsrv)
    if failing_requirements:
        return failing_requirements
    if prepPDB.check_winkits(srcsrv):
        return 3

    files = get_lib_source_files(root, cvdump, srcsrv, None)
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
