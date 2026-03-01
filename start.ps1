# ============================================================
# start.ps1 -- TACO Single-Click Setup (Windows PowerShell)
# Double-click OR right-click -> "Run with PowerShell"
# ============================================================

$ErrorActionPreference = "Stop"

# -- Colors --------------------------------------------------------------------
function Green($msg) { Write-Host $msg -ForegroundColor Green }
function Yellow($msg) { Write-Host $msg -ForegroundColor Yellow }
function Red($msg) { Write-Host $msg -ForegroundColor Red }
function Blue($msg) { Write-Host $msg -ForegroundColor Cyan }

Blue "========================================================"
Blue "  [TACO MVP -- Single-Click Start]"
Blue "========================================================"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$infra = Join-Path $root "infra"
$back = Join-Path $root "backend"
$front = Join-Path $root "frontend"

# -- Prerequisite checks --------------------------------------------------------
Blue "`n[ 1/5 ] Checking prerequisites..."

$checks = @{ "Docker" = "docker"; "Python" = "python"; "Node" = "node"; "pnpm" = "pnpm" }
foreach ($name in $checks.Keys) {
    try {
        $null = Get-Command $checks[$name] -ErrorAction Stop
        Green "  [OK] $name found"
    }
    catch {
        Red "  [X] $name not found. Please install it and re-run."
        exit 1
    }
}

# -- Check Docker daemon --------------------------------------------------------
try {
    $null = docker info 2>$null
    Green "  [OK] Docker daemon running"
}
catch {
    Red "  [X] Docker daemon is not running. Start Docker Desktop first."
    exit 1
}

# -- Start PostgreSQL via Docker Compose ---------------------------------------
Blue "`n[ 2/5 ] Starting PostgreSQL (Docker)..."
Push-Location $infra
try {
    cmd.exe /c "docker compose up -d postgres >nul 2>&1"
    if ($LASTEXITCODE -ne 0) { throw "Docker compose failed" }
    Green "  [OK] Postgres container started"
}
catch {
    Red "  [X] Failed to start Postgres. Check infra/docker-compose.yml"
    exit 1
}
finally {
    Pop-Location
}

# Wait for Postgres to be ready
Yellow "       Waiting for Postgres health check..."
$attempts = 0
do {
    Start-Sleep -Seconds 2
    $attempts++
    $health = docker inspect --format="{{.State.Health.Status}}" taco-postgres 2>$null
} while ($health -ne "healthy" -and $attempts -lt 15)

if ($health -ne "healthy") {
    Yellow "  [!] Postgres not healthy yet -- continuing anyway"
}
else {
    Green "  [OK] Postgres healthy"
}

# -- Install / verify backend venv ---------------------------------------------
Blue "`n[ 3/5 ] Setting up Python backend..."
Push-Location $back

if (-not (Test-Path ".venv")) {
    Yellow "       Creating Python virtual environment..."
    python -m venv .venv
}

$pip = Join-Path $back ".venv\Scripts\pip.exe"
$py = Join-Path $back ".venv\Scripts\python.exe"
$uvi = Join-Path $back ".venv\Scripts\uvicorn.exe"

Yellow "       Installing/verifying Python dependencies..."
& $pip install -r requirements.txt -q
Green "  [OK] Python dependencies ready"

# -- Start FastAPI backend ------------------------------------------------------
Yellow "       Starting FastAPI on http://localhost:8000 ..."
$backJob = Start-Process -FilePath $uvi `
    -ArgumentList "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info" `
    -WorkingDirectory $back `
    -PassThru -WindowStyle Minimized
Green "  [OK] Backend started (PID $($backJob.Id))"
Pop-Location

# Wait for /health
Yellow "       Waiting for backend to be ready..."
$attempts = 0; $ready = $false
do {
    Start-Sleep -Seconds 2; $attempts++
    try {
        $resp = Invoke-RestMethod -Uri http://localhost:8000/health -TimeoutSec 3 -ErrorAction Stop
        if ($resp.status -eq "ok") { $ready = $true }
    }
    catch {}
} while (-not $ready -and $attempts -lt 15)

if ($ready) { Green "  [OK] Backend healthy: $($resp.db)" }
else { Yellow "  [!] Backend not responding yet -- may still be starting" }

# -- Install frontend deps + start dev server -----------------------------------
Blue "`n[ 4/5 ] Setting up React frontend..."
Push-Location $front

if (-not (Test-Path "node_modules")) {
    Yellow "       Installing frontend dependencies (first run)..."
    pnpm install --silent
}
Green "  [OK] Frontend dependencies ready"

Yellow "       Starting Vite dev server on http://localhost:5173 ..."
$frontJob = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c pnpm run dev" `
    -WorkingDirectory $front `
    -PassThru -WindowStyle Minimized
Green "  [OK] Frontend started (PID $($frontJob.Id))"
Pop-Location

Start-Sleep -Seconds 3

# -- Run Smoke Test ------------------------------------------------------------
Blue "`n[ 5/5 ] Running smoke test..."
& $py (Join-Path $root "scripts\smoke_test.py")
if ($LASTEXITCODE -eq 0) {
    Green "  [OK] All smoke tests passed!"
}
else {
    Yellow "  [!] Some smoke tests failed (check output above)"
    Yellow "     Chat tests require valid API keys in backend/.env"
}

# -- Done ----------------------------------------------------------------------
Blue "`n========================================================"
Green "  TACO is running!"
Blue "========================================================"
Write-Host ""
Write-Host "  [API] Backend   ->  http://localhost:8000"      -ForegroundColor White
Write-Host "  [DOC] API Docs  ->  http://localhost:8000/docs"  -ForegroundColor White
Write-Host "  [UI]  Dashboard ->  http://localhost:5173"      -ForegroundColor White
Write-Host ""
Yellow "  Press Ctrl+C or close this window to STOP the servers."
Write-Host "  (Backend PID: $($backJob.Id)  Frontend PID: $($frontJob.Id))"
Write-Host ""

# Open browser
Start-Sleep -Seconds 2
Start-Process "http://localhost:5173"
Start-Process "http://localhost:8000/docs"

# Keep window open
try {
    $backJob.WaitForExit()
}
catch {
    # User Ctrl+C -- cleanup
    if (-not $backJob.HasExited) { $backJob.Kill() }
    if (-not $frontJob.HasExited) { $frontJob.Kill() }
    Yellow "`n  Servers stopped. Goodbye!"
}
