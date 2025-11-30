#!/bin/bash
# =============================================================================
# SyncBoard Development Stop Script
# =============================================================================
# This script stops all Docker containers
#
# Usage: ./stop-dev.sh
# =============================================================================

echo "🛑 Stopping SyncBoard services..."
docker-compose down

echo ""
echo "✅ All services stopped"
echo ""
echo "To start again: ./start-dev.sh"
echo "To reset everything: docker-compose down -v  (WARNING: deletes data)"
echo ""
