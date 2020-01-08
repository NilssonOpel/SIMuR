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

:: Build the .exe with a .pdb
copy CMakeLists.txt %ROOT%
cmake %ROOT%\CMakelists.txt -B %BUILD_DIR%
cmake --build %BUILD_DIR% --config RelWithDebInfo

:: Source index the .pdb
python ..\script\prepPDB.py %BUILD_DIR%\RelWithDebInfo\TestGitCat.pdb C:\WinKits\10\Debuggers\x64\srcsrv
if ERRORLEVEL 1 goto FAIL
:: Invalidate the source path
move %ROOT% hidden_%ROOT%

:: Provoke the crash
%BUILD_DIR%\RelWithDebInfo\TestGitCat.exe
goto NORMAL

:FAIL
echo Failed!
goto :EOF
:NORMAL
echo Success!