"""
Generate summaries for all documents in the knowledge base.

Run this script to backfill summaries for existing documents:
    python generate_summaries.py <password>
"""

import requests
import time
import sys

# Configuration
API_BASE = "http://localhost:8000"
USERNAME = "daz2208"  # Change this to your username

if len(sys.argv) < 2:
    print("Usage: python generate_summaries.py <password>")
    sys.exit(1)

PASSWORD = sys.argv[1]

def main():
    # 1. Login to get token
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

    # 2. Get all documents
    print("Fetching documents...")
    docs_response = requests.get(f"{API_BASE}/documents", headers=headers)

    if docs_response.status_code != 200:
        print(f"[ERROR] Failed to fetch documents: {docs_response.text}")
        sys.exit(1)

    data = docs_response.json()
    documents = data.get("documents", [])
    print(f"Found {len(documents)} documents\n")

    if not documents:
        print("No documents to process")
        return

    # 3. Generate summaries for each document
    succeeded = 0
    failed = 0

    for i, doc in enumerate(documents, 1):
        doc_id = doc["id"]
        title = doc.get("title", f"Document {doc_id}")

        print(f"[{i}/{len(documents)}] Processing: {title[:50]}...")

        try:
            response = requests.post(
                f"{API_BASE}/documents/{doc_id}/summarize",
                headers=headers,
                timeout=120  # 2 minute timeout per document
            )

            if response.status_code == 200:
                result = response.json()
                summaries_created = result.get("summaries_created", 0)
                print(f"  [OK] Created {summaries_created} summaries")
                succeeded += 1
            else:
                print(f"  [ERROR] Failed: {response.status_code} - {response.text[:100]}")
                failed += 1

        except Exception as e:
            print(f"  [ERROR] Error: {str(e)}")
            failed += 1

        # Small delay to avoid overwhelming the API
        time.sleep(0.5)

    # 4. Summary
    print(f"\n{'='*60}")
    print(f"Summary Generation Complete")
    print(f"{'='*60}")
    print(f"[OK] Succeeded: {succeeded}")
    print(f"[ERROR] Failed: {failed}")
    print(f"[INFO] Total: {len(documents)}")
    print(f"\nYou can now use Summary Search in the UI!")

if __name__ == "__main__":
    main()
