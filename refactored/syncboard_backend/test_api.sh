#!/bin/bash
# API Endpoint Testing Script

set -e

echo "========================================="
echo "SyncBoard 3.0 - API Endpoint Testing"
echo "========================================="
echo ""

# Get authentication token
TOKEN=$(cat token.txt)

echo "✓ Token loaded"
echo ""

# Test 1: Upload Text
echo "[1/8] Testing Text Upload..."
curl -s -X POST http://localhost:8000/upload_text \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "FastAPI is a modern Python web framework for building APIs. It uses type hints and supports async/await patterns for high performance."}' \
  > test_upload.json
echo "✓ Text upload response saved"
cat test_upload.json | python3 -m json.tool | head -15
echo ""

# Test 2: Get all documents
echo "[2/8] Testing Get All Documents..."
curl -s -X GET http://localhost:8000/documents \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20
echo ""

# Test 3: Search documents
echo "[3/8] Testing Search..."
curl -s -X GET "http://localhost:8000/search_full?q=FastAPI&top_k=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -25
echo ""

# Test 4: Get clusters
echo "[4/8] Testing Get Clusters..."
curl -s -X GET http://localhost:8000/clusters \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
echo ""

# Test 5: Analytics
echo "[5/8] Testing Analytics..."
curl -s -X GET "http://localhost:8000/analytics?time_period=30" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -40
echo ""

# Test 6: Upload URL (should handle gracefully without real API key)
echo "[6/8] Testing URL Upload..."
curl -s -X POST http://localhost:8000/upload_url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://fastapi.tiangolo.com/"}' \
  > test_url.json 2>&1
cat test_url.json | python3 -m json.tool 2>&1 | head -10 || echo "URL upload may require API key"
echo ""

# Test 7: Export all documents
echo "[7/8] Testing Export All (JSON)..."
curl -s -X GET "http://localhost:8000/export/all?format=json" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -30
echo ""

# Test 8: Health check (no auth needed)
echo "[8/8] Testing Health Check..."
curl -s http://localhost:8000/health | python3 -m json.tool
echo ""

echo "========================================="
echo "API Testing Complete"
echo "========================================="
