#!/usr/bin/env python3
"""
Debug script to check if concepts are being loaded properly from the database.
Run this from the syncboard_backend directory.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'sturdy-broccoli-main', 'refactored', 'syncboard_backend'))

from backend.database import get_db_context
from backend.db_models import DBDocument, DBConcept
from sqlalchemy.orm import joinedload

def main():
    print("="*60)
    print("CONCEPTS DEBUG SCRIPT")
    print("="*60)
    print()

    with get_db_context() as db:
        # Count total documents
        total_docs = db.query(DBDocument).count()
        print(f"📊 Total documents in database: {total_docs}")

        # Count total concepts
        total_concepts = db.query(DBConcept).count()
        print(f"📊 Total concepts in database: {total_concepts}")
        print()

        if total_docs == 0:
            print("❌ No documents found in database!")
            return

        # Load documents with concepts
        print("Loading documents with concepts...")
        docs = db.query(DBDocument).options(joinedload(DBDocument.concepts)).limit(10).all()

        print(f"\n📄 Showing first {len(docs)} documents:\n")

        docs_without_concepts = 0
        for doc in docs:
            concept_count = len(doc.concepts)
            status = "✅" if concept_count > 0 else "❌"

            if concept_count == 0:
                docs_without_concepts += 1

            print(f"{status} Document {doc.doc_id} (DB ID: {doc.id})")
            print(f"   Owner: {doc.owner_username}")
            print(f"   Filename: {doc.filename}")
            print(f"   KB ID: {doc.knowledge_base_id}")
            print(f"   Concepts: {concept_count}")

            if concept_count > 0:
                print(f"   Concept names: {', '.join([c.name for c in doc.concepts[:5]])}")
                if concept_count > 5:
                    print(f"   ... and {concept_count - 5} more")
            print()

        if docs_without_concepts > 0:
            print(f"⚠️  WARNING: {docs_without_concepts} out of {len(docs)} documents have NO concepts!")
            print(f"   This will cause 'not enough knowledge' errors.")
            print()

        # Check unique concepts
        unique_concepts = set()
        for doc in docs:
            for concept in doc.concepts:
                unique_concepts.add(concept.name)

        print(f"📈 Unique concepts in sample: {len(unique_concepts)}")
        if unique_concepts:
            print(f"   Sample concepts: {', '.join(list(unique_concepts)[:10])}")
        print()

        # Summary
        print("="*60)
        print("SUMMARY")
        print("="*60)
        if total_docs > 0 and total_concepts == 0:
            print("❌ PROBLEM: You have documents but NO concepts!")
            print("   This is why you're getting 'not enough knowledge' errors.")
            print()
            print("   POSSIBLE CAUSES:")
            print("   1. Documents were uploaded before concepts feature was working")
            print("   2. Concept extraction is failing silently")
            print("   3. Database migration issue")
            print()
            print("   SOLUTIONS:")
            print("   1. Re-upload your documents")
            print("   2. Check backend logs for concept extraction errors")
            print("   3. Run database migrations")
        elif len(unique_concepts) < 3:
            print(f"⚠️  WARNING: Only {len(unique_concepts)} unique concepts found")
            print(f"   Minimum required: 3")
            print(f"   Upload more diverse content to increase concept coverage")
        else:
            print("✅ Concepts are being loaded properly!")
            print(f"   {total_concepts} concepts across {total_docs} documents")

if __name__ == "__main__":
    main()
