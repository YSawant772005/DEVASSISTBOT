@echo off
REM Quick demo launcher for DevAssist
REM Windows + PowerShell compatible. Requires cloudflared (see root README).
REM Assumes backend runs on :8000 (uvicorn) and frontend on :4173 (vite preview).

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"

echo === DevAssist Demo Launcher ===
echo Checking if ports are in use...
echo.

REM Kill any existing cloudflared processes if requested? avoid, but just warn.
tasklist /FI "IMAGENAME eq cloudflared.exe" 2>&1 | find /I "cloudflared.exe" >NUL
if "%ERRORLEVEL%"=="0" (
  echo cloudflared is already running. Skipping spawning new tunnel processes.
  echo If you need fresh URLs, close cloudflared first.
  echo.
)

echo Starting backend tunnel (Quick Tunnel) to http://127.0.0.1:8000...
start "" powershell -NoExit -WindowStyle Normal -Command "cd '%BACKEND_DIR%'; & 'C:\Program Files (x86)\cloudflared\cloudflared.exe' tunnel --url http://127.0.0.1:8000 | Tee-Object -FilePath '%ROOT%backend-tunnel.log'"

echo Waiting 5 seconds for backend tunnel to initialize...
timeout /t 5 /nobreak >NUL

echo Starting frontend tunnel (Quick Tunnel) to http://127.0.0.1:4173...
start "" powershell -NoExit -WindowStyle Normal -Command "cd '%FRONTEND_DIR%'; & 'C:\Program Files (x86)\cloudflared\cloudflared.exe' tunnel --url http://127.0.0.1:4173 | Tee-Object -FilePath '%ROOT%frontend-tunnel.log'"

echo Waiting 5 seconds for frontend tunnel to initialize...
timeout /t 5 /nobreak >NUL

echo.
echo === Tunnels started ===
echo Backend tunnel logs: %ROOT%backend-tunnel.log
echo Frontend tunnel logs: %ROOT%frontend-tunnel.log
echo.
echo The public URLs will appear in those log files (and in the terminal windows).
echo Open the FRONTEND URL in a browser.
echo Ensure backend is running on :8000 and frontend preview is running on :4173 (see README).
echo.
pause
