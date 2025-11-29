#!/usr/bin/env python3
"""
Comprehensive API Test Script for Idea Seeds Feature

Run this inside the Docker container:
    docker-compose exec backend python test_idea_seeds_api.py

Or with authentication:
    docker-compose exec backend python test_idea_seeds_api.py --username admin --password admin
"""

import sys
import argparse
import requests
from typing import Optional

# Configuration
API_BASE = "http://localhost:8000"
TEST_USER = {
    "username": "test_idea_seeds_user",
    "password": "testpassword123",
    "email": "test_seeds@example.com"
}

class IdeaSeedsAPITester:
    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.headers = {}
        self.tests_passed = 0
        self.tests_failed = 0

    def print_header(self, text: str):
        print("\n" + "=" * 70)
        print(text)
        print("=" * 70)

    def print_test(self, name: str, passed: bool, details: str = ""):
        if passed:
            print(f"✅ {name}")
            if details:
                print(f"   {details}")
            self.tests_passed += 1
        else:
            print(f"❌ {name}")
            if details:
                print(f"   {details}")
            self.tests_failed += 1

    def register_user(self) -> bool:
        """Register a test user."""
        try:
            response = requests.post(
                f"{self.base_url}/users",
                json=TEST_USER
            )
            if response.status_code in [200, 201]:
                self.print_test("User Registration", True, f"User created: {TEST_USER['username']}")
                return True
            elif response.status_code == 400 and "already registered" in response.text.lower():
                self.print_test("User Registration", True, "User already exists (OK)")
                return True
            else:
                self.print_test("User Registration", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.print_test("User Registration", False, str(e))
            return False

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Login and get JWT token."""
        username = username or TEST_USER['username']
        password = password or TEST_USER['password']

        try:
            response = requests.post(
                f"{self.base_url}/token",
                data={
                    "username": username,
                    "password": password
                }
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.headers = {"Authorization": f"Bearer {self.token}"}
                self.print_test("User Login", True, f"Token obtained for {username}")
                return True
            else:
                self.print_test("User Login", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.print_test("User Login", False, str(e))
            return False

    def test_quick_ideas(self):
        """Test GET /quick-ideas endpoint."""
        try:
            response = requests.get(
                f"{self.base_url}/quick-ideas",
                headers=self.headers,
                params={"limit": 5}
            )
            if response.status_code == 200:
                data = response.json()
                count = data.get("count", 0)
                self.print_test(
                    "GET /quick-ideas",
                    True,
                    f"Retrieved {count} quick ideas (tier: {data.get('tier', 'N/A')})"
                )
            else:
                self.print_test("GET /quick-ideas", False, f"Status: {response.status_code}")
        except Exception as e:
            self.print_test("GET /quick-ideas", False, str(e))

    def test_idea_seeds_get(self):
        """Test GET /idea-seeds endpoint."""
        try:
            response = requests.get(
                f"{self.base_url}/idea-seeds",
                headers=self.headers,
                params={"limit": 10}
            )
            if response.status_code == 200:
                data = response.json()
                count = data.get("count", 0)
                self.print_test(
                    "GET /idea-seeds",
                    True,
                    f"Retrieved {count} idea seeds"
                )
                return data.get("ideas", [])
            else:
                self.print_test("GET /idea-seeds", False, f"Status: {response.status_code}")
                return []
        except Exception as e:
            self.print_test("GET /idea-seeds", False, str(e))
            return []

    def test_idea_seeds_combined(self):
        """Test GET /idea-seeds/combined endpoint."""
        try:
            response = requests.get(
                f"{self.base_url}/idea-seeds/combined",
                headers=self.headers,
                params={"max_ideas": 3}
            )
            if response.status_code == 200:
                data = response.json()
                count = data.get("count", 0)
                self.print_test(
                    "GET /idea-seeds/combined",
                    True,
                    f"Generated {count} combined ideas"
                )
            else:
                self.print_test("GET /idea-seeds/combined", False, f"Status: {response.status_code}")
        except Exception as e:
            self.print_test("GET /idea-seeds/combined", False, str(e))

    def test_save_idea(self, idea_seed_id: Optional[int] = None):
        """Test POST /ideas/save endpoint."""
        try:
            payload = {}
            if idea_seed_id:
                payload["idea_seed_id"] = idea_seed_id
            else:
                # Save custom idea
                payload = {
                    "title": "Test Custom Idea",
                    "description": "A test idea created by the API tester",
                    "suggestion_data": {
                        "complexity_level": "intermediate",
                        "effort_estimate": "3-5 hours"
                    }
                }

            response = requests.post(
                f"{self.base_url}/ideas/save",
                headers=self.headers,
                json=payload
            )
            if response.status_code == 200:
                data = response.json()
                saved_id = data.get("saved_idea", {}).get("id")
                self.print_test(
                    "POST /ideas/save",
                    True,
                    f"Idea saved successfully (ID: {saved_id})"
                )
                return saved_id
            else:
                self.print_test("POST /ideas/save", False, f"Status: {response.status_code}")
                return None
        except Exception as e:
            self.print_test("POST /ideas/save", False, str(e))
            return None

    def test_get_saved_ideas(self):
        """Test GET /ideas/saved endpoint."""
        try:
            response = requests.get(
                f"{self.base_url}/ideas/saved",
                headers=self.headers,
                params={"limit": 20}
            )
            if response.status_code == 200:
                data = response.json()
                count = data.get("count", 0)
                saved_ideas = data.get("saved_ideas", [])
                self.print_test(
                    "GET /ideas/saved",
                    True,
                    f"Retrieved {count} saved ideas"
                )
                return saved_ideas
            else:
                self.print_test("GET /ideas/saved", False, f"Status: {response.status_code}")
                return []
        except Exception as e:
            self.print_test("GET /ideas/saved", False, str(e))
            return []

    def test_update_saved_idea(self, saved_id: int):
        """Test PUT /ideas/saved/{saved_id} endpoint."""
        try:
            response = requests.put(
                f"{self.base_url}/ideas/saved/{saved_id}",
                headers=self.headers,
                params={
                    "status": "started",
                    "notes": "Testing the update endpoint"
                }
            )
            if response.status_code == 200:
                self.print_test(
                    "PUT /ideas/saved/{id}",
                    True,
                    f"Updated saved idea {saved_id}"
                )
            else:
                self.print_test("PUT /ideas/saved/{id}", False, f"Status: {response.status_code}")
        except Exception as e:
            self.print_test("PUT /ideas/saved/{id}", False, str(e))

    def test_mega_project(self, idea_ids: list):
        """Test POST /ideas/mega-project endpoint."""
        if len(idea_ids) < 2:
            self.print_test(
                "POST /ideas/mega-project",
                False,
                "Need at least 2 saved ideas to test mega-project"
            )
            return

        try:
            response = requests.post(
                f"{self.base_url}/ideas/mega-project",
                headers=self.headers,
                json={
                    "idea_ids": idea_ids[:2],  # Use first 2 ideas
                    "title": "Test Mega Project"
                }
            )
            if response.status_code == 200:
                data = response.json()
                mega_project = data.get("mega_project", {})
                title = mega_project.get("title", "N/A")
                self.print_test(
                    "POST /ideas/mega-project",
                    True,
                    f"Created mega-project: {title}"
                )
            else:
                self.print_test("POST /ideas/mega-project", False, f"Status: {response.status_code}")
        except Exception as e:
            self.print_test("POST /ideas/mega-project", False, str(e))

    def test_backfill(self):
        """Test POST /idea-seeds/backfill endpoint."""
        try:
            response = requests.post(
                f"{self.base_url}/idea-seeds/backfill",
                headers=self.headers
            )
            if response.status_code == 200:
                data = response.json()
                generated = data.get("total_ideas_generated", 0)
                self.print_test(
                    "POST /idea-seeds/backfill",
                    True,
                    f"Backfill completed: {generated} ideas generated"
                )
            else:
                self.print_test("POST /idea-seeds/backfill", False, f"Status: {response.status_code}")
        except Exception as e:
            self.print_test("POST /idea-seeds/backfill", False, str(e))

    def run_all_tests(self, use_existing_user: bool = False, username: str = None, password: str = None):
        """Run all API tests."""
        self.print_header("IDEA SEEDS API - COMPREHENSIVE TEST SUITE")

        # Authentication
        print("\n📋 Step 1: Authentication")
        print("-" * 70)
        if use_existing_user:
            if not self.login(username, password):
                print("\n❌ Authentication failed. Cannot continue.")
                return False
        else:
            self.register_user()
            if not self.login():
                print("\n❌ Authentication failed. Cannot continue.")
                return False

        # Test endpoints
        print("\n📋 Step 2: Testing Idea Seeds Endpoints")
        print("-" * 70)
        self.test_quick_ideas()
        seeds = self.test_idea_seeds_get()
        self.test_idea_seeds_combined()

        print("\n📋 Step 3: Testing Saved Ideas")
        print("-" * 70)
        # Save a custom idea
        saved_id = self.test_save_idea()

        # Get all saved ideas
        saved_ideas = self.test_get_saved_ideas()

        # Update saved idea if we created one
        if saved_id:
            self.test_update_saved_idea(saved_id)

        print("\n📋 Step 4: Testing Advanced Features")
        print("-" * 70)
        # Test mega-project if we have enough saved ideas
        if len(saved_ideas) >= 2:
            idea_ids = [idea["id"] for idea in saved_ideas[:2]]
            self.test_mega_project(idea_ids)
        else:
            print("⚠ Skipping mega-project test (need at least 2 saved ideas)")

        # Test backfill
        self.test_backfill()

        # Summary
        self.print_header("TEST SUMMARY")
        print(f"✅ Passed: {self.tests_passed}")
        print(f"❌ Failed: {self.tests_failed}")
        print()

        if self.tests_failed == 0:
            print("✅ ALL TESTS PASSED! Idea Seeds feature is fully functional.")
            return True
        else:
            print("❌ SOME TESTS FAILED. Please review the errors above.")
            return False


def main():
    parser = argparse.ArgumentParser(description="Test Idea Seeds API")
    parser.add_argument("--username", help="Username for existing user")
    parser.add_argument("--password", help="Password for existing user")
    parser.add_argument("--base-url", default=API_BASE, help="API base URL")
    args = parser.parse_args()

    tester = IdeaSeedsAPITester(base_url=args.base_url)

    use_existing = bool(args.username and args.password)
    success = tester.run_all_tests(
        use_existing_user=use_existing,
        username=args.username,
        password=args.password
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
