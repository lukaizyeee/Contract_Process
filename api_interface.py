import os
import threading
from core.search_engine import SemanticSearchEngine
from core.ingestion import DocProcessor
from core.word_processor import WordProcessor  # Import the new processor
from core.preview_generator import DocxPreviewGenerator # Import preview generator

# Global instance
_engine_instance = None
_processor = DocProcessor()
_word_processor = WordProcessor()  # Initialize word processor
_preview_generator = DocxPreviewGenerator() # Initialize preview generator
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

def modify_document_with_revisions(file_path: str, output_path: str, append_text: str):
    """
    Modify document with track changes enabled.
    """
    try:
        _word_processor.append_text_with_revision(file_path, output_path, append_text)
        return {"status": "success", "output_path": output_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_document_preview(file_path: str):
    """
    Generate HTML preview with track changes support.
    """
    try:
        return _preview_generator.generate_html(file_path)
    except Exception as e:
        return f"<html><body><p>Error generating preview: {str(e)}</p></body></html>"

if __name__ == "__main__":
    # Simple CLI test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python api_interface.py <path_to_docx> [query]")
        sys.exit(1)
        
    docx_path = sys.argv[1]
    
    # If using --modify flag
    if len(sys.argv) > 3 and sys.argv[2] == "--modify":
        text_to_add = sys.argv[3]
        out_path = docx_path.replace(".docx", "_revised.docx")
        print(f"Modifying {docx_path}...")
        res = modify_document_with_revisions(docx_path, out_path, text_to_add)
        print(res)
        sys.exit(0)

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
