#!/usr/bin/env bash
set -euo pipefail
# Simple dependency vulnerability scan using pip-audit.
# Usage: ./scripts/vuln_scan.sh
# Exits non-zero if vulnerabilities are found.

if ! command -v pip-audit >/dev/null 2>&1; then
  echo "[INFO] Installing pip-audit locally (will not modify requirements.txt)" >&2
  python -m pip install --upgrade pip >/dev/null 2>&1 || true
  python -m pip install pip-audit >/dev/null 2>&1
fi

# Prefer requirements.txt if present
if [[ -f requirements.txt ]]; then
  echo "[INFO] Auditing dependencies from requirements.txt" >&2
  pip-audit -r requirements.txt
else
  echo "[INFO] Auditing currently installed environment packages" >&2
  pip-audit
fi

count=$(pip-audit -r requirements.txt -f json 2>/dev/null | python -c 'import sys,json;data=json.load(sys.stdin);print(sum(len(v["vulns"]) for v in data))' || echo 0)
if [[ "$count" -gt 0 ]]; then
  echo "[FAIL] Found $count vulnerabilities." >&2
  exit 1
fi

echo "[OK] No known vulnerabilities found." >&2
