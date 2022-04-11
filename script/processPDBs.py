#!/usr/bin/env python3
#
#----------------------------------------------------------------------

import os
import sys

import simur

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def usage():
    print(f'usage: well, do not!  Use indexPDBs.py instead')

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

    if len(sys.argv) > 3:
        cvdump = sys.argv[3]

    # Invoke as indexPDBs.py but keep the distance
    this_dir = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(this_dir, 'indexPDBs.py')
    commando = ['python', script, '-t', root, '-s', srcsrv, '-c', cvdump]
    outputs, exit_code = simur.run_process(commando, True)
    print(outputs)

    return exit_code

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
