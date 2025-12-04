#!/usr/bin/env python3
"""
Comprehensive diagnostic script to troubleshoot "not enough knowledge" errors.
Run this inside the Docker container or locally with database access.

Usage:
    # Inside Docker container:
    docker-compose exec backend python backend/diagnose_knowledge.py

    # Or locally (from syncboard_backend directory):
    python backend/diagnose_knowledge.py
"""

from collections import Counter
from database import get_db_context
from db_models import DBDocument, DBConcept, DBCluster, DBKnowledgeBase
from sqlalchemy.orm import joinedload

# Thresholds from build_suggester.py
MIN_DOCUMENTS = 1
MIN_CONCEPTS = 2  # Reduced from 3 to match build_suggester.py
MIN_CLUSTERS = 1
MIN_CONTENT_LENGTH = 200

def main():
    print("="*80)
    print("SYNCBOARD KNOWLEDGE BANK DIAGNOSTIC")
    print("="*80)
    print()

    with get_db_context() as db:
        # 1. Check knowledge bases
        kbs = db.query(DBKnowledgeBase).all()
        print(f"📚 Knowledge Bases: {len(kbs)}")
        for kb in kbs:
            print(f"   - {kb.id} (Owner: {kb.owner_username})")
        print()

        if not kbs:
            print("❌ No knowledge bases found! Create one first.")
            return

        # Use first KB for diagnostic
        kb_id = kbs[0].id
        print(f"🔍 Diagnosing Knowledge Base: {kb_id}")
        print()

        # 2. Check documents
        docs = db.query(DBDocument).filter_by(knowledge_base_id=kb_id).all()
        total_docs = len(docs)
        print(f"📄 Documents: {total_docs}")

        if total_docs == 0:
            print("❌ PROBLEM: No documents in knowledge base!")
            print("   Solution: Upload documents via the UI or API")
            return
        elif total_docs < MIN_DOCUMENTS:
            print(f"⚠️  WARNING: Only {total_docs} documents (minimum: {MIN_DOCUMENTS})")
        else:
            print(f"✅ Document count OK (minimum: {MIN_DOCUMENTS})")
        print()

        # 3. Check concepts - THIS IS THE KEY ISSUE
        total_concepts = db.query(DBConcept).join(DBDocument).filter(
            DBDocument.knowledge_base_id == kb_id
        ).count()

        print(f"🏷️  Total Concepts: {total_concepts}")

        if total_concepts == 0:
            print("❌ CRITICAL PROBLEM: NO CONCEPTS FOUND!")
            print()
            print("   This is why you're getting 'not enough knowledge' errors.")
            print()
            print("   POSSIBLE CAUSES:")
            print("   1. Documents were uploaded before concept extraction was working")
            print("   2. Concept extraction is failing during upload")
            print("   3. OpenAI API key is invalid or quota exceeded")
            print()
            print("   SOLUTIONS:")
            print("   1. Check backend logs for concept extraction errors:")
            print("      docker-compose logs backend | grep -i concept")
            print("   2. Verify OpenAI API key is valid in .env file")
            print("   3. Re-upload your documents to trigger concept extraction")
            print()
            return
        elif total_concepts < MIN_CONCEPTS:
            print(f"⚠️  WARNING: Only {total_concepts} concepts (minimum: {MIN_CONCEPTS})")
            print(f"   Upload more diverse content to increase concepts")
        else:
            print(f"✅ Concept count OK (minimum: {MIN_CONCEPTS})")
        print()

        # 4. Check documents with concepts
        docs_with_concepts = 0
        docs_without_concepts = []
        unique_concepts = set()

        for doc in docs:
            concept_count = db.query(DBConcept).filter_by(document_id=doc.id).count()
            if concept_count > 0:
                docs_with_concepts += 1
                concepts = db.query(DBConcept).filter_by(document_id=doc.id).all()
                for c in concepts:
                    unique_concepts.add(c.name)
            else:
                docs_without_concepts.append(doc.doc_id)

        print(f"📊 Document Analysis:")
        print(f"   - With concepts: {docs_with_concepts}/{total_docs}")
        print(f"   - Without concepts: {len(docs_without_concepts)}/{total_docs}")
        print(f"   - Unique concept names: {len(unique_concepts)}")

        if docs_without_concepts:
            print(f"   - Document IDs missing concepts: {docs_without_concepts[:5]}")
            if len(docs_without_concepts) > 5:
                print(f"     ... and {len(docs_without_concepts) - 5} more")
        print()

        if len(unique_concepts) < MIN_CONCEPTS:
            print(f"❌ PROBLEM: Only {len(unique_concepts)} unique concepts (need {MIN_CONCEPTS})")
        else:
            print(f"✅ Unique concepts OK")
            print(f"   Sample concepts: {', '.join(list(unique_concepts)[:10])}")
        print()

        # 5. Check clusters
        clusters = db.query(DBCluster).filter_by(knowledge_base_id=kb_id).all()
        print(f"🗂️  Clusters: {len(clusters)}")

        if len(clusters) == 0:
            print("❌ PROBLEM: No clusters found!")
            print("   Clusters are created automatically when uploading documents")
        elif len(clusters) < MIN_CLUSTERS:
            print(f"⚠️  WARNING: Only {len(clusters)} clusters (minimum: {MIN_CLUSTERS})")
        else:
            print(f"✅ Cluster count OK (minimum: {MIN_CLUSTERS})")
            for cluster in clusters[:3]:
                doc_count = db.query(DBDocument).filter_by(cluster_id=cluster.id).count()
                print(f"   - {cluster.name}: {doc_count} documents")
        print()

        # 6. Check content length
        from backend.db_models import DBVectorDocument
        vector_docs = db.query(DBVectorDocument).join(DBDocument).filter(
            DBDocument.knowledge_base_id == kb_id
        ).all()

        total_content_length = sum(len(vd.content or "") for vd in vector_docs)
        print(f"📝 Total Content Length: {total_content_length:,} characters")

        if total_content_length < MIN_CONTENT_LENGTH:
            print(f"❌ PROBLEM: Content too short (minimum: {MIN_CONTENT_LENGTH} chars)")
        else:
            print(f"✅ Content length OK (minimum: {MIN_CONTENT_LENGTH} chars)")
        print()

        # 7. FINAL VERDICT
        print("="*80)
        print("VALIDATION SUMMARY")
        print("="*80)

        passed = []
        failed = []

        if total_docs >= MIN_DOCUMENTS:
            passed.append(f"✅ Documents: {total_docs} >= {MIN_DOCUMENTS}")
        else:
            failed.append(f"❌ Documents: {total_docs} < {MIN_DOCUMENTS}")

        if len(unique_concepts) >= MIN_CONCEPTS:
            passed.append(f"✅ Unique Concepts: {len(unique_concepts)} >= {MIN_CONCEPTS}")
        else:
            failed.append(f"❌ Unique Concepts: {len(unique_concepts)} < {MIN_CONCEPTS}")

        if len(clusters) >= MIN_CLUSTERS:
            passed.append(f"✅ Clusters: {len(clusters)} >= {MIN_CLUSTERS}")
        else:
            failed.append(f"❌ Clusters: {len(clusters)} < {MIN_CLUSTERS}")

        if total_content_length >= MIN_CONTENT_LENGTH:
            passed.append(f"✅ Content Length: {total_content_length:,} >= {MIN_CONTENT_LENGTH}")
        else:
            failed.append(f"❌ Content Length: {total_content_length:,} < {MIN_CONTENT_LENGTH}")

        print()
        for item in passed:
            print(item)
        for item in failed:
            print(item)
        print()

        if failed:
            print("❌ VALIDATION FAILED")
            print()
            print("This is why you're getting 'Add more content to your knowledge bank' errors.")
            print()
            print("RECOMMENDED ACTIONS:")
            if total_concepts == 0 or len(unique_concepts) < MIN_CONCEPTS:
                print("  1. Check backend logs for concept extraction errors")
                print("  2. Verify OpenAI API key is valid")
                print("  3. Re-upload documents to trigger concept extraction")
            else:
                print("  1. Upload more documents to your knowledge base")
                print("  2. Upload more diverse content (different topics)")
        else:
            print("✅ ALL VALIDATIONS PASSED")
            print()
            print("Your knowledge base should work for build suggestions.")
            print("If you're still getting errors, restart the backend:")
            print("  docker-compose restart backend")
        print()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error running diagnostic: {e}")
        import traceback
        traceback.print_exc()
