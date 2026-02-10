import sys
import os
import platform
import pytest
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import config
from core.ingestion import DocProcessor, Chunk

def test_environment_detection():
    """Verify that the environment detection logic works."""
    print(f"\nDetected OS: {config.os_type}")
    print(f"Detected Device: {config.device}")
    
    if platform.system() == "Darwin":
        assert config.os_type == "Darwin"
        # On GitHub Actions macos-latest runners (Intel), device might be CPU
        # On M1 runners, it might be MPS. 
        # We just check it's one of the valid options.
        assert config.device in ["cpu", "mps", "cuda"]
    elif platform.system() == "Windows":
        assert config.os_type == "Windows"

def test_doc_processor_basic():
    """Test basic chunking logic without needing a real file."""
    processor = DocProcessor(max_chars=50, window_size=2, overlap=1)
    
    # Test text cleaning
    raw_text = "  Hello   World!  \n  "
    cleaned = processor._clean_text(raw_text)
    assert cleaned == "Hello World!"
    
    # Test sliding window (direct method call for unit testing)
    long_text = "Sentence one. Sentence two. Sentence three. Sentence four."
    chunks = processor._sliding_window(long_text, index=0, source_type='paragraph')
    
    # window_size=2, overlap=1
    # Expected: [1,2], [2,3], [3,4]
    # "Sentence one. Sentence two."
    # "Sentence two. Sentence three."
    # "Sentence three. Sentence four."
    
    assert len(chunks) >= 2
    assert "Sentence one" in chunks[0].text
    assert "Sentence two" in chunks[0].text
    assert "Sentence two" in chunks[1].text  # Overlap check

@pytest.mark.skipif(not os.path.exists("test_contract.docx"), reason="Test file not found")
def test_integration_with_file():
    """Test ingestion with the generated test file."""
    processor = DocProcessor()
    chunks = processor.process("test_contract.docx")
    assert len(chunks) > 0
    # Check if we found the table
    table_chunks = [c for c in chunks if c.source_type == 'table']
    assert len(table_chunks) > 0
