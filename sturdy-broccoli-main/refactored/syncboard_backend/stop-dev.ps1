# =============================================================================
# SyncBoard Development Stop Script (Windows PowerShell)
# =============================================================================
# This script stops all Docker containers
#
# Usage: .\stop-dev.ps1
# =============================================================================

Write-Host "🛑 Stopping SyncBoard services..." -ForegroundColor Yellow
docker-compose down

Write-Host ""
Write-Host "✅ All services stopped" -ForegroundColor Green
Write-Host ""
Write-Host "To start again: .\start-dev.ps1" -ForegroundColor Cyan
Write-Host "To reset everything: docker-compose down -v  (WARNING: deletes data)" -ForegroundColor Yellow
Write-Host ""
