for /R %%I in (*.*.orig) do call :doit %%I %%~nI %%~pI
goto :EOF
:doit
pushd %3
del %2
ren %1 %2
popd