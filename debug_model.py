import torch
import os
import sys

# Add core path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))

def debug_loading():
    print(f"Python: {sys.version}")
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA Version: {torch.version.cuda}")
    
    print("\n--- Testing SentenceTransformer Load ---")
    try:
        from sentence_transformers import SentenceTransformer
        # Try loading a tiny model to test library functionality first
        # using 'all-MiniLM-L6-v2' which is small, or just check imports
        print("sentence_transformers imported.")
        
        from core.config import config
        print(f"Config Device: {config.device}")
        
        model_path = os.path.join(config.models_dir, "bge-m3")
        print(f"Target model path: {model_path}")
        
        if os.path.exists(model_path):
            print("Model directory exists.")
            # List files to ensure download is complete
            files = os.listdir(model_path)
            print(f"Files in dir: {files[:5]} ... (total {len(files)})")
            
            print("Attempting to load model (forcing CPU for test)...")
            model = SentenceTransformer(model_path, device="cpu")
            print("SUCCESS: Model loaded on CPU.")
            
            if torch.cuda.is_available():
                print("Attempting to move model to CUDA...")
                model = model.to("cuda")
                print("SUCCESS: Model moved to CUDA.")
        else:
            print("ERROR: Model directory does not exist.")
            
    except Exception as e:
        print(f"ERROR during loading: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_loading()
