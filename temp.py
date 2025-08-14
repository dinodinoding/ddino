@echo off
chcp 65001 > nul
tasklist /FI "IMAGENAME eq heating_monitor_worker.exe" | findstr "heating_monitor_worker.exe" > nul
if %errorlevel% neq 0 (
    start "" "c:\monitoring\heating\heating_monitor_worker.exe"
)
