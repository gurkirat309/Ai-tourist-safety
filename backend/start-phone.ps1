# =====================================================================
# AI Tourist Safety — run the tourist app for PHONE testing
#
# Starts: Postgres + Redis (Docker) -> builds the PWA -> backend -> ngrok
#
# The backend serves the built app on its OWN origin, so a single https
# tunnel covers both the app and the API. That matters because phones only
# allow GPS on secure origins, and it means no CORS and no second tunnel.
#
# Run:  powershell -ExecutionPolicy Bypass -File start-phone.ps1
# =====================================================================

$root    = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$mobile  = Join-Path $root "mobile"
$ngrok   = "C:\Users\91630\ngrok-bin\ngrok.exe"
$domain  = "uninjured-transfer-botanist.ngrok-free.dev"   # permanent dev domain

Set-Location $backend

# --- 1. Database + Redis ------------------------------------------------
Write-Host "`n[1/4] Starting Postgres + Redis (Docker)..." -ForegroundColor Cyan
try {
    docker info *> $null
    docker compose up -d postgres redis
    Write-Host "      DB + Redis up." -ForegroundColor Green
} catch {
    Write-Host "      Docker isn't running. Start Docker Desktop, then re-run." -ForegroundColor Yellow
    exit 1
}

# --- 2. Build the tourist PWA ------------------------------------------
# Uses .env.production (empty VITE_API_BASE) so the app calls its own origin.
Write-Host "`n[2/4] Building the tourist app..." -ForegroundColor Cyan
Push-Location $mobile
if (-not (Test-Path (Join-Path $mobile "node_modules"))) {
    Write-Host "      Installing dependencies (first run only)..." -ForegroundColor Gray
    npm install
}
npm run build
Pop-Location
if (-not (Test-Path (Join-Path $mobile "dist\index.html"))) {
    Write-Host "      Build failed - no dist/index.html." -ForegroundColor Red
    exit 1
}
Write-Host "      App built." -ForegroundColor Green

# --- 3. ngrok on the fixed domain --------------------------------------
Write-Host "`n[3/4] Starting ngrok on: $domain" -ForegroundColor Cyan
$already = try { Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 2 } catch { $null }
if ($already) {
    Write-Host "      ngrok already running - reusing it." -ForegroundColor Green
} else {
    Start-Process -FilePath $ngrok -ArgumentList @("http", "8000", "--url=$domain")
    Start-Sleep -Seconds 3
}

Write-Host "`n  Open this on your phone:" -ForegroundColor White
Write-Host "    https://$domain" -ForegroundColor Yellow
Write-Host "  (ngrok's free tier shows a warning page once - tap 'Visit Site'.)`n" -ForegroundColor Gray

# --- 4. Backend (this window; Ctrl+C to stop) --------------------------
Write-Host "[4/4] Starting backend... press Ctrl+C to stop.`n" -ForegroundColor Cyan
& "$backend\.venv\Scripts\uvicorn.exe" app.main:app --host 0.0.0.0 --port 8000
