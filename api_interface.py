import os
import threading
from core.search_engine import SemanticSearchEngine
from core.ingestion import DocProcessor

# Global instance
_engine_instance = None
_processor = DocProcessor()
_lock = threading.Lock()

def init_engine():
    """
    Initialize the search engine.
    """
    global _engine_instance
    with _lock:
        if _engine_instance is None:
            _engine_instance = SemanticSearchEngine()
    return _engine_instance

def process_file(file_path: str):
    """
    Process a .docx file and load it into the engine.
    """
    if _engine_instance is None:
        raise RuntimeError("Engine not initialized. Call init_engine() first.")
    
    # Check file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    chunks = _processor.process(file_path)
    _engine_instance.load_document(chunks)
    return {
        "status": "success",
        "chunk_count": len(chunks)
    }

def search_query(text: str, top_k: int = 10):
    """
    Search the loaded document.
    """
    if _engine_instance is None:
        raise RuntimeError("Engine not initialized. Call init_engine() first.")
        
    results = _engine_instance.search(text, top_k=top_k)
    return results

if __name__ == "__main__":
    # Simple CLI test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python api_interface.py <path_to_docx> [query]")
        sys.exit(1)
        
    docx_path = sys.argv[1]
    query_text = sys.argv[2] if len(sys.argv) > 2 else "termination clause"
    
    print("Initializing engine...")
    init_engine()
    
    print(f"Processing {docx_path}...")
    try:
        res = process_file(docx_path)
        print(f"Processed {res['chunk_count']} chunks.")
    except Exception as e:
        print(f"Error processing file: {e}")
        sys.exit(1)
    
    print(f"Searching for: {query_text}")
    results = search_query(query_text)
    
    print("\nResults:")
    for i, res in enumerate(results):
        print(f"\n--- Result {i+1} (Score: {res['score']:.4f}) ---")
        print(f"Index: {res['original_index']} ({res['source_type']})")
        print(f"Text: {res['text'][:200]}..." if len(res['text']) > 200 else f"Text: {res['text']}")
