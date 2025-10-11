# Security Considerations

## ⚠️ IMPORTANT: Default Credentials

This project contains **default credentials and keys** that must be changed before deploying to production:

1. **API Key**: The default API key is `secret12345`
   - Change with environment variable: `LPS2_API_KEY=your_secure_key_here`

2. **Admin Password**: The default admin password is `admin123`
   - Change with environment variable: `LPS2_ADMIN_PASSWORD=your_secure_password_here`

3. **Secret Key**: The default Flask secret key is `dev-insecure-secret-key`
   - Change with environment variable: `LPS2_SECRET_KEY=your_random_secret_key_here`

Deploying with default credentials poses a significant security risk. Generate strong, unique values for all these settings in production.

## Security Best Practices

1. **TLS Encryption**: Always enable TLS in production
   - Set `LPS2_ENABLE_TLS=1` and provide valid certificates

2. **Secure Storage**: Consider encrypting `memory_store.json` and `knowledge_store.json` files if they contain sensitive data

3. **Rate Limiting**: Adjust rate limit settings based on your deployment needs
   - Modify `LPS2_RATE_*` environment variables

4. **Audit Logging**: Monitor `audit.log` for suspicious activities

5. **Regular Updates**: Keep dependencies updated to address security vulnerabilities

6. **Login-First & Session Timeouts**: The application enforces a login page before accessing the UI and supports configurable session timeouts:
   - `LPS2_SESSION_IDLE_SECONDS` (default 1800s) – expires idle sessions
   - `LPS2_SESSION_ABSOLUTE_SECONDS` (default 28800s) – maximum session lifetime
   - API requests receive `401 {"error":"session_expired"}`; the client automatically redirects to `/login` with a toast.

For more detailed security information, see the [ARCHITECTURE.md](ARCHITECTURE.md) file.