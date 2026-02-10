import os
import platform
# Set HF mirror environment variable before any other imports that might use it
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import torch
from pathlib import Path

class Config:
    def __init__(self):
        self.os_type = platform.system()
        self.project_root = Path(__file__).parent.parent
        self.models_dir = self.project_root / "models"
        self.device = self._detect_device()
        self._setup_env()

    def _detect_device(self) -> str:
        """
        Detect hardware acceleration device.
        macOS: mps
        Windows: cuda (if available) else cpu
        Fallback: cpu
        """
        if self.os_type == "Darwin":
            if torch.backends.mps.is_available():
                return "mps"
        elif self.os_type == "Windows":
            if torch.cuda.is_available():
                return "cuda"
        
        return "cpu"

    def _setup_env(self):
        """
        Setup environment variables.
        """
        # Ensure models directory exists
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Set HF mirror if needed (as per plan)
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# Global config instance
config = Config()

if __name__ == "__main__":
    print(f"OS: {config.os_type}")
    print(f"Device: {config.device}")
    print(f"Models Dir: {config.models_dir}")
