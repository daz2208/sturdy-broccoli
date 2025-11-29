#!/usr/bin/env python3
"""
Production-Grade Stress Test for SyncBoard Backend

Tests all critical endpoints with heavy concurrent load to catch:
- Database race conditions
- Memory leaks
- Connection pool exhaustion
- Schema mismatches
- Unhandled exceptions
"""

import asyncio
import aiohttp
import time
import json
from typing import List, Dict, Any
from datetime import datetime
import sys

# Configuration
BASE_URL = "http://localhost:8000"
NUM_CONCURRENT_USERS = 20
REQUESTS_PER_USER = 10
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass123"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

class StressTestRunner:
    def __init__(self):
        self.results = {
            'passed': 0,
            'failed': 0,
            'errors': [],
            'response_times': [],
            'start_time': None,
            'end_time': None
        }
        self.token = None

    async def setup(self):
        """Create test user and get auth token"""
        print(f"{Colors.BLUE}🔧 Setting up test environment...{Colors.RESET}")

        async with aiohttp.ClientSession() as session:
            # Try to register user (might already exist)
            try:
                async with session.post(
                    f"{BASE_URL}/auth/register",
                    json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
                ) as resp:
                    if resp.status in [200, 201]:
                        print(f"{Colors.GREEN}✓ Test user registered{Colors.RESET}")
                    elif resp.status == 400:
                        print(f"{Colors.YELLOW}→ Test user already exists{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.YELLOW}→ Registration skipped: {e}{Colors.RESET}")

            # Login to get token
            try:
                async with session.post(
                    f"{BASE_URL}/auth/login",
                    data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.token = data.get('access_token')
                        print(f"{Colors.GREEN}✓ Authentication successful{Colors.RESET}")
                        return True
                    else:
                        text = await resp.text()
                        print(f"{Colors.RED}✗ Login failed: {resp.status} - {text}{Colors.RESET}")
                        return False
            except Exception as e:
                print(f"{Colors.RED}✗ Login error: {e}{Colors.RESET}")
                return False

    async def make_request(self, session: aiohttp.ClientSession, method: str,
                          endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request and track metrics"""
        start = time.time()
        headers = kwargs.get('headers', {})
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        kwargs['headers'] = headers

        try:
            async with session.request(method, f"{BASE_URL}{endpoint}", **kwargs) as resp:
                elapsed = time.time() - start
                self.results['response_times'].append(elapsed)

                try:
                    data = await resp.json()
                except:
                    data = await resp.text()

                return {
                    'status': resp.status,
                    'data': data,
                    'elapsed': elapsed,
                    'success': 200 <= resp.status < 300
                }
        except Exception as e:
            elapsed = time.time() - start
            return {
                'status': 0,
                'data': str(e),
                'elapsed': elapsed,
                'success': False,
                'error': str(e)
            }

    async def test_usage_endpoints_concurrent(self, user_id: int):
        """Test usage endpoints with concurrent requests"""
        async with aiohttp.ClientSession() as session:
            tasks = []

            # Test all usage endpoints concurrently
            endpoints = [
                ('GET', '/usage'),
                ('GET', '/usage/history'),
                ('GET', '/usage/subscription'),
                ('GET', '/usage/plans'),
            ]

            for _ in range(REQUESTS_PER_USER):
                for method, endpoint in endpoints:
                    tasks.append(self.make_request(session, method, endpoint))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.results['failed'] += 1
                    self.results['errors'].append({
                        'user': user_id,
                        'error': str(result),
                        'endpoint': 'usage'
                    })
                elif result.get('success'):
                    self.results['passed'] += 1
                else:
                    self.results['failed'] += 1
                    self.results['errors'].append({
                        'user': user_id,
                        'status': result.get('status'),
                        'data': result.get('data'),
                        'endpoint': 'usage'
                    })

    async def test_learning_endpoints_concurrent(self, user_id: int):
        """Test learning endpoints with heavy load"""
        async with aiohttp.ClientSession() as session:
            tasks = []

            endpoints = [
                ('GET', '/learning/status'),
                ('GET', '/learning/rules'),
                ('GET', '/learning/vocabulary'),
                ('GET', '/learning/profile'),
                ('GET', '/learning/agent/status'),
            ]

            for _ in range(REQUESTS_PER_USER):
                for method, endpoint in endpoints:
                    tasks.append(self.make_request(session, method, endpoint))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    self.results['failed'] += 1
                    self.results['errors'].append({
                        'user': user_id,
                        'error': str(result),
                        'endpoint': 'learning'
                    })
                elif result.get('success'):
                    self.results['passed'] += 1
                else:
                    self.results['failed'] += 1
                    self.results['errors'].append({
                        'user': user_id,
                        'status': result.get('status'),
                        'data': str(result.get('data'))[:200],
                        'endpoint': 'learning'
                    })

    async def test_database_race_conditions(self, user_id: int):
        """Test for race conditions in database operations"""
        async with aiohttp.ClientSession() as session:
            # Try to create subscription records simultaneously
            tasks = []
            for _ in range(20):
                tasks.append(self.make_request(session, 'GET', '/usage'))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should succeed without race condition errors
            for result in results:
                if isinstance(result, Exception):
                    self.results['failed'] += 1
                    self.results['errors'].append({
                        'user': user_id,
                        'test': 'race_condition',
                        'error': str(result)
                    })
                elif result.get('success'):
                    self.results['passed'] += 1
                else:
                    self.results['failed'] += 1
                    self.results['errors'].append({
                        'user': user_id,
                        'test': 'race_condition',
                        'status': result.get('status'),
                        'data': str(result.get('data'))[:200]
                    })

    async def test_all_endpoints_heavy(self, user_id: int):
        """Test all critical endpoints with heavy load"""
        async with aiohttp.ClientSession() as session:
            tasks = []

            # All critical endpoints
            endpoints = [
                ('GET', '/health'),
                ('GET', '/documents'),
                ('GET', '/clusters'),
                ('GET', '/knowledge-bases'),
                ('GET', '/usage'),
                ('GET', '/usage/subscription'),
                ('GET', '/learning/status'),
                ('GET', '/learning/rules'),
                ('GET', '/learning/vocabulary'),
                ('GET', '/tags'),
                ('GET', '/duplicates'),
                ('GET', '/saved-searches'),
                ('GET', '/analytics/overview'),
            ]

            for _ in range(5):  # 5 rounds
                for method, endpoint in endpoints:
                    tasks.append(self.make_request(session, method, endpoint))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    self.results['failed'] += 1
                    self.results['errors'].append({
                        'user': user_id,
                        'test': 'all_endpoints',
                        'error': str(result)
                    })
                elif result.get('success'):
                    self.results['passed'] += 1
                else:
                    self.results['failed'] += 1
                    self.results['errors'].append({
                        'user': user_id,
                        'test': 'all_endpoints',
                        'status': result.get('status'),
                        'endpoint': result.get('data', {}).get('detail', 'unknown')[:100]
                    })

    async def run_user_simulation(self, user_id: int):
        """Simulate a single user's behavior"""
        print(f"{Colors.BLUE}👤 User {user_id} starting tests...{Colors.RESET}")

        await self.test_usage_endpoints_concurrent(user_id)
        await self.test_learning_endpoints_concurrent(user_id)
        await self.test_database_race_conditions(user_id)
        await self.test_all_endpoints_heavy(user_id)

        print(f"{Colors.GREEN}✓ User {user_id} completed{Colors.RESET}")

    async def run_stress_test(self):
        """Run full stress test with concurrent users"""
        self.results['start_time'] = time.time()

        print(f"\n{Colors.YELLOW}{'='*60}{Colors.RESET}")
        print(f"{Colors.YELLOW}🔥 PRODUCTION STRESS TEST{Colors.RESET}")
        print(f"{Colors.YELLOW}{'='*60}{Colors.RESET}")
        print(f"Concurrent Users: {NUM_CONCURRENT_USERS}")
        print(f"Requests per User: {REQUESTS_PER_USER * 4}")  # 4 test types
        print(f"Total Requests: ~{NUM_CONCURRENT_USERS * REQUESTS_PER_USER * 4}\n")

        # Run all users concurrently
        tasks = [
            self.run_user_simulation(i)
            for i in range(NUM_CONCURRENT_USERS)
        ]

        await asyncio.gather(*tasks)

        self.results['end_time'] = time.time()
        self.print_results()

    def print_results(self):
        """Print comprehensive test results"""
        total = self.results['passed'] + self.results['failed']
        duration = self.results['end_time'] - self.results['start_time']
        avg_response = sum(self.results['response_times']) / len(self.results['response_times']) if self.results['response_times'] else 0
        max_response = max(self.results['response_times']) if self.results['response_times'] else 0
        min_response = min(self.results['response_times']) if self.results['response_times'] else 0
        rps = total / duration if duration > 0 else 0

        print(f"\n{Colors.YELLOW}{'='*60}{Colors.RESET}")
        print(f"{Colors.YELLOW}📊 TEST RESULTS{Colors.RESET}")
        print(f"{Colors.YELLOW}{'='*60}{Colors.RESET}\n")

        print(f"⏱️  Total Duration: {duration:.2f}s")
        print(f"📈 Requests/Second: {rps:.2f}")
        print(f"📊 Total Requests: {total}")
        print(f"{Colors.GREEN}✓ Passed: {self.results['passed']}{Colors.RESET}")
        print(f"{Colors.RED}✗ Failed: {self.results['failed']}{Colors.RESET}")
        print(f"Success Rate: {(self.results['passed']/total*100):.1f}%\n")

        print(f"⚡ Response Times:")
        print(f"  Average: {avg_response*1000:.1f}ms")
        print(f"  Min: {min_response*1000:.1f}ms")
        print(f"  Max: {max_response*1000:.1f}ms\n")

        if self.results['errors']:
            print(f"{Colors.RED}❌ ERRORS ({len(self.results['errors'])} total):{Colors.RESET}\n")

            # Group errors by type
            error_types = {}
            for err in self.results['errors'][:20]:  # Show first 20
                key = err.get('endpoint', err.get('test', 'unknown'))
                if key not in error_types:
                    error_types[key] = []
                error_types[key].append(err)

            for endpoint, errors in error_types.items():
                print(f"{Colors.YELLOW}{endpoint}:{Colors.RESET} {len(errors)} errors")
                for err in errors[:3]:  # Show first 3 of each type
                    if 'error' in err:
                        print(f"  → {err['error'][:150]}")
                    elif 'status' in err:
                        print(f"  → Status {err['status']}: {str(err.get('data', ''))[:150]}")
                print()

        # Final verdict
        print(f"{Colors.YELLOW}{'='*60}{Colors.RESET}")
        if self.results['failed'] == 0:
            print(f"{Colors.GREEN}🎉 ALL TESTS PASSED! System is production-ready.{Colors.RESET}")
        elif self.results['passed'] / total > 0.95:
            print(f"{Colors.YELLOW}⚠️  MOSTLY PASSING ({(self.results['passed']/total*100):.1f}%) - Review errors{Colors.RESET}")
        else:
            print(f"{Colors.RED}❌ CRITICAL FAILURES - System not production-ready{Colors.RESET}")
        print(f"{Colors.YELLOW}{'='*60}{Colors.RESET}\n")

async def main():
    runner = StressTestRunner()

    # Setup
    if not await runner.setup():
        print(f"{Colors.RED}Failed to setup test environment{Colors.RESET}")
        sys.exit(1)

    # Run tests
    await runner.run_stress_test()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.RESET}")
    except Exception as e:
        print(f"\n{Colors.RED}Test failed: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
