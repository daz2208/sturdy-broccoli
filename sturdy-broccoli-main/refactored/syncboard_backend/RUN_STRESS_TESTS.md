# Production Stress Test Suite

## Overview

This test suite performs comprehensive production-grade testing:

- **20 concurrent users** making requests simultaneously
- **10+ requests per user** across all endpoints
- **Race condition testing** for database operations
- **~1000 total requests** in under 30 seconds
- **Response time tracking** (avg, min, max)
- **Error detection** and categorization

## What Gets Tested

### 1. Usage & Billing Endpoints
- `/usage` - Get current usage (concurrent)
- `/usage/history` - Get usage history
- `/usage/subscription` - Get subscription details
- `/usage/plans` - List available plans

**Tests for:**
- Database race conditions when creating subscriptions
- Schema mismatches (started_at, expires_at, etc.)
- Concurrent usage record creation
- Foreign key constraint violations

### 2. Learning System Endpoints
- `/learning/status` - Learning system status
- `/learning/rules` - Get learned rules
- `/learning/vocabulary` - Get vocabulary
- `/learning/profile` - Get learning profile
- `/learning/agent/status` - Agent status

**Tests for:**
- Missing database tables
- Undefined field access
- Concurrent rule creation
- Profile calibration under load

### 3. All Critical Endpoints
- Health check
- Documents, Clusters, Knowledge Bases
- Tags, Duplicates, Saved Searches
- Analytics overview

**Tests for:**
- General stability under load
- Connection pool exhaustion
- Memory leaks
- Timeout handling

### 4. Database Race Conditions
- 20 simultaneous subscription creations
- Concurrent usage record updates
- Multiple users accessing same data

**Tests for:**
- Duplicate key violations
- Deadlocks
- Transaction isolation issues

## How to Run

### Prerequisites

1. **Backend must be running:**
   ```bash
   cd /home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend
   docker-compose up -d
   # OR
   ./start_services.sh
   ```

2. **Install Python dependencies:**
   ```bash
   pip install aiohttp asyncio
   ```

### Running Tests

#### Full Stress Test (Recommended)
```bash
cd /home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend
python3 test_production_stress.py
```

**Expected Output:**
```
🔧 Setting up test environment...
✓ Test user registered
✓ Authentication successful

============================================================
🔥 PRODUCTION STRESS TEST
============================================================
Concurrent Users: 20
Requests per User: 40
Total Requests: ~800

👤 User 0 starting tests...
👤 User 1 starting tests...
...
✓ User 19 completed

============================================================
📊 TEST RESULTS
============================================================

⏱️  Total Duration: 15.23s
📈 Requests/Second: 52.46
📊 Total Requests: 800
✓ Passed: 800
✗ Failed: 0
Success Rate: 100.0%

⚡ Response Times:
  Average: 145.3ms
  Min: 23.1ms
  Max: 523.7ms

============================================================
🎉 ALL TESTS PASSED! System is production-ready.
============================================================
```

#### Frontend Build Test
```bash
cd /home/user/sturdy-broccoli/sturdy-broccoli-main/refactored/syncboard_backend
./test_frontend_pages.sh
```

**Expected Output:**
```
🧪 Testing All Frontend Pages for Crashes
========================================

📦 Running production build...
✓ Compiled successfully

📊 Build Results:
  Errors: 0
  Warnings: 0

✅ BUILD SUCCESSFUL

🔍 Running TypeScript type check...

📊 Type Check Results:
  Type Errors: 0

✅ TYPE CHECK PASSED

📄 Page Count:
  Pages: 39
  Layouts: 15
  Total Routes: 54

✅ All frontend tests passed!
```

## Interpreting Results

### Success Criteria

✅ **PRODUCTION READY:**
- 100% success rate
- Average response time < 200ms
- No database errors
- No TypeScript errors

⚠️ **NEEDS REVIEW:**
- 95-99% success rate
- Response times 200-500ms
- Minor warnings

❌ **NOT PRODUCTION READY:**
- <95% success rate
- Response times > 500ms
- Database schema errors
- Frontend build failures

### Common Issues and Fixes

#### 1. "Failed to setup test environment"
**Cause:** Backend not running or database not accessible

**Fix:**
```bash
docker-compose up -d postgres backend
# Wait 10 seconds for DB to initialize
sleep 10
```

#### 2. "Database schema mismatches causing 500 errors"
**Cause:** Migration not run or schema out of sync

**Fix:**
```bash
# Drop and recreate all tables
python3 -c "
from backend.database import engine
from backend.db_models import Base
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print('✅ Database recreated')
"
```

#### 3. "TypeError: can't convert undefined to object"
**Cause:** Frontend accessing undefined API response fields

**Fix:** Already fixed in latest commit (d612879)

#### 4. High failure rate on specific endpoint
**Cause:** Missing database table or code bug

**Fix:**
1. Check error messages in test output
2. Look at backend logs: `docker-compose logs backend`
3. Verify table exists: `docker-compose exec postgres psql -U syncboard -c "\dt"`

## Customizing Tests

### Increase Load
Edit `test_production_stress.py`:
```python
NUM_CONCURRENT_USERS = 50  # More users
REQUESTS_PER_USER = 20     # More requests each
```

### Test Specific Endpoints
Modify the `test_all_endpoints_heavy` method to focus on specific routes.

### Add New Tests
Add new methods to `StressTestRunner` class:
```python
async def test_my_feature_concurrent(self, user_id: int):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(100):
            tasks.append(self.make_request(session, 'POST', '/my-endpoint'))
        results = await asyncio.gather(*tasks)
        # ... handle results
```

## Continuous Integration

### GitHub Actions
```yaml
- name: Run Stress Tests
  run: |
    docker-compose up -d
    sleep 10
    python3 test_production_stress.py
```

### Pre-Deployment Check
```bash
# Run before deploying to production
./test_frontend_pages.sh && python3 test_production_stress.py
if [ $? -eq 0 ]; then
  echo "✅ Ready to deploy"
  git push origin main
else
  echo "❌ Fix errors before deploying"
  exit 1
fi
```

## Expected Performance Benchmarks

### Development Environment
- Requests/Second: 30-60
- Average Response: 100-200ms
- Max Response: 500ms

### Production Environment
- Requests/Second: 100-200
- Average Response: 50-100ms
- Max Response: 300ms

## Monitoring in Production

After deployment, monitor these metrics:

1. **Response Times** - Should match or beat test results
2. **Error Rates** - Should be 0% for known endpoints
3. **Database Connections** - Should not max out pool
4. **Memory Usage** - Should remain stable under load

## Support

If tests fail:
1. Check backend logs: `docker-compose logs backend | tail -100`
2. Check database logs: `docker-compose logs postgres | tail -100`
3. Verify migrations: `docker-compose exec backend alembic current`
4. Review recent commits for schema changes
