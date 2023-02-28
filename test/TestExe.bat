setlocal
call variables.bat

mkdir %svn_local%
mkdir %git_local%

pushd %svn_local%
if exist %svn_dir% (
  svn update %svn_dir%
) else (
  svn co %SVN1%
)
popd

pushd %git_local%
if exist %git_dir1% (
  cd %git_dir1%
  git pull %GIT1%
) else (
  git clone %GIT1%
)
if exist %git_dir2% (
  cd %git_dir2%
  git pull %GIT2%
) else (
  git clone %GIT2%
)
popd

set CONFIG=RelWithDebInfo
set CONFIG=Debug

:: Build the .exe with a .pdb
copy CMakeLists.txt %ROOT%
cmake %ROOT%\CMakelists.txt -B %BUILD_DIR%
cmake --build %BUILD_DIR% --config %CONFIG%

:: Source index the .pdb
::python ..\script\prepPDB.py %BUILD_DIR%\%CONFIG%\TestGitCat.pdb C:\WinKits\10\Debuggers\x64\srcsrv
python ..\script\indexPDBs.py -t %BUILD_DIR%\%CONFIG% -u %BUILD_DIR%\%CONFIG%\TestGitCat.pdb
if ERRORLEVEL 1 goto FAIL
:: Invalidate the source path
move %ROOT% hidden_%ROOT%

:: Provoke the crash
%BUILD_DIR%\%CONFIG%\TestGitCat.exe
goto NORMAL

:FAIL
@echo Failed!
goto :EOF
:NORMAL
@echo Success!
@echo Run clean.bat to get rid of cruft (unless you want to debug something)
