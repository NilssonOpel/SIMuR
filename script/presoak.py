import os
import prepPDB
import simur
import sys

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def usage():
    the_script = os.path.basename(sys.argv[0])
    print(f'usage: {the_script}')
    print( '    update the cache in SIMUR_REPO_CACHE')

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def main():
    # Update the all the current repos off-line.  It can be tedious if vcget
    # should do all the clone:ing and pull:ing while a debugger is running
    presoak_file = simur.get_presoak_file()
    if not os.path.exists(presoak_file):
        print(f'No presoak file found ({presoak_file})')
        return 0

    presoak = simur.load_json_data(presoak_file)
    if not presoak:     # You may get an empty dictionary
        print(f'No presoak information found in {presoak_file}')
        return 0
    else:
        print(f'Processing {presoak_file}')
        for dir in presoak.keys():
            print(f'Looking at {dir}')
            if presoak[dir] == 'presoak':
                print(f'  Cloning {dir}')
            else:
                print(f'  Already cloned: {dir}')
            git_dir = simur.find_and_update_git_cache(dir)
            print(f'  Updated, git dir {git_dir}')

    return 0

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
