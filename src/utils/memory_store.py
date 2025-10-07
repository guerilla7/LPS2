import os
import json
import threading
import numpy as np
from typing import List, Dict, Any

from utils.embeddings import (
    generate_embedding,
    generate_embeddings,
    batch_cosine_similarity,
    cosine_similarity,
    get_embedding_model,
    _lazy_import_embeddings,
    _SENTENCE_TRANSFORMERS_AVAILABLE
)


class MemoryStore:
    """Simple JSON-backed vector memory store (MVP).

    Structure of JSON file:
    {
        "memories": [
            {"id": "..", "text": "..", "metadata": {...}, "embedding": [..floats..]}
        ]
    }
    """

    def __init__(self, path=None):
        """Initialize the memory store with an optional path."""
        if path is None:
            path = os.path.join(os.path.dirname(__file__), 'memory_store.json')
        self.path = path
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {"memories": []}
        self._load()

    # ---------------- Persistence ----------------
    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                    if 'memories' not in self._data:
                        self._data = {"memories": []}
        except Exception:
            # Corrupt file fallback
            self._data = {"memories": []}

    def _persist(self):
        try:
            tmp_path = self.path + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f)
            os.replace(tmp_path, self.path)
        except Exception:
            pass  # Best effort persistence

    # ---------------- Core API ----------------
    def add_memory(self, text: str, metadata: Dict[str, Any] = None) -> str:
        """Add a memory with optional metadata."""
        if not text.strip():
            return ''
        if not _lazy_import_embeddings():
            return ''
        model = get_embedding_model()
        if model is None:
            return ''
        try:
            emb = model.encode([text])[0].tolist()
        except Exception:
            return ''
        import uuid
        mem_id = str(uuid.uuid4())
        import time
        record = {
            "id": mem_id,
            "text": text,
            "metadata": metadata or {},
            "embedding": emb,
            "created": time.time()
        }
        with self._lock:
            self._data["memories"].append(record)
            self._persist()
        return mem_id

    # New helper to update metadata of a memory (e.g., to mark suspicious after sanitization)
    def update_metadata(self, mem_id: str, new_meta: Dict[str, Any]):
        with self._lock:
            for m in self._data.get('memories', []):
                if m.get('id') == mem_id:
                    meta = m.get('metadata', {})
                    meta.update(new_meta)
                    m['metadata'] = meta
                    self._persist()
                    return True
        return False

    def list_memories(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._data.get('memories', []))

    def delete_memory(self, mem_id: str) -> bool:
        removed = False
        with self._lock:
            memories = self._data.get('memories', [])
            new_list = [m for m in memories if m.get('id') != mem_id]
            if len(new_list) != len(memories):
                removed = True
                self._data['memories'] = new_list
                self._persist()
        return removed

    def delete_many(self, ids: List[str]) -> int:
        if not ids:
            return 0
        ids_set = set(ids)
        with self._lock:
            memories = self._data.get('memories', [])
            new_list = [m for m in memories if m.get('id') not in ids_set]
            removed = len(memories) - len(new_list)
            if removed:
                self._data['memories'] = new_list
                self._persist()
            return removed

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        if not _lazy_import_embeddings():
            return []
        model = get_embedding_model()
        if model is None:
            return []
        try:
            q_emb = model.encode([query])[0]
        except Exception:
            return []
        with self._lock:
            memories = list(self._data.get('memories', []))
        if not memories:
            return []
        # Compute cosine similarity
        try:
            import numpy as _np
            mat = _np.array([m['embedding'] for m in memories])
            qv = _np.array(q_emb)
            # Normalize
            mat_norm = mat / ( _np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9 )
            qv_norm = qv / ( _np.linalg.norm(qv) + 1e-9 )
            sims = mat_norm @ qv_norm
            # argsort descending
            idxs = sims.argsort()[::-1][:top_k]
            results = []
            for i in idxs:
                m = memories[i]
                results.append({
                    'id': m['id'],
                    'text': m['text'],
                    'metadata': m.get('metadata', {}),
                    'score': float(sims[i])
                })
            return results
        except Exception:
            return []

    def stats(self):
        with self._lock:
            return {
                'count': len(self._data.get('memories', [])),
                'path': self.path,
                'embedding_enabled': _SENTENCE_TRANSFORMERS_AVAILABLE
            }


# Global singleton (simple pattern)
_GLOBAL_MEMORY = None
_GLOBAL_MEMORY_LOCK = threading.Lock()


def get_memory_store():
    global _GLOBAL_MEMORY
    with _GLOBAL_MEMORY_LOCK:
        if _GLOBAL_MEMORY is None:
            try:
                _GLOBAL_MEMORY = MemoryStore()
            except Exception:
                return None
    return _GLOBAL_MEMORY
