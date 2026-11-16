@echo off
rem Build con registro in build\output\build_log.txt (nessun tasto da premere)
cd /d "%~dp0"
(echo.) | cmd /c "%~dp0BUILD_WINDOWS.cmd" > "%~dp0output\build_log.txt" 2>&1
echo FINE>> "%~dp0output\build_log.txt"
