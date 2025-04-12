@echo off
REM Run AutoPre3D GUI with Administrator privileges
@echo off
:: Check if already running with administrator privileges
NET FILE >NUL 2>&1
if %errorlevel% == 0 ( goto :main ) else ( goto :elevate )

:elevate
:: Elevate script via PowerShell
powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
exit /b

:main
:: Your actual script content below
echo Now running with administrator privileges!

echo Starting AutoPre3D GUI with Administrator privileges...

REM Check for Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in PATH. Please install Python.
    pause
    exit /b 1
)

REM Check for required Python packages
echo Checking for required Python packages...
python -c "import sys; sys.exit(0 if all(m in sys.modules or __import__(m) for m in ['PyQt5', 'yaml', 'win32gui']) else 1)" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing required packages...
    pip install PyQt5 pywin32 pyyaml
)

REM Request elevated privileges
powershell -Command "Start-Process cmd.exe -ArgumentList '/c cd /d %~dp0 && python gui_controller.py' -Verb RunAs"

echo If the GUI doesn't start, make sure you have granted administrator privileges.
echo The application window will appear in a few seconds...
timeout /t 5