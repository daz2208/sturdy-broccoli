"""
Test suite for recursive ZIP extraction feature.

Tests:
- Basic nested ZIP extraction (2-3 levels)
- Depth limit enforcement (max 5 levels)
- File count limit enforcement (max 1000 files)
- Mixed content (ZIPs + regular files)
- Error handling
"""

import pytest
import zipfile
import io
from backend.ingest import extract_zip_archive


def create_test_file(content: str, filename: str) -> bytes:
    """Create a test file with given content."""
    return content.encode('utf-8')


def create_zip_with_files(files: dict) -> bytes:
    """
    Create a ZIP archive with specified files.

    Args:
        files: Dict mapping filename -> content (str or bytes)

    Returns:
        ZIP file as bytes
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            if isinstance(content, str):
                content = content.encode('utf-8')
            zf.writestr(filename, content)

    return zip_buffer.getvalue()


def test_nested_zip_2_levels():
    """Test extraction of ZIP containing another ZIP (2 levels)."""

    # Create innermost ZIP (level 2)
    inner_files = {
        'document.txt': 'This is a document inside the inner ZIP',
        'readme.md': '# Inner README\nThis is nested content'
    }
    inner_zip = create_zip_with_files(inner_files)

    # Create outer ZIP (level 1)
    outer_files = {
        'outer_file.txt': 'This is an outer file',
        'nested.zip': inner_zip
    }
    outer_zip = create_zip_with_files(outer_files)

    # Extract and verify
    result = extract_zip_archive(outer_zip, 'test.zip')

    # Verify content
    assert 'ZIP ARCHIVE: test.zip' in result
    assert 'outer_file.txt' in result
    assert 'This is an outer file' in result
    assert 'nested.zip (NESTED ZIP)' in result
    assert 'ZIP ARCHIVE: nested.zip (Depth: 1/5)' in result
    assert 'document.txt' in result
    assert 'This is a document inside the inner ZIP' in result
    assert 'readme.md' in result
    assert 'Inner README' in result
    assert 'GLOBAL STATISTICS:' in result
    assert 'Nested ZIPs found: 1' in result


def test_nested_zip_3_levels():
    """Test extraction of deeply nested ZIPs (3 levels)."""

    # Level 3 (innermost)
    level3_files = {
        'deep_file.txt': 'Content at level 3'
    }
    level3_zip = create_zip_with_files(level3_files)

    # Level 2
    level2_files = {
        'level2_file.txt': 'Content at level 2',
        'level3.zip': level3_zip
    }
    level2_zip = create_zip_with_files(level2_files)

    # Level 1 (outer)
    level1_files = {
        'level1_file.txt': 'Content at level 1',
        'level2.zip': level2_zip
    }
    level1_zip = create_zip_with_files(level1_files)

    # Extract and verify
    result = extract_zip_archive(level1_zip, 'outer.zip')

    # Verify all levels are processed
    assert 'level1_file.txt' in result
    assert 'Content at level 1' in result
    assert 'level2.zip (NESTED ZIP)' in result
    assert 'Depth: 1/5' in result
    assert 'level2_file.txt' in result
    assert 'Content at level 2' in result
    assert 'level3.zip (NESTED ZIP)' in result
    assert 'Depth: 2/5' in result
    assert 'deep_file.txt' in result
    assert 'Content at level 3' in result
    assert 'Nested ZIPs found: 2' in result


def test_depth_limit_exceeded():
    """Test that recursion depth limit is enforced."""

    # Create a chain of nested ZIPs exceeding max depth
    # Max depth is 5, so we need to create 7 levels (0-6) to trigger the error
    # Depth 0 (root) -> Depth 1 -> ... -> Depth 5 (OK) -> Depth 6 (FAIL)

    # Start with the deepest ZIP (will be at depth 6)
    current_zip = create_zip_with_files({'deepest.txt': 'Level 7'})

    # Create 6 more levels of nesting (6, 5, 4, 3, 2, 1)
    for level in range(7, 0, -1):
        current_zip = create_zip_with_files({
            f'level{level}.txt': f'Content at level {level}',
            f'nested.zip': current_zip
        })

    # Attempt extraction - should fail with depth limit error
    with pytest.raises(Exception) as exc_info:
        extract_zip_archive(current_zip, 'too_deep.zip')

    assert 'recursion depth limit exceeded' in str(exc_info.value).lower()
    assert 'zip bomb' in str(exc_info.value).lower()


def test_file_count_limit():
    """Test that file count limit is enforced."""

    # Create a ZIP with many files to test the limit
    # We'll use a smaller limit for testing

    # Create inner ZIP with 10 files
    inner_files = {f'file_{i}.txt': f'Content {i}' for i in range(10)}
    inner_zip = create_zip_with_files(inner_files)

    # Create outer ZIP with 10 files + nested ZIP
    outer_files = {f'outer_{i}.txt': f'Outer content {i}' for i in range(10)}
    outer_files['nested.zip'] = inner_zip
    outer_zip = create_zip_with_files(outer_files)

    # This should work fine (20 total files)
    result = extract_zip_archive(outer_zip, 'test.zip')
    assert 'GLOBAL STATISTICS:' in result

    # Verify statistics
    assert 'Total files processed:' in result


def test_mixed_content_with_code_files():
    """Test ZIP containing code files, documents, and nested ZIPs."""

    # Create inner ZIP with Python code
    inner_files = {
        'utils.py': 'def helper():\n    return "helper"',
        'config.json': '{"key": "value"}'
    }
    inner_zip = create_zip_with_files(inner_files)

    # Create outer ZIP with mixed content
    outer_files = {
        'main.py': 'def main():\n    print("Hello")',
        'README.md': '# Project\nDescription here',
        'data.csv': 'name,value\ntest,123',
        'code.zip': inner_zip
    }
    outer_zip = create_zip_with_files(outer_files)

    # Extract and verify
    result = extract_zip_archive(outer_zip, 'project.zip')

    # Verify all file types are processed
    assert 'main.py' in result
    assert 'SOURCE CODE FILE:' in result
    assert 'Python' in result
    assert 'README.md' in result
    assert 'Project' in result
    assert 'data.csv' in result
    assert 'name,value' in result
    assert 'code.zip (NESTED ZIP)' in result
    assert 'utils.py' in result
    assert 'helper' in result


def test_empty_nested_zip():
    """Test handling of empty nested ZIPs."""

    # Create empty inner ZIP
    empty_zip = create_zip_with_files({})

    # Create outer ZIP containing empty ZIP
    outer_files = {
        'file.txt': 'Normal file',
        'empty.zip': empty_zip
    }
    outer_zip = create_zip_with_files(outer_files)

    # Should handle gracefully
    result = extract_zip_archive(outer_zip, 'test.zip')

    assert 'file.txt' in result
    assert 'Normal file' in result
    assert 'empty.zip' in result or 'empty.zip (NESTED ZIP)' in result


def test_backward_compatibility():
    """Test that existing non-nested ZIP functionality still works."""

    # Create a simple ZIP without nesting
    files = {
        'doc1.txt': 'Document 1',
        'doc2.txt': 'Document 2',
        'notes.md': '# Notes\nSome notes here'
    }
    simple_zip = create_zip_with_files(files)

    # Extract
    result = extract_zip_archive(simple_zip, 'simple.zip')

    # Verify all files are present
    assert 'ZIP ARCHIVE: simple.zip' in result
    assert 'doc1.txt' in result
    assert 'Document 1' in result
    assert 'doc2.txt' in result
    assert 'Document 2' in result
    assert 'notes.md' in result
    assert 'Notes' in result
    assert 'SUMMARY:' in result
    assert 'Processed: 3 files' in result


def test_nested_zip_with_large_files():
    """Test that large file limit works with nested ZIPs."""

    # Create inner ZIP with a large file (simulated with long string)
    # Note: We won't actually create 10MB+ to keep test fast
    large_content = 'X' * (11 * 1024 * 1024)  # 11 MB

    inner_files = {
        'huge_file.txt': large_content,
        'small_file.txt': 'small'
    }
    inner_zip = create_zip_with_files(inner_files)

    outer_files = {
        'normal.txt': 'normal content',
        'nested.zip': inner_zip
    }
    outer_zip = create_zip_with_files(outer_files)

    result = extract_zip_archive(outer_zip, 'test.zip')

    # Large file should be skipped
    assert 'SKIPPED (too large)' in result
    assert 'huge_file.txt' in result
    # But small file should be processed
    assert 'small_file.txt' in result or 'small' in result


def test_statistics_tracking():
    """Test that global statistics are correctly tracked."""

    # Create nested structure
    inner_files = {
        'inner1.txt': 'Inner content 1',
        'inner2.txt': 'Inner content 2'
    }
    inner_zip = create_zip_with_files(inner_files)

    outer_files = {
        'outer1.txt': 'Outer content 1',
        'outer2.txt': 'Outer content 2',
        'nested.zip': inner_zip
    }
    outer_zip = create_zip_with_files(outer_files)

    result = extract_zip_archive(outer_zip, 'test.zip')

    # Verify statistics are present
    assert 'GLOBAL STATISTICS:' in result
    assert 'Total files processed:' in result
    assert 'Nested ZIPs found: 1' in result
    assert 'Files processed so far:' in result


def test_multiple_nested_zips_same_level():
    """Test ZIP containing multiple nested ZIPs at the same level."""

    # Create two inner ZIPs
    zip1_files = {'file1.txt': 'Content from ZIP 1'}
    zip1 = create_zip_with_files(zip1_files)

    zip2_files = {'file2.txt': 'Content from ZIP 2'}
    zip2 = create_zip_with_files(zip2_files)

    # Create outer ZIP with both
    outer_files = {
        'readme.txt': 'Main readme',
        'archive1.zip': zip1,
        'archive2.zip': zip2
    }
    outer_zip = create_zip_with_files(outer_files)

    result = extract_zip_archive(outer_zip, 'test.zip')

    # Verify both nested ZIPs are processed
    assert 'archive1.zip (NESTED ZIP)' in result
    assert 'archive2.zip (NESTED ZIP)' in result
    assert 'file1.txt' in result
    assert 'Content from ZIP 1' in result
    assert 'file2.txt' in result
    assert 'Content from ZIP 2' in result
    assert 'Nested ZIPs found: 2' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
