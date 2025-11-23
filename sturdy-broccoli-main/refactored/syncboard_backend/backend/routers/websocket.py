"""
WebSocket Router for SyncBoard 3.0 Real-time Features.

Endpoints:
- WS /ws - Main WebSocket connection for real-time updates
- GET /ws/status - Get WebSocket server status
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from jose import jwt, JWTError

from ..websocket_manager import (
    manager,
    EventType,
    WebSocketEvent,
    broadcast_document_created,
    broadcast_document_updated,
)
from ..dependencies import get_user_default_kb_id
from ..auth import SECRET_KEY, ALGORITHM
from ..database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["websocket"],
)


async def get_user_from_token(token: str) -> tuple[str, int]:
    """
    Validate JWT token and return username and default KB ID.

    Args:
        token: JWT access token

    Returns:
        Tuple of (username, knowledge_base_id)

    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Get user's default KB
        db = SessionLocal()
        try:
            kb_id = get_user_default_kb_id(username, db)
        finally:
            db.close()

        return username, kb_id

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    Main WebSocket endpoint for real-time updates.

    Connect with: ws://host/ws?token=<jwt_token>

    Events received by client:
    - connected: Connection confirmed
    - document_created: New document added
    - document_updated: Document modified
    - document_deleted: Document removed
    - cluster_updated: Cluster changed
    - job_completed: Background job finished
    - notification: User notification
    - user_viewing: Another user viewing a document
    - user_left: User stopped viewing

    Events client can send:
    - viewing: {"doc_id": 123} - Set currently viewed document
    - ping: {} - Keep-alive ping
    """
    # Authenticate
    try:
        username, kb_id = await get_user_from_token(token)
    except HTTPException as e:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # Connect
    connection = await manager.connect(websocket, username, kb_id)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                event_type = message.get("event", "")

                # Handle client events
                if event_type == "viewing":
                    # User is viewing a document
                    doc_id = message.get("data", {}).get("doc_id")
                    manager.set_viewing_document(username, doc_id)

                    # Notify others in the KB
                    if doc_id:
                        await manager.broadcast_to_kb(
                            kb_id,
                            WebSocketEvent(
                                event_type=EventType.USER_VIEWING,
                                data={
                                    "doc_id": doc_id,
                                    "username": username,
                                    "viewers": manager.get_document_viewers(doc_id)
                                },
                                sender_username=username
                            ),
                            exclude_user=username
                        )

                elif event_type == "left":
                    # User stopped viewing
                    doc_id = connection.currently_viewing
                    manager.set_viewing_document(username, None)

                    if doc_id:
                        await manager.broadcast_to_kb(
                            kb_id,
                            WebSocketEvent(
                                event_type=EventType.USER_LEFT,
                                data={
                                    "doc_id": doc_id,
                                    "username": username,
                                    "viewers": manager.get_document_viewers(doc_id)
                                },
                                sender_username=username
                            ),
                            exclude_user=username
                        )

                elif event_type == "ping":
                    # Keep-alive - respond with pong
                    await websocket.send_json({"event": "pong", "data": {}})

                elif event_type == "sync_request":
                    # Client requesting sync (after reconnection)
                    await manager.send_personal(
                        username,
                        WebSocketEvent(
                            event_type=EventType.SYNC_RESPONSE,
                            data={
                                "online_users": manager.get_online_users(kb_id),
                                "connection_count": manager.get_connection_count()
                            }
                        )
                    )

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from {username}: {data[:100]}")

    except WebSocketDisconnect:
        await manager.disconnect(websocket, username)

        # Notify others about user leaving
        await manager.broadcast_to_kb(
            kb_id,
            WebSocketEvent(
                event_type=EventType.USER_LEFT,
                data={
                    "username": username,
                    "online_users": manager.get_online_users(kb_id)
                },
                sender_username=username
            )
        )


@router.get("/ws/status")
async def websocket_status():
    """
    Get WebSocket server status.

    Returns connection counts and online user info.
    """
    return {
        "status": "online",
        "total_connections": manager.get_connection_count(),
        "total_users": len(manager.user_connections),
        "rooms": {
            str(kb_id): list(users)
            for kb_id, users in manager.kb_rooms.items()
        }
    }


@router.get("/ws/presence/{doc_id}")
async def get_document_presence(doc_id: int):
    """
    Get list of users currently viewing a document.

    Args:
        doc_id: Document ID

    Returns:
        List of usernames viewing the document
    """
    return {
        "doc_id": doc_id,
        "viewers": manager.get_document_viewers(doc_id)
    }
