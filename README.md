# LPS2 – Local / Private / Secure Small Language Model Server

<div align="center">

<p>
<a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
<a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+"></a>
<a href="https://flask.palletsprojects.com/"><img src="https://img.shields.io/badge/Flask-2.2.2-green.svg" alt="Flask"></a>
<a href="https://github.com/guerilla7/LPS2"><img src="https://img.shields.io/badge/Maintained-yes-green.svg" alt="Maintained: yes"></a>
<a href="https://makeapullrequest.com"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
</p>

<p>
<a href="https://www.docker.com/"><img src="https://img.shields.io/badge/Docker-supported-blue.svg" alt="Docker"></a>
<a href="https://en.wikipedia.org/wiki/Transport_Layer_Security"><img src="https://img.shields.io/badge/Security-TLS-blue.svg" alt="Security: TLS"></a>
<a href="https://github.com/guerilla7/LPS2"><img src="https://img.shields.io/badge/GitHub-LPS2-orange.svg" alt="GitHub"></a>
</p>

<p>
<a href="https://github.com/guerilla7/LPS2/stargazers"><img src="https://img.shields.io/github/stars/guerilla7/LPS2.svg?style=social&label=Stars" alt="GitHub Stars"></a>
<a href="https://github.com/guerilla7/LPS2/network/members"><img src="https://img.shields.io/github/forks/guerilla7/LPS2.svg?style=social&label=Fork" alt="GitHub Forks"></a>
<a href="https://github.com/guerilla7/LPS2/issues"><img src="https://img.shields.io/github/issues/guerilla7/LPS2.svg" alt="GitHub Issues"></a>
<a href="https://github.com/guerilla7/LPS2/commits/main"><img src="https://img.shields.io/github/last-commit/guerilla7/LPS2.svg" alt="GitHub Last Commit"></a>
</p>

</div>

## Quick Start

Get up and running with LPS2 in minutes:

```bash
# Clone the repository
git clone https://github.com/guerilla7/LPS2.git
cd LPS2

# Start the development server
./scripts/run_dev.sh

# Visit http://localhost:5000 in your browser
# Default login: admin / admin123
```

### Docker Quickstart

```bash
# Build and run with Docker
docker build -t lps2 .
docker run -p 5000:5000 lps2

# Visit http://localhost:5000 in your browser
```

## Introduction: The Case for Local and Private LLM Inference

In an era where data privacy and security concerns are paramount, locally-hosted small language models (SLMs) offer compelling advantages over cloud-based alternatives. Running LLMs locally enables organizations to maintain complete control over sensitive data, eliminating exposure risks inherent in third-party API calls and data transfers. This is particularly crucial for cybersecurity applications and privacy-sensitive experiments where data sovereignty, regulatory compliance (GDPR, HIPAA, CCPA), and protection of intellectual property are non-negotiable requirements.

Local inference servers also provide enhanced operational security by eliminating external dependencies, reducing attack surfaces, and allowing for air-gapped deployments in high-security environments. While smaller models may not match the capabilities of their larger counterparts in some domains, recent research demonstrates that carefully fine-tuned SLMs can achieve comparable performance for specialized tasks while offering significantly reduced latency, lower computational overhead, and improved inference speed—critical factors for real-time applications.

## Features and Capabilities

LPS2 provides a streamlined, privacy‑focused chat interface over locally or self‑hosted OpenAI‑compatible inference endpoints:

### User Interface
- **Modern Chat UI**: Token estimation, undo functionality, command palette
- **Privacy Features**: PII preflight scanning, attachment support with image metadata stripping
- **Tool Integration**: Wikipedia search placeholder and extensible framework

### Admin Console
- **Knowledge Base Management**: Text/PDF ingestion with OCR support, search, deletion, and quarantine controls
- **Memory Management**: Browse, search, and delete conversation memories with summarization flags
- **Security Tools**: Quarantine viewer and comprehensive audit event logging
- **Inference Management**: Create, test, and activate multiple LLM endpoints with performance metrics

### Advanced Features
- **Retrieval-Augmented Generation**: Knowledge citations with confidence scoring
- **Conversation Memory**: Lightweight persistence with summarization and suspicious content flagging
- **Security Controls**: CSRF protection, API key authentication, rate limiting, and audit logging
- **Data Protection**: Heuristic PII redaction and content quarantine pipeline

### Technical Features
- **TLS Support**: Optional internal TLS (self-signed in development) with production guidance
- **Extensible Architecture**: Modular front-end utilities and unified navigation
- **Deployment Options**: Development mode and production-ready configurations

All features are designed with privacy, security, and local control as primary objectives, making LPS2 ideal for organizations with strict data sovereignty requirements.

## Project Structure (Simplified)

```
LPS2
├── src
│   ├── app.py                  # Flask app bootstrap, auth, TLS config
│   ├── config.py               # Env loader + runtime configuration
│   ├── routes/
│   │   └── chat.py             # All API endpoints (chat, KB, memory, profiles, audit, etc.)
│   ├── static/
│   │   ├── index.html          # Chat UI
│   │   ├── admin.html          # Admin Console UI
│   │   ├── js/common.js        # Shared front-end utilities
│   │   └── ... (assets)
│   └── utils/
│       ├── llm_client.py       # Base client for inference endpoint
│       ├── knowledge_store.py  # Embedding + search + ingest / quarantine
│       ├── memory_store.py     # Conversation memory persistence
│       ├── audit_logger.py     # Append‑only audit log
│       ├── rate_limiter.py     # Basic in-memory rate limiting
│       └── security_utils.py   # Redaction / sanitization helpers
├── scripts/
│   └── run_dev.sh              # Dev launcher (TLS self‑signed by default)
├── dev_certs/                  # Auto-generated self-signed certs (ignored in prod)
├── inference_profiles.json     # Persisted endpoint profiles (created at runtime)
├── Dockerfile                  # Production (Gunicorn) container recipe
├── requirements.txt
└── README.md
```

## ⚡ Quick Start (5 Minutes)

Get up and running in 5 minutes with these simplified steps:

```bash
# 1. Clone the repository and navigate to it
git clone <repository-url> && cd LPS2

# 2. Set up a local inference server (pick one)
## Option A: Start Ollama (recommended for Apple Silicon)
ollama pull llama3:8b && ollama serve &
export LPS2_LLM_ENDPOINT=http://localhost:11434/v1

## Option B: Use LM Studio (via GUI)
# Download and run LM Studio, start the server, then:
export LPS2_LLM_ENDPOINT=http://localhost:1234/v1

# 3. Launch the app with one command
bash scripts/run_dev.sh
```

Then open `https://localhost:5000` in your browser and accept the self-signed certificate warning.

Default login: `admin` / `admin123`

That's it! Start chatting with your local LLM while maintaining complete data privacy.

## Quick Start (Development)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd LPS2
   ```

2. **Install dependencies**:
   Make sure you have Python installed. Then, install the required packages using pip:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run (recommended)** – use the helper script (auto TLS + env + deps):
   ```bash
   bash scripts/run_dev.sh
   ```
   This will:
   * Create a virtualenv (if missing) & install dependencies.
   * Generate a self‑signed cert (if absent) and start HTTPS on `https://localhost:5000`.

   To disable dev TLS (HTTP only):
   ```bash
   export LPS2_DISABLE_TLS=1
   bash scripts/run_dev.sh
   ```

4. **Access**: `https://localhost:5000` (accept the self‑signed certificate warning).

5. **Default Credentials**: The first admin user/password come from environment variables (or defaults). See ENV section below.

## Basic Usage

Enter prompts in the chat UI; attachments (text / image) are sanitized (image metadata stripped). If the prompt risks including detected PII patterns (email, SSN-like, credit card, phone) an inline warning appears (dismissible). The request is forwarded to the active inference endpoint (initially from `LPS2_LLM_ENDPOINT` or an activated profile). Citations from the Knowledge Base appear when retrieval augmentation returns matches.

## Generation & Inference Controls

You can control response length and sampling via environment variables before starting the server:

```bash
export LPS2_MAX_TOKENS=2048        # Max tokens per request (also sets max_new_tokens)
export LPS2_CONTINUE_ROUNDS=3      # Allow up to 3 auto "Continue" follow-ups if model stops for length
export LPS2_AUTO_CONTINUE=1        # Enable (set 0 to disable auto-continuation)
export LPS2_TEMPERATURE=0.6        # Sampling temperature
export LPS2_TOP_P=0.9              # Nucleus sampling top-p
python src/app.py  # or bash scripts/run_dev.sh
```

If a response is cut off due to length, the client automatically issues continuation prompts ("Continue.") up to the configured number of rounds and concatenates the segments.

### Persistent Configuration (.env)

You can persist these and other settings by creating a `.env` file at project root (same level as `src/`). Example template in `ENV_EXAMPLE.txt`:

```
LPS2_API_KEY=change_me_secure_key
LPS2_MAX_TOKENS=2048
LPS2_CONTINUE_ROUNDS=3
LPS2_AUTO_CONTINUE=1
LPS2_TEMPERATURE=0.6
LPS2_TOP_P=0.9
```

On startup the app loads `.env` first (without overwriting already-exported environment variables), then falls back to defaults.

## Feature Overview

> **⚠️ SECURITY NOTICE:** This project contains default credentials that must be changed before deployment.  
> See [SECURITY.md](SECURITY.md) for important security information.

| Area | Highlights |
|------|------------|
| Authentication | Session login (username/password) + API key fallback (`LPS2_API_KEY`) |
| Authorization | Role-based admin (`LPS2_ADMIN_USERS`) gating for all mutating KB / memory / profile routes |
| CSRF | Per-session token required for unsafe (POST) when session auth in use |
| Knowledge Base | Text/PDF ingest (optional OCR via Tesseract), search, quarantine pipeline, deletion, source tagging |
| Memory Store | Rolling conversation memory with summaries, suspicious flags, deletion & search |
| Inference Profiles | Create/test (latency + model probe)/activate multiple endpoints with optional persistence |
| PII Guard & Redaction | Client-side preflight + server redaction heuristics (configurable) |
| Audit & Security | Append-only audit log for admin actions & ingestion events |
| UI Enhancements | Command palette, undo last exchange, token estimation, attachments, dark/light mode, nav bar |
| TLS | Self-signed by default in dev; production via reverse proxy + Let's Encrypt |
| Rate Limiting | In-memory window + burst controls (`LPS2_RATE_*`) |

See `src/config.py` for toggle logic.

## Enabling TLS (HTTPS)

For development you can enable HTTPS with a self-signed certificate. The built-in Flask server is not production grade; in production you should place Gunicorn/Uvicorn behind a reverse proxy (Nginx, Caddy, Traefik) terminating TLS with a trusted certificate (e.g., via Let's Encrypt).

### Quick Start (Self-Signed Dev Cert)

TLS is now enabled by default in the dev script. To opt out (HTTP only):

```bash
export LPS2_DISABLE_TLS=1
bash scripts/run_dev.sh
```

Otherwise simply run:

```bash
bash scripts/run_dev.sh
```

If no cert/key are provided, the dev script will auto-generate a pair in `dev_certs/` (requires `openssl`). Access the app at: `https://localhost:5000` (you'll need to accept the browser warning for the self-signed certificate).

### Generating Your Own Self-Signed Certificate Manually

```bash
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
   -subj "/C=US/ST=Dev/L=Local/O=LPS2/OU=Dev/CN=localhost" \
   -keyout dev-key.pem -out dev-cert.pem
export LPS2_ENABLE_TLS=1
export LPS2_TLS_CERT=$PWD/dev-cert.pem
export LPS2_TLS_KEY=$PWD/dev-key.pem
python src/app.py
```

### Production Recommendation (Trusted Certs)

Use a reverse proxy with automatic certificate renewal. Example (Caddyfile excerpt):

```
your.domain.com {
      reverse_proxy 127.0.0.1:5000
}
```

Or Nginx (snippet):

```
server {
   listen 443 ssl;
   server_name your.domain.com;
   ssl_certificate /etc/letsencrypt/live/your.domain.com/fullchain.pem;
   ssl_certificate_key /etc/letsencrypt/live/your.domain.com/privkey.pem;
   location / { proxy_pass http://127.0.0.1:5000; proxy_set_header Host $host; }
}
```

Set `LPS2_ENABLE_TLS=0` in that case and let the proxy handle encryption.

### Automatic Let's Encrypt Certificates

You should terminate TLS at a reverse proxy that can automatically obtain and renew certificates from Let's Encrypt. Two common approaches:

#### Option 1: Caddy (automatic HTTPS built-in)

`Caddyfile`:
```
your.domain.com {
      reverse_proxy 127.0.0.1:5000
      encode gzip
      # Optional hardening headers
      header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
      header X-Frame-Options "DENY"
      header X-Content-Type-Options "nosniff"
      header Referrer-Policy "strict-origin-when-cross-origin"
}
```
Run:
```bash
caddy run --config Caddyfile
```

Caddy will automatically request and renew certificates (ensure DNS A/AAAA records point to this host and port 80/443 are reachable).

#### Option 2: Nginx + Certbot

1. Install certbot + nginx plugin (Ubuntu example):
```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
```
2. Basic Nginx site config ( `/etc/nginx/sites-available/lps2.conf` ):
```
server {
      listen 80;
      server_name your.domain.com;
      location / {
            proxy_pass http://127.0.0.1:5000;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      }
}
```
3. Enable and test:
```bash
sudo ln -s /etc/nginx/sites-available/lps2.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```
4. Obtain cert:
```bash
sudo certbot --nginx -d your.domain.com --redirect
```
This updates the config to serve 443 with a valid cert and sets up auto-renew (`/etc/cron.d` or systemd timer). Test renewal:
```bash
sudo certbot renew --dry-run
```

#### Option 3: Docker + Caddy (Compose)

`docker-compose.yml` snippet:
```yaml
version: '3.9'
services:
   app:
      build: .
      environment:
         LPS2_ENABLE_TLS: "0"  # proxy will handle TLS
      expose:
         - "5000"
   caddy:
      image: caddy:2
      restart: unless-stopped
      ports:
         - "80:80"
         - "443:443"
      volumes:
         - ./Caddyfile:/etc/caddy/Caddyfile:ro
         - caddy-data:/data
         - caddy-config:/config
volumes:
   caddy-data:
   caddy-config:
```

#### Gunicorn (App Server) Command Examples

Recommended run behind proxy:
```bash
gunicorn -w 4 -k gthread --threads 8 -b 127.0.0.1:5000 --timeout 120 src.app:app
```

#### Security Headers (Proxy Layer)
Add at proxy (Nginx example inside server block):
```
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()";
```

#### Disable Internal TLS When Using a Proxy
Ensure:
```bash
export LPS2_ENABLE_TLS=0
```
or set `LPS2_DISABLE_TLS=1` with the dev script. Internal self-signed certs are unnecessary when a trusted proxy terminates HTTPS.

### Renewal Monitoring
For Certbot: check logs in `/var/log/letsencrypt/` and consider a cron alert on failure.
For Caddy: certificates auto-renew; inspect `docker logs caddy` (container) or journal logs for issues.

## Dependencies
Python packages (see `requirements.txt`):

| Package | Purpose |
|---------|---------|
| Flask / Werkzeug | Web framework & underlying server utilities |
| requests | Outbound HTTP to inference endpoints / testing profiles |
| sentence-transformers | Embeddings for knowledge base retrieval |
| numpy | Vector operations |
| Pillow (PIL) | Image handling & metadata stripping |
| PyPDF2 | PDF text extraction |
| pdf2image | PDF page rasterization (when OCR needed) |
| pytesseract | OCR (optional; requires system Tesseract) |
| gunicorn | Production WSGI server (container / proxy deployment) |

System dependencies (only if using PDF OCR path):
* poppler utils (for `pdf2image`) – e.g. `brew install poppler` or `apt install poppler-utils`
* tesseract OCR – e.g. `brew install tesseract` or `apt install tesseract-ocr`
* openssl (auto self-signed cert generation in dev script)

If OCR dependencies are missing, ingestion without OCR still works for plain text and directly extractable PDFs.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| LPS2_API_KEY | API key for non-session requests | secret12345 (dev) |
| LPS2_SECRET_KEY | Flask session secret | dev-insecure-secret-key |
| LPS2_ADMIN_USER / LPS2_ADMIN_PASSWORD | Seed admin credentials (if password provided) | admin / admin123 (dev) |
| LPS2_ADMIN_PASSWORD_HASH | Pre-hashed password (overrides plain) | – |
| LPS2_ADMIN_USERS | Comma list of admin usernames | admin |
| LPS2_LLM_ENDPOINT | Base inference endpoint (OpenAI compatible) | http://192.168.5.66:1234 |
| LPS2_MAX_TOKENS | Max model output tokens | 2048 |
| LPS2_CONTINUE_ROUNDS | Auto continuation attempts | 2 |
| LPS2_AUTO_CONTINUE | Enable auto-extension | 1 |
| LPS2_TEMPERATURE | Sampling temperature | 0.7 |
| LPS2_TOP_P | Nucleus sampling p | 0.95 |
| LPS2_RATE_WINDOW | Rate limit window seconds | 60 |
| LPS2_RATE_MAX | Max requests per IP per window | 120 |
| LPS2_RATE_BURST | Burst allowance | 30 |
| LPS2_QUARANTINE | Enable KB quarantine pipeline | 1 |
| LPS2_PII_REDACT | Enable server redaction heuristics | 1 |
| LPS2_ENABLE_TLS | Enable internal TLS (self-signed or provided cert) | 1 (via run_dev.sh) |
| LPS2_DISABLE_TLS | Force disable TLS in dev script | unset |
| LPS2_TLS_CERT / LPS2_TLS_KEY | Paths to cert/key for internal TLS | dev_certs/* if auto |
| LPS2_FORCE_HTTPS | Redirect HTTP→HTTPS (proxy scenarios) | 0 |
| LPS2_PORT | Listen port | 5000 |

Runtime profile system can supersede `LPS2_LLM_ENDPOINT` after activating an endpoint profile via Admin Console.

## 🖥️ Compatible Local LLM Inference Servers

This application is designed to work with any OpenAI API-compatible local inference server. Here are guides for setting up the most popular options:

### LM Studio

[LM Studio](https://lmstudio.ai/) offers a user-friendly GUI for running local models:

1. **Download & Install**: Get LM Studio from [lmstudio.ai](https://lmstudio.ai/)
2. **Load a Model**: Download a model like Llama-3-8B or Mistral-7B through the interface
3. **Start Local Server**: Click "Local Server" → "Start Server"
4. **Connect LPS2**:
   ```bash
   export LPS2_LLM_ENDPOINT=http://localhost:1234/v1
   bash scripts/run_dev.sh
   ```
   Alternatively, use the Admin Console to create a new endpoint profile.

LM Studio is ideal for beginners and desktop users, with excellent macOS and Windows support.

### Ollama

[Ollama](https://ollama.com/) offers a lightweight command-line approach:

1. **Install Ollama**:
   ```bash
   # macOS
   curl -fsSL https://ollama.com/install.sh | sh
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Pull a Model**:
   ```bash
   ollama pull llama3:8b
   # or
   ollama pull mistral:7b
   ```

3. **Start Server**:
   ```bash
   ollama serve
   ```

4. **Connect LPS2**:
   ```bash
   export LPS2_LLM_ENDPOINT=http://localhost:11434/v1
   bash scripts/run_dev.sh
   ```

Ollama provides excellent performance on Macs with Apple Silicon and has low resource requirements.

### vLLM

[vLLM](https://github.com/vllm-project/vllm) offers optimized high-performance inference:

1. **Install vLLM**:
   ```bash
   pip install vllm
   # CUDA required for GPU acceleration
   ```

2. **Start Server** with OpenAI-compatible API:
   ```bash
   python -m vllm.entrypoints.openai.api_server \
     --model=meta-llama/Llama-2-7b-chat-hf \
     --port=8000
   ```

3. **Connect LPS2**:
   ```bash
   export LPS2_LLM_ENDPOINT=http://localhost:8000/v1
   bash scripts/run_dev.sh
   ```

vLLM is ideal for higher-end systems with NVIDIA GPUs, offering maximum throughput and advanced features like tensor parallelism.

### Docker Compose with vLLM

For a full stack deployment, use this example `docker-compose.yml`:

```yaml
version: '3.8'
services:
  vllm:
    image: ghcr.io/vllm-project/vllm:latest
    command: --host 0.0.0.0 --port 8000 --model meta-llama/Llama-2-7b-chat-hf
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  
  lps2:
    build: .
    depends_on:
      - vllm
    environment:
      - LPS2_LLM_ENDPOINT=http://vllm:8000/v1
      - LPS2_ENABLE_TLS=0
    ports:
      - "5000:5000"
```

Run with: `docker compose up`

### Model Selection Recommendations

For optimal balance of performance and quality:

| Use Case | Recommended Models |
|----------|-------------------|
| General Chat | Llama-3-8B, Mistral-7B, Gemma-7B |
| Code & Technical | CodeLlama-7B, WizardCoder-Python-7B |
| Low Resources | TinyLlama-1.1B, Phi-3-mini-4k-instruct |
| High Quality | Llama-3-70B-Instruct (requires >24GB VRAM) |

Most models are available through Hugging Face or directly from model providers.

## Contributing

Feel free to submit issues or pull requests if you have suggestions or improvements for the project.

## Roadmap / Nice-to-Haves
* Pagination for large Knowledge Base & audit logs.
* Export/import utilities for KB and memory stores.
* Automated test suite (auth, CSRF, profile activation, rate limit).
* Pluggable embedding backends & vector DB abstraction.
* WebSocket streaming responses.

---
For production deployment, prefer: Gunicorn (workers) + Caddy/Nginx TLS termination + hardened headers + real secrets management (Vault/SM) + external persistence (database / object store) for scaling beyond single host.

## About the Author

<div align="center">
  <img src="https://img.shields.io/badge/Created%20By-Ron%20F.%20Del%20Rosario-1f425f.svg">
  <p>
    <img src="https://img.shields.io/badge/GitHub%20Handle-guerilla7-181717.svg?style=for-the-badge&logo=github">
  </p>
  <p><i>Developed with ☕ and passion for secure, privacy-focused LLM applications</i></p>
</div>