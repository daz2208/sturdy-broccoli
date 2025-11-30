#!/bin/bash
# =============================================================================
# SyncBoard Development Startup Script
# =============================================================================
# This script starts the backend services in Docker and provides instructions
# for starting the frontend.
#
# Usage: ./start-dev.sh
# =============================================================================

set -e

echo "=========================================="
echo "SyncBoard Development Environment Setup"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ ERROR: Docker is not running!"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  WARNING: .env file not found!"
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo "⚠️  IMPORTANT: Please edit .env and add your OPENAI_API_KEY!"
    echo ""
fi

# Stop any running containers
echo "🛑 Stopping any existing containers..."
docker-compose down

echo ""
echo "🚀 Starting backend services (this may take a minute)..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check container status
echo ""
echo "📊 Container Status:"
docker-compose ps

echo ""
echo "🔍 Checking backend health..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Backend is healthy!"
        break
    fi
    attempt=$((attempt + 1))
    echo "   Waiting for backend to be ready... ($attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Backend failed to start properly!"
    echo "Check logs with: docker-compose logs backend"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Backend services are running!"
echo "=========================================="
echo ""
echo "Services available:"
echo "  • Backend API:       http://localhost:8000"
echo "  • API Docs:          http://localhost:8000/docs"
echo "  • Flower (Monitor):  http://localhost:5555 (admin/admin)"
echo "  • PostgreSQL:        localhost:5432"
echo "  • Redis:             localhost:6379"
echo ""
echo "Backend logs: docker-compose logs -f backend"
echo "All logs:     docker-compose logs -f"
echo ""
echo "=========================================="
echo "Next Steps: Start the Frontend"
echo "=========================================="
echo ""
echo "In a new terminal window, run:"
echo "  cd frontend"
echo "  npm install    (first time only)"
echo "  npm run dev"
echo ""
echo "Then open: http://localhost:3000"
echo ""
echo "=========================================="
echo "Troubleshooting"
echo "=========================================="
echo ""
echo "If you have connection issues, see:"
echo "  ../../../DOCKER_WSL_TROUBLESHOOTING.md"
echo ""
echo "Quick checks:"
echo "  • Test backend:  curl http://localhost:8000/health"
echo "  • View logs:     docker-compose logs backend"
echo "  • Restart:       docker-compose restart backend"
echo "  • Stop all:      docker-compose down"
echo ""
