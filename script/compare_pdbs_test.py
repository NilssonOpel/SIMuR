#!/usr/bin/env python3
#
#----------------------------------------------------------------------

import argparse
import os
import sys
import textwrap

import prepPDB
import simur

_my_name = os.path.basename(__file__)
_default_srcsrv = 'C:/Program Files (x86)/Windows Kits/10/Debuggers/x64/srcsrv'

DESCRIPTION = f"""
Compare the PDBs in the directory --new with the ones in --facit
  --srcsrv_dir may for example be (if you have it on a server)
      //seupp-s-rptmgr/ExternalAccess/IndexingServices/WinKit10Debuggers/srcsrv
    or (if you have it locally)
      C:/Program Files (x86)/Windows Kits/10/Debuggers/x64/srcsrv
"""
USAGE_EXAMPLE = f"""
Examples:
> {_my_name} -t D:/build4711/build_Win32_14
             -f D:/build0001/build_Win32_14
             -s //seupp-s-rptmgr/ExternalAccess/IndexingServices/WinKit10Debuggers/srcsrv
  Will compare contents in -t and -f and tell number of indexed source files
  (output taken from srctool.exe)

> {_my_name} -t D:/build4711/build_Win32_14
             -f D:/build0001/build_Win32_14
             -s {_default_srcsrv}
             -b basename.pdb
  Will find the two 'basename.pdb:s' under -t and -f and open BeyondCompare on
  their srcsrv entries

> {_my_name} -t D:/build4711/build_Win32_14
             -f D:/build0001/build_Win32_14
             -s {_default_srcsrv}
             -u
  Will make a test.unprocessed and a facit.unprocessed file containing the
  unprocessed (not indexed) source files in respective

"""

#-------------------------------------------------------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(_my_name,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(DESCRIPTION),
        epilog=textwrap.dedent(USAGE_EXAMPLE))
    add = parser.add_argument

    add('-q', '--quiet', action='store_true',
        help='be more quiet')
    add('-v', '--verbose', action='store_true',
        help='be more verbose')
    add('-d', '--debug_level', type=int, default=0, help='set debug level')

    add('-t', '--test', metavar='test-dir',
        required=True,
        help='root path to pdbs under test (recursively)')
    add('-f', '--facit', metavar='facit-dir',
        help='root path to earlier pdbs (recursively)')
    add('-s', '--srcsrv_dir', metavar='srcsrv',
        default=_default_srcsrv ,
        help='WinKits srcsrv directory')
    add('-b', '--beyond_compare', metavar='an_specific.pdb',
        help='Run BeyondCompare on the srvsrv output on a given .pdb file')
    add('-u', '--unprocessed', action='store_true',
        help='Make files test.unprocessed and facit.unprocessed')
    add('-l', '--list_missed_files', action='store_true',
        help='Make file suspects.list')

    return parser.parse_args()

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def collect_all_pdb_files(directory):
    the_chosen_ones = {}
    ext = '.pdb'
    bad1 = '.ENU.pdb'
    bad2 = '.JPN.pdb'
    for root, _dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(ext):
                if file.endswith(bad1):
                    continue
                if file.endswith(bad2):
                    continue
                full_path = os.path.join(root, file)
                the_chosen_ones[file] = full_path

    return the_chosen_ones

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def list_pdbs(pdb_list, options):
    for pdb in pdb_list:
        print(pdb)

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def compare_population(test_pdbs, facit_pdbs, options):
    facit_bases = facit_pdbs.keys()
    test_bases = test_pdbs.keys()
    in_facit_not_in_test = facit_bases - test_bases
    in_test_not_in_facit = test_bases - facit_bases

    print('Compare .pdb population:')
    if in_facit_not_in_test:
        print('These were in --facit but not in --test')
        list_pdbs(in_facit_not_in_test, options)
    else:
        print('All in --facit were also in --test')

    if in_test_not_in_facit:
        print('These were in --test but not in --facit')
        list_pdbs(in_test_not_in_facit, options)
    else:
        print('All in --test were also in --facit')
    print()

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def get_last_line_of_srctool_reply(commando, options):
    raw_data, _exit_code = simur.run_process(commando, False)

    my_line = raw_data.splitlines()[-1]
    return my_line

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def accumulate_srctool_reply(the_pdb, commando, accumulated_set, options):
#    checker = 'AmpSyncClientPool.h'
    raw_data, exit_code = simur.run_process(commando, False)
    my_lines = raw_data.splitlines()
    if len(my_lines) in range(1,3):
        if my_lines[0].endswith('is not source indexed.'):
            print(my_lines[0])
        elif my_lines[0].startswith('No source information in pdb'):
            # Could be a static library - skip
            pass
        else:
            print(f'{the_pdb} has funny indexing')

    my_lines = my_lines[:-1]
#    for line in my_lines:
#        if os.path.basename(line) == checker:
#            print(f'Unprocessed {line} in {commando}')
    accumulated_set |= set(my_lines)
    return accumulated_set

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def compare_contents(test_pdbs, facit_pdbs, options):
    intersection = test_pdbs.keys() & facit_pdbs.keys()

    print('Compare .pdb contents - index rate:')
    srctool = os.path.join(options.srcsrv_dir, 'srctool.exe')
    for item in intersection:
        test_pdb = test_pdbs[item]
        facit_pdb = facit_pdbs[item]
        test_commando = [srctool, '-u', test_pdb]
        facit_commando = [srctool, '-u', facit_pdb]
        test_output = get_last_line_of_srctool_reply(test_commando, options)
        facit_output = get_last_line_of_srctool_reply(facit_commando, options)
        print(f'{item}:')
        print(f'  {test_output}')
        print(f'  {facit_output}\n')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def write_set_to_file(file_name, the_set, options):
    with open(file_name, 'w') as fp:
        sorted_list = sorted(the_set)  # now a list!
        for line in sorted_list:
            if len(line) == 0:
                continue
            # Do not know what this is, but lines starting with a star ('*')
            # refers to a non-existing .inj file in the object directory, e.g.
            # *D:\master\build\DriverLib\DriverLib.dir\Release\TdlVector.inj:1
            if line[0] == '*':
                continue
            line += '\n'
            fp.write(line)

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def list_unprocessed(test_dir, test_data, options):
    repo_roots_file = os.path.join(test_dir, 'repo_roots.json')
    if not os.path.exists(repo_roots_file):
        print(f'Cannot proceed - {repo_roots_file} does not exist')
    repo_roots = simur.load_json_data(repo_roots_file)
    root_lists = repo_roots.values()
    root_paths = [item for sub_list in root_lists for item in sub_list]

    test_data = sorted(test_data)
    this_dir = os.getcwd()
    output_file = os.path.join(this_dir, 'suspects.list')
    with open(output_file, 'w') as fp:
        for root in root_paths:
            root_end = len(root)
            fp.write(f'VCS root {root}:\n')
            triggered = False
            for data in test_data:
                if data.startswith(root):
                    data_next = data[root_end]
                    # Is it really the same? E.g ide vs ide_build
                    if data_next == '\\' or data_next == '/':
                        fp.write(f'{data}\n')
                        triggered = True
            if not triggered:
                fp.write('- OK -\n')
            fp.write('\n')
    print(f'Saved {output_file} with potentially missing files')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def save_unprocessed(test_pdbs, facit_pdbs, options):
    intersection = test_pdbs.keys() & facit_pdbs.keys()

    print('Compare .pdb contents - save all unprocessed')
    srctool = os.path.join(options.srcsrv_dir, 'srctool.exe')
    test_set = set()
    facit_set = set()
    for item in intersection:
        test_pdb = test_pdbs[item]
        facit_pdb = facit_pdbs[item]
        test_commando = [srctool, '-u', test_pdb]
        facit_commando = [srctool, '-u', facit_pdb]
        test_set = accumulate_srctool_reply(test_pdb,
            test_commando, test_set, options)
        facit_set = accumulate_srctool_reply(facit_pdb,
            facit_commando, facit_set, options)
        if options.verbose:
            print(f'Add unprocessed items from {item}')

    test_file = 'test.unprocessed'
    facit_file = 'facit.unprocessed'
    this_dir = os.getcwd()
    test_file = os.path.join(this_dir, test_file)
    facit_file = os.path.join(this_dir, facit_file)
    write_set_to_file(test_file, test_set, options)
    print(f'Saved all unprocessed items from {options.test} to {test_file}')
    if not options.list_missed_files:
        write_set_to_file(facit_file, facit_set, options)
        print(f'Saved all unprocessed items from {options.facit} to {facit_file}')
    return test_set

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def diff_on_saved_files(test_output, facit_output, options):
    test_file = 'test.srcsrv'
    facit_file = 'facit.srcsrv'
    temp_dir = os.environ['TEMP']
    test_file = os.path.join(temp_dir, test_file)
    facit_file = os.path.join(temp_dir, facit_file)
    write_set_to_file(test_file, test_output, options)
    write_set_to_file(facit_file, facit_output, options)
    visualdiff_commando = [
        'C:\\Program Files\\Beyond Compare 4\\BComp.exe',
        test_file,
        facit_file
        ]
    test_output, _exit_code = simur.run_process(visualdiff_commando, False)

    os.unlink(test_file)
    os.unlink(facit_file)

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def compare_srcsrv_content(test_pdbs, facit_pdbs, options):
    pdb_to_find = options.beyond_compare
    intersection = test_pdbs.keys() & facit_pdbs.keys()

    print('Compare .pdb - srcsrv content:')

    if not pdb_to_find in intersection:
        print(f'Cannot find {pdb_to_find} in current selections')
        return 3

    pdbstr = os.path.join(options.srcsrv_dir, 'pdbstr.exe')
    test_pdb = test_pdbs[pdb_to_find]
    facit_pdb = facit_pdbs[pdb_to_find]
    test_commando = [pdbstr, '-r','-s:srcsrv', f'-p:{test_pdb}']
    facit_commando = [pdbstr, '-r','-s:srcsrv', f'-p:{facit_pdb}']
    test_output, _exit_code = simur.run_process(test_commando, False)
    facit_output, _exit_code = simur.run_process(facit_commando, False)
    test_output = test_output.splitlines()
    facit_output = facit_output.splitlines()

    print(f'{pdb_to_find}:')
    diff_on_saved_files(test_output, facit_output, options)
    return 0

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def main():
    options = parse_arguments()

    test_dir= options.test
    srcsrv = options.srcsrv_dir

    if prepPDB.check_winkits(srcsrv, options):
        return 3

    test_pdbs = collect_all_pdb_files(test_dir)
    if not test_pdbs:
        print(f'No PDB:s found in directory {test_dir}')
        return 3

    if not options.list_missed_files:
        if not options.facit:
            print('option -f required')
            return 3
        facit_dir = options.facit
        facit_pdbs = collect_all_pdb_files(facit_dir)
        if not facit_pdbs:
            print(f'No PDB:s found in directory {facit_pdbs}')
            return 3

    if options.unprocessed:
        test_data = save_unprocessed(test_pdbs, facit_pdbs, options)
    elif options.beyond_compare:
        compare_srcsrv_content(test_pdbs, facit_pdbs, options)
    elif options.list_missed_files:
        test_data = save_unprocessed(test_pdbs, test_pdbs, options)
        list_unprocessed(test_dir, test_data, options)
    else:
        compare_population(test_pdbs, facit_pdbs, options)
        compare_contents(test_pdbs, facit_pdbs, options)
    return 0


#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
