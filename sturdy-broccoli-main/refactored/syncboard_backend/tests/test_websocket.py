"""
Tests for WebSocket real-time features.

Tests the WebSocket manager and endpoint functionality.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


# =============================================================================
# WebSocket Manager Unit Tests
# =============================================================================

@pytest.mark.asyncio
async def test_connection_manager_initialization():
    """Test ConnectionManager initializes correctly."""
    from backend.websocket_manager import ConnectionManager

    manager = ConnectionManager()

    assert manager.user_connections == {}
    assert manager.kb_rooms == {}
    assert manager.document_viewers == {}
    assert manager.get_connection_count() == 0


@pytest.mark.asyncio
async def test_websocket_event_creation():
    """Test WebSocketEvent creation and serialization."""
    from backend.websocket_manager import WebSocketEvent, EventType

    event = WebSocketEvent(
        event_type=EventType.DOCUMENT_CREATED,
        data={"doc_id": 123, "title": "Test Doc"},
        sender_username="testuser"
    )

    json_str = event.to_json()
    parsed = json.loads(json_str)

    assert parsed["event"] == "document_created"
    assert parsed["data"]["doc_id"] == 123
    assert parsed["data"]["title"] == "Test Doc"
    assert parsed["sender"] == "testuser"
    assert "timestamp" in parsed


@pytest.mark.asyncio
async def test_connection_manager_connect():
    """Test connecting a user to the manager."""
    from backend.websocket_manager import ConnectionManager

    manager = ConnectionManager()

    # Mock WebSocket
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()

    # Connect user
    connection = await manager.connect(mock_ws, "testuser", 1)

    # Verify connection
    assert connection.username == "testuser"
    assert connection.knowledge_base_id == 1
    assert "testuser" in manager.user_connections
    assert len(manager.user_connections["testuser"]) == 1
    assert "testuser" in manager.kb_rooms[1]
    assert manager.get_connection_count() == 1

    # Verify accept and welcome message were called
    mock_ws.accept.assert_called_once()
    mock_ws.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_connection_manager_disconnect():
    """Test disconnecting a user from the manager."""
    from backend.websocket_manager import ConnectionManager

    manager = ConnectionManager()

    # Mock WebSocket
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()

    # Connect then disconnect
    await manager.connect(mock_ws, "testuser", 1)
    assert manager.get_connection_count() == 1

    await manager.disconnect(mock_ws, "testuser")
    assert manager.get_connection_count() == 0
    assert "testuser" not in manager.user_connections


@pytest.mark.asyncio
async def test_connection_manager_broadcast_to_kb():
    """Test broadcasting to all users in a knowledge base."""
    from backend.websocket_manager import ConnectionManager, WebSocketEvent, EventType

    manager = ConnectionManager()

    # Create mock WebSockets for two users
    mock_ws1 = AsyncMock()
    mock_ws1.accept = AsyncMock()
    mock_ws1.send_text = AsyncMock()

    mock_ws2 = AsyncMock()
    mock_ws2.accept = AsyncMock()
    mock_ws2.send_text = AsyncMock()

    # Connect both to same KB
    await manager.connect(mock_ws1, "user1", 1)
    await manager.connect(mock_ws2, "user2", 1)

    # Reset mock calls after connection messages
    mock_ws1.send_text.reset_mock()
    mock_ws2.send_text.reset_mock()

    # Broadcast event
    event = WebSocketEvent(
        event_type=EventType.DOCUMENT_CREATED,
        data={"doc_id": 123},
        sender_username="user1"
    )
    await manager.broadcast_to_kb(1, event, exclude_user="user1")

    # user1 should NOT receive (excluded sender)
    mock_ws1.send_text.assert_not_called()

    # user2 should receive
    mock_ws2.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_connection_manager_presence_tracking():
    """Test document presence/viewing tracking."""
    from backend.websocket_manager import ConnectionManager

    manager = ConnectionManager()

    # Set viewing state
    manager.set_viewing_document("user1", 123)
    manager.set_viewing_document("user2", 123)
    manager.set_viewing_document("user3", 456)

    # Check viewers
    assert set(manager.get_document_viewers(123)) == {"user1", "user2"}
    assert manager.get_document_viewers(456) == ["user3"]
    assert manager.get_document_viewers(999) == []

    # Clear viewing state
    manager.set_viewing_document("user1", None)
    assert manager.get_document_viewers(123) == ["user2"]


@pytest.mark.asyncio
async def test_connection_manager_online_users():
    """Test getting online users list."""
    from backend.websocket_manager import ConnectionManager

    manager = ConnectionManager()

    mock_ws1 = AsyncMock()
    mock_ws1.accept = AsyncMock()
    mock_ws1.send_text = AsyncMock()

    mock_ws2 = AsyncMock()
    mock_ws2.accept = AsyncMock()
    mock_ws2.send_text = AsyncMock()

    mock_ws3 = AsyncMock()
    mock_ws3.accept = AsyncMock()
    mock_ws3.send_text = AsyncMock()

    # Connect users to different KBs
    await manager.connect(mock_ws1, "user1", 1)
    await manager.connect(mock_ws2, "user2", 1)
    await manager.connect(mock_ws3, "user3", 2)

    # Check online users
    kb1_users = manager.get_online_users(1)
    assert set(kb1_users) == {"user1", "user2"}

    kb2_users = manager.get_online_users(2)
    assert kb2_users == ["user3"]

    all_users = manager.get_online_users()
    assert set(all_users) == {"user1", "user2", "user3"}


# =============================================================================
# Helper Function Tests
# =============================================================================

@pytest.mark.asyncio
async def test_broadcast_document_created():
    """Test broadcast_document_created helper."""
    from backend.websocket_manager import broadcast_document_created, manager

    # Reset manager
    manager.user_connections = {}
    manager.kb_rooms = {}

    # Create mock connection
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()

    await manager.connect(mock_ws, "user1", 1)
    mock_ws.send_text.reset_mock()

    # Broadcast (user1 is sender, so won't receive)
    await broadcast_document_created(1, 123, "Test Doc", "text", "user1")

    # Should not receive since sender is excluded
    mock_ws.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_send_notification():
    """Test send_notification helper."""
    from backend.websocket_manager import send_notification, manager

    # Reset manager
    manager.user_connections = {}
    manager.kb_rooms = {}

    # Create mock connection
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()

    await manager.connect(mock_ws, "user1", 1)
    mock_ws.send_text.reset_mock()

    # Send notification
    await send_notification("user1", "Test Title", "Test message", "success")

    # Verify message sent
    mock_ws.send_text.assert_called_once()
    sent_data = json.loads(mock_ws.send_text.call_args[0][0])
    assert sent_data["event"] == "notification"
    assert sent_data["data"]["title"] == "Test Title"
    assert sent_data["data"]["message"] == "Test message"
    assert sent_data["data"]["type"] == "success"
