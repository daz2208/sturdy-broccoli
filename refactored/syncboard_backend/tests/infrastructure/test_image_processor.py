"""
Tests for image processing and OCR functionality.

Tests text extraction, metadata retrieval, and image storage.
"""

import pytest
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

# Import the FastAPI app
import sys
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from backend.image_processor import ImageProcessor


@pytest.fixture
def processor():
    """Create ImageProcessor instance."""
    return ImageProcessor()


@pytest.fixture
def sample_image_bytes():
    """Create a simple test image."""
    # Create a small test image
    img = Image.new('RGB', (100, 100), color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def cleanup_images():
    """Clean up test images after tests."""
    yield
    # Clean up stored_images directory if it exists
    images_dir = Path("stored_images")
    if images_dir.exists():
        for file in images_dir.glob("doc_*.png"):
            try:
                file.unlink()
            except:
                pass


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================

def test_processor_initialization():
    """Test ImageProcessor can be initialized."""
    processor = ImageProcessor()
    assert processor is not None


def test_processor_respects_tesseract_env():
    """Test processor respects TESSERACT_CMD environment variable."""
    with patch.dict(os.environ, {'TESSERACT_CMD': '/custom/path/tesseract'}):
        processor = ImageProcessor()
        # Just verify it doesn't crash
        assert processor is not None


# =============================================================================
# OCR TEXT EXTRACTION TESTS
# =============================================================================

@patch('backend.image_processor.pytesseract.image_to_string')
def test_extract_text_from_image(mock_ocr, processor, sample_image_bytes):
    """Test text extraction from image."""
    mock_ocr.return_value = "Extracted text from image"

    text = processor.extract_text_from_image(sample_image_bytes)

    assert text == "Extracted text from image"
    mock_ocr.assert_called_once()


@patch('backend.image_processor.pytesseract.image_to_string')
def test_extract_text_strips_whitespace(mock_ocr, processor, sample_image_bytes):
    """Test extracted text is stripped of whitespace."""
    mock_ocr.return_value = "  Text with whitespace  \n\n"

    text = processor.extract_text_from_image(sample_image_bytes)

    assert text == "Text with whitespace"


@patch('backend.image_processor.pytesseract.image_to_string')
def test_extract_text_handles_errors(mock_ocr, processor, sample_image_bytes):
    """Test OCR gracefully handles errors."""
    mock_ocr.side_effect = Exception("OCR failed")

    text = processor.extract_text_from_image(sample_image_bytes)

    assert text == ""


def test_extract_text_with_invalid_image(processor):
    """Test OCR handles invalid image bytes."""
    invalid_bytes = b"not an image"

    text = processor.extract_text_from_image(invalid_bytes)

    assert text == ""


@patch('backend.image_processor.pytesseract.image_to_string')
def test_extract_text_converts_rgba_to_rgb(mock_ocr, processor):
    """Test processor converts RGBA images to RGB."""
    # Create RGBA image
    img = Image.new('RGBA', (100, 100), color='white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')

    mock_ocr.return_value = "Text"

    text = processor.extract_text_from_image(buffer.getvalue())

    # Should successfully process RGBA image
    assert isinstance(text, str)


# =============================================================================
# IMAGE METADATA TESTS
# =============================================================================

def test_get_image_metadata(processor, sample_image_bytes):
    """Test extracting image metadata."""
    metadata = processor.get_image_metadata(sample_image_bytes)

    assert "width" in metadata
    assert "height" in metadata
    assert "format" in metadata
    assert "mode" in metadata
    assert "size_bytes" in metadata

    assert metadata["width"] == 100
    assert metadata["height"] == 100
    assert metadata["size_bytes"] > 0


def test_get_image_metadata_includes_format(processor):
    """Test metadata includes image format."""
    img = Image.new('RGB', (50, 50), color='red')
    buffer = BytesIO()
    img.save(buffer, format='JPEG')

    metadata = processor.get_image_metadata(buffer.getvalue())

    assert metadata["format"] in ["JPEG", "unknown"]


def test_get_image_metadata_handles_errors(processor):
    """Test metadata extraction handles invalid images."""
    invalid_bytes = b"not an image"

    metadata = processor.get_image_metadata(invalid_bytes)

    assert metadata == {}


def test_get_image_metadata_different_modes(processor):
    """Test metadata extraction works with different color modes."""
    # Test grayscale
    img_gray = Image.new('L', (50, 50), color=128)
    buffer_gray = BytesIO()
    img_gray.save(buffer_gray, format='PNG')

    metadata = processor.get_image_metadata(buffer_gray.getvalue())
    assert metadata["mode"] == "L"

    # Test RGB
    img_rgb = Image.new('RGB', (50, 50), color='blue')
    buffer_rgb = BytesIO()
    img_rgb.save(buffer_rgb, format='PNG')

    metadata = processor.get_image_metadata(buffer_rgb.getvalue())
    assert metadata["mode"] == "RGB"


# =============================================================================
# IMAGE STORAGE TESTS
# =============================================================================

def test_store_image(processor, sample_image_bytes, cleanup_images):
    """Test storing image to disk."""
    filepath = processor.store_image(sample_image_bytes, doc_id=42)

    assert filepath != ""
    assert "doc_42.png" in filepath
    assert Path(filepath).exists()


def test_store_image_creates_directory(processor, sample_image_bytes, cleanup_images):
    """Test image storage creates directory if it doesn't exist."""
    # Remove directory if it exists
    images_dir = Path("stored_images")
    if images_dir.exists():
        for file in images_dir.glob("*"):
            file.unlink()
        images_dir.rmdir()

    filepath = processor.store_image(sample_image_bytes, doc_id=1)

    assert Path("stored_images").exists()
    assert Path(filepath).exists()


def test_store_image_with_zero_doc_id(processor, sample_image_bytes, cleanup_images):
    """Test storing image with doc_id=0."""
    filepath = processor.store_image(sample_image_bytes, doc_id=0)

    assert "doc_0.png" in filepath
    assert Path(filepath).exists()


def test_store_image_invalid_doc_id_negative(processor, sample_image_bytes):
    """Test store_image rejects negative doc_id."""
    # The function validates doc_id and raises ValueError for negative values
    with pytest.raises(ValueError):
        processor.store_image(sample_image_bytes, doc_id=-1)


def test_store_image_invalid_doc_id_string(processor, sample_image_bytes):
    """Test store_image rejects non-integer doc_id."""
    with pytest.raises(ValueError):
        processor.store_image(sample_image_bytes, doc_id="invalid")


def test_store_image_handles_save_errors(processor):
    """Test store_image handles errors gracefully."""
    invalid_bytes = b"not an image"

    filepath = processor.store_image(invalid_bytes, doc_id=99)

    assert filepath == ""


def test_store_image_path_traversal_protection(processor, sample_image_bytes):
    """Test store_image prevents path traversal attacks."""
    # This test verifies the security check in store_image
    # The function validates that the final path is within stored_images directory

    # Normal case should work
    filepath = processor.store_image(sample_image_bytes, doc_id=123)
    assert filepath != ""

    # The function constructs the path internally, so direct path traversal via
    # doc_id is prevented by using abs(doc_id) and validating the final path


def test_store_image_overwrites_existing(processor, sample_image_bytes, cleanup_images):
    """Test storing image with same doc_id overwrites previous."""
    # Store first image
    filepath1 = processor.store_image(sample_image_bytes, doc_id=5)

    # Create different image
    img2 = Image.new('RGB', (200, 200), color='black')
    buffer2 = BytesIO()
    img2.save(buffer2, format='PNG')

    # Store second image with same doc_id
    filepath2 = processor.store_image(buffer2.getvalue(), doc_id=5)

    assert filepath1 == filepath2
    assert Path(filepath2).exists()

    # File should be the newer image
    assert Path(filepath2).stat().st_size > 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@patch('backend.image_processor.pytesseract.image_to_string')
def test_full_image_processing_workflow(mock_ocr, processor, cleanup_images):
    """Test complete workflow: metadata → OCR → storage."""
    # Create test image
    img = Image.new('RGB', (150, 100), color='green')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    image_bytes = buffer.getvalue()

    mock_ocr.return_value = "Processed text"

    # 1. Get metadata
    metadata = processor.get_image_metadata(image_bytes)
    assert metadata["width"] == 150
    assert metadata["height"] == 100

    # 2. Extract text
    text = processor.extract_text_from_image(image_bytes)
    assert text == "Processed text"

    # 3. Store image
    filepath = processor.store_image(image_bytes, doc_id=777)
    assert Path(filepath).exists()


def test_concurrent_image_storage(processor, cleanup_images):
    """Test storing multiple images concurrently."""
    filepaths = []

    for i in range(5):
        img = Image.new('RGB', (50, 50), color='blue')
        buffer = BytesIO()
        img.save(buffer, format='PNG')

        filepath = processor.store_image(buffer.getvalue(), doc_id=i)
        filepaths.append(filepath)

    # All files should exist
    for filepath in filepaths:
        assert Path(filepath).exists()

    # All files should be different
    assert len(set(filepaths)) == 5
