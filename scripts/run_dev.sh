#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d venv ]; then
  echo "[run_dev] Creating virtual environment..." >&2
  python3 -m venv venv
fi

source venv/bin/activate

# Make sure pip is available
if ! command -v pip &> /dev/null; then
  echo "[run_dev] Installing pip within the virtual environment..." >&2
  curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py
  python get-pip.py
  rm get-pip.py
fi

if [ -f requirements.txt ]; then
  echo "[run_dev] Ensuring dependencies are installed..." >&2
  python -m pip install -q -r requirements.txt
fi

# Allow custom port
PORT="${LPS2_PORT:-5000}"

# Kill anything on chosen port to avoid bind errors (portable: avoid bash 4 'mapfile')
EXISTING="$(lsof -t -iTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$EXISTING" ]; then
  echo "[run_dev] Killing existing processes on :${PORT}: $EXISTING" >&2
  for p in $EXISTING; do
    if [ -n "$p" ]; then
      kill "$p" 2>/dev/null || true
    fi
  done
  sleep 1
  LEFT="$(lsof -t -iTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$LEFT" ]; then
    echo "[run_dev] WARNING: Some processes still listening on ${PORT}: $LEFT" >&2
  fi
fi

export PYTHONPATH=src:${PYTHONPATH:-}
# Use modern Flask debug flag instead of deprecated FLASK_ENV
export FLASK_DEBUG=1

# SECURITY SETTINGS
# Check if we're using default security settings
if [ -z "${LPS2_API_KEY:-}" ]; then
  echo -e "\n\033[31;1m⚠️  SECURITY WARNING: Using default API key 'secret12345'\033[0m" >&2
  echo -e "\033[33m   This is only for development and MUST be changed in production.\033[0m" >&2
  echo -e "\033[33m   Set LPS2_API_KEY environment variable to a strong, unique value.\033[0m\n" >&2
  export LPS2_API_KEY="secret12345"
fi

if [ -z "${LPS2_SECRET_KEY:-}" ]; then
  echo -e "\033[31;1m⚠️  SECURITY WARNING: Using default Flask secret key\033[0m" >&2
  echo -e "\033[33m   This is only for development and MUST be changed in production.\033[0m" >&2
  echo -e "\033[33m   Set LPS2_SECRET_KEY environment variable to a strong, random value.\033[0m\n" >&2
fi

if [ -z "${LPS2_ADMIN_PASSWORD:-}" ]; then
  echo -e "\033[31;1m⚠️  SECURITY WARNING: Using default admin password 'admin123'\033[0m" >&2
  echo -e "\033[33m   This is only for development and MUST be changed in production.\033[0m" >&2
  echo -e "\033[33m   Set LPS2_ADMIN_PASSWORD environment variable to a strong password.\033[0m\n" >&2
fi

# Enable TLS by default unless explicitly disabled
if [ -z "${LPS2_ENABLE_TLS:-}" ] && [ -z "${LPS2_DISABLE_TLS:-}" ]; then
  export LPS2_ENABLE_TLS=1
fi
if [ "${LPS2_DISABLE_TLS:-}" != "" ]; then
  # If user sets disable flag, override any enable flag
  unset LPS2_ENABLE_TLS || true
fi

echo "[run_dev] Starting app (http://127.0.0.1:${PORT}) ..." >&2
if [ "${LPS2_ENABLE_TLS:-}" != "" ] && [[ "${LPS2_ENABLE_TLS}" =~ ^(1|true|yes|on)$ ]]; then
  CERT_DIR="dev_certs"
  mkdir -p "$CERT_DIR"
  : "${LPS2_TLS_CERT:=$CERT_DIR/dev-cert.pem}"
  : "${LPS2_TLS_KEY:=$CERT_DIR/dev-key.pem}"
  export LPS2_TLS_CERT LPS2_TLS_KEY
  if [ ! -f "$LPS2_TLS_CERT" ] || [ ! -f "$LPS2_TLS_KEY" ]; then
    echo "[run_dev] Generating self-signed certificate..." >&2
    openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
      -subj "/C=US/ST=Dev/L=Local/O=LPS2/OU=Dev/CN=localhost" \
      -keyout "$LPS2_TLS_KEY" -out "$LPS2_TLS_CERT" >/dev/null 2>&1 || {
        echo "[run_dev] ERROR: openssl not available or cert generation failed" >&2
      }
  fi
  echo "[run_dev] TLS enabled: https://127.0.0.1:5000" >&2
else
  echo "[run_dev] TLS disabled (set LPS2_ENABLE_TLS=1 to enable)." >&2
fi
exec python src/app.py
