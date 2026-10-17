# Requires: PowerShell 5.1+, cloudflared installed at C:\Program Files (x86)\cloudflared\cloudflared.exe
# This script starts two Quick Tunnels (backend and frontend). 
# It does NOT start the app processes; ensure backend (:8000) and frontend preview (:4173) are already running.

$root = $PSScriptRoot
$backendLog = Join-Path $root 'backend-tunnel.log'
$frontendLog = Join-Path $root 'frontend-tunnel.log'
$cloudflared = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'

if (-not (Test-Path $cloudflared)) {
  Write-Error "cloudflared not found at $cloudflared. Install from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/."
  exit 1
}

Write-Host "=== DevAssist Demo Launcher ==="
Write-Host "Backend will tunnel http://127.0.0.1:8000 -> backend-tunnel.log"
Write-Host "Frontend will tunnel http://127.0.0.1:4173 -> frontend-tunnel.log"
Write-Host ""

# Start backend tunnel
Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--url','http://127.0.0.1:8000') -WindowStyle Normal -RedirectStandardOutput $backendLog -RedirectStandardError $backendLog

# Start frontend tunnel
Start-Process -FilePath $cloudflared -ArgumentList @('tunnel','--url','http://127.0.0.1:4173') -WindowStyle Normal -RedirectStandardOutput $frontendLog -RedirectStandardError $frontendLog

Write-Host "Tunnels starting. Check the logs for public URLs..."
Write-Host "  backend-tunnel.log"
Write-Host "  frontend-tunnel.log"
Write-Host ""
Write-Host "Open the FRONTEND public URL in a browser. Share that URL with the evaluator."
Write-Host ""
Write-Host "To get the URLs now: Get-Content $backendLog -Tail 5; Get-Content $frontendLog -Tail 5"
Write-Host ""
Write-Host "Note: Quick Tunnel URLs change on restart."
Write-Host ""
Write-Host "Press Enter to exit this launcher (tunnels keep running in their own windows)."
[void][System.Console]::ReadLine()
