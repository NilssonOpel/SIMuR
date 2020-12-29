@echo off
setlocal
call variables.bat
rd /s /q %BUILD_DIR%
rd /s /q %BUILD_LIB_DIR%
rd /s /q %ROOT%
rd /s /q %LIB_ROOT%
rd /s /q hidden_%ROOT%
rd /s /q hidden_%LIB_ROOT%

rd /s /q %JUNKTION%
junction -d %JUNKTION%
:: and maybe also
rd /s /q %LOCALAPPDATA%\Sourceserver
:: Will remove VS's own internal SRCSRV cache

:: but may not
:: rd /s /q %SIMUR_REPO_CACHE%
:: Since that will remove you current cache of the repos