@echo off
REM =============================================================================
REM SyncBoard Development Stop Script (Windows Batch)
REM =============================================================================
REM This script stops all Docker containers
REM
REM Usage: stop-dev.bat
REM =============================================================================

echo Stopping SyncBoard services...
docker-compose down

echo.
echo All services stopped
echo.
echo To start again: start-dev.bat
echo To reset everything: docker-compose down -v  (WARNING: deletes data)
echo.
