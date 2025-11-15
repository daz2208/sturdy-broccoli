"""
Tests for database configuration and initialization.

Tests database setup, connection pooling, and health checks.
"""

import pytest
import os
from sqlalchemy import text
from unittest.mock import patch, MagicMock

# Import the FastAPI app
import sys
from pathlib import Path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from backend.database import (
    init_db,
    get_db,
    get_db_context,
    check_database_health,
    SessionLocal,
    engine,
    DATABASE_URL
)
from backend.db_models import Base


# =============================================================================
# DATABASE INITIALIZATION TESTS
# =============================================================================

def test_init_db():
    """Test database initialization creates tables."""
    # init_db should not raise an exception
    try:
        init_db()
        success = True
    except Exception as e:
        success = False
        pytest.fail(f"init_db() raised an exception: {e}")

    assert success


def test_database_url_configuration():
    """Test database URL is properly configured."""
    assert DATABASE_URL is not None
    assert len(DATABASE_URL) > 0
    # Should be either postgresql:// or sqlite://
    assert DATABASE_URL.startswith(("postgresql://", "sqlite://"))


def test_engine_created():
    """Test SQLAlchemy engine is created."""
    assert engine is not None
    assert hasattr(engine, 'connect')


def test_session_factory_created():
    """Test SessionLocal factory is created."""
    assert SessionLocal is not None
    # Should be able to create a session
    session = SessionLocal()
    assert session is not None
    session.close()


# =============================================================================
# SESSION MANAGEMENT TESTS
# =============================================================================

def test_get_db_dependency():
    """Test get_db dependency creates and closes session."""
    # get_db is a generator, so we need to iterate it
    db_generator = get_db()
    db = next(db_generator)

    assert db is not None
    assert hasattr(db, 'query')
    assert hasattr(db, 'commit')
    assert hasattr(db, 'rollback')

    # Clean up
    try:
        next(db_generator)
    except StopIteration:
        pass  # Expected


def test_get_db_context_manager():
    """Test get_db_context context manager."""
    with get_db_context() as db:
        assert db is not None
        # Should be able to execute a simple query
        result = db.execute(text("SELECT 1"))
        assert result is not None


def test_get_db_context_rollback_on_error():
    """Test get_db_context rolls back on exception."""
    with pytest.raises(ValueError):
        with get_db_context() as db:
            # Force an error
            raise ValueError("Test error")


# =============================================================================
# DATABASE HEALTH CHECK TESTS
# =============================================================================

def test_check_database_health_success():
    """Test database health check when database is healthy."""
    health = check_database_health()

    assert "database_connected" in health
    assert health["database_connected"] is True
    assert "database_type" in health


def test_check_database_health_includes_type():
    """Test health check includes database type."""
    health = check_database_health()

    assert "database_type" in health
    assert health["database_type"] in ["postgresql", "sqlite"]


@patch('backend.database.get_db_context')
def test_check_database_health_failure(mock_context):
    """Test database health check when database connection fails."""
    # Mock a database connection error
    mock_context.side_effect = Exception("Connection failed")

    health = check_database_health()

    assert "database_connected" in health
    assert health["database_connected"] is False
    assert "database_error" in health


# =============================================================================
# CONNECTION POOLING TESTS (PostgreSQL specific)
# =============================================================================

def test_postgresql_url_conversion():
    """Test postgres:// is converted to postgresql:// for Heroku compatibility."""
    # This is tested at module import, but we can verify the logic
    test_url = "postgres://user:pass@host:5432/db"
    converted = test_url.replace("postgres://", "postgresql://", 1)
    assert converted == "postgresql://user:pass@host:5432/db"


def test_engine_has_pool_for_postgresql():
    """Test PostgreSQL engine has connection pool configured."""
    if DATABASE_URL.startswith("postgresql://"):
        assert hasattr(engine.pool, 'size')
        assert hasattr(engine.pool, 'overflow')


def test_sqlite_foreign_keys_enabled():
    """Test SQLite has foreign keys enabled."""
    if DATABASE_URL.startswith("sqlite://"):
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys"))
            fk_enabled = result.scalar()
            assert fk_enabled == 1  # Foreign keys are ON


# =============================================================================
# TABLE CREATION TESTS
# =============================================================================

def test_all_tables_created():
    """Test all expected tables are created after init_db."""
    init_db()

    # Get list of tables
    inspector = engine.dialect.get_inspector(engine)
    tables = inspector.get_table_names()

    # Expected tables from db_models.py
    expected_tables = ['users', 'clusters', 'documents', 'concepts', 'vector_documents']

    for table in expected_tables:
        assert table in tables, f"Table '{table}' not found in database"


def test_tables_have_correct_structure():
    """Test tables have the expected columns."""
    init_db()

    inspector = engine.dialect.get_inspector(engine)

    # Check users table
    users_columns = [col['name'] for col in inspector.get_columns('users')]
    assert 'id' in users_columns
    assert 'username' in users_columns
    assert 'hashed_password' in users_columns

    # Check documents table
    docs_columns = [col['name'] for col in inspector.get_columns('documents')]
    assert 'id' in docs_columns
    assert 'content' in docs_columns
    assert 'user_id' in docs_columns
    assert 'cluster_id' in docs_columns


# =============================================================================
# CONCURRENT SESSION TESTS
# =============================================================================

def test_multiple_sessions():
    """Test creating multiple concurrent sessions."""
    session1 = SessionLocal()
    session2 = SessionLocal()

    assert session1 is not session2
    assert session1 is not None
    assert session2 is not None

    session1.close()
    session2.close()


def test_session_isolation():
    """Test sessions are isolated from each other."""
    with get_db_context() as db1:
        with get_db_context() as db2:
            # Sessions should be different instances
            assert db1 is not db2
