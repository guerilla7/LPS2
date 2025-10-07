"""Central configuration module.

Loads environment variables and provides defaults for demo.
In production, never hard-code secrets; rely on env / secret manager.
"""
from __future__ import annotations
import os

# --- Simple .env loader (no external dependency) ---------------------------
# Loads key=value lines from a .env file located at project root (parent of src)
# Only sets variables that are not already present in the environment.
def _load_dotenv():
    try:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        env_path = os.path.join(root, '.env')
        if not os.path.exists(env_path):
            return
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                # Preserve existing explicit exports
                if k and k not in os.environ:
                    os.environ[k] = v.strip()
    except Exception:
        # Fail silently – config falls back to defaults
        pass

_load_dotenv()

# Security configuration
API_KEY = os.environ.get('LPS2_API_KEY')
if not API_KEY or API_KEY == 'secret12345':
    # Let app.py handle the warning since it's more visible there
    API_KEY = 'secret12345'  # Insecure default, only for development

# Rate limiting configuration
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get('LPS2_RATE_WINDOW', '60'))
RATE_LIMIT_MAX_REQUESTS = int(os.environ.get('LPS2_RATE_MAX', '120'))  # per IP per window
RATE_LIMIT_BURST = int(os.environ.get('LPS2_RATE_BURST', '30'))  # short burst allowance

# User-specific rate limits (higher limits for authenticated users)
USER_RATE_LIMIT_WINDOW = int(os.environ.get('LPS2_USER_RATE_WINDOW', '60'))
USER_RATE_LIMIT_MAX = int(os.environ.get('LPS2_USER_RATE_MAX', '240'))  # higher for logged in users
USER_RATE_LIMIT_BURST = int(os.environ.get('LPS2_USER_RATE_BURST', '60'))

# Admin-specific rate limits (highest tier)
ADMIN_RATE_LIMIT_WINDOW = int(os.environ.get('LPS2_ADMIN_RATE_WINDOW', '60'))
ADMIN_RATE_LIMIT_MAX = int(os.environ.get('LPS2_ADMIN_RATE_MAX', '600'))
ADMIN_RATE_LIMIT_BURST = int(os.environ.get('LPS2_ADMIN_RATE_BURST', '120'))

CSRF_TOKEN_EXPIRY = int(os.environ.get('LPS2_CSRF_EXPIRY', '3600'))  # CSRF token expires after 1 hour by default

QUARANTINE_ENABLED = os.environ.get('LPS2_QUARANTINE', '1') not in ('0','false','no')
PII_REDACT_ENABLED = os.environ.get('LPS2_PII_REDACT', '1') not in ('0','false','no')

# Simple regex patterns for PII/Secrets (MVP heuristic)
PII_PATTERNS = {
    'email': r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
    'ipv4': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    'ssn_like': r'\b\d{3}-\d{2}-\d{4}\b',
    'credit_card': r'\b(?:\d[ -]*?){13,16}\b',
    'aws_access_key': r'AKIA[0-9A-Z]{16}',
    'generic_secret': r'(?i)(api|secret|token|key)[=: ]+[A-Za-z0-9-_]{8,}'
}

REDACTION_REPLACEMENT = '[REDACTED]'

# LLM generation controls (tunable via environment)
MAX_OUTPUT_TOKENS = int(os.environ.get('LPS2_MAX_TOKENS', '2048'))  # per single request (default increased)
AUTO_CONTINUE = os.environ.get('LPS2_AUTO_CONTINUE', '1') not in ('0','false','no')
CONTINUE_ROUNDS = int(os.environ.get('LPS2_CONTINUE_ROUNDS', '2'))  # max follow-up continuations if length-capped
GEN_TEMPERATURE = float(os.environ.get('LPS2_TEMPERATURE', '0.7'))
TOP_P = float(os.environ.get('LPS2_TOP_P', '0.95'))

# LLM server base URL (OpenAI-compatible). Override with LPS2_LLM_ENDPOINT env var.
# Default local LM Studio (or other OpenAI-compatible) endpoint.
# Updated per latest network change. Override with LPS2_LLM_ENDPOINT to avoid future code edits.
LLM_SERVER_URL = os.environ.get('LPS2_LLM_ENDPOINT', 'http://192.168.5.66:1234')

