setlocal
call variables.bat

mkdir %svn_local%
mkdir %git_local%

pushd %svn_local%
if exist %SVN1% (
  svn update %SVN1%
) else (
  svn co %SVN1%
)
popd

pushd %git_local%
if exist %GIT1% (
  git pull %GIT1%
) else (
  git clone %GIT1%
)
if exist %GIT2% (
  git pull %GIT2%
) else (
  git clone %GIT2%
)
popd

mkdir %svn_lib_local%
mkdir %git_lib_local%

pushd %svn_lib_local%
if exist %SVN1% (
  svn update %SVN1%
) else (
  svn co %SVN1%
)
popd

pushd %git_lib_local%
if exist %GIT1% (
  git pull %GIT1%
) else (
  git clone %GIT1%
)
if exist %GIT2% (
  git pull %GIT2%
) else (
  git clone %GIT2%
)
popd

set CONFIG=RelWithDebInfo
set CONFIG=Debug

:: Make the .lib with a .pdb
copy CMakeLib.txt %LIB_ROOT%\CMakeLists.txt
cmake %LIB_ROOT%\CMakelists.txt -B %BUILD_LIB_DIR%
cmake --build %BUILD_LIB_DIR% --config %CONFIG%

::python ..\script\processPDBs.py %BUILD_LIB_DIR%\%CONFIG%\
python ..\script\indexPDBs.py -t %BUILD_LIB_DIR%\%CONFIG%\
if ERRORLEVEL 1 goto FAIL

:: Hide the lib sources
move %LIB_ROOT% hidden_%LIB_ROOT%

:: Make the .exe with a .pdb
copy CMakeExeLib.txt %ROOT%\CMakeLists.txt
mkdir %BUILD_DIR%\%CONFIG%
copy %BUILD_LIB_DIR%\%CONFIG% %BUILD_DIR%\%CONFIG%
cmake %ROOT%\CMakelists.txt -B %BUILD_DIR% -DMY_LIB_DIR=%BUILD_DIR%/%CONFIG%
cmake --build %BUILD_DIR% --config %CONFIG%

:: Source index the .pdb
::python ..\script\prepPDB.py %BUILD_DIR%\%CONFIG%\TestGitCat.pdb C:\WinKits\10\Debuggers\x64\srcsrv
python ..\script\indexPDBs.py -t %BUILD_DIR%\%CONFIG%\
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
