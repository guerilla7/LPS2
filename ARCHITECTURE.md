# LPS2 System Architecture

This document provides an overview of the LPS2 (Local, Private, Secure Small Language Model Server) architecture, its components, and how they interact.

## System Overview

LPS2 is a Flask-based web application that provides a privacy-focused chat interface for local or self-hosted LLM (Large Language Model) inference. It is designed with security, privacy, and extensibility in mind.

## Key Components

### 1. Core Application

- **app.py**: Main application entry point, sets up Flask, authentication, and routes
   - Enforces login-first access and configurable session timeouts (idle/absolute)
- **config.py**: Central configuration module that loads environment variables with defaults
- **routes/**: Directory containing route handlers for different endpoints
  - **chat.py**: Handles chat-related routes and LLM interactions

### 2. Utility Modules

- **utils/embeddings.py**: Centralized interface for text embeddings generation
- **utils/knowledge_store.py**: Manages knowledge base with semantic search capabilities
- **utils/memory_store.py**: Manages conversation memory with vector search
- **utils/security_utils.py**: Security-focused utilities for content sanitization and protection
- **utils/rate_limiter.py**: Rate limiting implementation with tiered access levels
- **utils/audit_logger.py**: Logging system for security-relevant events
- **utils/user_utils.py**: User management utilities and secure password handling
- **utils/error_handler.py**: Standardized error handling and reporting

### 3. Frontend

- **static/index.html**: Main chat interface
- **static/login.html**: Authentication interface
- **static/admin.html**: Administration panel
- **static/js/common.js**: Shared JavaScript utilities
   - Centralized fetch with CSRF handling and session-expired (401) redirect/toast logic

## Data Flow

1. **Request Flow**:
   - Client sends request through the web interface
   - Authentication/authorization layer validates access
   - Rate limiting is applied based on user tier
   - Request is routed to appropriate handler

2. **Chat Interaction Flow**:
   - User submits query via chat interface
   - System checks for PII and applies redaction if enabled
   - Query is enhanced with relevant knowledge base results
   - Previous conversation memory is retrieved
   - Augmented query is sent to LLM
   - Response is logged and returned to user

3. **Knowledge Base Flow**:
   - Documents are ingested through admin interface
   - Content is sanitized and chunked
   - Vector embeddings are generated for chunks
   - Embeddings and metadata are stored for retrieval
   - Retrieved during chat for context augmentation

## Security Architecture

### Authentication & Authorization

- Session-based authentication for web interface
- API key authentication for programmatic access
- Role-based access control (user/admin)
- CSRF protection for state-changing operations
 - Login-first enforcement and session timeouts (idle/absolute), with client-side redirect on expiration

### Content Security

- Input sanitization to prevent prompt injection
- PII detection and optional redaction
- Suspicious content flagging
- Audit logging of security events

### Privacy Protection

- All data remains local (no external API calls)
- In-memory rate limiting to prevent abuse
- Content quarantine for potentially harmful material

## Deployment Architecture

### Local Development

- Flask development server with auto-reload
- Optional TLS support for secure local testing

### Production Deployment

- Gunicorn WSGI server for production
- Docker container with non-root user
- Environment variable configuration

## Extensibility Points

- **Knowledge Sources**: Add new document types and sources
- **Tool Integration**: Add new tools via the extensible tool framework
- **LLM Backends**: Support different inference endpoints via profiles

## Configuration Options

Configuration is managed through environment variables with sensible defaults. Key options include:

- `LPS2_API_KEY`: API key for authentication
- `LPS2_SECRET_KEY`: Session encryption key
- `LPS2_ADMIN_PASSWORD`: Admin user password
- `LPS2_ENABLE_TLS`: Enable/disable TLS encryption
- `LPS2_RATE_WINDOW`, `LPS2_RATE_MAX`, `LPS2_RATE_BURST`: Rate limiting parameters
- `LPS2_QUARANTINE`: Enable/disable content quarantine
- `LPS2_PII_REDACT`: Enable/disable PII redaction

For a complete list of configuration options, see the `ENV_EXAMPLE.txt` file.

## System Requirements

- Python 3.8+
- Sufficient memory for embedding models
- Docker (optional)