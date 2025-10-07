"""Simple JSON lines audit logger for security-relevant events."""
from __future__ import annotations
import json, os, threading, time

_LOCK = threading.Lock()
AUDIT_PATH = os.environ.get('LPS2_AUDIT_LOG', os.path.join(os.path.dirname(__file__), 'audit.log'))

def audit(event: str, **fields):
    rec = {
        'ts': time.time(),
        'event': event,
        **fields
    }
    line = json.dumps(rec, ensure_ascii=False)
    with _LOCK:
        with open(AUDIT_PATH, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

def read_audit(limit: int = 500):
    try:
        if not os.path.exists(AUDIT_PATH):
            return []
        with open(AUDIT_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-limit:]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []
