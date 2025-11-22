"""
Test URL validation and multiple URL detection.

Tests the new URL validation functions that detect and prevent
concatenated URLs from being processed as single URLs.
"""

import pytest
from backend.sanitization import (
    detect_multiple_urls,
    validate_and_split_url,
    validate_url,
)
from fastapi import HTTPException


class TestDetectMultipleUrls:
    """Test detect_multiple_urls function."""

    def test_single_url(self):
        """Test detection of single URL."""
        url = "https://www.youtube.com/watch?v=abc123"
        result = detect_multiple_urls(url)
        assert len(result) == 1
        assert result[0] == url

    def test_two_urls_with_spaces(self):
        """Test detection of two URLs separated by spaces."""
        url = "https://example.com https://youtube.com/watch?v=123"
        result = detect_multiple_urls(url)
        assert len(result) == 2
        assert result[0] == "https://example.com"
        assert result[1] == "https://youtube.com/watch?v=123"

    def test_two_urls_with_encoded_spaces(self):
        """Test detection of two URLs with URL-encoded spaces (%20)."""
        url = "https://www.youtube.com/watch?v=EoCdf-CKEHk%20%20%20%20https://www.youtube.com/watch?v=TsOOwFBRpKc"
        result = detect_multiple_urls(url)
        assert len(result) == 2
        assert result[0] == "https://www.youtube.com/watch?v=EoCdf-CKEHk"
        assert result[1] == "https://www.youtube.com/watch?v=TsOOwFBRpKc"

    def test_multiple_urls_with_newlines(self):
        """Test detection of URLs separated by newlines."""
        url = "https://example.com\nhttps://youtube.com/watch?v=123\nhttps://wikipedia.org"
        result = detect_multiple_urls(url)
        assert len(result) == 3

    def test_empty_string(self):
        """Test empty string returns empty list."""
        result = detect_multiple_urls("")
        assert len(result) == 0

    def test_no_urls(self):
        """Test string with no URLs returns empty list."""
        result = detect_multiple_urls("just some text without urls")
        assert len(result) == 0

    def test_urls_with_commas(self):
        """Test URLs separated by commas."""
        url = "https://example.com,https://youtube.com"
        result = detect_multiple_urls(url)
        assert len(result) == 2

    def test_urls_with_semicolons(self):
        """Test URLs separated by semicolons."""
        url = "https://example.com;https://youtube.com"
        result = detect_multiple_urls(url)
        assert len(result) == 2

    def test_url_with_trailing_punctuation(self):
        """Test URL with trailing punctuation is cleaned."""
        url = "https://example.com."
        result = detect_multiple_urls(url)
        assert len(result) == 1
        assert result[0] == "https://example.com"


class TestValidateAndSplitUrl:
    """Test validate_and_split_url function."""

    def test_valid_single_url(self):
        """Test valid single URL passes validation."""
        url = "https://www.youtube.com/watch?v=abc123"
        is_valid, urls, error = validate_and_split_url(url)
        assert is_valid is True
        assert len(urls) == 1
        assert error is None

    def test_multiple_urls_rejected(self):
        """Test multiple URLs are rejected with helpful error."""
        url = "https://example.com https://youtube.com/watch?v=123"
        is_valid, urls, error = validate_and_split_url(url)
        assert is_valid is False
        assert len(urls) == 2
        assert "Multiple URLs detected" in error
        assert "batch upload endpoint" in error

    def test_concatenated_urls_with_encoded_spaces(self):
        """Test concatenated URLs with %20 are rejected."""
        url = "https://www.youtube.com/watch?v=EoCdf-CKEHk%20%20%20%20https://www.youtube.com/watch?v=TsOOwFBRpKc"
        is_valid, urls, error = validate_and_split_url(url)
        assert is_valid is False
        assert len(urls) == 2
        assert "Multiple URLs detected" in error

    def test_empty_url(self):
        """Test empty URL is rejected."""
        is_valid, urls, error = validate_and_split_url("")
        assert is_valid is False
        assert len(urls) == 0
        assert "empty" in error.lower()

    def test_no_valid_urls(self):
        """Test string with no URLs is rejected."""
        is_valid, urls, error = validate_and_split_url("just some text")
        assert is_valid is False
        assert len(urls) == 0
        assert "No valid URLs detected" in error

    def test_too_many_urls(self):
        """Test too many URLs are rejected."""
        # Create 11 URLs (max is 10)
        urls_list = [f"https://example{i}.com" for i in range(11)]
        url = " ".join(urls_list)
        is_valid, urls, error = validate_and_split_url(url, max_urls=10)
        assert is_valid is False
        assert "Too many URLs" in error or "Multiple URLs" in error

    def test_localhost_url_rejected(self):
        """Test localhost URL is rejected for security."""
        url = "http://localhost:8000/admin"
        is_valid, urls, error = validate_and_split_url(url)
        assert is_valid is False
        assert "internal" in error.lower() or "private" in error.lower()

    def test_file_protocol_rejected(self):
        """Test file:// protocol is rejected."""
        url = "file:///etc/passwd"
        is_valid, urls, error = validate_and_split_url(url)
        assert is_valid is False


class TestValidateUrl:
    """Test basic validate_url function."""

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        url = "https://www.example.com/article"
        result = validate_url(url)
        assert result == url

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        url = "http://www.example.com/article"
        result = validate_url(url)
        assert result == url

    def test_localhost_rejected(self):
        """Test localhost is rejected."""
        with pytest.raises(HTTPException) as exc:
            validate_url("http://localhost/admin")
        assert exc.value.status_code == 400
        assert "internal" in str(exc.value.detail).lower()

    def test_private_ip_rejected(self):
        """Test private IP is rejected."""
        with pytest.raises(HTTPException) as exc:
            validate_url("http://192.168.1.1/admin")
        assert exc.value.status_code == 400

    def test_file_protocol_rejected(self):
        """Test file:// protocol is rejected."""
        with pytest.raises(HTTPException) as exc:
            validate_url("file:///etc/passwd")
        assert exc.value.status_code == 400
        assert "scheme" in str(exc.value.detail).lower()

    def test_empty_url_rejected(self):
        """Test empty URL is rejected."""
        with pytest.raises(HTTPException) as exc:
            validate_url("")
        assert exc.value.status_code == 400

    def test_url_too_long_rejected(self):
        """Test very long URL is rejected."""
        long_url = "https://example.com/" + "a" * 3000
        with pytest.raises(HTTPException) as exc:
            validate_url(long_url)
        assert exc.value.status_code == 400
        assert "too long" in str(exc.value.detail).lower()


class TestRealWorldScenarios:
    """Test real-world scenarios that caused the bug."""

    def test_original_bug_scenario(self):
        """Test the exact scenario that caused doc 4 to be malformed."""
        # This is the exact URL that was stored in the database
        malformed_url = "https://www.youtube.com/watch?v=EoCdf-CKEHk%20%20%20%20https://www.youtube.com/watch?v=TsOOwFBRpKc"

        # Detect multiple URLs
        detected = detect_multiple_urls(malformed_url)
        assert len(detected) == 2
        assert "EoCdf-CKEHk" in detected[0]
        assert "TsOOwFBRpKc" in detected[1]

        # Validation should reject this
        is_valid, urls, error = validate_and_split_url(malformed_url)
        assert is_valid is False
        assert len(urls) == 2
        assert "Multiple URLs detected" in error

    def test_copy_paste_from_browser(self):
        """Test URLs copy-pasted from browser with extra whitespace."""
        url = "  https://www.youtube.com/watch?v=abc123  "
        detected = detect_multiple_urls(url)
        assert len(detected) == 1

    def test_urls_from_email_with_newlines(self):
        """Test URLs from email that may have newlines."""
        url = "Check out these videos:\nhttps://www.youtube.com/watch?v=abc123\nhttps://www.youtube.com/watch?v=def456"
        detected = detect_multiple_urls(url)
        assert len(detected) == 2
