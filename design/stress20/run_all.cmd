@echo off
set "TASK_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
call "%~dp0compile_runner.cmd"
if errorlevel 1 exit /b %errorlevel%
"%TASK_PYTHON%" -X utf8 "%~dp0retest.py" all --fresh
if errorlevel 1 exit /b %errorlevel%
"%TASK_PYTHON%" -X utf8 "%~dp0targeted_checks.py"
if errorlevel 1 exit /b %errorlevel%
"%TASK_PYTHON%" -X utf8 "%~dp0scale_tests.py"
if errorlevel 1 exit /b %errorlevel%
"%TASK_PYTHON%" -X utf8 "%~dp0final_audit.py"
