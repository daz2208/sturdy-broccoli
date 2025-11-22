"""
Test suite for ZIP content cleaning for AI processing.

Verifies that formatting metadata is removed while keeping actual content.
"""

import pytest
from backend.ingest import clean_zip_content_for_ai


def test_clean_zip_removes_headers():
    """Test that ZIP headers are removed."""
    input_text = """ZIP ARCHIVE: project.zip
Files: 5 total, 5 processed, 0 skipped
Total size: 2.4 MB
Files processed so far: 5/1000

CONTENTS:
------------------------------------------------------------

=== src/main.py ===
def main():
    print("Hello World")

------------------------------------------------------------

SUMMARY:
Processed: 5 files
Skipped: 0 files
Success rate: 100.0%"""

    result = clean_zip_content_for_ai(input_text)

    # Should not contain ZIP metadata
    assert 'ZIP ARCHIVE' not in result
    assert 'Files:' not in result
    assert 'Total size:' not in result
    assert 'CONTENTS:' not in result
    assert 'SUMMARY:' not in result
    assert 'Processed:' not in result

    # Should contain actual code
    assert 'def main():' in result
    assert 'print("Hello World")' in result


def test_clean_zip_keeps_code_content():
    """Test that actual code content is preserved."""
    input_text = """ZIP ARCHIVE: code.zip
=== app.py ===
SOURCE CODE FILE: app.py
Language: Python

CODE:
import flask

app = flask.Flask(__name__)

@app.route('/')
def home():
    return "Hello"

------------------------------------------------------------

=== README.md ===
# Project Title
This is a README file

------------------------------------------------------------"""

    result = clean_zip_content_for_ai(input_text)

    # Should contain code
    assert 'import flask' in result
    assert 'app = flask.Flask(__name__)' in result
    assert '@app.route' in result
    assert 'def home():' in result

    # Should contain README content
    assert '# Project Title' in result
    assert 'This is a README file' in result


def test_clean_zip_handles_nested_zips():
    """Test cleaning output from nested ZIPs."""
    input_text = """ZIP ARCHIVE: outer.zip

=== nested.zip (NESTED ZIP) ===
ZIP ARCHIVE: nested.zip (Depth: 1/5)
Files: 2 total, 2 processed

=== inner_file.txt ===
This is content from a nested ZIP

------------------------------------------------------------

GLOBAL STATISTICS:
Total files processed: 3
Nested ZIPs found: 1
Max depth reached: 1"""

    result = clean_zip_content_for_ai(input_text)

    # Should contain actual content
    assert 'This is content from a nested ZIP' in result

    # Should not contain metadata
    assert 'NESTED ZIP' not in result
    assert 'Depth: 1/5' not in result
    assert 'GLOBAL STATISTICS' not in result
    assert 'Nested ZIPs found' not in result


def test_clean_zip_removes_separators():
    """Test that separator lines are removed."""
    input_text = """=== file1.txt ===
Content 1
============================================================
=== file2.txt ===
Content 2
------------------------------------------------------------"""

    result = clean_zip_content_for_ai(input_text)

    # Should contain content
    assert 'Content 1' in result
    assert 'Content 2' in result

    # Should not contain separator lines
    assert '============' not in result
    assert '----' not in result


def test_clean_zip_handles_multiple_files():
    """Test cleaning with multiple extracted files."""
    input_text = """ZIP ARCHIVE: project.zip

=== utils.py ===
def helper():
    return 42

=== config.json ===
{
  "setting": "value"
}

=== data.csv ===
name,age
Alice,30"""

    result = clean_zip_content_for_ai(input_text)

    # All content should be present
    assert 'def helper():' in result
    assert 'return 42' in result
    assert '"setting": "value"' in result
    assert 'name,age' in result
    assert 'Alice,30' in result


def test_clean_zip_preserves_file_boundaries():
    """Test that files are separated appropriately."""
    input_text = """=== file1.txt ===
First file content

=== file2.txt ===
Second file content"""

    result = clean_zip_content_for_ai(input_text)

    # Content should be present
    assert 'First file content' in result
    assert 'Second file content' in result

    # Files should be separated (either by --- or blank lines)
    # The important thing is they're not mashed together
    assert 'First file contentSecond file content' not in result.replace('\n', '').replace(' ', '')


def test_clean_zip_removes_error_messages():
    """Test that error/skip messages are removed."""
    input_text = """=== file1.txt ===
Good content

⚠️  SKIPPED (too large): huge_file.bin
   Size: 50.0 MB

⚠️  FAILED: broken_file.txt
   Error: Could not decode

=== file2.txt ===
More good content"""

    result = clean_zip_content_for_ai(input_text)

    # Good content should be present
    assert 'Good content' in result
    assert 'More good content' in result

    # Error messages should be removed
    assert '⚠️' not in result
    assert 'SKIPPED' not in result
    assert 'FAILED' not in result
    assert 'too large' not in result


def test_clean_zip_empty_input():
    """Test handling of empty input."""
    result = clean_zip_content_for_ai("")
    assert result == ""


def test_clean_zip_only_metadata():
    """Test input with only metadata (no content)."""
    input_text = """ZIP ARCHIVE: empty.zip
Files: 0 total, 0 processed
SUMMARY:
Processed: 0 files"""

    result = clean_zip_content_for_ai(input_text)

    # Should be empty or nearly empty after cleaning
    assert len(result.strip()) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
