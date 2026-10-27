@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %errorlevel%
cl /nologo /std:c++17 /EHsc /O2 /W4 /utf-8 "%~dp0runner.cpp" /Fe:"%~dp0runner.exe" /Fo:"%~dp0runner.obj"
