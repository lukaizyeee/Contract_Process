import torch
import numpy as np
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from .config import config  # Import config first to set env vars
from sentence_transformers import SentenceTransformer, CrossEncoder, util
from huggingface_hub import HfApi, hf_hub_download
from .ingestion import Chunk

class SemanticSearchEngine:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SemanticSearchEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def _fetch_remote_file_list(self, repo_id: str) -> List[Tuple[str, Optional[int]]]:
        api = HfApi()
        model_info = api.model_info(repo_id)
        siblings = model_info.siblings or []
        return [
            (sibling.rfilename, getattr(sibling, "size", None))
            for sibling in siblings
            if sibling.rfilename and not sibling.rfilename.endswith(".DS_Store")
        ]

    def _is_model_complete_offline(self, local_model_dir: Path) -> bool:
        if not (local_model_dir / "config.json").exists():
            return False

        has_weight = any(
            (local_model_dir / candidate).exists()
            for candidate in [
                "pytorch_model.bin",
                "model.safetensors",
                "model.bin",
                "model.onnx",
                "onnx/model.onnx",
            ]
        )
        has_tokenizer = any(
            (local_model_dir / candidate).exists()
            for candidate in [
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.txt",
                "sentencepiece.bpe.model",
                "spiece.model",
            ]
        )

        return has_weight and has_tokenizer

    def _collect_missing_files(
        self,
        local_model_dir: Path,
        files: List[Tuple[str, Optional[int]]],
    ) -> Tuple[List[str], List[str], List[str]]:
        missing_files: List[str] = []
        size_mismatch_files: List[str] = []
        unknown_size_files: List[str] = []

        for relative_path, remote_size in files:
            local_file = local_model_dir / relative_path

            if not local_file.exists():
                missing_files.append(relative_path)
                continue

            if remote_size is None:
                unknown_size_files.append(relative_path)
                continue

            try:
                local_size = local_file.stat().st_size
            except OSError:
                missing_files.append(relative_path)
                continue

            if local_size != remote_size:
                size_mismatch_files.append(relative_path)

        to_download = missing_files + size_mismatch_files
        return to_download, missing_files, size_mismatch_files

    def _ensure_model_downloaded(self, repo_id: str, local_path: str):
        """
        Ensure model is fully downloaded.
        Preferred check: compare against remote file list.
        Fallback check: local critical files heuristic when remote is unavailable.
        """
        local_model_dir = Path(local_path)
        local_model_dir.mkdir(parents=True, exist_ok=True)

        print(f"Checking local model completeness: {repo_id} -> {local_model_dir}", flush=True)

        try:
            remote_files = self._fetch_remote_file_list(repo_id)
            files_to_download, missing_files, size_mismatch_files = self._collect_missing_files(
                local_model_dir,
                remote_files,
            )

            if not files_to_download:
                print(f"Model is complete locally. Skip download: {repo_id}", flush=True)
                return

            print(
                (
                    f"Local model incomplete: {len(files_to_download)} files need sync "
                    f"(missing={len(missing_files)}, size_mismatch={len(size_mismatch_files)}, total={len(remote_files)})."
                ),
                flush=True,
            )
        except Exception as check_error:
            print(f"Remote completeness check failed for {repo_id}: {check_error}", flush=True)
            if self._is_model_complete_offline(local_model_dir):
                print(f"Offline heuristic says model is complete. Skip download: {repo_id}", flush=True)
                return

            print(f"Offline heuristic says model is incomplete. Re-downloading full snapshot: {repo_id}", flush=True)
            files_to_download = []

        print(f"Model download required. Downloading {repo_id} to {local_model_dir}...", flush=True)

        try:
            if not files_to_download:
                # When remote file listing is unavailable, fallback to full snapshot recovery.
                from huggingface_hub import snapshot_download

                snapshot_download(repo_id=repo_id, local_dir=str(local_model_dir), ignore_patterns=["*.DS_Store"])
                print(f"Download completed (snapshot): {repo_id}", flush=True)
                return

            total_files = len(files_to_download)
            max_workers = self._resolve_download_workers(total_files)
            print(f"[{repo_id}] Total files: {total_files}, workers: {max_workers}", flush=True)

            if total_files == 0:
                print(f"[{repo_id}] No files to download.", flush=True)
                return

            completed = 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_filename = {
                    executor.submit(
                        hf_hub_download,
                        repo_id=repo_id,
                        filename=filename,
                        local_dir=str(local_model_dir),
                    ): filename
                    for filename in files_to_download
                }

                for future in as_completed(future_to_filename):
                    filename = future_to_filename[future]
                    try:
                        future.result()
                        completed += 1
                        print(f"[{repo_id}] ({completed}/{total_files}) done {filename}", flush=True)
                    except Exception as thread_error:
                        print(f"[{repo_id}] failed {filename}: {thread_error}", flush=True)
                        raise

            print(f"Download completed: {repo_id}", flush=True)
        except Exception as e:
            print(f"Error downloading {repo_id}: {e}", flush=True)
            raise

    @staticmethod
    def _resolve_download_workers(total_files: int) -> int:
        env_value = os.getenv("MODEL_DOWNLOAD_WORKERS", "4")
        try:
            requested = int(env_value)
        except ValueError:
            requested = 4

        requested = max(1, requested)
        if total_files <= 0:
            return 1

        return min(requested, total_files, 8)
            
    def __init__(self):
        if self._initialized:
            return
        
        self.device = config.device
        self.models_dir = str(config.models_dir)
        
        # Model names
        self.embedding_model_name = "BAAI/bge-m3"
        self.reranker_model_name = "BAAI/bge-reranker-large"
        
        # --- Embedding Model ---
        print(f"Loading Embedding Model: {self.embedding_model_name} on {self.device}...", flush=True)
        embedding_path = os.path.join(self.models_dir, "bge-m3")
        self._ensure_model_downloaded(self.embedding_model_name, embedding_path)
            
        print("Initializing SentenceTransformer...", flush=True)
        # Force CPU loading first if CUDA is problematic during init
        try:
            self.embedder = SentenceTransformer(
                embedding_path, 
                device="cpu"
            )
            if self.device == "cuda":
                print("Moving Embedding Model to CUDA...", flush=True)
                self.embedder = self.embedder.to("cuda")
        except Exception as e:
            print(f"Error loading embedding model: {e}", flush=True)
            raise e
        print("SentenceTransformer initialized.", flush=True)
        
        # --- Reranker Model ---
        print(f"Loading Reranker Model: {self.reranker_model_name} on {self.device}...", flush=True)
        reranker_path = os.path.join(self.models_dir, "bge-reranker-large")
        self._ensure_model_downloaded(self.reranker_model_name, reranker_path)
             
        print("Initializing CrossEncoder...", flush=True)
        try:
            self.reranker = CrossEncoder(
                reranker_path, 
                device="cpu"
            )
            if self.device == "cuda":
                print("Moving Reranker Model to CUDA...", flush=True)
                self.reranker.model = self.reranker.model.to("cuda")
        except Exception as e:
            print(f"Error loading reranker model: {e}", flush=True)
            raise e
        print("CrossEncoder initialized.", flush=True)
        
        self.chunks: List[Chunk] = []
        self.doc_vectors = None
        self._initialized = True

    def load_document(self, chunks: List[Chunk]):
        """
        Encode chunks and store vectors.
        """
        self.chunks = chunks
        texts = [chunk.text for chunk in chunks]
        
        if not texts:
            self.doc_vectors = None
            return

        print(f"Encoding {len(texts)} chunks...", flush=True)
        # encode returns numpy array by default unless convert_to_tensor=True
        # Using convert_to_tensor=True for performance as per plan
        embeddings = self.embedder.encode(
            texts, 
            convert_to_tensor=True, 
            normalize_embeddings=True,
            show_progress_bar=True
        )
        
        self.doc_vectors = embeddings

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Two-stage search: Embedding Retrieval + Reranking
        """
        if not self.chunks or self.doc_vectors is None:
            return []

        # Step 1: Retrieval (Bi-Encoder)
        # Note: bge-m3 supports multilingual, so no need to translate query
        query_vector = self.embedder.encode(query, convert_to_tensor=True, normalize_embeddings=True)
        
        # Retrieve Top-N (e.g., 2*top_k or fixed 20/50) for reranking
        # Plan says "Step 1... 选取 Top-10" but usually we want more for reranker.
        # Plan says: "Step 1 (粗排): ... 并选取 Top-10. Step 2 (精排): ... 输入 Reranker 模型进行重排."
        # If we only pick Top-10 for reranking, the reranker can only reorder those 10.
        # Usually we pick Top-50 or Top-100.
        # But if the plan strictly says "Select Top-10", I should follow it or slightly improve.
        # "Select Top-10" for coarse sort might be a typo for "Top-N" where N > K, 
        # or it means we only care about top 10.
        # However, if user wants Top-10 output, and we only rerank Top-10, it's just reordering.
        # I'll use top_k * 2 or at least 20 to give reranker some room to promote items.
        # But to strictly follow "Select Top-10" instruction in plan step 1:
        # "Step 1 (粗排): ... 并选取 Top-10"
        # "Step 2 (精排): ... 将 Query 和 Top-10 的文本对 ... 输入 Reranker"
        # "Step 3 (输出): 返回 ... Top-K"
        # If Top-K is 10, then we just reorder.
        # I will follow the plan literally for now: Retrieve Top-10 (or Top-K if K > 10).
        
        retrieve_k = max(top_k, 10)
        hits = util.semantic_search(query_vector, self.doc_vectors, top_k=min(retrieve_k, len(self.chunks)))[0]
        
        # Step 2: Reranking (Cross-Encoder)
        # Prepare pairs: [[query, doc_text], ...]
        cross_inp = [[query, self.chunks[hit['corpus_id']].text] for hit in hits]
        
        if not cross_inp:
            return []
            
        cross_scores = self.reranker.predict(cross_inp)
        
        # Combine scores with hits
        for idx, score in enumerate(cross_scores):
            hits[idx]['cross_score'] = score
            
        # Sort by cross_score descending
        hits.sort(key=lambda x: x['cross_score'], reverse=True)
        
        # Select Final Top-K
        final_hits = hits[:top_k]
        
        results = []
        for hit in final_hits:
            chunk = self.chunks[hit['corpus_id']]
            results.append({
                'text': chunk.text,
                'original_index': chunk.original_index,
                'source_type': chunk.source_type,
                'metadata': chunk.metadata,
                'score': float(hit['cross_score']), # Reranker score (logits usually, or sigmoid)
                'initial_score': float(hit['score']) # Cosine similarity
            })
            
        return results
