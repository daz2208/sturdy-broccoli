# =============================================================================
# SyncBoard Development Startup Script (Windows PowerShell)
# =============================================================================
# This script starts the backend services in Docker and provides instructions
# for starting the frontend.
#
# Usage: .\start-dev.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "SyncBoard Development Environment Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not running"
    }
} catch {
    Write-Host "❌ ERROR: Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Docker is running" -ForegroundColor Green
Write-Host ""

# Check if .env file exists
if (-not (Test-Path .env)) {
    Write-Host "⚠️  WARNING: .env file not found!" -ForegroundColor Yellow
    Write-Host "Creating .env file from .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "✅ Created .env file" -ForegroundColor Green
    Write-Host "⚠️  IMPORTANT: Please edit .env and add your OPENAI_API_KEY!" -ForegroundColor Yellow
    Write-Host ""
}

# Stop any running containers
Write-Host "🛑 Stopping any existing containers..." -ForegroundColor Yellow
docker-compose down

Write-Host ""
Write-Host "🚀 Starting backend services (this may take a minute)..." -ForegroundColor Cyan
docker-compose up -d

Write-Host ""
Write-Host "⏳ Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check container status
Write-Host ""
Write-Host "📊 Container Status:" -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "🔍 Checking backend health..." -ForegroundColor Cyan
$maxAttempts = 30
$attempt = 0
$healthy = $false

while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Backend is healthy!" -ForegroundColor Green
            $healthy = $true
            break
        }
    } catch {
        # Backend not ready yet
    }
    $attempt++
    Write-Host "   Waiting for backend to be ready... ($attempt/$maxAttempts)" -ForegroundColor Yellow
    Start-Sleep -Seconds 2
}

if (-not $healthy) {
    Write-Host "❌ Backend failed to start properly!" -ForegroundColor Red
    Write-Host "Check logs with: docker-compose logs backend" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "✅ Backend services are running!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Services available:" -ForegroundColor Cyan
Write-Host "  • Backend API:       http://localhost:8000" -ForegroundColor White
Write-Host "  • API Docs:          http://localhost:8000/docs" -ForegroundColor White
Write-Host "  • Flower (Monitor):  http://localhost:5555 (admin/admin)" -ForegroundColor White
Write-Host "  • PostgreSQL:        localhost:5432" -ForegroundColor White
Write-Host "  • Redis:             localhost:6379" -ForegroundColor White
Write-Host ""
Write-Host "Backend logs: docker-compose logs -f backend" -ForegroundColor Yellow
Write-Host "All logs:     docker-compose logs -f" -ForegroundColor Yellow
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Next Steps: Start the Frontend" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "In a new terminal window, run:" -ForegroundColor White
Write-Host "  cd frontend" -ForegroundColor Yellow
Write-Host "  npm install    (first time only)" -ForegroundColor Yellow
Write-Host "  npm run dev" -ForegroundColor Yellow
Write-Host ""
Write-Host "Then open: http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Troubleshooting" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "If you have connection issues, see:" -ForegroundColor White
Write-Host "  ..\..\..\DOCKER_WSL_TROUBLESHOOTING.md" -ForegroundColor Yellow
Write-Host ""
Write-Host "Quick checks:" -ForegroundColor White
Write-Host "  • Test backend:  curl http://localhost:8000/health" -ForegroundColor Yellow
Write-Host "  • View logs:     docker-compose logs backend" -ForegroundColor Yellow
Write-Host "  • Restart:       docker-compose restart backend" -ForegroundColor Yellow
Write-Host "  • Stop all:      docker-compose down" -ForegroundColor Yellow
Write-Host ""
