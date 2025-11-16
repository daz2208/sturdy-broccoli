"""
Cloud Service Integrations Router (Phase 5)

Handles OAuth authentication and file imports for:
- GitHub
- Google Drive
- Dropbox
- Notion

OAuth Flow:
1. User clicks "Connect" → GET /integrations/{service}/authorize
2. Backend generates state token, redirects to provider OAuth
3. Provider redirects back → GET /integrations/{service}/callback
4. Backend exchanges code for token, stores encrypted in DB
5. User can browse files and import
"""

import os
import secrets
import json
import logging
from typing import Optional, Literal
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..db_models import DBIntegrationToken, DBIntegrationImport
from ..models.integrations import (
    IntegrationsStatus,
    IntegrationConnectionStatus,
    IntegrationToken,
)
from ..models.auth import User
from ..routers.auth import get_current_user
from ..utils.encryption import encrypt_token, decrypt_token
from ..redis_client import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integrations",
    tags=["integrations"],
    responses={401: {"description": "Unauthorized"}},
)

# =============================================================================
# OAuth Configuration
# =============================================================================

# Service configurations
SERVICE_CONFIGS = {
    "github": {
        "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
        "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "user_info_url": "https://api.github.com/user",
        "scopes": "repo read:user",
        "redirect_uri": os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/integrations/github/callback"),
    },
    "google": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "user_info_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": "https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/userinfo.email",
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/integrations/google/callback"),
    },
    "dropbox": {
        "client_id": os.getenv("DROPBOX_APP_KEY", ""),
        "client_secret": os.getenv("DROPBOX_APP_SECRET", ""),
        "authorize_url": "https://www.dropbox.com/oauth2/authorize",
        "token_url": "https://api.dropboxapi.com/oauth2/token",
        "user_info_url": "https://api.dropboxapi.com/2/users/get_current_account",
        "scopes": "",  # Dropbox uses app permissions, not OAuth scopes
        "redirect_uri": os.getenv("DROPBOX_REDIRECT_URI", "http://localhost:8000/integrations/dropbox/callback"),
    },
    "notion": {
        "client_id": os.getenv("NOTION_CLIENT_ID", ""),
        "client_secret": os.getenv("NOTION_CLIENT_SECRET", ""),
        "authorize_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "user_info_url": "https://api.notion.com/v1/users/me",
        "scopes": "",  # Notion uses capabilities, not OAuth scopes
        "redirect_uri": os.getenv("NOTION_REDIRECT_URI", "http://localhost:8000/integrations/notion/callback"),
    },
}


def get_service_config(service: str) -> dict:
    """
    Get OAuth configuration for a service.

    Args:
        service: Service name (github, google, dropbox, notion)

    Returns:
        dict: Service configuration

    Raises:
        HTTPException: If service not supported or not configured
    """
    if service not in SERVICE_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Service '{service}' not supported. Valid services: {list(SERVICE_CONFIGS.keys())}"
        )

    config = SERVICE_CONFIGS[service]

    # Validate required configuration
    if not config["client_id"] or not config["client_secret"]:
        raise HTTPException(
            status_code=500,
            detail=f"{service.title()} integration not configured. Please set {service.upper()}_CLIENT_ID and {service.upper()}_CLIENT_SECRET environment variables."
        )

    return config


# =============================================================================
# OAuth State Management (CSRF Protection)
# =============================================================================

def generate_oauth_state(user_id: str, service: str) -> str:
    """
    Generate and store OAuth state token for CSRF protection.

    Args:
        user_id: User ID initiating OAuth
        service: Service name

    Returns:
        str: State token
    """
    redis_client = get_redis_client()

    # Generate cryptographically secure random state
    state = secrets.token_urlsafe(32)

    # Store state in Redis with 10-minute expiration
    state_data = json.dumps({
        "user_id": user_id,
        "service": service,
        "timestamp": datetime.utcnow().isoformat()
    })

    redis_client.setex(
        f"oauth_state:{state}",
        600,  # 10 minutes
        state_data
    )

    logger.info(f"Generated OAuth state for user {user_id}, service {service}")
    return state


def validate_oauth_state(state: str, expected_service: str) -> str:
    """
    Validate OAuth state token and return user_id.

    Args:
        state: State token from OAuth callback
        expected_service: Expected service name

    Returns:
        str: User ID

    Raises:
        HTTPException: If state invalid or expired
    """
    redis_client = get_redis_client()

    # Retrieve state data from Redis
    state_data_str = redis_client.get(f"oauth_state:{state}")

    if not state_data_str:
        logger.warning(f"Invalid or expired OAuth state: {state[:10]}...")
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state token. Please try connecting again."
        )

    # Parse state data
    try:
        state_data = json.loads(state_data_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Corrupted state data")

    # Validate service matches
    if state_data["service"] != expected_service:
        logger.warning(
            f"Service mismatch: expected {expected_service}, got {state_data['service']}"
        )
        raise HTTPException(status_code=400, detail="Service mismatch")

    # Delete state (single use)
    redis_client.delete(f"oauth_state:{state}")

    logger.info(f"Validated OAuth state for user {state_data['user_id']}, service {expected_service}")
    return state_data["user_id"]


# =============================================================================
# Token Storage and Retrieval
# =============================================================================

def store_integration_token(
    db: Session,
    user_id: str,
    service: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_in: Optional[int] = None,
    token_type: str = "Bearer",
    scope: Optional[str] = None,
    provider_user_id: Optional[str] = None,
    provider_user_email: Optional[str] = None,
    provider_user_name: Optional[str] = None,
) -> DBIntegrationToken:
    """
    Store encrypted OAuth token in database.

    Args:
        db: Database session
        user_id: User ID
        service: Service name
        access_token: OAuth access token (will be encrypted)
        refresh_token: OAuth refresh token (will be encrypted)
        expires_in: Token expiration in seconds
        token_type: Token type (usually "Bearer")
        scope: Granted scopes
        provider_user_id: User ID from provider
        provider_user_email: Email from provider
        provider_user_name: Name from provider

    Returns:
        DBIntegrationToken: Stored token record
    """
    # Calculate expiration timestamp
    expires_at = None
    if expires_in:
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    # Encrypt tokens
    encrypted_access_token = encrypt_token(access_token)
    encrypted_refresh_token = encrypt_token(refresh_token) if refresh_token else None

    # Check if token already exists
    existing_token = db.query(DBIntegrationToken).filter_by(
        user_id=user_id,
        service=service
    ).first()

    if existing_token:
        # Update existing token
        existing_token.access_token = encrypted_access_token
        existing_token.refresh_token = encrypted_refresh_token
        existing_token.token_type = token_type
        existing_token.expires_at = expires_at
        existing_token.scope = scope
        existing_token.provider_user_id = provider_user_id
        existing_token.provider_user_email = provider_user_email
        existing_token.provider_user_name = provider_user_name
        existing_token.updated_at = datetime.utcnow()

        logger.info(f"Updated {service} token for user {user_id}")
        db.commit()
        db.refresh(existing_token)
        return existing_token
    else:
        # Create new token
        new_token = DBIntegrationToken(
            user_id=user_id,
            service=service,
            access_token=encrypted_access_token,
            refresh_token=encrypted_refresh_token,
            token_type=token_type,
            expires_at=expires_at,
            scope=scope,
            provider_user_id=provider_user_id,
            provider_user_email=provider_user_email,
            provider_user_name=provider_user_name,
        )

        db.add(new_token)
        logger.info(f"Stored new {service} token for user {user_id}")
        db.commit()
        db.refresh(new_token)
        return new_token


def get_integration_token(
    db: Session,
    user_id: str,
    service: str,
    decrypt: bool = True
) -> Optional[DBIntegrationToken]:
    """
    Retrieve integration token from database.

    Args:
        db: Database session
        user_id: User ID
        service: Service name
        decrypt: Whether to decrypt tokens (default True)

    Returns:
        DBIntegrationToken or None: Token record with decrypted tokens
    """
    token = db.query(DBIntegrationToken).filter_by(
        user_id=user_id,
        service=service
    ).first()

    if not token:
        return None

    if decrypt:
        # Decrypt tokens before returning
        # Note: This modifies the ORM object temporarily, doesn't persist
        try:
            token.access_token = decrypt_token(token.access_token)
            if token.refresh_token:
                token.refresh_token = decrypt_token(token.refresh_token)
        except Exception as e:
            logger.error(f"Failed to decrypt {service} token for user {user_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to decrypt {service} token. Please reconnect."
            )

    # Update last_used timestamp
    token.last_used = datetime.utcnow()
    db.commit()

    return token


def delete_integration_token(db: Session, user_id: str, service: str) -> bool:
    """
    Delete integration token from database.

    Args:
        db: Database session
        user_id: User ID
        service: Service name

    Returns:
        bool: True if deleted, False if not found
    """
    token = db.query(DBIntegrationToken).filter_by(
        user_id=user_id,
        service=service
    ).first()

    if token:
        db.delete(token)
        db.commit()
        logger.info(f"Deleted {service} token for user {user_id}")
        return True

    return False


# =============================================================================
# Generic OAuth Endpoints
# =============================================================================

@router.get("/{service}/authorize")
async def initiate_oauth(
    service: Literal["github", "google", "dropbox", "notion"],
    current_user: User = Depends(get_current_user)
):
    """
    Initiate OAuth flow for a cloud service.

    Flow:
    1. Generate state token (CSRF protection)
    2. Build authorization URL with client_id, redirect_uri, scope, state
    3. Redirect user to provider's OAuth page

    Args:
        service: Cloud service name
        current_user: Authenticated user

    Returns:
        RedirectResponse: Redirect to provider OAuth page
    """
    config = get_service_config(service)

    # Generate state token
    state = generate_oauth_state(current_user.username, service)

    # Build authorization URL
    auth_params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "state": state,
        "response_type": "code",
    }

    # Add scopes if service uses them
    if config["scopes"]:
        auth_params["scope"] = config["scopes"]

    # Google-specific: request offline access for refresh token
    if service == "google":
        auth_params["access_type"] = "offline"
        auth_params["prompt"] = "consent"

    # Build URL
    from urllib.parse import urlencode
    auth_url = f"{config['authorize_url']}?{urlencode(auth_params)}"

    logger.info(f"Initiating {service} OAuth for user {current_user.username}")
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/{service}/callback")
async def oauth_callback(
    service: Literal["github", "google", "dropbox", "notion"],
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State token for CSRF validation"),
    error: Optional[str] = Query(None, description="Error from provider"),
    error_description: Optional[str] = Query(None, description="Error description"),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth callback from provider.

    Flow:
    1. Validate state token
    2. Exchange authorization code for access token
    3. Fetch user info from provider
    4. Store encrypted token in database
    5. Redirect to success page

    Args:
        service: Cloud service name
        code: Authorization code
        state: State token
        error: Error code (if OAuth failed)
        error_description: Error description
        db: Database session

    Returns:
        RedirectResponse: Redirect to frontend success/error page
    """
    # Check for OAuth errors
    if error:
        logger.error(f"{service} OAuth error: {error} - {error_description}")
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Connection Failed</title></head>
                <body style="font-family: Arial; padding: 40px; text-align: center;">
                    <h1>❌ Connection Failed</h1>
                    <p>{service.title()} OAuth error: {error_description or error}</p>
                    <p><a href="/">Return to SyncBoard</a></p>
                </body>
            </html>
            """,
            status_code=400
        )

    # Validate state
    try:
        user_id = validate_oauth_state(state, service)
    except HTTPException as e:
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Invalid State</title></head>
                <body style="font-family: Arial; padding: 40px; text-align: center;">
                    <h1>⚠️ Invalid Request</h1>
                    <p>{e.detail}</p>
                    <p><a href="/">Return to SyncBoard</a></p>
                </body>
            </html>
            """,
            status_code=400
        )

    config = get_service_config(service)

    # Exchange code for access token
    import requests

    token_data = {
        "client_id": config["client_id"],
        "client_secret": config["client_secret"],
        "code": code,
        "redirect_uri": config["redirect_uri"],
        "grant_type": "authorization_code",
    }

    headers = {"Accept": "application/json"}

    try:
        response = requests.post(
            config["token_url"],
            data=token_data,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        token_response = response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to exchange {service} code for token: {e}")
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Token Exchange Failed</title></head>
                <body style="font-family: Arial; padding: 40px; text-align: center;">
                    <h1>❌ Connection Failed</h1>
                    <p>Failed to exchange authorization code for access token.</p>
                    <p>Error: {str(e)}</p>
                    <p><a href="/">Return to SyncBoard</a></p>
                </body>
            </html>
            """,
            status_code=500
        )

    # Extract token information
    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")
    expires_in = token_response.get("expires_in")
    token_type = token_response.get("token_type", "Bearer")
    scope = token_response.get("scope")

    if not access_token:
        logger.error(f"{service} token response missing access_token: {token_response}")
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Invalid Token Response</title></head>
                <body style="font-family: Arial; padding: 40px; text-align: center;">
                    <h1>❌ Connection Failed</h1>
                    <p>Invalid token response from {service.title()}.</p>
                    <p><a href="/">Return to SyncBoard</a></p>
                </body>
            </html>
            """,
            status_code=500
        )

    # Fetch user info from provider
    provider_user_id = None
    provider_user_email = None
    provider_user_name = None

    try:
        user_headers = {
            "Authorization": f"{token_type} {access_token}",
            "Accept": "application/json"
        }

        user_response = requests.get(
            config["user_info_url"],
            headers=user_headers,
            timeout=10
        )
        user_response.raise_for_status()
        user_info = user_response.json()

        # Extract user info (service-specific)
        if service == "github":
            provider_user_id = str(user_info.get("id", ""))
            provider_user_email = user_info.get("email", "")
            provider_user_name = user_info.get("login", "")
        elif service == "google":
            provider_user_id = user_info.get("id", "")
            provider_user_email = user_info.get("email", "")
            provider_user_name = user_info.get("name", "")
        elif service == "dropbox":
            provider_user_id = user_info.get("account_id", "")
            provider_user_email = user_info.get("email", "")
            provider_user_name = user_info.get("name", {}).get("display_name", "")
        elif service == "notion":
            # Notion user info structure is different
            provider_user_id = user_info.get("id", "")
            provider_user_email = user_info.get("person", {}).get("email", "")
            provider_user_name = user_info.get("name", "")

    except Exception as e:
        logger.warning(f"Failed to fetch {service} user info: {e}")
        # Continue anyway, user info is not critical

    # Store encrypted token
    try:
        store_integration_token(
            db=db,
            user_id=user_id,
            service=service,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type=token_type,
            scope=scope,
            provider_user_id=provider_user_id,
            provider_user_email=provider_user_email,
            provider_user_name=provider_user_name,
        )
    except Exception as e:
        logger.error(f"Failed to store {service} token: {e}")
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>Storage Failed</title></head>
                <body style="font-family: Arial; padding: 40px; text-align: center;">
                    <h1>❌ Connection Failed</h1>
                    <p>Failed to store connection token.</p>
                    <p>Error: {str(e)}</p>
                    <p><a href="/">Return to SyncBoard</a></p>
                </body>
            </html>
            """,
            status_code=500
        )

    logger.info(f"Successfully connected {service} for user {user_id}")

    # Success page with auto-redirect
    return HTMLResponse(
        content=f"""
        <html>
            <head>
                <title>Connected Successfully</title>
                <meta http-equiv="refresh" content="3;url=/" />
            </head>
            <body style="font-family: Arial; padding: 40px; text-align: center;">
                <h1>✅ Connected Successfully!</h1>
                <p>Your {service.title()} account has been connected.</p>
                <p>Redirecting to SyncBoard in 3 seconds...</p>
                <p><a href="/">Click here if not redirected</a></p>
            </body>
        </html>
        """,
        status_code=200
    )


@router.get("/status")
async def get_integration_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> IntegrationsStatus:
    """
    Get connection status for all cloud services.

    Returns status for each service:
    - connected: Whether service is connected
    - user: Provider username
    - email: Provider email
    - connected_at: When connection was made
    - last_sync: When last import occurred

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        IntegrationsStatus: Connection status for all services
    """
    status = IntegrationsStatus()

    for service in ["github", "google", "dropbox", "notion"]:
        token = db.query(DBIntegrationToken).filter_by(
            user_id=current_user.username,
            service=service
        ).first()

        if token:
            # Get last import time
            last_import = db.query(DBIntegrationImport).filter_by(
                user_id=current_user.username,
                service=service,
                status="completed"
            ).order_by(DBIntegrationImport.completed_at.desc()).first()

            status.connections[service] = IntegrationConnectionStatus(
                connected=True,
                user=token.provider_user_name or token.provider_user_id,
                email=token.provider_user_email,
                connected_at=token.connected_at,
                last_sync=last_import.completed_at if last_import else None
            )
        else:
            status.connections[service] = IntegrationConnectionStatus(connected=False)

    return status


@router.post("/{service}/disconnect")
async def disconnect_service(
    service: Literal["github", "google", "dropbox", "notion"],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect a cloud service.

    This deletes the stored OAuth token. The user will need to
    reconnect to use this service again.

    Note: This does NOT revoke the token with the provider.
    Users should revoke access through the provider's settings
    for complete disconnection.

    Args:
        service: Cloud service name
        current_user: Authenticated user
        db: Database session

    Returns:
        dict: Success message
    """
    deleted = delete_integration_token(db, current_user.username, service)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"{service.title()} is not connected"
        )

    logger.info(f"Disconnected {service} for user {current_user.username}")

    return {
        "message": f"{service.title()} disconnected successfully",
        "service": service
    }


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
async def integration_health_check():
    """
    Check integration system health.

    Verifies:
    - OAuth configuration
    - Encryption module
    - Redis connectivity

    Returns:
        dict: Health status
    """
    from ..utils.encryption import check_encryption_health

    health = {
        "healthy": True,
        "services_configured": [],
        "services_missing": [],
        "encryption": check_encryption_health(),
        "redis_connected": False,
    }

    # Check service configurations
    for service in ["github", "google", "dropbox", "notion"]:
        config = SERVICE_CONFIGS[service]
        if config["client_id"] and config["client_secret"]:
            health["services_configured"].append(service)
        else:
            health["services_missing"].append(service)

    # Check Redis connectivity
    try:
        redis_client = get_redis_client()
        redis_client.ping()
        health["redis_connected"] = True
    except Exception as e:
        health["healthy"] = False
        health["redis_error"] = str(e)

    # Overall health
    if not health["encryption"]["healthy"] or not health["redis_connected"]:
        health["healthy"] = False

    return health
