import os
import prepPDB
import simur
import sys

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
def usage():
    the_script = os.path.basename(sys.argv[0])
    print(f'usage: {the_script} pdb-dir')
    print(f'  e.g. {the_script} RelWithDebInfo')
    print( '    update the cache in pdb-dir')

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

    cache_file = os.path.join(root, 'vcs_cache.json')
    if not os.path.exists(cache_file):
        print(f'No cache file found, \'{cache_file}\' expected')
        return 3
    vcs_cache = simur.load_json_data(cache_file)
    vcs_cache = prepPDB.verify_cache_data(vcs_cache)
    simur.store_json_data(cache_file, vcs_cache)

    return 0

#-------------------------------------------------------------------------------
#
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main())
