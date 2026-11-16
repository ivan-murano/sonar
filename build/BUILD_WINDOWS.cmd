@echo off
rem ============================================================================
rem  Sonar - creazione dell'installazione Windows (doppio clic)
rem  Risultato: build\output\Sonar-Setup.exe  e la cartella dist\Sonar
rem  Serve: Python 3.12 e il codice del modello (cartella del progetto del modello).
rem ============================================================================
setlocal EnableExtensions
cd /d "%~dp0.."
set ROOT=%CD%
for /f "tokens=2 delims='" %%v in ('findstr /b "__version__" sonar_app\__init__.py') do set VERSION=%%v
echo Sonar %VERSION% - build Windows
echo.

rem --- codice del modello -----------------------------------------------------
if not defined SONAR_MODEL_CODE if exist "%ROOT%\..\..\src\sonar\cli.py" set SONAR_MODEL_CODE=%ROOT%\..\..
if not defined SONAR_MODEL_CODE if exist "D:\noise_pollution\src\sonar\cli.py" set SONAR_MODEL_CODE=D:\noise_pollution
if not defined SONAR_MODEL_CODE set /p SONAR_MODEL_CODE=Cartella del progetto del modello (es. D:\noise_pollution): 
if not exist "%SONAR_MODEL_CODE%\src\sonar\cli.py" (
  echo Codice del modello non trovato in "%SONAR_MODEL_CODE%".
  goto fail
)
for %%i in ("%SONAR_MODEL_CODE%") do set SONAR_MODEL_CODE=%%~fi
echo Modello: %SONAR_MODEL_CODE%

rem --- ambiente Python di build ------------------------------------------------
rem Serve un Python 3.12 standard (python.org o python-build-standalone): il Python del runtime Codex
rem impacchettato non riesce a creare connessioni HTTPS (OpenSSL), quindi non viene usato.
set PY=%ROOT%\.venv-build\Scripts\python.exe
if exist "%ROOT%\.venv-build\pyvenv.cfg" findstr /i "codex-runtimes" "%ROOT%\.venv-build\pyvenv.cfg" >nul && rmdir /s /q "%ROOT%\.venv-build"
if exist "%PY%" goto have_venv
set "BASE="
if defined SONAR_PYTHON set "BASE=%SONAR_PYTHON%"
if defined BASE goto make_venv
where py >nul 2>nul
if errorlevel 1 goto use_uv
py -3.12 -c "import sys; assert 'codex' not in sys.executable.lower()" >nul 2>nul
if errorlevel 1 goto use_uv
set "BASE=py -3.12"
goto make_venv
:use_uv
set "UVDIR=%ROOT%\build\uv"
if not exist "%UVDIR%\uv.exe" powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:UV_INSTALL_DIR='%UVDIR%'; $env:UV_NO_MODIFY_PATH='1'; irm https://astral.sh/uv/install.ps1 | iex"
if not exist "%UVDIR%\uv.exe" goto fail
echo Creo l'ambiente di build con Python 3.12 standalone (uv)
"%UVDIR%\uv.exe" venv --python 3.12 --seed "%ROOT%\.venv-build"
if errorlevel 1 goto fail
goto have_venv
:make_venv
echo Creo l'ambiente di build con: %BASE%
%BASE% -m venv "%ROOT%\.venv-build"
if errorlevel 1 goto fail
:have_venv
"%PY%" -m pip install --disable-pip-version-check -q -r build\requirements-build.txt
if errorlevel 1 goto fail

rem --- verifiche --------------------------------------------------------------
"%PY%" -m sonar_app.check_model
if errorlevel 1 goto fail
"%PY%" -m pytest -q -p no:cacheprovider tests
if errorlevel 1 goto fail

rem --- eseguibile -------------------------------------------------------------
if "%SONAR_SKIP_EXE%"=="1" if exist dist\Sonar\Sonar.exe goto exe_ready
if exist dist\Sonar rmdir /s /q dist\Sonar
"%PY%" -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller build\sonar.spec
if errorlevel 1 goto fail
"%PY%" build\bundle_models.py dist\Sonar "%SONAR_MODEL_CODE%"
if errorlevel 1 goto fail
"%PY%" build\collect_licenses.py dist\Sonar
copy /y LICENSE.txt dist\Sonar\ >nul
copy /y docs\AUTHORS.txt dist\Sonar\ >nul
copy /y docs\THIRD_PARTY_NOTICES.md dist\Sonar\ >nul
:exe_ready
echo.
echo Controllo dell'eseguibile...
set SONAR_MODEL_CODE_BUILD=%SONAR_MODEL_CODE%
set SONAR_MODEL_CODE=
"dist\Sonar\Sonar.exe" --selftest > build\selftest.txt 2>&1
"dist\Sonar\Sonar.exe" --netdiag > build\netdiag.txt 2>&1
set SONAR_MODEL_CODE=%SONAR_MODEL_CODE_BUILD%
type build\selftest.txt
findstr /c:"ESITO: OK" build\selftest.txt >nul || goto fail

rem --- programma di installazione (Inno Setup) --------------------------------
rem (percorsi in variabili: le parentesi di "Program Files (x86)" romperebbero i blocchi if)
set "PF86=%ProgramFiles(x86)%"
set "PF64=%ProgramFiles%"
set "ISCC="
call :find_iscc
if defined ISCC goto have_iscc
echo Inno Setup non trovato: provo a installarlo con winget...
winget install --id JRSoftware.InnoSetup -e --scope user --silent --accept-source-agreements --accept-package-agreements
call :find_iscc
if defined ISCC goto have_iscc
winget install --id JRSoftware.InnoSetup -e --silent --accept-source-agreements --accept-package-agreements
call :find_iscc
if defined ISCC goto have_iscc
echo.
echo Inno Setup non disponibile: l'app e' pronta in dist\Sonar\Sonar.exe (versione portatile).
echo Per il programma di installazione: installare Inno Setup 6 da https://jrsoftware.org/isdl.php e rilanciare.
goto done
:have_iscc
echo Inno Setup: %ISCC%
"%ISCC%" /Q /DAppVersion=%VERSION% build\installer.iss
if errorlevel 1 goto fail
echo.
echo Fatto: build\output\Sonar-Setup.exe (versione %VERSION%)
:done
echo Versione portatile: dist\Sonar\Sonar.exe
pause
exit /b 0
:fail
echo.
echo Build non riuscita: inviare i messaggi qui sopra.
pause
exit /b 1

:find_iscc
if exist "%PF86%\Inno Setup 6\ISCC.exe" set "ISCC=%PF86%\Inno Setup 6\ISCC.exe"
if exist "%PF64%\Inno Setup 6\ISCC.exe" set "ISCC=%PF64%\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
exit /b 0
