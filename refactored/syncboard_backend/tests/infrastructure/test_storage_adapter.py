"""
Tests for database storage adapter.

Tests the adapter pattern that provides file-storage-compatible interface
with database backend.
"""

import pytest
from unittest.mock import MagicMock, patch

# Import the FastAPI app
import sys
from pathlib import Path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from backend.db_storage_adapter import load_storage_from_db, save_storage_to_db
from backend.vector_store import VectorStore
from backend.models import DocumentMetadata, Cluster, Concept
from backend.db_models import DBUser, DBCluster, DBDocument, DBConcept, DBVectorDocument, Base
from backend.database import get_db_context, init_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_db():
    """Create an in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    vs = MagicMock(spec=VectorStore)
    vs.add_document = MagicMock(side_effect=lambda content, doc_id=None: doc_id if doc_id is not None else len(vs.add_document.call_args_list) - 1)
    return vs


# =============================================================================
# LOAD FROM DATABASE TESTS
# =============================================================================

@patch('backend.db_storage_adapter.get_db_context')
def test_load_storage_from_db_empty(mock_context, mock_vector_store, test_db):
    """Test loading from empty database."""
    mock_context.return_value.__enter__ = MagicMock(return_value=test_db)
    mock_context.return_value.__exit__ = MagicMock(return_value=False)

    documents, metadata, clusters, users = load_storage_from_db(mock_vector_store)

    assert documents == {}
    assert metadata == {}
    assert clusters == {}
    assert users == {}


@patch('backend.db_storage_adapter.get_db_context')
def test_load_storage_from_db_with_data(mock_context, mock_vector_store, test_db):
    """Test loading documents, clusters, and users from database."""
    # Add test data to database
    user = DBUser(username="testuser", hashed_password="hashed123")
    test_db.add(user)

    cluster = DBCluster(id=0, name="Test Cluster", primary_concepts=["test"], skill_level="beginner")
    test_db.add(cluster)

    vdoc = DBVectorDocument(doc_id=0, content="Test document content")
    test_db.add(vdoc)

    doc = DBDocument(
        doc_id=0,
        owner_username="testuser",
        cluster_id=0,
        source_type="text",
        content_length=20,
        skill_level="beginner"
    )
    test_db.add(doc)
    test_db.flush()  # Flush to get the auto-generated ID

    concept = DBConcept(
        document_id=doc.id,
        name="TestConcept",
        category="test",
        confidence=0.9
    )
    test_db.add(concept)

    test_db.commit()

    mock_context.return_value.__enter__ = MagicMock(return_value=test_db)
    mock_context.return_value.__exit__ = MagicMock(return_value=False)

    documents, metadata, clusters, users = load_storage_from_db(mock_vector_store)

    assert len(documents) == 1
    assert 0 in documents
    assert documents[0] == "Test document content"

    assert len(metadata) == 1
    assert 0 in metadata
    assert metadata[0].owner == "testuser"
    assert metadata[0].cluster_id == 0

    assert len(clusters) == 1
    assert 0 in clusters
    assert clusters[0].name == "Test Cluster"

    assert len(users) == 1
    assert "testuser" in users
    assert users["testuser"] == "hashed123"


@patch('backend.db_storage_adapter.get_db_context')
def test_load_storage_handles_exception(mock_context, mock_vector_store):
    """Test load_storage gracefully handles database errors."""
    mock_context.side_effect = Exception("Database connection error")

    # Should return empty dicts instead of raising
    documents, metadata, clusters, users = load_storage_from_db(mock_vector_store)

    assert documents == {}
    assert metadata == {}
    assert clusters == {}
    assert users == {}


# =============================================================================
# SAVE TO DATABASE TESTS
# =============================================================================

@patch('backend.db_storage_adapter.get_db_context')
def test_save_storage_to_db_empty(mock_context, test_db):
    """Test saving empty storage to database."""
    mock_context.return_value.__enter__ = MagicMock(return_value=test_db)
    mock_context.return_value.__exit__ = MagicMock(return_value=False)

    save_storage_to_db({}, {}, {}, {})

    # Should complete without error
    assert True


@patch('backend.db_storage_adapter.get_db_context')
def test_save_storage_to_db_with_data(mock_context, test_db):
    """Test saving documents, clusters, and users to database."""
    mock_context.return_value.__enter__ = MagicMock(return_value=test_db)
    mock_context.return_value.__exit__ = MagicMock(return_value=False)

    # Prepare data
    documents = {0: "Test document content"}

    metadata = {
        0: DocumentMetadata(
            doc_id=0,
            owner="testuser",
            source_type="text",
            source_url=None,
            filename=None,
            image_path=None,
            concepts=[Concept(name="Test", category="test", confidence=0.9)],
            skill_level="beginner",
            cluster_id=0,
            ingested_at="2024-01-01T00:00:00",
            content_length=20
        )
    }

    clusters = {
        0: Cluster(
            id=0,
            name="Test Cluster",
            doc_ids=[0],
            primary_concepts=["test"],
            skill_level="beginner",
            doc_count=1
        )
    }

    users = {"testuser": "hashed123"}

    save_storage_to_db(documents, metadata, clusters, users)

    # Verify data was saved
    assert test_db.query(DBUser).filter_by(username="testuser").first() is not None
    assert test_db.query(DBCluster).filter_by(id=0).first() is not None
    assert test_db.query(DBVectorDocument).filter_by(doc_id=0).first() is not None
    assert test_db.query(DBDocument).filter_by(doc_id=0).first() is not None


@patch('backend.db_storage_adapter.get_db_context')
def test_save_storage_updates_existing(mock_context, test_db):
    """Test save_storage updates existing records instead of creating duplicates."""
    mock_context.return_value.__enter__ = MagicMock(return_value=test_db)
    mock_context.return_value.__exit__ = MagicMock(return_value=False)

    # Add initial data
    user = DBUser(username="testuser", hashed_password="old_hash")
    test_db.add(user)
    test_db.commit()

    # Update with new hash
    users = {"testuser": "new_hash"}
    save_storage_to_db({}, {}, {}, users)

    # Should update, not create duplicate
    all_users = test_db.query(DBUser).filter_by(username="testuser").all()
    assert len(all_users) == 1
    assert all_users[0].hashed_password == "new_hash"


@patch('backend.db_storage_adapter.get_db_context')
def test_save_storage_handles_errors(mock_context):
    """Test save_storage raises exception on database errors."""
    mock_db = MagicMock()
    mock_db.commit.side_effect = Exception("Database error")
    mock_context.return_value.__enter__ = MagicMock(return_value=mock_db)
    mock_context.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(Exception):
        save_storage_to_db({}, {}, {}, {"user": "hash"})


# =============================================================================
# VECTOR STORE INTEGRATION TESTS
# =============================================================================

@patch('backend.db_storage_adapter.get_db_context')
def test_load_rebuilds_vector_store(mock_context, test_db):
    """Test loading from database rebuilds vector store properly."""
    # Add vector documents
    vdoc1 = DBVectorDocument(doc_id=0, content="First document")
    vdoc2 = DBVectorDocument(doc_id=1, content="Second document")
    test_db.add(vdoc1)
    test_db.add(vdoc2)
    test_db.commit()

    mock_context.return_value.__enter__ = MagicMock(return_value=test_db)
    mock_context.return_value.__exit__ = MagicMock(return_value=False)

    vector_store = MagicMock(spec=VectorStore)
    call_count = [0]

    def mock_add(content, doc_id=None):
        if doc_id is not None:
            return doc_id
        result = call_count[0]
        call_count[0] += 1
        return result

    vector_store.add_document = mock_add

    documents, _, _, _ = load_storage_from_db(vector_store)

    assert len(documents) == 2
    assert 0 in documents
    assert 1 in documents


# =============================================================================
# DATA CONSISTENCY TESTS
# =============================================================================

@patch('backend.db_storage_adapter.get_db_context')
def test_concepts_are_loaded_correctly(mock_context, test_db):
    """Test that concepts are properly loaded from database."""
    vdoc = DBVectorDocument(doc_id=0, content="Test")
    test_db.add(vdoc)

    doc = DBDocument(
        doc_id=0,
        owner_username="test",
        cluster_id=0,
        source_type="text",
        content_length=4,
        skill_level="beginner"
    )
    test_db.add(doc)
    test_db.flush()

    concept1 = DBConcept(document_id=doc.id, name="Concept1", category="cat1", confidence=0.9)
    concept2 = DBConcept(document_id=doc.id, name="Concept2", category="cat2", confidence=0.8)
    test_db.add(concept1)
    test_db.add(concept2)
    test_db.commit()

    mock_context.return_value.__enter__ = MagicMock(return_value=test_db)
    mock_context.return_value.__exit__ = MagicMock(return_value=False)

    vs = MagicMock(spec=VectorStore)
    vs.add_document = MagicMock(return_value=0)

    _, metadata, _, _ = load_storage_from_db(vs)

    assert len(metadata[0].concepts) == 2
    concept_names = [c.name for c in metadata[0].concepts]
    assert "Concept1" in concept_names
    assert "Concept2" in concept_names
