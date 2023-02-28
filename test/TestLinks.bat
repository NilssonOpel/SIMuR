setlocal
call variables.bat

mkdir %JUNKTION%
:: Make a junction - to test that we do not follow it
junction %ROOT% %JUNKTION%

mkdir %svn_junction%
mkdir %git_junction%

pushd %svn_junction%
if exist %svn_dir% (
  svn update %svn_dir%
) else (
  svn co %SVN1%
)
popd

:: Take out the git repos here - and then make a junction to it
:: This to test that we do not follow the junction
pushd %git_junction%
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
::python ..\script\processPDBs.py %BUILD_DIR%\%CONFIG%\
python ..\script\indexPDBs.py -t %BUILD_DIR%\%CONFIG%\ -u %BUILD_DIR%\%CONFIG%\TestGitCat.pdb
if ERRORLEVEL 1 goto FAIL
:: Invalidate the source path
move %ROOT% hidden_%ROOT%

:: Provoke the crash
::%BUILD_DIR%\%CONFIG%\TestGitCat.exe
%SRCSRV%\srctool.exe -c %BUILD_DIR%\%CONFIG%\TestGitCat.pdb
if %ERRORLEVEL% EQU 10 goto NORMAL
echo Wrong no of indexed files - should be 10 but is %ERRORLEVEL%

:FAIL
echo Failed!
goto :EOF
:NORMAL
@echo Success!
@echo To provoke a crash, execute "%BUILD_DIR%\%CONFIG%\TestGitCat.exe"
@echo Run clean.bat to get rid of cruft (unless you want to debug something)
