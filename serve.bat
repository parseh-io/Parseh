@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Parseh on Windows -- double-click this file.
rem
rem   serve.bat           the first time: a setup wizard (what ./install.sh is on
rem                       Linux and macOS); then it starts the server and opens
rem                       Parseh in the browser (http://localhost:7654/ on a
rem                       fresh install; the port is on Settings > Network)
rem   serve.bat 9000      ... on another port, this once
rem   serve.bat setup     run the wizard again
rem   serve.bat stop      stop a running server (the stop button on any page does too)
rem   serve.bat status    is it running, and where
rem   serve.bat cert      a fresh certificate, e.g. after the addresses changed
rem
rem This file only finds a Python 3 -- the Parseh environment when there is
rem one (install.bat makes it, and the wizard offers to), as serve.sh prefers,
rem else any Python 3 -- and hands over to lib\launcher.py, which does
rem everything else.  The server runs in this window: close it, press Ctrl-C,
rem or use the stop button on any page to stop it.  (Line endings must stay
rem CRLF: cmd.exe misreads labels otherwise.)
setlocal
chcp 65001 >nul
title Parseh
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "ENVNAME=ilya-frank"
set "PY="

rem ---- 1. the environment, when it exists -- lib\runtime.py's order: ---------
rem $PARSEH_PYTHON, this folder's .runtime\env, then ilya-frank wherever a
rem conda, a mamba or a micromamba keeps its environments
if defined PARSEH_PYTHON if exist "%PARSEH_PYTHON%" set "PY="%PARSEH_PYTHON%""
if not defined PY if exist "%~dp0.runtime\env\python.exe" call :use_env "%~dp0.runtime\env"
if not defined PY for %%r in ("%USERPROFILE%\miniconda3" "%USERPROFILE%\anaconda3" "%USERPROFILE%\miniforge3" "%USERPROFILE%\mambaforge" "%USERPROFILE%\micromamba" "%USERPROFILE%\.conda" "%LOCALAPPDATA%\miniconda3" "%LOCALAPPDATA%\anaconda3" "%LOCALAPPDATA%\miniforge3" "%LOCALAPPDATA%\mambaforge" "%LOCALAPPDATA%\Programs\miniconda3" "%LOCALAPPDATA%\Programs\anaconda3" "%ProgramData%\miniconda3" "%ProgramData%\anaconda3" "%ProgramData%\miniforge3") do call :try_conda "%%~r"

rem ---- 2. otherwise any Python 3.8 or newer --------------------------------
if not defined PY call :try_py py -3
if not defined PY call :try_py python
if not defined PY call :try_py python3
if not defined PY for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :try_py "%%~d\python.exe"
if not defined PY for /d %%d in ("%ProgramFiles%\Python3*") do call :try_py "%%~d\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" call :try_py "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3
if defined PY goto run

rem ---- 3. no Python at all: the first page of the wizard is installing one --
echo.
echo   Parseh needs Python 3, and this computer does not have it.
echo.
echo   The simplest way: close this window and double-click install.bat, which
echo   brings its own Python with everything else Parseh needs.  Or:
echo.
where winget >nul 2>nul
if errorlevel 1 goto nowinget
echo   winget (the Windows package manager) can install it now:
echo     winget install -e --id Python.Python.3.12
echo.
choice /c YN /n /m "  Install Python 3.12 now? [Y/N] "
if errorlevel 2 goto nopython
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
rem the installer puts the py launcher in C:\Windows, which is already on the PATH
call :try_py py -3
if not defined PY for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :try_py "%%~d\python.exe"
if defined PY goto run
echo.
echo   Python was installed but cannot be found from here yet: close this
echo   window and double-click serve.bat again.
goto fail

:nowinget
echo   Install it from  https://www.python.org/downloads/windows/  (any 3.8 or
echo   newer), then double-click serve.bat again.
start "" https://www.python.org/downloads/windows/
goto fail

:nopython
echo   Install Python 3 from https://www.python.org/downloads/windows/ and run this again.
goto fail

:run
rem ONE LINE, READ WHOLE BEFORE IT RUNS.  cmd.exe reads a .bat from the disk a
rem line at a time, going on at the offset where it stopped -- and an update
rem from Settings replaces this very file while the launcher below waits on the
rem server.  So what runs after the launcher is on the launcher's own line, read
rem before it started: a new serve.bat is never read from the middle.
%PY% lib\launcher.py %* & if errorlevel 1 (echo. & pause & exit /b 1) else exit /b 0

:fail
echo.
pause
exit /b 1

rem ---- subroutines -----------------------------------------------------------
:try_conda
rem try_conda <conda root>: its ilya-frank environment, if it has one
if defined PY goto :eof
if not exist "%~1\envs\%ENVNAME%\python.exe" goto :eof
set "PATH=%~1\Library\bin;%PATH%"
call :use_env "%~1\envs\%ENVNAME%"
goto :eof

:use_env
rem use_env <environment>: its python, and its programs first on the PATH --
rem what activating it does, as far as anything here is concerned
set "PY="%~1\python.exe""
set "PATH=%~1;%~1\Library\bin;%~1\Scripts;%PATH%"
goto :eof

:try_py
rem try_py <command...>: keep it if it is a Python 3.8+ (the Microsoft Store's
rem "python" stub is not: it only prints an advertisement and fails)
if defined PY goto :eof
%* -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul
if errorlevel 1 goto :eof
set "PY=%*"
goto :eof
