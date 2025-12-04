@echo off
REM =============================================================================
REM SyncBoard Development Startup Script (Windows Batch)
REM =============================================================================
REM This script starts the backend services in Docker
REM
REM Usage: start-dev.bat
REM =============================================================================

echo ==========================================
echo SyncBoard Development Environment Setup
echo ==========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop and try again.
    exit /b 1
)

echo Docker is running
echo.

REM Check if .env file exists
if not exist .env (
    echo WARNING: .env file not found!
    echo Creating .env file from .env.example...
    copy .env.example .env
    echo Created .env file
    echo IMPORTANT: Please edit .env and add your OPENAI_API_KEY!
    echo.
)

REM Stop any running containers
echo Stopping any existing containers...
docker-compose down

echo.
echo Starting backend services (this may take a minute)...
docker-compose up -d

echo.
echo Waiting for services to be ready...
timeout /t 5 /nobreak >nul

REM Check container status
echo.
echo Container Status:
docker-compose ps

echo.
echo Checking backend health...
set /a attempts=0
:healthcheck
set /a attempts+=1
if %attempts% gtr 30 goto healthfail

curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 goto healthok

echo    Waiting for backend to be ready... (%attempts%/30)
timeout /t 2 /nobreak >nul
goto healthcheck

:healthfail
echo.
echo ERROR: Backend failed to start properly!
echo Check logs with: docker-compose logs backend
exit /b 1

:healthok
echo Backend is healthy!
echo.
echo ==========================================
echo Backend services are running!
echo ==========================================
echo.
echo Services available:
echo   - Backend API:       http://localhost:8000
echo   - API Docs:          http://localhost:8000/docs
echo   - Flower (Monitor):  http://localhost:5555 (admin/admin)
echo   - PostgreSQL:        localhost:5432
echo   - Redis:             localhost:6379
echo.
echo Backend logs: docker-compose logs -f backend
echo All logs:     docker-compose logs -f
echo.
echo ==========================================
echo Next Steps: Start the Frontend
echo ==========================================
echo.
echo In a new terminal window, run:
echo   cd frontend
echo   npm install    (first time only)
echo   npm run dev
echo.
echo Then open: http://localhost:3000
echo.
