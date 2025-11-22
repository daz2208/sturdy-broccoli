"""
Backfill chunks for all documents in the knowledge base.

Run this before generating summaries:
    python backfill_chunks.py <password>
"""

import requests
import time
import sys

# Configuration
API_BASE = "http://localhost:8000"
USERNAME = "daz2208"

if len(sys.argv) < 2:
    print("Usage: python backfill_chunks.py <password>")
    sys.exit(1)

PASSWORD = sys.argv[1]

def main():
    # 1. Login
    print(f"Logging in as {USERNAME}...")
    login_response = requests.post(
        f"{API_BASE}/token",
        json={"username": USERNAME, "password": PASSWORD}
    )

    if login_response.status_code != 200:
        print(f"[ERROR] Login failed: {login_response.text}")
        sys.exit(1)

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[OK] Login successful\n")

    # 2. Check chunk status
    print("Checking chunk status...")
    status_response = requests.get(f"{API_BASE}/admin/chunk-status", headers=headers)

    if status_response.status_code == 200:
        status = status_response.json()
        print(f"Total documents: {status['total_documents']}")
        print(f"Chunked: {status['chunked_documents']}")
        print(f"Pending: {status['pending_documents']}")
        print(f"Total chunks: {status['total_chunks']}\n")

    # 3. Backfill chunks
    print("Starting chunk backfill...")
    print("This may take a while depending on document size...\n")

    backfill_response = requests.post(
        f"{API_BASE}/admin/backfill-chunks",
        json={"max_documents": 100, "generate_embeddings": True},
        headers=headers,
        timeout=600  # 10 minute timeout
    )

    if backfill_response.status_code != 200:
        print(f"[ERROR] Backfill failed: {backfill_response.text}")
        sys.exit(1)

    result = backfill_response.json()
    print(f"[OK] Processed: {result['processed']}")
    print(f"[OK] Succeeded: {result['succeeded']}")
    print(f"[ERROR] Failed: {result['failed']}")
    print(f"[INFO] Skipped: {result['skipped']}\n")

    if result['results']:
        print("Details:")
        for r in result['results']:
            print(f"  - {r.get('message', r)}")

    print(f"\n{'='*60}")
    print("Chunking complete! Now run:")
    print("  python generate_summaries.py password1234")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
