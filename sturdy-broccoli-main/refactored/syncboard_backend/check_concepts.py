#!/usr/bin/env python3
"""
Check where concepts are actually stored - concepts table vs document_summaries
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backend.database import get_db_context
from backend.db_models import DBDocument, DBConcept, DBDocumentSummary

def main():
    print("="*80)
    print("CHECKING CONCEPTS STORAGE")
    print("="*80)
    print()

    with get_db_context() as db:
        # Check concepts table
        total_concepts = db.query(DBConcept).count()
        print(f"📊 Concepts in 'concepts' table: {total_concepts}")

        if total_concepts > 0:
            sample = db.query(DBConcept).limit(5).all()
            for c in sample:
                print(f"   - {c.name} ({c.category}, confidence: {c.confidence:.2f})")
        print()

        # Check document_summaries key_concepts
        summaries_with_concepts = db.query(DBDocumentSummary).filter(
            DBDocumentSummary.key_concepts.isnot(None)
        ).count()
        print(f"📊 Document summaries with key_concepts: {summaries_with_concepts}")

        if summaries_with_concepts > 0:
            sample = db.query(DBDocumentSummary).filter(
                DBDocumentSummary.key_concepts.isnot(None)
            ).limit(3).all()
            for s in sample:
                print(f"   Doc {s.document_id}: {s.key_concepts}")
        print()

        # Check documents and their concepts via relationship
        docs = db.query(DBDocument).limit(5).all()
        print(f"📄 Checking first {len(docs)} documents:")
        for doc in docs:
            concept_count = len(doc.concepts)  # This uses the relationship
            print(f"   Doc {doc.doc_id} ({doc.filename}): {concept_count} concepts via relationship")
            if concept_count > 0:
                print(f"      Concepts: {[c.name for c in doc.concepts[:3]]}")
        print()

        # DIAGNOSIS
        print("="*80)
        print("DIAGNOSIS")
        print("="*80)
        if total_concepts == 0:
            print("❌ PROBLEM: No concepts in 'concepts' table!")
            print("   The code expects concepts in the 'concepts' table,")
            print("   but they might only be in 'document_summaries.key_concepts'.")
            print()
            if summaries_with_concepts > 0:
                print("   ✅ BUT: document_summaries HAS key_concepts")
                print("   This means concept extraction is working,")
                print("   but they're not being saved to the 'concepts' table.")
                print()
                print("   SOLUTION: Check the document upload code to ensure")
                print("   concepts are saved to BOTH places, or update the")
                print("   metadata loading code to read from document_summaries.")
        else:
            print("✅ Concepts exist in 'concepts' table")
            print(f"   {total_concepts} concepts found")

if __name__ == "__main__":
    main()
