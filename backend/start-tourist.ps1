# =====================================================================
# AI Tourist Safety - one-command startup
# Starts: Postgres + Redis (Docker) -> ngrok (fixed domain) -> backend
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File start-tourist.ps1
# =====================================================================

$backend = "C:\AI_tourist_safety\backend"
$ngrok   = "C:\Users\91630\ngrok-bin\ngrok.exe"
$domain  = "uninjured-transfer-botanist.ngrok-free.dev"   # your permanent ngrok dev domain

Set-Location $backend

# --- 1. Database + Redis via Docker --------------------------------
Write-Host "`n[1/3] Starting Postgres + Redis (Docker)..." -ForegroundColor Cyan
try {
    docker info *> $null
    docker compose up -d postgres redis
    Write-Host "      DB + Redis up." -ForegroundColor Green
} catch {
    Write-Host "      Docker isn't running. Start Docker Desktop, then re-run this script." -ForegroundColor Yellow
    Write-Host "      (Skipping DB start for now.)" -ForegroundColor Yellow
}

# --- 2. ngrok on the FIXED domain (opens its own window) -----------
Write-Host "`n[2/3] Starting ngrok on fixed domain: $domain" -ForegroundColor Cyan
$already = try { (Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 2) } catch { $null }
if ($already) {
    Write-Host "      ngrok already running - reusing it." -ForegroundColor Green
} else {
    Start-Process -FilePath $ngrok -ArgumentList @("http","8000","--url=$domain")
    Start-Sleep -Seconds 3
    Write-Host "      ngrok started. Public URL: https://$domain" -ForegroundColor Green
}

# --- 3. Backend (runs in THIS window; Ctrl+C to stop) --------------
Write-Host "`n[3/3] Starting backend (uvicorn)... press Ctrl+C to stop.`n" -ForegroundColor Cyan
& "$backend\.venv\Scripts\uvicorn.exe" app.main:app --reload
