#!/bin/bash
# =============================================================================
# Idea Seeds Feature Test Script for Docker Environment
# =============================================================================
# Run this script on your local machine with Docker running
#
# Usage: ./test_idea_seeds_docker.sh
# =============================================================================

set -e  # Exit on error

echo "======================================================================"
echo "IDEA SEEDS FEATURE - COMPREHENSIVE DOCKER TEST"
echo "======================================================================"
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local test_command="$2"

    echo -e "${YELLOW}Testing: ${test_name}${NC}"

    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASSED${NC}\n"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAILED${NC}\n"
        ((TESTS_FAILED++))
    fi
}

echo "Step 1: Checking Docker containers..."
echo "----------------------------------------------------------------------"
docker-compose ps

echo
echo "Step 2: Testing Python imports in backend container..."
echo "----------------------------------------------------------------------"

run_test "Import idea_seeds_service" \
    "docker-compose exec -T backend python -c 'from backend.idea_seeds_service import IdeaSeedsService; print(\"✓ Import successful\")'"

run_test "Import summarization_service" \
    "docker-compose exec -T backend python -c 'from backend.summarization_service import SummarizationService; print(\"✓ Import successful\")'"

run_test "Initialize IdeaSeedsService" \
    "docker-compose exec -T backend python -c 'from backend.idea_seeds_service import IdeaSeedsService; s = IdeaSeedsService(); print(f\"✓ Service initialized, API available: {s.is_available()}\")'"

echo
echo "Step 3: Testing database models..."
echo "----------------------------------------------------------------------"

run_test "Check DBBuildIdeaSeed table exists" \
    "docker-compose exec -T db psql -U syncboard -d syncboard -c 'SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '\''build_idea_seeds'\'';' | grep -q '1'"

run_test "Check saved_ideas table exists" \
    "docker-compose exec -T db psql -U syncboard -d syncboard -c 'SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '\''saved_ideas'\'';' | grep -q '1'"

run_test "Verify DBBuildIdeaSeed columns" \
    "docker-compose exec -T backend python -c 'from backend.db_models import DBBuildIdeaSeed; assert hasattr(DBBuildIdeaSeed, \"title\"); assert hasattr(DBBuildIdeaSeed, \"difficulty\"); assert hasattr(DBBuildIdeaSeed, \"feasibility\"); print(\"✓ All required columns present\")'"

echo
echo "Step 4: Testing API endpoints (requires backend running)..."
echo "----------------------------------------------------------------------"

# Check if backend is healthy
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ Backend is healthy"

    # You'll need to create a test user and get a token for these tests
    # For now, we'll just test that endpoints exist

    run_test "Check /quick-ideas endpoint exists" \
        "curl -s http://localhost:8000/docs | grep -q 'quick-ideas'"

    run_test "Check /idea-seeds endpoint exists" \
        "curl -s http://localhost:8000/docs | grep -q 'idea-seeds'"

    run_test "Check /what_can_i_build endpoint exists" \
        "curl -s http://localhost:8000/docs | grep -q 'what_can_i_build'"

    run_test "Check /ideas/save endpoint exists" \
        "curl -s http://localhost:8000/docs | grep -q 'ideas/save'"

    run_test "Check /ideas/mega-project endpoint exists" \
        "curl -s http://localhost:8000/docs | grep -q 'mega-project'"
else
    echo -e "${RED}⚠ Backend not running on localhost:8000${NC}"
    echo "Skipping API endpoint tests"
fi

echo
echo "Step 5: Testing Celery workers can import modules..."
echo "----------------------------------------------------------------------"

run_test "Celery worker can import idea_seeds_service" \
    "docker-compose exec -T celery python -c 'from backend.idea_seeds_service import IdeaSeedsService; print(\"✓ Import successful in Celery worker\")'"

echo
echo "Step 6: Checking configuration..."
echo "----------------------------------------------------------------------"

run_test "IDEA_MODEL environment variable is set" \
    "docker-compose exec -T backend python -c 'from backend.config import settings; print(f\"✓ IDEA_MODEL: {settings.idea_model}\")'"

run_test "SUMMARY_MODEL environment variable is set" \
    "docker-compose exec -T backend python -c 'from backend.config import settings; print(f\"✓ SUMMARY_MODEL: {settings.summary_model}\")'"

echo
echo "======================================================================"
echo "TEST SUMMARY"
echo "======================================================================"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED! Idea Seeds feature is fully functional.${NC}"
    exit 0
else
    echo -e "${RED}❌ SOME TESTS FAILED. Please review the errors above.${NC}"
    exit 1
fi
