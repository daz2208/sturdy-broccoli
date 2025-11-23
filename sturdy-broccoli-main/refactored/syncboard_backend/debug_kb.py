"""
Quick diagnostic script to check what's in your knowledge bank.
"""
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from database import SessionLocal
from db_models import DBDocument, DBKnowledgeBase
from sqlalchemy import func

def check_knowledge_bank():
    """Check what documents are in the database."""
    db = SessionLocal()

    try:
        # Get all knowledge bases
        print("\n=== KNOWLEDGE BASES ===")
        kbs = db.query(DBKnowledgeBase).all()
        for kb in kbs:
            print(f"  KB: {kb.name} (ID: {kb.id[:8]}...)")
            print(f"     Owner: {kb.owner_username}")
            print(f"     Documents: {kb.document_count}")
            print()

        # Get all documents
        print("=== DOCUMENTS IN DATABASE ===")
        docs = db.query(DBDocument).order_by(DBDocument.created_at.desc()).limit(50).all()

        if not docs:
            print("  ❌ NO DOCUMENTS FOUND IN DATABASE!")
            print("     Your ZIP upload may have failed.")
            return

        print(f"  Found {len(docs)} recent documents:\n")

        for doc in docs:
            print(f"  Doc ID: {doc.doc_id}")
            print(f"    File: {doc.filename or 'N/A'}")
            print(f"    Owner: {doc.owner_username}")
            print(f"    Source: {doc.source_type}")
            print(f"    Size: {len(doc.content_preview or '')} chars")
            print(f"    Cluster: {doc.cluster_name or 'None'}")
            print(f"    Created: {doc.created_at}")
            print()

        # Check for n8n files specifically
        print("\n=== SEARCHING FOR N8N FILES ===")
        n8n_docs = db.query(DBDocument).filter(
            func.lower(DBDocument.filename).like('%n8n%')
        ).all()

        if n8n_docs:
            print(f"  ✅ Found {len(n8n_docs)} n8n files!")
            for doc in n8n_docs:
                print(f"     - {doc.filename} (doc_id: {doc.doc_id})")
        else:
            print("  ❌ No n8n files found in database!")

        # Check for JSON files
        print("\n=== SEARCHING FOR JSON FILES ===")
        json_docs = db.query(DBDocument).filter(
            func.lower(DBDocument.filename).like('%.json%')
        ).all()

        if json_docs:
            print(f"  ✅ Found {len(json_docs)} JSON files!")
            for doc in json_docs[:10]:  # Show first 10
                print(f"     - {doc.filename} (doc_id: {doc.doc_id})")
            if len(json_docs) > 10:
                print(f"     ... and {len(json_docs) - 10} more")
        else:
            print("  ❌ No JSON files found in database!")

        # Check document chunks (for RAG)
        print("\n=== DOCUMENT CHUNKS (for RAG) ===")
        from db_models import DBDocumentChunk
        chunk_count = db.query(func.count(DBDocumentChunk.id)).scalar()
        chunks_with_embeddings = db.query(func.count(DBDocumentChunk.id)).filter(
            DBDocumentChunk.embedding.isnot(None)
        ).scalar()

        print(f"  Total chunks: {chunk_count}")
        print(f"  Chunks with embeddings: {chunks_with_embeddings}")

        if chunk_count == 0:
            print("  ⚠️  No document chunks! RAG won't work well.")
            print("     Documents need to be chunked for AI features.")

    finally:
        db.close()

if __name__ == "__main__":
    check_knowledge_bank()
