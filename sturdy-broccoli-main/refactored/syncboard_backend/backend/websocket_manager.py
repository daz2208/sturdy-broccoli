"""
WebSocket Manager for SyncBoard 3.0 Real-time Features.

Handles WebSocket connections for:
- Live document updates
- Real-time notifications
- Cluster changes
- Background job completion events
- Collaboration presence (who's viewing what)
"""

import json
import logging
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """WebSocket event types."""
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"

    # Document events
    DOCUMENT_CREATED = "document_created"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_DELETED = "document_deleted"

    # Cluster events
    CLUSTER_CREATED = "cluster_created"
    CLUSTER_UPDATED = "cluster_updated"
    CLUSTER_DELETED = "cluster_deleted"
    CLUSTERS_RECLUSTERED = "clusters_reclustered"

    # Job events
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"

    # Collaboration events
    USER_VIEWING = "user_viewing"
    USER_LEFT = "user_left"

    # Notification events
    NOTIFICATION = "notification"

    # Sync events
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"

    # Autonomous Learning Agent events
    LEARNING_OBSERVATION = "learning_observation"
    LEARNING_DECISION = "learning_decision"
    LEARNING_RULE_CREATED = "learning_rule_created"
    LEARNING_RULE_DEACTIVATED = "learning_rule_deactivated"
    LEARNING_THRESHOLD_ADJUSTED = "learning_threshold_adjusted"
    LEARNING_SELF_EVALUATION = "learning_self_evaluation"


@dataclass
class WebSocketEvent:
    """Structured WebSocket event."""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sender_username: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps({
            "event": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "sender": self.sender_username
        })


@dataclass
class UserConnection:
    """Represents a connected user's WebSocket session."""
    websocket: WebSocket
    username: str
    knowledge_base_id: str  # UUID string
    connected_at: datetime = field(default_factory=datetime.utcnow)
    currently_viewing: Optional[int] = None  # doc_id currently being viewed


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts.

    Features:
    - Per-user connection tracking
    - Per-knowledge-base rooms for scoped broadcasts
    - Presence tracking (who's viewing what)
    - Event broadcasting with filtering
    """

    def __init__(self):
        # Map: username -> List[UserConnection]
        self.user_connections: Dict[str, List[UserConnection]] = {}

        # Map: kb_id (UUID string) -> Set[username] (for room-based broadcasting)
        self.kb_rooms: Dict[str, Set[str]] = {}

        # Map: doc_id -> Set[username] (presence tracking)
        self.document_viewers: Dict[int, Set[str]] = {}

        logger.info("WebSocket ConnectionManager initialized")

    async def connect(
        self,
        websocket: WebSocket,
        username: str,
        knowledge_base_id: str
    ) -> UserConnection:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
            username: Authenticated user's username
            knowledge_base_id: User's active knowledge base (UUID string)

        Returns:
            UserConnection object
        """
        await websocket.accept()

        connection = UserConnection(
            websocket=websocket,
            username=username,
            knowledge_base_id=knowledge_base_id
        )

        # Add to user connections
        if username not in self.user_connections:
            self.user_connections[username] = []
        self.user_connections[username].append(connection)

        # Add to knowledge base room
        if knowledge_base_id not in self.kb_rooms:
            self.kb_rooms[knowledge_base_id] = set()
        self.kb_rooms[knowledge_base_id].add(username)

        logger.info(f"WebSocket connected: {username} (KB: {knowledge_base_id})")

        # Send connection confirmation
        await self.send_personal(
            username,
            WebSocketEvent(
                event_type=EventType.CONNECTED,
                data={
                    "message": "Connected to SyncBoard real-time updates",
                    "knowledge_base_id": knowledge_base_id
                }
            )
        )

        return connection

    async def disconnect(self, websocket: WebSocket, username: str):
        """
        Handle WebSocket disconnection.

        Args:
            websocket: The disconnected WebSocket
            username: User's username
        """
        if username in self.user_connections:
            # Remove specific connection
            self.user_connections[username] = [
                conn for conn in self.user_connections[username]
                if conn.websocket != websocket
            ]

            # Clean up if no more connections for user
            if not self.user_connections[username]:
                del self.user_connections[username]

                # Remove from all KB rooms
                for kb_id in list(self.kb_rooms.keys()):
                    self.kb_rooms[kb_id].discard(username)
                    if not self.kb_rooms[kb_id]:
                        del self.kb_rooms[kb_id]

                # Remove from document viewers
                for doc_id in list(self.document_viewers.keys()):
                    self.document_viewers[doc_id].discard(username)
                    if not self.document_viewers[doc_id]:
                        del self.document_viewers[doc_id]

        logger.info(f"WebSocket disconnected: {username}")

    async def send_personal(self, username: str, event: WebSocketEvent):
        """
        Send event to a specific user (all their connections).

        Args:
            username: Target username
            event: Event to send
        """
        if username in self.user_connections:
            message = event.to_json()
            for conn in self.user_connections[username]:
                try:
                    await conn.websocket.send_text(message)
                except Exception as e:
                    logger.error(f"Failed to send to {username}: {e}")

    async def broadcast_to_kb(
        self,
        knowledge_base_id: str,
        event: WebSocketEvent,
        exclude_user: Optional[str] = None
    ):
        """
        Broadcast event to all users in a knowledge base.

        Args:
            knowledge_base_id: Target KB (UUID string)
            event: Event to broadcast
            exclude_user: Optional username to exclude (usually sender)
        """
        if knowledge_base_id not in self.kb_rooms:
            return

        message = event.to_json()

        for username in self.kb_rooms[knowledge_base_id]:
            if username == exclude_user:
                continue

            if username in self.user_connections:
                for conn in self.user_connections[username]:
                    try:
                        await conn.websocket.send_text(message)
                    except Exception as e:
                        logger.error(f"Broadcast failed for {username}: {e}")

    async def broadcast_to_all(self, event: WebSocketEvent):
        """
        Broadcast event to all connected users.

        Args:
            event: Event to broadcast
        """
        message = event.to_json()

        for username, connections in self.user_connections.items():
            for conn in connections:
                try:
                    await conn.websocket.send_text(message)
                except Exception as e:
                    logger.error(f"Global broadcast failed for {username}: {e}")

    def set_viewing_document(self, username: str, doc_id: Optional[int]):
        """
        Update which document a user is viewing (presence tracking).

        Args:
            username: User's username
            doc_id: Document ID being viewed (None to clear)
        """
        # Clear previous viewing state
        for existing_doc_id in list(self.document_viewers.keys()):
            self.document_viewers[existing_doc_id].discard(username)
            if not self.document_viewers[existing_doc_id]:
                del self.document_viewers[existing_doc_id]

        # Set new viewing state
        if doc_id is not None:
            if doc_id not in self.document_viewers:
                self.document_viewers[doc_id] = set()
            self.document_viewers[doc_id].add(username)

    def get_document_viewers(self, doc_id: int) -> List[str]:
        """Get list of usernames currently viewing a document."""
        return list(self.document_viewers.get(doc_id, set()))

    def get_online_users(self, knowledge_base_id: Optional[str] = None) -> List[str]:
        """
        Get list of online users.

        Args:
            knowledge_base_id: Optional KB filter (UUID string)

        Returns:
            List of online usernames
        """
        if knowledge_base_id:
            return list(self.kb_rooms.get(knowledge_base_id, set()))
        return list(self.user_connections.keys())

    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self.user_connections.values())


# Global connection manager instance
manager = ConnectionManager()


# =============================================================================
# Helper functions for broadcasting from other modules
# =============================================================================

async def broadcast_document_created(
    knowledge_base_id: str,
    doc_id: int,
    title: str,
    source_type: str,
    created_by: str
):
    """Broadcast document creation event."""
    await manager.broadcast_to_kb(
        knowledge_base_id,
        WebSocketEvent(
            event_type=EventType.DOCUMENT_CREATED,
            data={
                "doc_id": doc_id,
                "title": title,
                "source_type": source_type
            },
            sender_username=created_by
        ),
        exclude_user=created_by
    )


async def broadcast_document_updated(
    knowledge_base_id: str,
    doc_id: int,
    updated_by: str,
    changes: Dict[str, Any] = None
):
    """Broadcast document update event."""
    await manager.broadcast_to_kb(
        knowledge_base_id,
        WebSocketEvent(
            event_type=EventType.DOCUMENT_UPDATED,
            data={
                "doc_id": doc_id,
                "changes": changes or {}
            },
            sender_username=updated_by
        ),
        exclude_user=updated_by
    )


async def broadcast_document_deleted(
    knowledge_base_id: str,
    doc_id: int,
    deleted_by: str
):
    """Broadcast document deletion event."""
    await manager.broadcast_to_kb(
        knowledge_base_id,
        WebSocketEvent(
            event_type=EventType.DOCUMENT_DELETED,
            data={"doc_id": doc_id},
            sender_username=deleted_by
        ),
        exclude_user=deleted_by
    )


async def broadcast_cluster_created(
    knowledge_base_id: str,
    cluster_id: int,
    cluster_name: str,
    document_count: int
):
    """Broadcast cluster creation event."""
    await manager.broadcast_to_kb(
        knowledge_base_id,
        WebSocketEvent(
            event_type=EventType.CLUSTER_CREATED,
            data={
                "cluster_id": cluster_id,
                "name": cluster_name,
                "document_count": document_count
            }
        )
    )


async def broadcast_cluster_updated(
    knowledge_base_id: str,
    cluster_id: int,
    cluster_name: str,
    document_count: int
):
    """Broadcast cluster update event."""
    await manager.broadcast_to_kb(
        knowledge_base_id,
        WebSocketEvent(
            event_type=EventType.CLUSTER_UPDATED,
            data={
                "cluster_id": cluster_id,
                "name": cluster_name,
                "document_count": document_count
            }
        )
    )


async def broadcast_cluster_deleted(
    knowledge_base_id: str,
    cluster_id: int
):
    """Broadcast cluster deletion event."""
    await manager.broadcast_to_kb(
        knowledge_base_id,
        WebSocketEvent(
            event_type=EventType.CLUSTER_DELETED,
            data={"cluster_id": cluster_id}
        )
    )


async def broadcast_job_completed(
    username: str,
    job_id: str,
    job_type: str,
    result: Dict[str, Any] = None
):
    """Broadcast job completion to specific user."""
    await manager.send_personal(
        username,
        WebSocketEvent(
            event_type=EventType.JOB_COMPLETED,
            data={
                "job_id": job_id,
                "job_type": job_type,
                "result": result or {}
            }
        )
    )


async def broadcast_job_failed(
    username: str,
    job_id: str,
    job_type: str,
    error: str
):
    """Broadcast job failure to specific user."""
    await manager.send_personal(
        username,
        WebSocketEvent(
            event_type=EventType.JOB_FAILED,
            data={
                "job_id": job_id,
                "job_type": job_type,
                "error": error
            }
        )
    )


async def send_notification(
    username: str,
    title: str,
    message: str,
    notification_type: str = "info"
):
    """Send notification to specific user."""
    await manager.send_personal(
        username,
        WebSocketEvent(
            event_type=EventType.NOTIFICATION,
            data={
                "title": title,
                "message": message,
                "type": notification_type  # info, success, warning, error
            }
        )
    )
