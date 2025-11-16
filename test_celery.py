#!/usr/bin/env python3
"""
Simple script to test Celery integration end-to-end.
"""
import requests
import time
import base64
import json
import sys

API_BASE = "http://localhost:8000"

def create_test_file():
    """Create a simple test file content."""
    content = """# Test Document for Celery Integration

This is a test document to verify that the Celery background task processing is working correctly.

## Key Concepts
- Asynchronous processing
- Background jobs
- Task queues
- Redis integration
- Real-time progress tracking

## Expected Behavior
When this file is uploaded:
1. It should be queued immediately (<1 second response)
2. A job_id should be returned
3. The job status can be polled
4. Progress updates should be visible
5. The task should complete successfully
6. The document should be processed and added to a cluster
"""
    return base64.b64encode(content.encode()).decode()

def register_user(username, password):
    """Register a new user."""
    try:
        response = requests.post(
            f"{API_BASE}/users",
            json={"username": username, "password": password}
        )
        if response.status_code == 200:
            print(f"✅ User '{username}' registered successfully")
            return True
        elif response.status_code == 400 and "already exists" in response.text:
            print(f"ℹ️  User '{username}' already exists")
            return True
        else:
            print(f"❌ Registration failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False

def login(username, password):
    """Login and get JWT token."""
    try:
        response = requests.post(
            f"{API_BASE}/token",
            json={"username": username, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"✅ Logged in successfully")
            print(f"   Token: {token[:50]}...")
            return token
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def upload_file(token, filename, content_base64):
    """Upload a file and get job ID."""
    try:
        response = requests.post(
            f"{API_BASE}/upload_file",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "filename": filename,
                "content": content_base64
            }
        )
        if response.status_code == 200:
            data = response.json()
            job_id = data.get("job_id")
            print(f"✅ File queued successfully")
            print(f"   Job ID: {job_id}")
            print(f"   Filename: {data.get('filename')}")
            return job_id
        else:
            print(f"❌ Upload failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return None

def poll_job_status(token, job_id, max_attempts=60):
    """Poll job status until completion or timeout."""
    print(f"\n📊 Polling job status...")
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        try:
            response = requests.get(
                f"{API_BASE}/jobs/{job_id}/status",
                headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                data = response.json()
                state = data.get("state")
                meta = data.get("meta", {})
                result = data.get("result")

                message = meta.get("message", "Processing...")
                percent = meta.get("percent", 0)

                # Print progress
                progress_bar = "█" * int(percent / 5) + "░" * (20 - int(percent / 5))
                print(f"   [{progress_bar}] {percent}% - {message}", end="\r")

                if state == "SUCCESS":
                    print(f"\n✅ Job completed successfully!")
                    print(f"   Doc ID: {result.get('doc_id')}")
                    print(f"   Cluster ID: {result.get('cluster_id')}")
                    print(f"   Concepts: {len(result.get('concepts', []))} extracted")
                    return True
                elif state == "FAILURE":
                    error = meta.get("error", "Unknown error")
                    print(f"\n❌ Job failed: {error}")
                    return False
                elif state in ["PENDING", "PROCESSING", "RETRY"]:
                    # Continue polling
                    time.sleep(1)
                else:
                    print(f"\n⚠️  Unknown state: {state}")
                    time.sleep(1)
            else:
                print(f"\n❌ Status check failed: {response.status_code}")
                time.sleep(1)

        except Exception as e:
            print(f"\n❌ Polling error: {e}")
            time.sleep(1)

    print(f"\n⏱️  Timeout after {max_attempts} seconds")
    return False

def main():
    """Run end-to-end test."""
    print("=" * 60)
    print("🧪 Celery Integration End-to-End Test")
    print("=" * 60)

    # Test parameters
    username = "celery_test_user"
    password = "celery_test_pass_123"
    filename = "test_celery_integration.md"

    print(f"\n📝 Test Configuration:")
    print(f"   Username: {username}")
    print(f"   Filename: {filename}")
    print(f"   API Base: {API_BASE}")

    # Step 1: Register user
    print(f"\n1️⃣  Registering test user...")
    if not register_user(username, password):
        sys.exit(1)

    # Step 2: Login
    print(f"\n2️⃣  Logging in...")
    token = login(username, password)
    if not token:
        sys.exit(1)

    # Step 3: Create test file
    print(f"\n3️⃣  Creating test file content...")
    content_base64 = create_test_file()
    print(f"   File size: {len(base64.b64decode(content_base64))} bytes")

    # Step 4: Upload file
    print(f"\n4️⃣  Uploading file to Celery queue...")
    job_id = upload_file(token, filename, content_base64)
    if not job_id:
        sys.exit(1)

    # Step 5: Poll job status
    print(f"\n5️⃣  Monitoring job progress...")
    success = poll_job_status(token, job_id)

    # Results
    print(f"\n" + "=" * 60)
    if success:
        print("🎉 TEST PASSED - Celery integration working!")
        print("=" * 60)
        print("\n✅ All systems operational:")
        print("   • Redis: Running")
        print("   • FastAPI Backend: Running")
        print("   • Celery Worker: Processing tasks")
        print("   • Job Polling: Real-time progress")
        print("   • Task Completion: Successful")
        sys.exit(0)
    else:
        print("❌ TEST FAILED - Check logs for details")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
