@echo off
if "%~1"=="utf8" goto main
chcp 65001 >nul
cmd /c "%~f0" utf8
exit /b

:main
setlocal EnableExtensions DisableDelayedExpansion
color 0B
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"

set "OUTPUT_DIR=output"
set "CONFIG_FILE=config.json"
set "USE_MODEL=false"
set "LAST_ERROR="

if not exist input mkdir input
if not exist output mkdir output

:header
cls
echo ╔════════════════════════════════════════════════════════════╗
echo ║ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❈ ✧ ❈ ✦ ❈ ✧ ❈  ║
echo ║ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❈ ✧ ❈ ✦ ❈ ✧ ❈  ║
echo ║                                                            ║
echo ║        ██╗  ██╗  ████╗  █████╗    ████╗  ███████╗          ║
echo ║        ██║ ██╔╝ ██╔═██╗ ██╔═██╗  ██╔═██╗ ██╔════╝          ║
echo ║        █████╔╝  ██████║ █████╔╝  ██████║ ███████╗          ║
echo ║        ██╔═██╗  ██╔═██║ ██╔═██╗  ██╔═██╗ ╚════██║          ║
echo ║        ██║  ██╗ ██║ ██║ ██║  ██║ ██║ ██║ ███████║          ║
echo ║        ╚═╝  ╚═╝ ╚═╝ ╚═╝ ╚═╝  ╚═╝ ╚═╝ ╚═╝ ╚══════╝          ║
echo ║                                                            ║
echo ║ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❈ ✧ ❈  ║
echo ║ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❉ ✧ ❈ ✦ ❈ ✧ ❈  ║
echo ╠════════════════════════════════════════════════════════════╣
echo ║              ⚛️⚛️【律师画像数据采集表】⚛️⚛️                ║
echo ╠════════════════════════════════════════════════════════════╣
echo ║                    🐉 清洗入库工具  🐉                     ║
echo ╚════════════════════════════════════════════════════════════╝

:menu
echo +------------------ Core Workflow ------------------+
echo ^|                                                   ^|
echo ^|  [1] Clean user template                          ^|
echo ^|  [2] Clean developer template                     ^|
echo ^|  [3] Choose Excel file manually                   ^|
echo ^|                                                   ^|
echo +------------------ Helper Tools -------------------+
echo ^|                                                   ^|
echo ^|  [4] Show latest output file                      ^|
echo ^|  [5] Diagnostics                                  ^|
echo ^|                                                   ^|
echo +------------------ System -------------------------+
echo ^|                                                   ^|
echo ^|  [0] Exit                                         ^|
echo ^|                                                   ^|
echo +---------------------------------------------------+
echo.
set "opt="
set /p opt="Input number and press Enter: "

if "%opt%"=="1" goto run_user
if "%opt%"=="2" goto run_dev
if "%opt%"=="3" goto choose_file
if "%opt%"=="4" goto show_latest
if "%opt%"=="5" goto diagnostics
if "%opt%"=="0" exit /b
echo.
echo [WARN] Invalid input. Please choose 0-5.
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
goto run_clean

:run_dev
call :find_by_keyword "开发版" INPUT_FILE
if not defined INPUT_FILE (
	echo.
	echo [WARN] Developer template not found in input folder.
	timeout /t 3 >nul
	goto header
)
goto run_clean

:choose_file
cls
echo +---------------- Choose Excel File ----------------+
echo   Excel lock files starting with ~$ are hidden.
echo +---------------------------------------------------+
echo.
set /a IDX=0
for %%F in (input\*.xlsx) do (
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
	goto header
)

echo.
set "CHOICE="
set /p CHOICE="Input file number, or press Enter to return: "
if "%CHOICE%"=="" goto header
call set "INPUT_FILE=%%FILE_%CHOICE%%%"
if not defined INPUT_FILE (
	echo.
	echo [WARN] Invalid file number.
	timeout /t 2 >nul
	goto choose_file
)
goto run_clean

:run_clean
echo.
echo [INPUT ] input\%INPUT_FILE%
echo [OUTPUT] %OUTPUT_DIR%
echo.
echo [RUN] Cleaning workbook...
python clean_to_json.py --input "input\%INPUT_FILE%" --output-dir "%OUTPUT_DIR%" --config "%CONFIG_FILE%" --use-model "%USE_MODEL%"
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
echo ^|                                                   ^|
echo ^|  [1] Python and dependency check                  ^|
echo ^|  [2] List input files                             ^|
echo ^|  [3] Python script syntax check                   ^|
echo ^|  [0] Return                                       ^|
echo ^|                                                   ^|
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
python --version
python -m pip --version
python -c "import openpyxl; print('openpyxl', openpyxl.__version__)"
set "LAST_ERROR=%ERRORLEVEL%"
goto end_action

:list_inputs
echo.
echo input folder:
echo.
dir /b input\*.xlsx 2>nul
set "LAST_ERROR=%ERRORLEVEL%"
goto end_action

:check_script
echo.
python -m py_compile clean_to_json.py
set "LAST_ERROR=%ERRORLEVEL%"
goto end_action

:find_by_keyword
set "%~2="
for %%F in (input\*.xlsx) do (
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
set "INPUT_FILE="
echo Press any key to return to main menu...
pause >nul
goto header
