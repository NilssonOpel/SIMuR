@ECHO OFF
:: Put this bat file in your path and redirect and invoke your python your way
:: Remember that the call to 'vcget.cmd' will be in your PDB:s forever while
:: vcget.py and python itself will evolve...
python %~p0\vcget.py %*