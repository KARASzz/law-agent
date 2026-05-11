@echo off
if "%~1"=="utf8" goto main
chcp 65001 >nul
cmd /c "%~f0" utf8
exit /b

:main
setlocal EnableExtensions DisableDelayedExpansion
color 0B
cd /d "%~dp0"

set "PROJECT_ROOT=%~dp0"
set "WORK_DIR=%PROJECT_ROOT%law_agent\profile_ingestion"
set "INPUT_DIR=%WORK_DIR%\input"
set "OUTPUT_DIR=%WORK_DIR%\output"
set "CONFIG_FILE=%WORK_DIR%\config.json"
set "CLIENT_PROFILE_DB=%PROJECT_ROOT%data\client_profiles.db"
set "CANDIDATE_DB=%PROJECT_ROOT%data\profile_candidates.db"
set "USE_MODEL=false"
set "LAST_ERROR="
set "PYTHONPATH=%PROJECT_ROOT%"

if exist "%PROJECT_ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_CMD=%PROJECT_ROOT%.venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

if not exist "%INPUT_DIR%" mkdir "%INPUT_DIR%"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if not exist "%PROJECT_ROOT%data" mkdir "%PROJECT_ROOT%data"

:header
cls
echo ============================================================
echo                  Law Agent Profile Pipeline
echo ============================================================
echo.
echo Project root: %PROJECT_ROOT%
echo Work dir:     %WORK_DIR%
echo Python:       %PYTHON_CMD%
echo.

:menu
echo +---------------- Official Profile ----------------+
echo ^|  [1] Clean user template                         ^|
echo ^|  [2] Clean developer template                    ^|
echo ^|  [3] Choose Excel file manually                  ^|
echo ^|  [4] Clean chosen file and import to DB          ^|
echo +---------------- Assistant Candidates ------------+
echo ^|  [5] Clean assistant table to candidate pool     ^|
echo ^|  [6] Promote candidates to official profile DB   ^|
echo ^|  [7] Candidate pool stats                        ^|
echo +---------------- Helper Tools --------------------+
echo ^|  [8] Show latest output file                     ^|
echo ^|  [9] Diagnostics                                 ^|
echo ^|  [0] Exit                                        ^|
echo +--------------------------------------------------+
echo.
set "opt="
set /p opt="Input number and press Enter: "

if "%opt%"=="1" goto run_user
if "%opt%"=="2" goto run_dev
if "%opt%"=="3" goto choose_file
if "%opt%"=="4" goto choose_file_import
if "%opt%"=="5" goto run_assistant
if "%opt%"=="6" goto promote_candidates
if "%opt%"=="7" goto candidate_stats
if "%opt%"=="8" goto show_latest
if "%opt%"=="9" goto diagnostics
if "%opt%"=="0" exit /b
echo.
echo [WARN] Invalid input. Please choose 0-9.
timeout /t 2 >nul
goto header

:run_user
call :find_by_keyword "用户填写版" INPUT_FILE
if not defined INPUT_FILE (
    echo.
    echo [WARN] User template not found in input folder.
    timeout /t 3 >nul
    goto header
)
set "IMPORT_AFTER_CLEAN=false"
goto run_clean_profile

:run_dev
call :find_by_keyword "开发版" INPUT_FILE
if not defined INPUT_FILE (
    echo.
    echo [WARN] Developer template not found in input folder.
    timeout /t 3 >nul
    goto header
)
set "IMPORT_AFTER_CLEAN=false"
goto run_clean_profile

:choose_file
set "IMPORT_AFTER_CLEAN=false"
goto choose_profile_file

:choose_file_import
set "IMPORT_AFTER_CLEAN=true"
goto choose_profile_file

:choose_profile_file
cls
echo +---------------- Choose Profile Excel File ----------------+
echo   Excel lock files starting with ~$ are hidden.
echo +-----------------------------------------------------------+
echo.
call :choose_excel INPUT_FILE
if not defined INPUT_FILE goto header
goto run_clean_profile

:run_clean_profile
echo.
echo [INPUT ] %INPUT_DIR%\%INPUT_FILE%
echo [OUTPUT] %OUTPUT_DIR%
if "%IMPORT_AFTER_CLEAN%"=="true" echo [DB    ] %CLIENT_PROFILE_DB%
echo.
echo [RUN] Cleaning official profile workbook...
if "%IMPORT_AFTER_CLEAN%"=="true" (
    "%PYTHON_CMD%" -m law_agent.profile_pipeline clean-profile --input "%INPUT_DIR%\%INPUT_FILE%" --output-dir "%OUTPUT_DIR%" --config "%CONFIG_FILE%" --use-model "%USE_MODEL%" --import-db "%CLIENT_PROFILE_DB%"
) else (
    "%PYTHON_CMD%" -m law_agent.profile_pipeline clean-profile --input "%INPUT_DIR%\%INPUT_FILE%" --output-dir "%OUTPUT_DIR%" --config "%CONFIG_FILE%" --use-model "%USE_MODEL%"
)
set "LAST_ERROR=%ERRORLEVEL%"
goto end_action

:run_assistant
call :find_by_keyword "助理" INPUT_FILE
if not defined INPUT_FILE (
    echo.
    echo [WARN] Assistant table not found by keyword. Choose manually.
    echo.
    call :choose_excel INPUT_FILE
    if not defined INPUT_FILE goto header
)
echo.
echo [INPUT ] %INPUT_DIR%\%INPUT_FILE%
echo [OUTPUT] %OUTPUT_DIR%
echo [DB    ] %CANDIDATE_DB%
echo.
echo [RUN] Cleaning assistant workbook to candidate pool...
"%PYTHON_CMD%" -m law_agent.profile_pipeline clean-assistant --input "%INPUT_DIR%\%INPUT_FILE%" --output-dir "%OUTPUT_DIR%" --config "%CONFIG_FILE%" --candidate-db "%CANDIDATE_DB%"
set "LAST_ERROR=%ERRORLEVEL%"
goto end_action

:promote_candidates
cls
echo +---------------- Promote Candidates ----------------+
echo Candidate DB: %CANDIDATE_DB%
echo Profile DB:   %CLIENT_PROFILE_DB%
echo +----------------------------------------------------+
echo.
"%PYTHON_CMD%" -m law_agent.profile_pipeline list-candidates --config "%CONFIG_FILE%" --candidate-db "%CANDIDATE_DB%" --promotion-status "not_promoted" --limit 20
echo.
echo Type candidate ids separated by comma, type ALL for all pass candidates,
echo or press Enter to return.
echo.
set "CANDIDATE_IDS="
set /p CANDIDATE_IDS="Candidates: "
if "%CANDIDATE_IDS%"=="" goto header
if /I "%CANDIDATE_IDS%"=="ALL" (
    "%PYTHON_CMD%" -m law_agent.profile_pipeline promote-candidates --config "%CONFIG_FILE%" --candidate-db "%CANDIDATE_DB%" --client-profile-db "%CLIENT_PROFILE_DB%" --output-dir "%OUTPUT_DIR%" --all-pass
) else (
    "%PYTHON_CMD%" -m law_agent.profile_pipeline promote-candidates --config "%CONFIG_FILE%" --candidate-db "%CANDIDATE_DB%" --client-profile-db "%CLIENT_PROFILE_DB%" --output-dir "%OUTPUT_DIR%" --candidate-ids "%CANDIDATE_IDS%"
)
set "LAST_ERROR=%ERRORLEVEL%"
goto end_action

:candidate_stats
echo.
"%PYTHON_CMD%" -m law_agent.profile_pipeline candidate-stats --config "%CONFIG_FILE%" --candidate-db "%CANDIDATE_DB%"
set "LAST_ERROR=%ERRORLEVEL%"
goto end_action

:show_latest
echo.
echo Latest output file:
echo.
for /f "delims=" %%F in ('dir /b /a:-d /o:-d "%OUTPUT_DIR%\*.json" 2^>nul') do (
    echo   %OUTPUT_DIR%\%%F
    set "LAST_ERROR=0"
    goto end_action
)
echo [WARN] No JSON output file found.
set "LAST_ERROR=1"
goto end_action

:diagnostics
cls
echo +---------------- Diagnostics ----------------------+
echo ^|  [1] Python and dependency check                 ^|
echo ^|  [2] List input files                            ^|
echo ^|  [3] Python module syntax check                  ^|
echo ^|  [0] Return                                      ^|
echo +---------------------------------------------------+
echo.
set "diag_opt="
set /p diag_opt="Input number and press Enter: "

if "%diag_opt%"=="1" goto check_python
if "%diag_opt%"=="2" goto list_inputs
if "%diag_opt%"=="3" goto check_script
if "%diag_opt%"=="0" goto header
echo.
echo [WARN] Invalid input. Please choose 0-3.
timeout /t 2 >nul
goto diagnostics

:check_python
echo.
"%PYTHON_CMD%" --version
"%PYTHON_CMD%" -m pip --version
"%PYTHON_CMD%" -c "import openpyxl; import law_agent.profile_pipeline; print('openpyxl', openpyxl.__version__); print('profile_pipeline ok')"
set "LAST_ERROR=%ERRORLEVEL%"
goto end_action

:list_inputs
echo.
echo input folder:
echo.
dir /b "%INPUT_DIR%\*.xlsx" 2>nul
set "LAST_ERROR=%ERRORLEVEL%"
goto end_action

:check_script
echo.
"%PYTHON_CMD%" -m py_compile "%PROJECT_ROOT%law_agent\profile_pipeline.py"
if errorlevel 1 (
    set "LAST_ERROR=1"
    goto end_action
)
"%PYTHON_CMD%" -m py_compile "%WORK_DIR%\clean_to_json.py"
set "LAST_ERROR=%ERRORLEVEL%"
goto end_action

:choose_excel
set "%~1="
set /a IDX=0
for %%F in ("%INPUT_DIR%\*.xlsx") do (
    echo %%~nxF | findstr /B /C:"~$" >nul
    if errorlevel 1 (
        set /a IDX+=1
        call set "FILE_%%IDX%%=%%~nxF"
        call echo   [%%IDX%%] %%~nxF
    )
)

if "%IDX%"=="0" (
    echo.
    echo [WARN] No usable .xlsx files found in input folder.
    timeout /t 3 >nul
    exit /b 1
)

echo.
set "CHOICE="
set /p CHOICE="Input file number, or press Enter to return: "
if "%CHOICE%"=="" exit /b 1
call set "%~1=%%FILE_%CHOICE%%%"
if not defined %~1 (
    echo.
    echo [WARN] Invalid file number.
    timeout /t 2 >nul
    exit /b 1
)
exit /b 0

:find_by_keyword
set "%~2="
for %%F in ("%INPUT_DIR%\*.xlsx") do (
    echo %%~nxF | findstr /B /C:"~$" >nul
    if errorlevel 1 (
        echo %%~nxF | findstr /C:%~1 >nul
        if not errorlevel 1 (
            set "%~2=%%~nxF"
            exit /b 0
        )
    )
)
exit /b 1

:end_action
echo.
echo ---------------------------------------
if "%LAST_ERROR%"=="0" (
    echo [DONE] Task completed.
) else (
    echo [ERROR] Task failed. Exit code: %LAST_ERROR%
)
set "LAST_ERROR="
echo.
pause
goto header
