@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %errorlevel%
cl /nologo /std:c++14 /EHsc /O2 /W4 /permissive- /utf-8 "%~dp0benchmark.cpp" /Fe:"%~dp0benchmark.exe" /Fo:"%~dp0benchmark.obj"
if errorlevel 1 exit /b %errorlevel%
cl /nologo /std:c++14 /EHsc /O2 /W4 /permissive- /utf-8 "%~dp0integration_check.cpp" /Fe:"%~dp0submission_check.exe" /Fo:"%~dp0submission_check.obj"
