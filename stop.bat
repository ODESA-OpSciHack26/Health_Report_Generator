@echo off
rem Windows: double-click to stop the home page.
cd /d "%~dp0"
docker compose down
ping -n 4 127.0.0.1 >nul
