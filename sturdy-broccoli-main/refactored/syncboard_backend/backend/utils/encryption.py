"""
Token Encryption Utilities

Provides secure encryption/decryption for OAuth tokens using Fernet symmetric encryption.

Security Features:
- AES-128-CBC encryption via Fernet
- HMAC authentication
- Base64 encoding
- Key rotation support

Environment:
- ENCRYPTION_KEY: Base64-encoded 32-byte Fernet key (required)
"""

import base64
import logging
from cryptography.fernet import Fernet, InvalidToken
from typing import Optional

try:
    from ..config import settings
except ImportError:
    # Fallback for standalone imports
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Encryption Key Management
# =============================================================================

def get_encryption_key() -> bytes:
    """
    Get encryption key from environment variable.

    Returns:
        bytes: Fernet encryption key

    Raises:
        ValueError: If ENCRYPTION_KEY not set or invalid
    """
    key_str = settings.encryption_key

    if not key_str:
        raise ValueError(
            "ENCRYPTION_KEY environment variable must be set. "
            "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )

    try:
        # Validate key format
        key_bytes = key_str.encode() if isinstance(key_str, str) else key_str
        Fernet(key_bytes)  # Test key validity
        return key_bytes
    except Exception as e:
        raise ValueError(f"Invalid ENCRYPTION_KEY: {e}")


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Use this to create a new key for ENCRYPTION_KEY environment variable.

    Returns:
        str: Base64-encoded encryption key

    Example:
        >>> key = generate_encryption_key()
        >>> print(f"ENCRYPTION_KEY={key}")
    """
    return Fernet.generate_key().decode()


# Initialize cipher
try:
    _cipher = Fernet(get_encryption_key())
    logger.info("✅ Encryption initialized successfully")
except ValueError as e:
    logger.error(f"❌ Encryption initialization failed: {e}")
    _cipher = None


# =============================================================================
# Encryption Functions
# =============================================================================

def encrypt_token(token: str) -> str:
    """
    Encrypt an OAuth token for secure database storage.

    Args:
        token: Plain text OAuth token

    Returns:
        str: Encrypted token (base64 encoded)

    Raises:
        ValueError: If encryption not initialized
        Exception: If encryption fails

    Example:
        >>> access_token = "gho_abc123..."
        >>> encrypted = encrypt_token(access_token)
        >>> # Store encrypted in database
    """
    if _cipher is None:
        raise ValueError("Encryption not initialized. Check ENCRYPTION_KEY environment variable.")

    try:
        token_bytes = token.encode('utf-8')
        encrypted_bytes = _cipher.encrypt(token_bytes)
        return encrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Token encryption failed: {e}")
        raise


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt an OAuth token retrieved from database.

    Args:
        encrypted_token: Encrypted token (base64 encoded)

    Returns:
        str: Plain text OAuth token

    Raises:
        ValueError: If encryption not initialized
        InvalidToken: If token invalid or tampered with
        Exception: If decryption fails

    Example:
        >>> encrypted = get_token_from_db(user_id, service)
        >>> token = decrypt_token(encrypted)
        >>> # Use token for API calls
    """
    if _cipher is None:
        raise ValueError("Encryption not initialized. Check ENCRYPTION_KEY environment variable.")

    try:
        encrypted_bytes = encrypted_token.encode('utf-8')
        decrypted_bytes = _cipher.decrypt(encrypted_bytes)
        return decrypted_bytes.decode('utf-8')
    except InvalidToken:
        logger.error("Token decryption failed: Invalid token or tampered data")
        raise ValueError("Invalid or tampered token")
    except Exception as e:
        logger.error(f"Token decryption failed: {e}")
        raise


# =============================================================================
# Token Validation
# =============================================================================

def is_token_encrypted(token: str) -> bool:
    """
    Check if a token is encrypted (vs plain text).

    Args:
        token: Token string to check

    Returns:
        bool: True if token appears to be encrypted

    Note:
        This is a heuristic check. Fernet tokens start with specific prefixes.
    """
    if not token:
        return False

    # Fernet tokens are base64-encoded and start with 'gAAAAA'
    # (token version + timestamp)
    return token.startswith('gAAAAA')


def validate_encrypted_token(encrypted_token: str) -> bool:
    """
    Validate that an encrypted token can be decrypted.

    Args:
        encrypted_token: Encrypted token to validate

    Returns:
        bool: True if token is valid and can be decrypted
    """
    try:
        decrypt_token(encrypted_token)
        return True
    except Exception:
        return False


# =============================================================================
# Secure Token Comparison
# =============================================================================

def secure_compare(token1: Optional[str], token2: Optional[str]) -> bool:
    """
    Constant-time string comparison to prevent timing attacks.

    Args:
        token1: First token
        token2: Second token

    Returns:
        bool: True if tokens are equal

    Note:
        Uses secrets.compare_digest for timing-attack resistance.
    """
    if token1 is None or token2 is None:
        return token1 is token2

    import secrets
    return secrets.compare_digest(token1, token2)


# =============================================================================
# Key Rotation Support
# =============================================================================

def rotate_token_encryption(
    old_encrypted_token: str,
    old_key: str,
    new_key: str
) -> str:
    """
    Re-encrypt a token with a new encryption key.

    Use this for key rotation without losing existing tokens.

    Args:
        old_encrypted_token: Token encrypted with old key
        old_key: Old Fernet encryption key
        new_key: New Fernet encryption key

    Returns:
        str: Token encrypted with new key

    Example:
        >>> from backend.config import settings
        >>> old_key = settings.encryption_key  # Save old key first
        >>> new_key = settings.encryption_key  # After updating .env with new key
        >>> for token_row in db.query(IntegrationToken).all():
        >>>     token_row.access_token = rotate_token_encryption(
        >>>         token_row.access_token, old_key, new_key
        >>>     )
        >>>     db.commit()
    """
    # Decrypt with old key
    old_cipher = Fernet(old_key.encode())
    decrypted = old_cipher.decrypt(old_encrypted_token.encode()).decode()

    # Re-encrypt with new key
    new_cipher = Fernet(new_key.encode())
    new_encrypted = new_cipher.encrypt(decrypted.encode()).decode()

    return new_encrypted


# =============================================================================
# Module Health Check
# =============================================================================

def check_encryption_health() -> dict:
    """
    Check encryption module health and configuration.

    Returns:
        dict: Health check results

    Example:
        >>> health = check_encryption_health()
        >>> if not health["healthy"]:
        >>>     logger.error(f"Encryption unhealthy: {health['error']}")
    """
    try:
        if _cipher is None:
            return {
                "healthy": False,
                "error": "Encryption not initialized",
                "key_set": bool(settings.encryption_key)
            }

        # Test encryption/decryption
        test_token = "test_token_12345"
        encrypted = encrypt_token(test_token)
        decrypted = decrypt_token(encrypted)

        if decrypted != test_token:
            return {
                "healthy": False,
                "error": "Encryption test failed: decryption mismatch"
            }

        return {
            "healthy": True,
            "key_set": True,
            "test_passed": True
        }

    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "key_set": bool(settings.encryption_key)
        }


# =============================================================================
# Initialization Check
# =============================================================================

if __name__ == "__main__":
    print("Encryption Module Test")
    print("=" * 50)

    # Health check
    health = check_encryption_health()
    print(f"\nHealth Check: {health}")

    if health["healthy"]:
        # Test encryption
        test_token = "gho_test123456789"
        print(f"\nOriginal: {test_token}")

        encrypted = encrypt_token(test_token)
        print(f"Encrypted: {encrypted[:50]}...")

        decrypted = decrypt_token(encrypted)
        print(f"Decrypted: {decrypted}")

        print(f"\nMatch: {decrypted == test_token}")
        print("✅ Encryption module working correctly!")
    else:
        print(f"\n❌ Encryption module not initialized properly")
        print(f"Error: {health.get('error')}")
        print("\nTo fix:")
        print("1. Generate a key:")
        print("   python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'")
        print("2. Add to .env:")
        print("   ENCRYPTION_KEY=<generated-key>")
