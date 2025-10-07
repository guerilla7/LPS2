import os
import json
import threading
import time
import hashlib
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

from utils.embeddings import (
    generate_embedding, 
    generate_embeddings, 
    batch_cosine_similarity,
    cosine_similarity,
    get_embedding_model,
    _lazy_import_embeddings,
    _SENTENCE_TRANSFORMERS_AVAILABLE,
    CURRENT_EMBEDDING_MODEL_NAME
)


def _simple_chunk(text: str, max_chars: int = 1200, overlap: int = 200) -> List[str]:
    """Naive text chunker with character windows + overlap.

    Splits on paragraph boundaries when possible but enforces max length.
    """
    paras = [p.strip() for p in text.split('\n') if p.strip()]
    chunks: List[str] = []
    buf = []
    current_len = 0
    for p in paras:
        if current_len + len(p) + 1 <= max_chars:
            buf.append(p)
            current_len += len(p) + 1
        else:
            if buf:
                chunks.append('\n'.join(buf))
            # start new buffer; if single paragraph longer than max, hard slice
            if len(p) > max_chars:
                start = 0
                while start < len(p):
                    seg = p[start:start+max_chars]
                    chunks.append(seg)
                    start += max_chars - overlap if overlap < max_chars else max_chars
                buf = []
                current_len = 0
            else:
                buf = [p]
                current_len = len(p)
    if buf:
        chunks.append('\n'.join(buf))
    # add overlap by merging tail of previous chunk into next (simple method) not needed for MVP retrieval; can revisit
    return chunks


def _heading_semantic_chunks(text: str, max_chars: int = 1200, overlap: int = 200) -> List[str]:
    """Heading-aware chunking for Markdown-like text.

    Strategy:
    - Split by lines, track current heading stack.
    - Accumulate paragraphs under heading context.
    - Merge until size threshold reached, then start new chunk with heading context repeated.
    Fallback: if result empty, use _simple_chunk.
    """
    lines = text.splitlines()
    headings: List[Tuple[int, str]] = []  # (level, title)
    current_buf: List[str] = []
    current_len = 0
    chunks: List[str] = []

    def heading_prefix():
        if not headings:
            return ''
        return '\n'.join([('#' * lvl) + ' ' + title for lvl, title in headings]) + '\n\n'

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith('#'):
            # Flush current buffer as chunk if has content
            if current_buf:
                content = heading_prefix() + '\n'.join(current_buf)
                chunks.append(content)
                current_buf = []
                current_len = 0
            # Parse heading
            hashes = 0
            for ch in line:
                if ch == '#':
                    hashes += 1
                else:
                    break
            level = max(1, min(6, hashes))
            title = line[hashes:].strip() or 'Untitled'
            # Trim stack to parent level-1
            headings = [h for h in headings if h[0] < level]
            headings.append((level, title))
            continue
        # Normal paragraph line
        if current_len + len(line) + 1 > max_chars and current_buf:
            # Emit chunk
            content = heading_prefix() + '\n'.join(current_buf)
            chunks.append(content)
            # Overlap: keep last overlap chars
            if overlap > 0 and current_buf:
                joined = '\n'.join(current_buf)
                tail = joined[-overlap:]
                current_buf = [tail]
                current_len = len(tail)
            else:
                current_buf = []
                current_len = 0
        current_buf.append(line)
        current_len += len(line) + 1
    if current_buf:
        content = heading_prefix() + '\n'.join(current_buf)
        chunks.append(content)
    # Fallback if nothing produced
    if not chunks:
        return _simple_chunk(text, max_chars=max_chars, overlap=overlap)
    # Enforce max_chars post-hoc (rare overflows)
    final: List[str] = []
    for ch in chunks:
        if len(ch) <= max_chars:
            final.append(ch)
        else:
            final.extend(_simple_chunk(ch, max_chars=max_chars, overlap=overlap))
    return final


class KnowledgeStore:
    def __init__(self, path: Optional[str] = None):
        if path is None:
            path = os.path.join(os.path.dirname(__file__), 'knowledge_store.json')
        self.path = path
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {"documents": []}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
                    if 'documents' not in self._data:
                        self._data = {"documents": []}
        except Exception:
            self._data = {"documents": []}

    def _persist(self):
        try:
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._data, f)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def ingest_text(self, text: str, source: str, metadata: Optional[Dict[str, Any]] = None, doc_id: Optional[str] = None, replace: bool = False) -> Dict[str, Any]:
        if not text.strip():
            return {"error": "empty text"}
        if not _lazy_import_embeddings():
            return {"error": "embeddings unavailable"}
        model = get_embedding_model()
        if model is None:
            return {"error": "embedding model not loaded"}
        # Prefer heading-aware when markdown indicators present
        if '#' in text or '##' in text:
            chunks = _heading_semantic_chunks(text)
        else:
            # If existing documents have different embedding model and NEW model name differs, schedule background rebuild.
            try:
                needs = False
                for d in self._data.get('documents', []):
                    if d.get('embedding_model') != CURRENT_EMBEDDING_MODEL_NAME:
                        needs = True
                        break
                if needs:
                    # Start rebuild non-blocking
                    threading.Thread(target=self.rebuild_embeddings, kwargs={'force': False}, daemon=True).start()
            except Exception:
                pass
            chunks = _simple_chunk(text)
        if not chunks:
            return {"error": "no chunks produced"}
        # Sanitize each chunk and capture suspicious flags prior to embedding
        from .security_utils import sanitize_text
        from config import QUARANTINE_ENABLED
        import json as _json
        sanitized_chunks = []
        suspicious_indexes = set()
        for idx, ch in enumerate(chunks):
            sanitized, meta = sanitize_text(ch)
            if meta.get('suspicious'):
                suspicious_indexes.add(idx)
            sanitized_chunks.append(sanitized)
        embeds = model.encode(sanitized_chunks)
        import uuid
        if doc_id is None:
            doc_id = str(uuid.uuid4())
        checksum = hashlib.sha256(text.encode('utf-8')).hexdigest()
        # If replace flag set, drop existing doc with same id
        if replace and doc_id:
            with self._lock:
                prev_docs = self._data.get('documents', [])
                self._data['documents'] = [d for d in prev_docs if d.get('doc_id') != doc_id]
        doc = {
            'doc_id': doc_id,
            'source': source,
            'created': time.time(),
            'embedding_model': CURRENT_EMBEDDING_MODEL_NAME,
            'meta': metadata or {},
            'checksum': checksum,
            'chunks': []
        }
        if suspicious_indexes and QUARANTINE_ENABLED:
            # Write full original + sanitized doc to quarantine file instead of storing in main index
            qpath = self.path + '.quarantine'
            record = {
                'doc_id': doc_id,
                'source': source,
                'created': time.time(),
                'checksum': checksum,
                'suspicious_chunks': list(sorted([int(i) for i in suspicious_indexes])),
                'chunk_count': len(sanitized_chunks)
            }
            try:
                existing = []
                if os.path.exists(qpath):
                    with open(qpath, 'r', encoding='utf-8') as f:
                        existing = _json.load(f)
                existing.append(record)
                with open(qpath + '.tmp', 'w', encoding='utf-8') as f:
                    _json.dump(existing, f)
                os.replace(qpath + '.tmp', qpath)
            except Exception:
                pass
            return {"doc_id": doc_id, "quarantined": True, "chunks": len(sanitized_chunks), "checksum": checksum}
        else:
            for idx, (ch, emb) in enumerate(zip(sanitized_chunks, embeds)):
                chunk_record = {
                    'id': str(uuid.uuid4()),
                    'index': idx,
                    'text': ch,
                    'embedding': emb.tolist(),
                    'len': len(ch)
                }
                if idx in suspicious_indexes:
                    chunk_record['suspicious'] = True
                doc['chunks'].append(chunk_record)
            if suspicious_indexes:
                doc['meta']['suspicious'] = True
            with self._lock:
                self._data['documents'].append(doc)
                self._persist()
            return {"doc_id": doc_id, "chunks": len(doc['chunks']), "checksum": checksum, "replaced": replace}

    def stats(self):
        with self._lock:
            docs = self._data.get('documents', [])
            chunk_count = sum(len(d.get('chunks', [])) for d in docs)
            return {
                'documents': len(docs),
                'chunks': chunk_count,
                'path': self.path,
                'embedding_enabled': _SENTENCE_TRANSFORMERS_AVAILABLE
            }

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        if not _lazy_import_embeddings():
            return []
        model = get_embedding_model()
        if model is None:
            return []
        try:
            q = model.encode([query])[0]
        except Exception:
            return []
        with self._lock:
            docs = list(self._data.get('documents', []))
        if not docs:
            return []
        # Flatten chunks
        all_chunks = []
        for d in docs:
            for c in d.get('chunks', []):
                all_chunks.append((d, c))
        if not all_chunks:
            return []
        import numpy as _np
        mat = _np.array([c['embedding'] for _, c in all_chunks])
        qv = _np.array(q)
        mat_norm = mat / (_np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
        qv_norm = qv / (_np.linalg.norm(qv) + 1e-9)
        sims = mat_norm @ qv_norm
        idxs = sims.argsort()[::-1][:top_k]
        results: List[Dict[str, Any]] = []
        for i in idxs:
            d, c = all_chunks[i]
            results.append({
                'chunk_id': c['id'],
                'doc_id': d['doc_id'],
                'source': d['source'],
                'index': c['index'],
                'text': c['text'],
                'score': float(sims[i])
            })
        return results

    # -------- Document Management --------
    def list_documents(self) -> List[Dict[str, Any]]:
        with self._lock:
            docs = list(self._data.get('documents', []))
        out = []
        for d in docs:
            out.append({
                'doc_id': d.get('doc_id'),
                'source': d.get('source'),
                'created': d.get('created'),
                'chunks': len(d.get('chunks', [])),
                'embedding_model': d.get('embedding_model'),
                'checksum': d.get('checksum')
            })
        return out

    def delete_documents(self, doc_ids: List[str]) -> int:
        if not doc_ids:
            return 0
        ids = set(doc_ids)
        with self._lock:
            docs = self._data.get('documents', [])
            new_docs = [d for d in docs if d.get('doc_id') not in ids]
            removed = len(docs) - len(new_docs)
            if removed:
                self._data['documents'] = new_docs
                self._persist()
            return removed

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for d in self._data.get('documents', []):
                if d.get('doc_id') == doc_id:
                    return d
        return None

    # -------- Rebuild Embeddings (Background) --------
    def _init_rebuild_state(self):
        if not hasattr(self, '_rebuild_state'):
            self._rebuild_state = {
                'running': False,
                'started_at': None,
                'updated_at': None,
                'total_docs': 0,
                'rebuilt_docs': 0,
                'errors': [],
                'target_model': CURRENT_EMBEDDING_MODEL_NAME,
                'force': False
            }

    def rebuild_status(self) -> Dict[str, Any]:
        self._init_rebuild_state()
        return dict(self._rebuild_state)

    def rebuild_embeddings(self, force: bool = False) -> Dict[str, Any]:
        self._init_rebuild_state()
        if self._rebuild_state['running']:
            return self.rebuild_status()
        # Determine docs needing rebuild
        with self._lock:
            docs = list(self._data.get('documents', []))
        targets = []
        for d in docs:
            if force or d.get('embedding_model') != CURRENT_EMBEDDING_MODEL_NAME:
                targets.append(d.get('doc_id'))
        self._rebuild_state.update({
            'running': True,
            'started_at': time.time(),
            'updated_at': time.time(),
            'total_docs': len(targets),
            'rebuilt_docs': 0,
            'errors': [],
            'target_model': CURRENT_EMBEDDING_MODEL_NAME,
            'force': force
        })
        th = threading.Thread(target=self._rebuild_worker, args=(targets,), daemon=True)
        th.start()
        return self.rebuild_status()

    def _rebuild_worker(self, targets: List[str]):
        try:
            model = get_embedding_model()
            if model is None:
                raise RuntimeError('Embedding model unavailable')
            for doc_id in targets:
                with self._lock:
                    doc = None
                    for d in self._data.get('documents', []):
                        if d.get('doc_id') == doc_id:
                            doc = d
                            break
                if not doc:
                    continue
                # Re-embed chunk texts
                texts = [c['text'] for c in doc.get('chunks', [])]
                try:
                    embs = model.encode(texts)
                except Exception as e:
                    self._rebuild_state['errors'].append(f"{doc_id[:8]}: {e}")
                    continue
                # Update embeddings
                for c, emb in zip(doc.get('chunks', []), embs):
                    c['embedding'] = emb.tolist()
                doc['embedding_model'] = CURRENT_EMBEDDING_MODEL_NAME
                with self._lock:
                    self._persist()
                self._rebuild_state['rebuilt_docs'] += 1
                self._rebuild_state['updated_at'] = time.time()
        except Exception as e:
            self._rebuild_state['errors'].append(str(e))
        finally:
            self._rebuild_state['running'] = False
            self._rebuild_state['updated_at'] = time.time()



_GLOBAL_KNOWLEDGE = None
_GLOBAL_KNOWLEDGE_LOCK = threading.Lock()


def get_knowledge_store() -> Optional[KnowledgeStore]:
    global _GLOBAL_KNOWLEDGE
    with _GLOBAL_KNOWLEDGE_LOCK:
        if _GLOBAL_KNOWLEDGE is None:
            try:
                _GLOBAL_KNOWLEDGE = KnowledgeStore()
            except Exception:
                return None
    return _GLOBAL_KNOWLEDGE
