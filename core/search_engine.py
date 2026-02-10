import torch
import numpy as np
import os
from typing import List, Dict, Any
from .config import config  # Import config first to set env vars
from sentence_transformers import SentenceTransformer, CrossEncoder, util
from huggingface_hub import snapshot_download
from .ingestion import Chunk

class SemanticSearchEngine:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SemanticSearchEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.device = config.device
        self.models_dir = str(config.models_dir)
        
        # Model names
        self.embedding_model_name = "BAAI/bge-m3"
        self.reranker_model_name = "BAAI/bge-reranker-large"
        
        print(f"Loading Embedding Model: {self.embedding_model_name} on {self.device}...")
        
        # Download explicitly to a local folder (not cache) to avoid symlinks
        embedding_path = os.path.join(self.models_dir, "bge-m3")
        print(f"Checking/Downloading {self.embedding_model_name} to {embedding_path}...")
        try:
            snapshot_download(repo_id=self.embedding_model_name, local_dir=embedding_path, ignore_patterns=["*.DS_Store"])
        except Exception as e:
            print(f"Warning: Failed to download/check embedding model: {e}")
            print("Trying to load from local path anyway...")
            
        print("Initializing SentenceTransformer...")
        self.embedder = SentenceTransformer(
            embedding_path, 
            device=self.device
        )
        print("SentenceTransformer initialized.")
        
        print(f"Loading Reranker Model: {self.reranker_model_name} on {self.device}...")
        
        reranker_path = os.path.join(self.models_dir, "bge-reranker-large")
        print(f"Checking/Downloading {self.reranker_model_name} to {reranker_path}...")
        try:
            snapshot_download(repo_id=self.reranker_model_name, local_dir=reranker_path, ignore_patterns=["*.DS_Store"])
        except Exception as e:
            print(f"Warning: Failed to download/check reranker model: {e}")
            print("Trying to load from local path anyway...")
             
        print("Initializing CrossEncoder...")
        self.reranker = CrossEncoder(
            reranker_path, 
            device=self.device
        )
        print("CrossEncoder initialized.")
        
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

        print(f"Encoding {len(texts)} chunks...")
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
