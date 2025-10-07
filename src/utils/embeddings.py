"""Shared embedding utilities for semantic search and memory functions.

This module provides a centralized interface for generating text embeddings
used by both the knowledge store and memory store modules, avoiding code duplication.

The module uses the SentenceTransformer library to generate vector embeddings 
of text, which are used for semantic search and memory retrieval. The embeddings
are cached to improve performance and reduce resource usage.

Typical usage:
    ```python
    from utils.embeddings import generate_embedding, cosine_similarity

    # Generate embedding for a text
    embedding = generate_embedding("Your text here")
    
    # Compare similarity between two texts
    similarity = cosine_similarity(embedding1, embedding2)
    ```

For batch operations:
    ```python
    from utils.embeddings import generate_embeddings, batch_cosine_similarity
    
    # Generate embeddings for multiple texts
    embeddings = generate_embeddings(["Text 1", "Text 2", "Text 3"])
    
    # Compare a query embedding against multiple document embeddings
    similarities = batch_cosine_similarity(query_embedding, document_embeddings)
    ```

The default embedding model is 'sentence-transformers/all-MiniLM-L6-v2', but
can be configured through the LPS2_EMBED_MODEL environment variable.
"""

import os
import threading
from typing import List, Optional, Any, Dict, Union
import numpy as np
from numpy.typing import NDArray

_EMBEDDING_MODEL = None
_EMBEDDING_MODEL_LOCK = threading.Lock()

_SENTENCE_TRANSFORMERS_AVAILABLE = False
SentenceTransformer = None  # type: ignore

# Default model if not specified in environment
DEFAULT_EMBEDDING_MODEL = 'sentence-transformers/all-MiniLM-L6-v2'

# Current model from environment or default
CURRENT_EMBEDDING_MODEL_NAME = os.environ.get(
    'LPS2_EMBED_MODEL', 
    DEFAULT_EMBEDDING_MODEL
)

def _lazy_import_embeddings() -> bool:
    """Lazily import sentence-transformers to avoid startup overhead."""
    global SentenceTransformer, np, _SENTENCE_TRANSFORMERS_AVAILABLE
    if _SENTENCE_TRANSFORMERS_AVAILABLE:
        return True
    try:
        from sentence_transformers import SentenceTransformer as _ST  # type: ignore
        SentenceTransformer = _ST
        _SENTENCE_TRANSFORMERS_AVAILABLE = True
        return True
    except ImportError:
        return False

def get_embedding_model() -> Any:
    """Get the embedding model, initializing it if necessary."""
    global _EMBEDDING_MODEL
    if not _lazy_import_embeddings():
        return None
    
    with _EMBEDDING_MODEL_LOCK:
        if _EMBEDDING_MODEL is None:
            _EMBEDDING_MODEL = SentenceTransformer(CURRENT_EMBEDDING_MODEL_NAME)
    
    return _EMBEDDING_MODEL

def generate_embedding(text: str) -> Optional[NDArray[np.float32]]:
    """Generate an embedding vector for the given text.
    
    Args:
        text: The text to embed
        
    Returns:
        Numpy array embedding or None if embedding fails
    """
    model = get_embedding_model()
    if model is None:
        return None
    
    try:
        return model.encode(text, show_progress_bar=False)
    except Exception:
        return None

def generate_embeddings(texts: List[str]) -> List[Optional[NDArray[np.float32]]]:
    """Generate embeddings for multiple texts.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors (or None for failed embeddings)
    """
    model = get_embedding_model()
    if model is None:
        return [None] * len(texts)
    
    try:
        return model.encode(texts, show_progress_bar=False)
    except Exception:
        return [None] * len(texts)

def cosine_similarity(a: NDArray[np.float32], b: NDArray[np.float32]) -> float:
    """Calculate cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0
        
    return np.dot(a, b) / (norm_a * norm_b)

def batch_cosine_similarity(query: NDArray[np.float32], 
                           embeddings: List[NDArray[np.float32]]) -> List[float]:
    """Calculate cosine similarity between a query and multiple embeddings."""
    if not embeddings:
        return []
        
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return [0.0] * len(embeddings)
    
    normalized_query = query / query_norm
    
    similarities = []
    for emb in embeddings:
        emb_norm = np.linalg.norm(emb)
        if emb_norm == 0:
            similarities.append(0.0)
        else:
            normalized_emb = emb / emb_norm
            similarities.append(float(np.dot(normalized_query, normalized_emb)))
    
    return similarities