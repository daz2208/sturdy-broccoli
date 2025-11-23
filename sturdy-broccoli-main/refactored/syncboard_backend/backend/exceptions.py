"""
Custom Exceptions for SyncBoard Backend.

Provides specific exception types for different error scenarios,
improving error handling, debugging, and user-facing error messages.
"""


class SyncBoardError(Exception):
    """Base exception for all SyncBoard errors."""
    pass


# =============================================================================
# File Processing Exceptions
# =============================================================================

class FileProcessingError(SyncBoardError):
    """Raised when file processing fails."""
    pass


class UnsupportedFileTypeError(FileProcessingError):
    """Raised when an unsupported file type is uploaded."""

    def __init__(self, file_type: str, supported_types: list = None):
        self.file_type = file_type
        self.supported_types = supported_types or []
        msg = f"Unsupported file type: {file_type}"
        if supported_types:
            msg += f". Supported types: {', '.join(supported_types)}"
        super().__init__(msg)


class FileTooLargeError(FileProcessingError):
    """Raised when a file exceeds the maximum allowed size."""

    def __init__(self, size: int, max_size: int):
        self.size = size
        self.max_size = max_size
        super().__init__(f"File size ({size} bytes) exceeds maximum ({max_size} bytes)")


class FileDecodingError(FileProcessingError):
    """Raised when a file cannot be decoded."""

    def __init__(self, filename: str, encoding: str = None):
        self.filename = filename
        self.encoding = encoding
        msg = f"Failed to decode file: {filename}"
        if encoding:
            msg += f" (tried {encoding})"
        super().__init__(msg)


# =============================================================================
# Transcription Exceptions
# =============================================================================

class TranscriptionError(SyncBoardError):
    """Raised when audio/video transcription fails."""
    pass


class TranscriptionServiceUnavailable(TranscriptionError):
    """Raised when the transcription service is not available."""

    def __init__(self, service: str = "whisper"):
        self.service = service
        super().__init__(f"Transcription service '{service}' is unavailable")


class TranscriptionTimeoutError(TranscriptionError):
    """Raised when transcription takes too long."""

    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Transcription timed out after {timeout_seconds} seconds")


# =============================================================================
# URL/Network Exceptions
# =============================================================================

class URLValidationError(SyncBoardError):
    """Raised when URL validation fails."""
    pass


class SSRFAttemptError(URLValidationError):
    """Raised when a potential SSRF attack is detected."""

    def __init__(self, url: str):
        self.url = url
        super().__init__(f"Access to internal/private URLs is forbidden: {url}")


class URLFetchError(SyncBoardError):
    """Raised when fetching URL content fails."""

    def __init__(self, url: str, reason: str = None):
        self.url = url
        self.reason = reason
        msg = f"Failed to fetch URL: {url}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


# =============================================================================
# ZIP/Archive Exceptions
# =============================================================================

class ZIPExtractionError(FileProcessingError):
    """Raised when ZIP extraction fails."""
    pass


class ZIPBombDetectedError(ZIPExtractionError):
    """Raised when a potential ZIP bomb is detected."""

    def __init__(self, reason: str = "Compression ratio too high"):
        self.reason = reason
        super().__init__(f"Potential ZIP bomb detected: {reason}")


class ZIPExtractionTimeoutError(ZIPExtractionError):
    """Raised when ZIP extraction times out."""

    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"ZIP extraction timed out after {timeout_seconds} seconds")


class ZIPNestingLimitError(ZIPExtractionError):
    """Raised when ZIP nesting exceeds the allowed depth."""

    def __init__(self, depth: int, max_depth: int):
        self.depth = depth
        self.max_depth = max_depth
        super().__init__(f"ZIP nesting depth ({depth}) exceeds maximum ({max_depth})")


# =============================================================================
# AI/LLM Exceptions
# =============================================================================

class LLMError(SyncBoardError):
    """Base exception for LLM-related errors."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when LLM API rate limit is exceeded."""

    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        msg = "LLM API rate limit exceeded"
        if retry_after:
            msg += f". Retry after {retry_after} seconds"
        super().__init__(msg)


class LLMResponseParseError(LLMError):
    """Raised when LLM response cannot be parsed."""

    def __init__(self, expected_format: str = "JSON"):
        self.expected_format = expected_format
        super().__init__(f"Failed to parse LLM response as {expected_format}")


class ConceptExtractionError(LLMError):
    """Raised when concept extraction fails."""
    pass


# =============================================================================
# Authentication Exceptions
# =============================================================================

class AuthenticationError(SyncBoardError):
    """Base exception for authentication errors."""
    pass


class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""

    def __init__(self):
        super().__init__("Invalid username or password")


class TokenExpiredError(AuthenticationError):
    """Raised when authentication token has expired."""

    def __init__(self):
        super().__init__("Authentication token has expired")


# =============================================================================
# Configuration Exceptions
# =============================================================================

class ConfigurationError(SyncBoardError):
    """Raised when there's a configuration problem."""

    def __init__(self, setting: str, reason: str = None):
        self.setting = setting
        self.reason = reason
        msg = f"Configuration error: {setting}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class MissingAPIKeyError(ConfigurationError):
    """Raised when a required API key is missing."""

    def __init__(self, key_name: str):
        self.key_name = key_name
        super().__init__(key_name, "API key not configured")
