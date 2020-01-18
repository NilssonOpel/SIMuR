@echo off
setlocal
call variables.bat
rd /s /q build
rd /s /q %ROOT%
rd /s /q hidden_%ROOT%

:: and maybe also
rd /s /q %LOCALAPPDATA%\Sourceserver
:: Will remove VS's own internal SRCSRV cache

:: but may not
:: rd /s /q %SIMUR_REPO_CACHE%
:: Since that will remove you current cache of the repos