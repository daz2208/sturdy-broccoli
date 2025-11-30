#!/bin/bash
# Diagnostic script to check system status

echo "=========================================="
echo "SYNCBOARD DIAGNOSTIC REPORT"
echo "=========================================="
echo ""

echo "1. Checking Docker Compose services..."
docker compose ps
echo ""

echo "2. Checking backend health..."
curl -s http://localhost:8000/health || echo "❌ Backend not responding"
echo ""

echo "3. Checking Celery worker status..."
docker compose logs --tail=20 celery 2>&1 | grep -i "error\|ready\|failed" || echo "No Celery logs found"
echo ""

echo "4. Checking recent backend errors..."
docker compose logs --tail=30 backend 2>&1 | grep -i "error\|exception\|failed" || echo "No recent errors"
echo ""

echo "5. Checking database connection..."
docker compose exec -T db pg_isready 2>&1 || echo "❌ Database not responding"
echo ""

echo "6. Checking recent upload task logs..."
docker compose logs --tail=50 celery 2>&1 | grep -i "upload\|process_file" || echo "No upload logs found"
echo ""

echo "=========================================="
echo "DIAGNOSTIC COMPLETE"
echo "=========================================="
