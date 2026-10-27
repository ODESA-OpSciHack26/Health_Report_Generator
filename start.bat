@echo off
rem Windows: double-click to start the home page and open it in the browser.
rem The first start builds the image (about 3 minutes). Stop with stop.bat.
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
    echo Docker is not running. Start Docker Desktop, wait for "Engine running", then try again.
    pause
    exit /b 1
)

docker compose up -d app
if errorlevel 1 (
    echo The page could not be started. See the messages above.
    pause
    exit /b 1
)

echo Waiting for the page...
set tries=0
:wait
curl -fs http://localhost:8501/_stcore/health >nul 2>&1 && goto ready
set /a tries+=1
if %tries% geq 60 (
    echo The page did not start. See: docker compose logs app
    pause
    exit /b 1
)
rem Waits 2 seconds; ping works in every window, timeout does not.
ping -n 3 127.0.0.1 >nul
goto wait

:ready
start "" http://localhost:8501
echo The page is open at http://localhost:8501 - stop it with stop.bat.
ping -n 6 127.0.0.1 >nul
