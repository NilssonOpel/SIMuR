@echo off
setlocal
call variables.bat
rd /s /q build
rd /s /q %ROOT%
rd /s /q hidden_%ROOT%

:: and maby also
rd /s /q %LOCALAPPDATA%\Sourceserver