"""
Authentication Router for SyncBoard 3.0 Knowledge Bank.

Endpoints:
- POST /users - Register new user
- POST /token - Login and get JWT token
- GET /auth/{provider}/login - Initiate OAuth login
- GET /auth/{provider}/callback - OAuth callback
"""

import os
import secrets
import logging
import httpx
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models import User, UserCreate, Token, UserLogin
from ..auth import hash_password, verify_password, create_access_token
from ..sanitization import sanitize_username
from ..dependencies import get_repository
from ..repository_interface import KnowledgeBankRepository
from ..redis_client import redis_client

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Test mode detection
TESTING = os.environ.get('TESTING') == 'true'
REGISTER_RATE_LIMIT = "1000/minute" if TESTING else "3/minute"
LOGIN_RATE_LIMIT = "1000/minute" if TESTING else "5/minute"

# Create router
router = APIRouter(
    prefix="",
    tags=["authentication"],
    responses={401: {"description": "Unauthorized"}},
)

# =============================================================================
# Registration Endpoint
# =============================================================================

@router.post("/users", response_model=User)
@limiter.limit(REGISTER_RATE_LIMIT)
async def create_user(
    request: Request,
    user_create: UserCreate,
    repo: KnowledgeBankRepository = Depends(get_repository)
) -> User:
    """
    Register new user.

    Rate limited to 3 attempts per minute in production (1000/min in tests) to prevent abuse.

    Args:
        request: FastAPI request object (for rate limiting)
        user_create: User creation data (username, password)
        repo: Repository instance

    Returns:
        Created user object

    Raises:
        HTTPException 400: If username already exists or is invalid
    """
    # Sanitize username to prevent injection attacks
    username = sanitize_username(user_create.username)

    # Check if user already exists
    existing_user = await repo.get_user(username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Add user to database via repository
    hashed_password = hash_password(user_create.password)
    await repo.add_user(username, hashed_password)
    logger.info(f"Created user: {username}")

    return User(username=username)

# =============================================================================
# Login Endpoint
# =============================================================================

@router.post("/token", response_model=Token)
@limiter.limit(LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    user_login: UserLogin,
    repo: KnowledgeBankRepository = Depends(get_repository)
) -> Token:
    """
    Login and get JWT token.

    Rate limited to 5 attempts per minute in production (1000/min in tests) to prevent brute force attacks.

    Security: Uses bcrypt password verification (timing-attack resistant).

    Args:
        request: FastAPI request object (for rate limiting)
        user_login: Login credentials (username, password)
        repo: Repository instance

    Returns:
        JWT access token

    Raises:
        HTTPException 401: If credentials are invalid
    """
    # Sanitize username to prevent injection attacks
    username = sanitize_username(user_login.username)

    # Get user from repository
    stored_hash = await repo.get_user(username)

    if not stored_hash or not verify_password(user_login.password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    access_token = create_access_token(data={"sub": username})
    return Token(access_token=access_token)

# =============================================================================
# OAuth Configuration for User Login
# =============================================================================

# OAuth providers for user authentication (different from integration OAuth)
OAUTH_LOGIN_CONFIGS = {
    "google": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "user_info_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": "openid email profile",
        "redirect_uri": os.getenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"),
    },
    "github": {
        "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
        "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "user_info_url": "https://api.github.com/user",
        "emails_url": "https://api.github.com/user/emails",
        "scopes": "read:user user:email",
        "redirect_uri": os.getenv("OAUTH_GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback"),
    },
}

# Frontend callback URL for OAuth success/failure
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def get_oauth_config(provider: str) -> dict:
    """Get OAuth configuration for a login provider."""
    if provider not in OAUTH_LOGIN_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported OAuth provider: {provider}. Supported: {list(OAUTH_LOGIN_CONFIGS.keys())}"
        )

    config = OAUTH_LOGIN_CONFIGS[provider]
    if not config["client_id"] or not config["client_secret"]:
        raise HTTPException(
            status_code=503,
            detail=f"OAuth provider {provider} is not configured. Please set environment variables."
        )

    return config


# =============================================================================
# OAuth Login Endpoints
# =============================================================================

@router.get("/auth/{provider}/login")
async def oauth_login(provider: str, request: Request):
    """
    Initiate OAuth login flow.

    Redirects user to OAuth provider's authorization page.

    Args:
        provider: OAuth provider (google, github)
        request: FastAPI request object

    Returns:
        Redirect to OAuth provider
    """
    config = get_oauth_config(provider)

    # Generate CSRF state token
    state = secrets.token_urlsafe(32)

    # Store state in Redis with 10 minute expiry
    if redis_client:
        redis_client.setex(f"oauth_state:{state}", 600, provider)

    # Build authorization URL
    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "state": state,
    }

    # Add scopes (different format for each provider)
    if provider == "google":
        params["scope"] = config["scopes"]
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    elif provider == "github":
        params["scope"] = config["scopes"]

    auth_url = f"{config['authorize_url']}?{urlencode(params)}"
    logger.info(f"OAuth login initiated for provider: {provider}")

    return RedirectResponse(url=auth_url)


@router.get("/auth/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    repo: KnowledgeBankRepository = Depends(get_repository)
):
    """
    Handle OAuth callback from provider.

    Exchanges authorization code for access token, fetches user info,
    creates/links account, and issues JWT token.

    Args:
        provider: OAuth provider (google, github)
        request: FastAPI request object
        code: Authorization code from provider
        state: CSRF state token
        error: Error from provider (if any)

    Returns:
        Redirect to frontend with JWT token or error
    """
    # Handle OAuth errors
    if error:
        logger.warning(f"OAuth error from {provider}: {error}")
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error={error}")

    if not code or not state:
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=missing_params")

    # Verify state token
    stored_provider = redis_client.get(f"oauth_state:{state}") if redis_client else None
    if not stored_provider or stored_provider != provider:
        logger.warning(f"Invalid OAuth state token for {provider}")
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=invalid_state")

    # Delete used state token
    if redis_client:
        redis_client.delete(f"oauth_state:{state}")

    config = get_oauth_config(provider)

    try:
        async with httpx.AsyncClient() as client:
            # Exchange code for access token
            token_data = {
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "code": code,
                "redirect_uri": config["redirect_uri"],
            }

            if provider == "google":
                token_data["grant_type"] = "authorization_code"
                token_response = await client.post(
                    config["token_url"],
                    data=token_data,
                    headers={"Accept": "application/json"}
                )
            elif provider == "github":
                token_response = await client.post(
                    config["token_url"],
                    data=token_data,
                    headers={"Accept": "application/json"}
                )

            if token_response.status_code != 200:
                logger.error(f"Token exchange failed for {provider}: {token_response.text}")
                return RedirectResponse(url=f"{FRONTEND_URL}/login?error=token_exchange_failed")

            token_json = token_response.json()
            access_token = token_json.get("access_token")

            if not access_token:
                logger.error(f"No access token in response from {provider}")
                return RedirectResponse(url=f"{FRONTEND_URL}/login?error=no_access_token")

            # Fetch user info
            user_response = await client.get(
                config["user_info_url"],
                headers={"Authorization": f"Bearer {access_token}"}
            )

            if user_response.status_code != 200:
                logger.error(f"User info fetch failed for {provider}: {user_response.text}")
                return RedirectResponse(url=f"{FRONTEND_URL}/login?error=user_info_failed")

            user_info = user_response.json()

            # Extract email based on provider
            email = None
            if provider == "google":
                email = user_info.get("email")
            elif provider == "github":
                email = user_info.get("email")
                # GitHub may not return email in user info, need to fetch from emails endpoint
                if not email:
                    emails_response = await client.get(
                        config["emails_url"],
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    if emails_response.status_code == 200:
                        emails = emails_response.json()
                        # Find primary verified email
                        for e in emails:
                            if e.get("primary") and e.get("verified"):
                                email = e.get("email")
                                break
                        # Fallback to first verified email
                        if not email:
                            for e in emails:
                                if e.get("verified"):
                                    email = e.get("email")
                                    break

            if not email:
                logger.error(f"Could not get email from {provider}")
                return RedirectResponse(url=f"{FRONTEND_URL}/login?error=no_email")

            # Sanitize email as username
            username = sanitize_username(email.split("@")[0])
            oauth_id = f"{provider}:{user_info.get('id', email)}"

            # OAuth mapping key (store as special "user" where password is the actual username)
            oauth_mapping_key = f"oauth:{oauth_id}"

            # Check if OAuth user exists
            oauth_mapping = await repo.get_user(oauth_mapping_key)

            if oauth_mapping:
                # Existing OAuth user - the "password" field stores the actual username
                username = oauth_mapping
                logger.info(f"OAuth login for existing user: {username}")
            else:
                # New OAuth user - create account
                # Ensure unique username
                base_username = username
                counter = 1
                while await repo.get_user(username):
                    username = f"{base_username}{counter}"
                    counter += 1

                # Create user with random password (they'll use OAuth to login)
                random_password = secrets.token_urlsafe(32)
                hashed_password = hash_password(random_password)
                await repo.add_user(username, hashed_password)

                # Store OAuth mapping (username stored as "password" for the mapping key)
                await repo.add_user(oauth_mapping_key, username)

                logger.info(f"Created OAuth user: {username} ({provider})")

            # Generate JWT token
            jwt_token = create_access_token(data={"sub": username})

            # Redirect to frontend with token
            return RedirectResponse(
                url=f"{FRONTEND_URL}/login?token={jwt_token}&username={username}"
            )

    except httpx.RequestError as e:
        logger.error(f"HTTP error during OAuth for {provider}: {e}")
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=network_error")
    except Exception as e:
        logger.error(f"OAuth callback error for {provider}: {e}")
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=callback_failed")
