@ECHO OFF
:: Put this bat file in your path and redirect and invoke your python your way
:: Remember that the call to 'vcget.cmd' will be in your PDB:s forever while
:: vcget.py and python itself will evolve...
set SIMUR_REPO_CACHE=\\our-server\shared_dir\SIMuR_cache
python %~p0\vcget.py %*