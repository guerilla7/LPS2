from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
import time
import secrets
from routes.chat import init_chat_route
import sys
import warnings
from datetime import timedelta

import os
# SECURITY WARNING: Default API key for development only
if 'LPS2_API_KEY' not in os.environ:
    default_api_key = 'secret12345'
    warnings.warn(
        f"\n\n‼️  SECURITY WARNING: Using default insecure API key '{default_api_key}'.\n"
        "    This is only for development and MUST be changed in production.\n"
        "    Set the LPS2_API_KEY environment variable to a strong, unique value.\n",
        category=RuntimeWarning, stacklevel=2
    )
    os.environ['LPS2_API_KEY'] = default_api_key

app = Flask(__name__, static_folder="static")

# SECURITY WARNING: Default secret key for development only
default_secret_key = 'dev-insecure-secret-key'
app_secret = os.environ.get('LPS2_SECRET_KEY', default_secret_key)
if app_secret == default_secret_key:
    warnings.warn(
        "\n\n‼️  SECURITY WARNING: Using default insecure Flask secret key.\n"
        "    This is only for development and MUST be changed in production.\n"
        "    Set the LPS2_SECRET_KEY environment variable to a strong, random value.\n",
        category=RuntimeWarning, stacklevel=2
    )
app.secret_key = app_secret

# If TLS is enabled, tighten cookie security defaults
if os.environ.get('LPS2_ENABLE_TLS', '').lower() in ('1','true','yes','on'):
    app.config.update(
        SESSION_COOKIE_SECURE=True,      # Only sent over HTTPS
        SESSION_COOKIE_HTTPONLY=True,    # Not accessible to JS
        SESSION_COOKIE_SAMESITE='Lax',   # Mitigate CSRF on top-level navigations
        PREFERRED_URL_SCHEME='https'
    )

# Optional forced redirect to HTTPS (useful when running behind a reverse proxy terminating TLS)
if os.environ.get('LPS2_FORCE_HTTPS', '').lower() in ('1','true','yes','on'):
    @app.before_request
    def _enforce_https():
        # Respect common proxy header; fall back to request.scheme
        proto = request.headers.get('X-Forwarded-Proto', request.scheme)
        if proto != 'https':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

# --- Simple in-memory user store (for local dev) ---
from werkzeug.security import generate_password_hash, check_password_hash

DEFAULT_USER = os.environ.get('LPS2_ADMIN_USER', 'admin')
_pwd_plain = os.environ.get('LPS2_ADMIN_PASSWORD')
_pwd_hash_env = os.environ.get('LPS2_ADMIN_PASSWORD_HASH')
if _pwd_hash_env:
    DEFAULT_HASH = _pwd_hash_env
else:
    if not _pwd_plain:
        _pwd_plain = 'admin123'  # Dev fallback
        warnings.warn(
            "\n\n‼️  SECURITY WARNING: Using default admin password 'admin123'.\n"
            "    This is only for development and MUST be changed in production.\n"
            "    Set the LPS2_ADMIN_PASSWORD environment variable to a strong, unique password.\n",
            category=RuntimeWarning, stacklevel=2
        )
    DEFAULT_HASH = generate_password_hash(_pwd_plain)
USERS = {DEFAULT_USER: DEFAULT_HASH}
ADMIN_USERS = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS', DEFAULT_USER).split(',') if u.strip()}

def login_required(fn):
    def _wrap(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('login_page'))
        return fn(*args, **kwargs)
    _wrap.__name__ = fn.__name__
    return _wrap

def admin_required(fn):
    def _wrap(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('login_page'))
        if session.get('user') not in ADMIN_USERS:
            return jsonify({'error': 'forbidden'}), 403
        return fn(*args, **kwargs)
    _wrap.__name__ = fn.__name__
    return _wrap


# Initialize chat route
init_chat_route(app)

# Serve the UI
@app.route('/')
@login_required
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/login', methods=['GET'])
def login_page():
    # If already logged in, redirect to app
    if session.get('user'):
        return redirect('/')
    return send_from_directory(app.static_folder, 'login.html')

@app.route('/login', methods=['POST'])
def login_post():
    # Step 1: Extract and validate credentials
    try:
        # Import here to avoid circular imports
        from utils.schemas import LoginSchema
        from utils.validation import validate_data
        data = request.json if request.is_json else request.form
        is_valid, validated_data, errors = validate_data(data, LoginSchema)
        if not is_valid:
            return jsonify({'error': 'validation_error', 'message': 'Invalid login credentials', 'details': errors}), 400
        username = validated_data['username'].strip()
        password = validated_data['password']
    except ImportError:
        # Fallback if validation module is not available
        data = request.json if request.is_json else request.form
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if not username or not password:
            return jsonify({'error': 'missing_credentials'}), 400
    except Exception as e:
        # Log the error but continue with a simple schema-less validation
        app.logger.error(f"Login validation error: {str(e)}")
        data = request.json if request.is_json else request.form
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if not username or not password:
            return jsonify({'error': 'missing_credentials'}), 400

    # Step 2: Verify credentials
    stored = USERS.get(username)
    if not stored or not check_password_hash(stored, password):
        return jsonify({'error': 'invalid_credentials'}), 401

    # Step 3: Establish session
    session['user'] = username
    session['csrf_token'] = secrets.token_urlsafe(32)
    session['login_time'] = int(time.time())
    session['last_activity'] = int(time.time())
    session.permanent = True
    return jsonify({'ok': True, 'user': username})

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    session.pop('csrf_token', None)
    session.pop('login_time', None)
    session.pop('last_activity', None)
    return jsonify({'ok': True})

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/auth/status')
def auth_status():
    """Return basic authentication status so frontend can decide whether to send API key headers.

    {"authenticated": true/false, "user": <username or null>}
    """
    user = session.get('user')
    token = session.get('csrf_token')
    # If user exists but no token (e.g., session predates feature), issue one
    if user and not token:
        token = secrets.token_urlsafe(32)
        session['csrf_token'] = token
    is_admin = bool(user in ADMIN_USERS) if user else False
    return jsonify({'authenticated': bool(user), 'user': user, 'csrf_token': token, 'is_admin': is_admin})

# --- Session enforcement and timeouts ---
@app.before_request
def _enforce_login_and_timeouts():
    # Allow health and auth status without auth
    if request.endpoint in {'health', 'auth_status', 'login_page', 'login_post'}:
        return None

    path = request.path or ''
    # Block direct access to static HTML except login.html when not authenticated
    if not session.get('user'):
        if path in {'/', '/admin'}:
            return redirect(url_for('login_page'))
        if path.startswith('/static/') and path.lower().endswith('.html') and not path.endswith('/login.html') and not path.endswith('login.html'):
            return redirect(url_for('login_page'))
        # For API routes without session, allow existing key-based flows to proceed.
        # UI routes will be guarded by above conditions.
        return None

    # Session present: enforce idle and absolute timeouts
    now_ts = int(time.time())
    try:
        idle_limit = int(os.environ.get('LPS2_SESSION_IDLE_SECONDS', '1800'))  # 30 minutes default
    except Exception:
        idle_limit = 1800
    try:
        abs_limit = int(os.environ.get('LPS2_SESSION_ABSOLUTE_SECONDS', '28800'))  # 8 hours default
    except Exception:
        abs_limit = 28800

    login_time = session.get('login_time') or now_ts
    last_activity = session.get('last_activity') or now_ts

    expired = False
    reason = None
    if abs_limit > 0 and (now_ts - login_time) > abs_limit:
        expired = True
        reason = 'absolute_timeout'
    elif idle_limit > 0 and (now_ts - last_activity) > idle_limit:
        expired = True
        reason = 'idle_timeout'

    if expired:
        # Clear session and respond appropriately (JSON vs HTML)
        session.pop('user', None)
        session.pop('csrf_token', None)
        session.pop('login_time', None)
        session.pop('last_activity', None)
        wants_json = request.is_json or (request.accept_mimetypes.best == 'application/json')
        if wants_json or request.path.startswith('/chat') or request.path.startswith('/admin/llm-endpoints'):
            return jsonify({'error': 'session_expired', 'reason': reason}), 401
        return redirect(url_for('login_page'))

    # Refresh idle timer
    session['last_activity'] = now_ts
    return None

@app.route('/admin')
@login_required
@admin_required
def admin_page():
    return send_from_directory(app.static_folder, 'admin.html')

if __name__ == '__main__':
    # Configure absolute session lifetime for Flask's permanent session cookie behavior
    try:
        _abs_secs = int(os.environ.get('LPS2_SESSION_ABSOLUTE_SECONDS', '28800'))
        app.permanent_session_lifetime = timedelta(seconds=_abs_secs)
    except Exception:
        pass
    enable_tls = os.environ.get('LPS2_ENABLE_TLS', '').lower() in ('1','true','yes','on')
    cert_path = os.environ.get('LPS2_TLS_CERT')
    key_path = os.environ.get('LPS2_TLS_KEY')
    ssl_context = None
    port = int(os.environ.get('LPS2_PORT', '5000'))
    if enable_tls:
        if cert_path and key_path and os.path.exists(cert_path) and os.path.exists(key_path):
            ssl_context = (cert_path, key_path)
            print(f"[TLS] Starting with TLS enabled using cert={cert_path} key={key_path}")
        else:
            print('[TLS] LPS2_ENABLE_TLS set but certificate paths missing or invalid. Falling back to HTTP.')
    else:
        print('[TLS] Running without TLS (HTTP). Set LPS2_ENABLE_TLS=1 and provide LPS2_TLS_CERT/LPS2_TLS_KEY to enable.')
    print(f"[LPS2] Listening on port {port} (TLS={'on' if ssl_context else 'off'})")
    # NOTE: Built-in Flask server is not production grade; for production use gunicorn/uwsgi behind a real web server.
    app.run(host='0.0.0.0', port=port, ssl_context=ssl_context)