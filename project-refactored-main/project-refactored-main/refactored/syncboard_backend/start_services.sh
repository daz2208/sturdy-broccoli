#!/bin/bash
#
# SyncBoard Services Startup Script
# ==================================
# This script starts all required services for the SyncBoard application:
# - Redis (message broker and cache)
# - FastAPI (web server)
# - Celery (background task worker)
#
# Usage:
#   ./start_services.sh [start|stop|restart|status]
#
# Environment Variables Required:
#   SYNCBOARD_SECRET_KEY  - JWT token secret
#   ENCRYPTION_KEY        - Token encryption key (Fernet)
#   OPENAI_API_KEY        - OpenAI API key
#   REDIS_URL             - Redis connection URL
#   DATABASE_URL          - Database connection URL
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/tmp"
REDIS_PORT=6379
FASTAPI_PORT=8000

# Load environment variables from .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "📋 Loading environment variables from .env..."
    export $(cat "$SCRIPT_DIR/.env" | grep -v '^#' | xargs)
fi

# Verify required environment variables
check_env_vars() {
    local missing_vars=()

    [ -z "$SYNCBOARD_SECRET_KEY" ] && missing_vars+=("SYNCBOARD_SECRET_KEY")
    [ -z "$ENCRYPTION_KEY" ] && missing_vars+=("ENCRYPTION_KEY")
    [ -z "$REDIS_URL" ] && missing_vars+=("REDIS_URL")
    [ -z "$DATABASE_URL" ] && missing_vars+=("DATABASE_URL")

    if [ ${#missing_vars[@]} -ne 0 ]; then
        echo "❌ Missing required environment variables: ${missing_vars[*]}"
        echo ""
        echo "Please set them in .env or export them before running this script."
        echo ""
        echo "Example .env file:"
        echo "  SYNCBOARD_SECRET_KEY=\$(openssl rand -hex 32)"
        echo "  ENCRYPTION_KEY=\$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
        echo "  REDIS_URL=redis://localhost:6379/0"
        echo "  DATABASE_URL=sqlite:///./syncboard.db"
        echo "  OPENAI_API_KEY=sk-your-openai-key"
        exit 1
    fi
}

# Start Redis
start_redis() {
    echo "🚀 Starting Redis..."
    if pgrep -x "redis-server" > /dev/null; then
        echo "✅ Redis already running (PID: $(pgrep -x redis-server))"
    else
        redis-server --daemonize yes --port $REDIS_PORT
        sleep 1
        if redis-cli -p $REDIS_PORT ping > /dev/null 2>&1; then
            echo "✅ Redis started successfully on port $REDIS_PORT"
        else
            echo "❌ Failed to start Redis"
            exit 1
        fi
    fi
}

# Start FastAPI
start_fastapi() {
    echo "🚀 Starting FastAPI..."
    if pgrep -f "uvicorn backend.main:app" > /dev/null; then
        echo "✅ FastAPI already running (PID: $(pgrep -f 'uvicorn backend.main:app'))"
    else
        cd "$SCRIPT_DIR"
        nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port $FASTAPI_PORT > "$LOG_DIR/uvicorn.log" 2>&1 &
        sleep 2
        if curl -s http://localhost:$FASTAPI_PORT/health > /dev/null 2>&1; then
            echo "✅ FastAPI started successfully on port $FASTAPI_PORT"
        else
            echo "❌ Failed to start FastAPI (check $LOG_DIR/uvicorn.log)"
            exit 1
        fi
    fi
}

# Start Celery
start_celery() {
    echo "🚀 Starting Celery worker..."
    if pgrep -f "celery.*backend.celery_app.*worker" > /dev/null; then
        echo "✅ Celery already running (PID: $(pgrep -f 'celery.*backend.celery_app.*worker' | head -1))"
    else
        cd "$SCRIPT_DIR"
        nohup python -m celery -A backend.celery_app worker --loglevel=info > "$LOG_DIR/celery.log" 2>&1 &
        sleep 3
        if pgrep -f "celery.*backend.celery_app.*worker" > /dev/null; then
            echo "✅ Celery worker started successfully"
        else
            echo "❌ Failed to start Celery (check $LOG_DIR/celery.log)"
            exit 1
        fi
    fi
}

# Stop all services
stop_services() {
    echo "🛑 Stopping services..."

    # Stop Celery
    if pgrep -f "celery.*backend.celery_app.*worker" > /dev/null; then
        echo "Stopping Celery..."
        pkill -f "celery.*backend.celery_app.*worker"
        echo "✅ Celery stopped"
    fi

    # Stop FastAPI
    if pgrep -f "uvicorn backend.main:app" > /dev/null; then
        echo "Stopping FastAPI..."
        pkill -f "uvicorn backend.main:app"
        echo "✅ FastAPI stopped"
    fi

    # Stop Redis (optional - comment out if you want Redis to keep running)
    # if pgrep -x "redis-server" > /dev/null; then
    #     echo "Stopping Redis..."
    #     redis-cli -p $REDIS_PORT shutdown
    #     echo "✅ Redis stopped"
    # fi

    echo "✅ All services stopped"
}

# Check service status
check_status() {
    echo "📊 Service Status:"
    echo ""

    # Redis
    if pgrep -x "redis-server" > /dev/null; then
        if redis-cli -p $REDIS_PORT ping > /dev/null 2>&1; then
            echo "✅ Redis: Running (PID: $(pgrep -x redis-server), Port: $REDIS_PORT)"
        else
            echo "⚠️  Redis: Process running but not responding"
        fi
    else
        echo "❌ Redis: Not running"
    fi

    # FastAPI
    if pgrep -f "uvicorn backend.main:app" > /dev/null; then
        if curl -s http://localhost:$FASTAPI_PORT/health > /dev/null 2>&1; then
            echo "✅ FastAPI: Running (PID: $(pgrep -f 'uvicorn backend.main:app'), Port: $FASTAPI_PORT)"
        else
            echo "⚠️  FastAPI: Process running but health check failed"
        fi
    else
        echo "❌ FastAPI: Not running"
    fi

    # Celery
    if pgrep -f "celery.*backend.celery_app.*worker" > /dev/null; then
        local worker_count=$(pgrep -f "celery.*backend.celery_app.*worker" | wc -l)
        echo "✅ Celery: Running ($worker_count processes)"
    else
        echo "❌ Celery: Not running"
    fi

    echo ""
    echo "📁 Log files:"
    echo "  - FastAPI: $LOG_DIR/uvicorn.log"
    echo "  - Celery:  $LOG_DIR/celery.log"
}

# Main command handler
case "${1:-start}" in
    start)
        echo "🚀 Starting SyncBoard Services..."
        echo ""
        check_env_vars
        start_redis
        start_fastapi
        start_celery
        echo ""
        echo "✅ All services started successfully!"
        echo ""
        check_status
        ;;

    stop)
        stop_services
        ;;

    restart)
        stop_services
        sleep 2
        echo ""
        check_env_vars
        start_redis
        start_fastapi
        start_celery
        echo ""
        echo "✅ All services restarted successfully!"
        echo ""
        check_status
        ;;

    status)
        check_status
        ;;

    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
