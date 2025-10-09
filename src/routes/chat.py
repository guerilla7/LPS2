from flask import Blueprint, request, jsonify, session
import io
from utils.llm_client import LLMClient
from utils.memory_store import get_memory_store
from utils.knowledge_store import get_knowledge_store
from utils.security_utils import sanitize_text, build_guardrail_preamble, redact_pii
from config import API_KEY, QUARANTINE_ENABLED, LLM_SERVER_URL
from utils.rate_limiter import check_rate
from utils.audit_logger import audit, read_audit  # added
import os
from functools import wraps
import base64
from io import BytesIO
import logging
from collections import deque
try:
    from PIL import Image
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False

# Basic logger setup (idempotent)
logger = logging.getLogger("chat")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

chat_bp = Blueprint('chat', __name__)
llm_client = LLMClient(LLM_SERVER_URL)
_MODEL_LATENCIES = deque(maxlen=50)  # seconds

# --- Inference Endpoint Profiles (Option 5) ---------------------------------
import json, time, threading
_PROFILES_LOCK = threading.Lock()
_PROFILES_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'inference_profiles.json'))
_ENDPOINT_PROFILES = { 'profiles': {}, 'active': None }

def _load_profiles():
    global _ENDPOINT_PROFILES
    if os.path.exists(_PROFILES_PATH):
        try:
            with open(_PROFILES_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                _ENDPOINT_PROFILES = data
        except Exception:
            pass

def _save_profiles():
    tmp = _PROFILES_PATH + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(_ENDPOINT_PROFILES, f, indent=2)
        os.replace(tmp, _PROFILES_PATH)
    except Exception as e:
        logger.error(f"profile_save_failed: {e}")

_load_profiles()

def _test_endpoint_connectivity(endpoint: str, timeout: float = 4.0):
    """Attempt to fetch /v1/models and measure latency.

    Returns dict: {ok: bool, latency_ms?, model?, error?, detail?, checked_at}
    """
    start = time.time()
    import requests as _req
    endpoint_clean = (endpoint or '').strip().rstrip('/')
    if not endpoint_clean:
        return {'ok': False, 'error': 'invalid', 'detail': 'empty', 'checked_at': time.time()}
    if not (endpoint_clean.startswith('http://') or endpoint_clean.startswith('https://')):
        return {'ok': False, 'error': 'invalid_scheme', 'detail': 'must start http:// or https://', 'checked_at': time.time()}
    url = endpoint_clean + '/v1/models'
    try:
        resp = _req.get(url, timeout=timeout)
    except _req.exceptions.ConnectTimeout:
        return {'ok': False, 'error': 'timeout', 'detail': 'connect_timeout', 'checked_at': time.time()}
    except _req.exceptions.ReadTimeout:
        return {'ok': False, 'error': 'timeout', 'detail': 'read_timeout', 'checked_at': time.time()}
    except _req.exceptions.SSLError as e:
        return {'ok': False, 'error': 'ssl_error', 'detail': str(e), 'checked_at': time.time()}
    except _req.exceptions.ConnectionError as e:
        return {'ok': False, 'error': 'connection_refused', 'detail': str(e), 'checked_at': time.time()}
    except Exception as e:
        return {'ok': False, 'error': 'request_failed', 'detail': str(e), 'checked_at': time.time()}
    elapsed_ms = (time.time() - start) * 1000.0
    if resp.status_code != 200:
        return {'ok': False, 'error': 'http_error', 'detail': f'status {resp.status_code}', 'latency_ms': round(elapsed_ms,1), 'checked_at': time.time()}
    try:
        data = resp.json()
    except Exception:
        return {'ok': False, 'error': 'invalid_response', 'detail': 'non-json', 'latency_ms': round(elapsed_ms,1), 'checked_at': time.time()}
    models = data.get('data') or []
    model_id = None
    if models and isinstance(models[0], dict):
        model_id = models[0].get('id')
    return {'ok': True, 'endpoint': endpoint_clean, 'model': model_id, 'latency_ms': round(elapsed_ms,1), 'checked_at': time.time()}


def _validate_csrf_if_session():
    """Validate CSRF token for unsafe methods when using session auth.

    Skips validation for safe methods or when no session user is present (API key only flows).
    Expects token in header 'X-CSRF-Token' or JSON body field 'csrf_token'.
    Returns a Flask response on failure, or None on success.
    """
    if request.method in ('GET','HEAD','OPTIONS'):
        return None
    if not session.get('user'):
        return None
    
    # Get expected token from session
    expected = session.get('csrf_token')
    if not expected:
        logger.warning(f"CSRF validation failed: No CSRF token in session for user {session.get('user')}")
        return jsonify({'error':'csrf_missing'}), 400
    
    # Look for token in headers first (preferred)
    provided = request.headers.get('X-CSRF-Token')
    
    # Fall back to JSON body if not in headers
    if not provided and request.is_json:
        try:
            provided = (request.json or {}).get('csrf_token')
        except Exception as e:
            logger.error(f"Error extracting CSRF from JSON: {str(e)}")
            provided = None
    
    # Check if token is valid
    if not provided:
        logger.warning(f"CSRF validation failed: No CSRF token provided in request for user {session.get('user')}")
        return jsonify({'error':'csrf_missing'}), 400
    
    if provided != expected:
        logger.warning(f"CSRF validation failed: Invalid token for user {session.get('user')}. Expected '{expected[:5]}...', got '{provided[:5] if provided else None}...'")
        return jsonify({'error':'csrf_invalid'}), 403
    
    return None

# --- Runtime LLM endpoint management helpers ---------------------------------
def _update_llm_endpoint(new_endpoint: str, persist: bool = False):
    """Update the global llm_client base URL at runtime. Optionally persist to .env.

    Args:
        new_endpoint: Base URL like http://host:port
        persist: If True, upsert LPS2_LLM_ENDPOINT in project .env file (idempotent)
    """
    global llm_client
    clean = (new_endpoint or '').strip().rstrip('/')
    if not clean:
        raise ValueError('empty endpoint')
    if not (clean.startswith('http://') or clean.startswith('https://')):
        raise ValueError('endpoint must start with http:// or https://')
    # Live mutate existing client to avoid losing latency deque
    try:
        llm_client.server_base = clean
        llm_client.api_url = clean + '/v1/chat/completions'
    except Exception:
        # Fallback to new instance
        llm_client = LLMClient(clean)
    os.environ['LPS2_LLM_ENDPOINT'] = clean  # For any child processes / subsequent imports
    if persist:
        try:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            env_path = os.path.join(root, '.env')
            lines = []
            found = False
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped.startswith('LPS2_LLM_ENDPOINT='):
                            lines.append(f'LPS2_LLM_ENDPOINT={clean}\n')
                            found = True
                        else:
                            lines.append(line)
            if not found:
                lines.append(f'LPS2_LLM_ENDPOINT={clean}\n')
            tmp = env_path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            os.replace(tmp, env_path)
        except Exception as e:
            raise RuntimeError(f'persist_failed: {e}')
    return clean
def require_api_key(fn):
    """Decorator that enforces API key unless a logged-in session user exists.

    This lets the UI rely on either a session cookie (local login) OR the legacy
    API key header. If a session user is present we skip API key validation to
    avoid double auth requirements.
    """
    @wraps(fn)
    def _wrap(*args, **kwargs):
        # If user authenticated via session, allow
        if session.get('user'):
            return fn(*args, **kwargs)
        expected = API_KEY
        if expected:
            provided = request.headers.get('X-API-Key') or request.headers.get('Authorization', '')
            if provided.startswith('Bearer '):
                provided = provided[7:].strip()
            if provided != expected:
                return jsonify({'error': 'unauthorized'}), 401
        return fn(*args, **kwargs)
    return _wrap

# --- Profile management routes (placed after require_api_key definition) ---
@chat_bp.route('/admin/llm-endpoints/profiles', methods=['GET'])
@require_api_key
def list_profiles():
    # Admin-only (session user must be admin if session present)
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    with _PROFILES_LOCK:
        data = json.loads(json.dumps(_ENDPOINT_PROFILES))
    return jsonify(data)

@chat_bp.route('/admin/llm-endpoints/profiles/test', methods=['POST'])
@require_api_key
def test_profile_endpoint():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    
    # Log request for debugging
    logger.info(f"test_profile_endpoint: headers={dict(request.headers)}")
    if request.is_json:
        logger.info(f"test_profile_endpoint: json={request.json}")
    
    fail = _validate_csrf_if_session()
    if fail: 
        logger.warning(f"CSRF validation failed in test_profile_endpoint")
        return fail
    
    endpoint = ((request.json or {}).get('endpoint') or '').strip()
    if not endpoint:
        return jsonify({'error':'endpoint_required'}), 400
    
    result = _test_endpoint_connectivity(endpoint)
    audit('endpoint_test', endpoint=endpoint, ok=result.get('ok'), error=result.get('error'))
    return jsonify(result), (200 if result.get('ok') else 400)

@chat_bp.route('/admin/llm-endpoints/profiles', methods=['POST'])
@require_api_key
def upsert_profile():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    
    # Log request for debugging
    logger.info(f"upsert_profile: headers={dict(request.headers)}")
    if request.is_json:
        logger.info(f"upsert_profile: json={request.json}")
    
    fail = _validate_csrf_if_session()
    if fail:
        logger.warning(f"CSRF validation failed in upsert_profile")
        return fail
    
    data = request.json or {}
    name = (data.get('name') or '').strip()
    endpoint = (data.get('endpoint') or '').strip()
    persist = bool(data.get('persist'))
    
    if not name or not endpoint:
        return jsonify({'error':'name_and_endpoint_required'}), 400
    test_res = _test_endpoint_connectivity(endpoint)
    with _PROFILES_LOCK:
        _ENDPOINT_PROFILES['profiles'][name] = {
            'endpoint': endpoint.rstrip('/'),
            'last_test': test_res
        }
        if persist:
            _save_profiles()
    audit('endpoint_profile_upsert', name=name, endpoint=endpoint, ok=test_res.get('ok'), persist=persist)
    return jsonify({'saved': True, 'profile': name, 'test': test_res}), (200 if test_res.get('ok') else 400)

@chat_bp.route('/admin/llm-endpoints/profiles/activate', methods=['POST'])
@require_api_key
def activate_profile():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    
    # Log request for debugging
    logger.info(f"activate_profile: headers={dict(request.headers)}")
    if request.is_json:
        logger.info(f"activate_profile: json={request.json}")
    
    fail = _validate_csrf_if_session()
    if fail:
        logger.warning(f"CSRF validation failed in activate_profile")
        return fail
    
    data = request.json or {}
    name = (data.get('name') or '').strip()
    persist = bool(data.get('persist'))
    
    if not name:
        return jsonify({'error':'name_required'}), 400
    
    with _PROFILES_LOCK:
        prof = _ENDPOINT_PROFILES['profiles'].get(name)
        if not prof:
            return jsonify({'error':'not_found'}), 404
        endpoint = prof['endpoint']
    
    test_res = _test_endpoint_connectivity(endpoint)
    if not test_res.get('ok'):
        return jsonify({'error':'activation_failed', 'test': test_res}), 400
    
    try:
        updated = _update_llm_endpoint(endpoint, persist=False)
    except Exception as e:
        return jsonify({'error':'update_failed', 'detail': str(e)}), 400
    
    with _PROFILES_LOCK:
        _ENDPOINT_PROFILES['active'] = name
        _ENDPOINT_PROFILES['profiles'][name]['last_test'] = test_res
        if persist:
            _save_profiles()
    
    audit('endpoint_profile_activate', name=name, endpoint=endpoint)
    return jsonify({'activated': name, 'endpoint': updated, 'test': test_res})

@chat_bp.route('/admin/llm-endpoints/profiles/delete', methods=['POST'])
@require_api_key
def delete_profile():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    
    # Log request for debugging
    logger.info(f"delete_profile: headers={dict(request.headers)}")
    if request.is_json:
        logger.info(f"delete_profile: json={request.json}")
    
    fail = _validate_csrf_if_session()
    if fail:
        logger.warning(f"CSRF validation failed in delete_profile")
        return fail
    
    data = request.json or {}
    name = (data.get('name') or '').strip()
    persist = bool(data.get('persist'))
    
    if not name:
        return jsonify({'error':'name_required'}), 400
    
    with _PROFILES_LOCK:
        if _ENDPOINT_PROFILES.get('active') == name:
            return jsonify({'error':'cannot_delete_active'}), 400
        
        removed = bool(_ENDPOINT_PROFILES['profiles'].pop(name, None))
        if persist:
            _save_profiles()
    
    audit('endpoint_profile_delete', name=name, removed=removed)
    return jsonify({'deleted': removed, 'profile': name})

SUMMARIZE_TRIGGER_COUNT = 50
SUMMARIZE_BATCH_SIZE = 15
SUMMARIZATION_MAX_CHARS_PER_ITEM = 300

def maybe_summarize(memory_store):
    try:
        memories = memory_store.list_memories()
        # Filter out summary memories
        base = [m for m in memories if not m.get('metadata', {}).get('summary')]
        if len(base) <= SUMMARIZE_TRIGGER_COUNT:
            return None
        # Oldest first (they are appended in order already)
        batch = base[:SUMMARIZE_BATCH_SIZE]
        if not batch:
            return None
        snippets = []
        for m in batch:
            txt = m.get('text', '')
            if len(txt) > SUMMARIZATION_MAX_CHARS_PER_ITEM:
                txt = txt[:SUMMARIZATION_MAX_CHARS_PER_ITEM] + '...'
            snippets.append(f"ID {m['id'][:8]}:: {txt}")
        prompt = (
            "You are a memory compression module. Summarize the following prior conversation or context snippets into a concise, information-dense memory. "
            "Capture stable facts, user preferences, key objectives, unresolved questions, and important constraints. Avoid duplicating ephemeral chit-chat. "
            "Return bullet points (max ~20) grouped logically. Remove PII unless essential.\n\n" + "\n".join(snippets)
        )
        # Use model to summarize
        result = llm_client.send_prompt(prompt)
        summary_text = result.get('response') or ''
        # Add summary memory
        summary_id = memory_store.add_memory(summary_text, metadata={'summary': True, 'source_ids': [m['id'] for m in batch]})
        # Delete originals
        memory_store.delete_many([m['id'] for m in batch])
        logger.info(f"Summarization created {summary_id} from {len(batch)} memories")
        return summary_id
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return None

@chat_bp.route('/chat', methods=['POST'])
def chat():
    # Rate limiting (per IP)
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()
    if not check_rate(ip):
        return jsonify({'error': 'rate_limited'}), 429
    
    # Validate request if not multipart (multipart will be validated separately)
    if not request.content_type or not request.content_type.startswith('multipart/form-data'):
        try:
            from utils.schemas import ChatMessageSchema
            from utils.validation import validate_data
            
            # Direct validation
            data = request.json or {}
            is_valid, validated_data, errors = validate_data(data, ChatMessageSchema)
            
            if not is_valid:
                return jsonify({
                    'error': 'validation_error', 
                    'message': 'Invalid chat message',
                    'details': errors
                }), 400
                
            # For convenience in the rest of the function
            request.validated_data = validated_data
        except ImportError:
            # Validation module not available, continue with normal flow
            logger.debug("Validation module not available, skipping validation")
        except Exception as e:
            # Log but continue with the request to maintain backward compatibility
            logger.exception(f"Validation error: {e}")
    
    prompt = None
    file_content = None
    file_type = None
    # Audit early chat request (size only, not full prompt to avoid sensitive leakage)
    try:
        content_length = request.content_length
    except Exception:
        content_length = None
    audit('chat_request', ip=ip, content_length=content_length)

    image_sanitized = None  # Will become True/False when image processed
    extended_flag = False
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        prompt = request.form.get('prompt', '')
        extended_flag = request.form.get('extended') in ('1','true','on','yes')
        file = request.files.get('file')
        if file:
            file_type = file.content_type or ''
            # Enforce a hard server-side size limit (2MB) even though client validates
            file.seek(0, 2)  # move to end
            size_bytes = file.tell()
            file.seek(0)
            MAX_BYTES = 2 * 1024 * 1024
            if size_bytes > MAX_BYTES:
                return jsonify({'error': 'File too large (max 2MB).'}), 400
            if file_type.startswith('text'):
                try:
                    file_content = file.read().decode('utf-8', errors='replace')
                except Exception:
                    return jsonify({'error': 'Failed to decode text file as UTF-8.'}), 400
            elif file_type.startswith('image'):
                if not _PIL_AVAILABLE:
                    return jsonify({'error': 'Image processing not available (Pillow missing).'}), 500
                raw_bytes = file.read()
                before_size = len(raw_bytes)
                try:
                    img = Image.open(BytesIO(raw_bytes))
                    img.load()
                    original_format = (img.format or 'PNG').upper()
                    target_format = 'PNG' if original_format not in ('PNG', 'JPEG', 'JPG', 'WEBP') else original_format
                    buf = BytesIO()
                    save_kwargs = {}
                    if target_format in ('JPEG', 'JPG'):
                        if img.mode in ('RGBA', 'LA'):
                            from PIL import Image as _Image
                            bg = _Image.new('RGB', img.size, (255, 255, 255))
                            bg.paste(img, mask=img.split()[-1])
                            img = bg
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')
                        save_kwargs.update({'quality': 90, 'optimize': True, 'progressive': True})
                    else:
                        if img.mode not in ('RGB', 'L', 'RGBA') and target_format == 'PNG':
                            img = img.convert('RGBA') if 'A' in img.mode else img.convert('RGB')
                    # Re-encode WITHOUT metadata
                    img.save(buf, format=target_format, **save_kwargs)
                    sanitized_bytes = buf.getvalue()
                    after_size = len(sanitized_bytes)
                    file_content = base64.b64encode(sanitized_bytes).decode('utf-8')
                    image_sanitized = True
                    logger.info(f"Image sanitized: format={target_format} size_before={before_size} size_after={after_size}")
                except Exception as e:
                    logger.error(f"Image sanitization failed: {e}")
                    return jsonify({'error': 'Failed to sanitize image.'}), 400
            else:
                return jsonify({'error': 'Unsupported file type (only text and image allowed).'}), 400
    else:
        data = request.json
        prompt = data.get('prompt', '')
        extended_flag = bool(data.get('extended'))

    if not prompt and not file_content:
        return jsonify({'error': 'Prompt or file is required'}), 400
        
    # Initialize conversation history in session if it doesn't exist
    if 'conversation_history' not in session:
        session['conversation_history'] = []
        
    # Get existing conversation history
    conversation_history = session.get('conversation_history', [])
        
    # -------- Retrieval (Memory) --------
    memory_used_ids = []
    knowledge_used = []
    system_blocks = []
    memory_store = get_memory_store()
    if memory_store:
        try:
            retrieved_m = memory_store.search(prompt, top_k=5)
            if retrieved_m:
                memory_used_ids = [r['id'] for r in retrieved_m]
                snippets = []
                for r in retrieved_m:
                    txt = r['text']
                    if len(txt) > 500:
                        txt = txt[:500] + '...'
                    sanitized, meta = sanitize_text(txt)
                    flag = ' !' if meta.get('suspicious') else ''
                    snippets.append(f"[{r['id'][:8]} | score={r['score']:.3f}{flag}] {sanitized}")
                system_blocks.append("MEMORY SNIPPETS:\n" + "\n".join(snippets))
        except Exception as e:
            logger.error(f"Memory retrieval failed: {e}")
    knowledge_store = get_knowledge_store()
    knowledge_block = None
    citations = []
    knowledge_confidence = None
    refusal = False
    if knowledge_store:
        try:
            retrieved_k = knowledge_store.search(prompt, top_k=5)
            if retrieved_k:
                knowledge_used = [rk['chunk_id'] for rk in retrieved_k]
                top_score = retrieved_k[0]['score']
                mean_top3 = sum(r['score'] for r in retrieved_k[:3]) / min(3, len(retrieved_k))
                # Confidence heuristic
                if top_score >= 0.75 and mean_top3 >= 0.70:
                    knowledge_confidence = 'high'
                elif top_score >= 0.65:
                    knowledge_confidence = 'medium'
                else:
                    knowledge_confidence = 'low'
                if knowledge_confidence == 'low':
                    refusal = True
                kb_snippets = []
                for i, rk in enumerate(retrieved_k, start=1):
                    txt = rk['text']
                    preview = txt[:160] + ('...' if len(txt) > 160 else '')
                    if len(txt) > 600:
                        txt = txt[:600] + '...'
                    sanitized, meta = sanitize_text(txt)
                    flag = ' !' if meta.get('suspicious') else ''
                    kb_snippets.append(f"[S{i}{flag} score={rk['score']:.3f} src={rk['source']} idx={rk['index']}]\n{sanitized}")
                    citations.append({
                        's': i,
                        'chunk_id': rk['chunk_id'],
                        'doc_id': rk['doc_id'],
                        'source': rk['source'],
                        'index': rk['index'],
                        'score': rk['score'],
                        'preview': preview
                    })
                if not refusal:
                    knowledge_block = (
                        "KNOWLEDGE BASE CONTEXT (use strictly; cite sources as [S#]):\n" + "\n---\n".join(kb_snippets)
                    )
        except Exception as e:
            logger.error(f"Knowledge retrieval failed: {e}")
    if knowledge_block:
        system_blocks.append(knowledge_block)
    system_content = None
    if system_blocks:
        guard = build_guardrail_preamble()
        system_content = guard + "\n\n" + "\n\n".join(system_blocks) + "\n\nIf insufficient context, state lack of information rather than guessing."

    if refusal and not system_blocks:
        # No usable knowledge context and low confidence – return refusal response early
        early_resp = {
            'response': "I don't have sufficient information in the knowledge base to answer confidently.",
            'memory_used': memory_used_ids,
            'knowledge_used': knowledge_used,
            'citations': citations,
            'knowledge_confidence': knowledge_confidence,
            'refusal': True
        }
        if image_sanitized is not None:
            early_resp['image_sanitized'] = image_sanitized
        return jsonify(early_resp)

    # Map extended flag to auto continuation override (extended => enable, else use default config)
    
    # Prepare messages with conversation history
    messages = []
    
    # Add system message first if present
    if system_content:
        messages.append({"role": "system", "content": system_content})
    
    # Add conversation history (up to last 10 messages to avoid context overflow)
    max_history = 10  # Adjust as needed based on token limits
    history_messages = conversation_history[-max_history:] if len(conversation_history) > max_history else conversation_history
    messages.extend(history_messages)
    
    # Add the current user message
    if file_content and file_type and file_type.startswith('image'):
        # Handle image content
        data_url = f"data:{file_type};base64,{file_content}"
        user_msg = {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}}
            ]
        }
        messages.append(user_msg)
    else:
        if file_content and file_type and file_type.startswith('text'):
            augmented = f"{prompt}\n\n---\nAttached file content:\n{file_content}\n---"
        else:
            augmented = prompt
        messages.append({"role": "user", "content": augmented})
    
    # Send prompt with conversation history
    result = llm_client.send_prompt(prompt, file_content=file_content, file_type=file_type, 
                                   system_content=system_content, messages=messages,
                                   auto_continue=(True if extended_flag else None))
                                   
    # If tool_calls are present, execute them and continue the conversation
    tool_calls = result.get('tool_calls')
    
    # Capture messages used for tool processing if needed
    tool_messages = messages.copy()
    tool_results = []
    if tool_calls:
        for call in tool_calls:
            tool_result = llm_client.execute_tool(call)
            tool_results.append({
                "name": call["function"]["name"],
                "result": tool_result
            })
            # Add assistant tool call and tool result to messages
            messages.append({
                "role": "assistant",
                "tool_calls": [call]
            })
            messages.append({
                "role": "tool",
                "content": tool_result,
                "tool_call_id": call["id"]
            })
        # Send updated messages to LLM for final response
    final_result = llm_client.send_prompt(prompt, messages=tool_messages, auto_continue=(True if extended_flag else None))
    metrics = final_result.get('metrics') or {}
    # Record latency metric (duration) if available
    if metrics and isinstance(metrics.get('duration'), (int, float)):
        try:
            _MODEL_LATENCIES.append(float(metrics['duration']))
        except Exception:
            pass
            
    # Update conversation history with the new exchange
    # Add user message to history
    if file_content and file_type and file_type.startswith('text'):
        user_content = f"{prompt}\n\n[Attached text file]"
    elif file_content and file_type and file_type.startswith('image'):
        user_content = f"{prompt}\n\n[Attached image]"
    else:
        user_content = prompt
    
    # Add to conversation history
    conversation_history.append({"role": "user", "content": user_content})
    
    # Add assistant response to history
    response_text = final_result.get('response', '')
    conversation_history.append({"role": "assistant", "content": response_text})
    
    # Store updated conversation history in session (limit to last 20 messages to manage session size)
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-20:]
    session['conversation_history'] = conversation_history
    # Make sure session is saved
    session.modified = True
    resp = {
        'response': final_result.get('response'),
        'tool_results': tool_results,
        'raw': final_result.get('raw'),
        'memory_used': memory_used_ids,
        'knowledge_used': knowledge_used,
        'citations': citations,
        'knowledge_confidence': knowledge_confidence,
        'refusal': False,
        'continuation_rounds': final_result.get('continuation_rounds'),
        'finish_reason': final_result.get('finish_reason'),
        'extended': extended_flag,
        'metrics': metrics
    }
    if image_sanitized is not None:
        resp['image_sanitized'] = image_sanitized
    # Store new memory AFTER final response (user prompt only for now)
    if memory_store:
        try:
            enrich = ''
            if file_content and file_type and file_type.startswith('text'):
                enrich = f"\n[AttachedFile]\n{file_content[:800]}"  # limit
            full_text = prompt + enrich
            # PII redaction before sanitize
            redacted_full, pii_stats = redact_pii(full_text)
            sanitized_full, meta = sanitize_text(redacted_full)
            meta_out = {"file_type": file_type or None}
            if meta.get('suspicious'):
                meta_out['suspicious'] = True
            if pii_stats:
                meta_out['pii_redacted'] = pii_stats
            # Store sanitized version (original discarded to avoid poisoning)
            memory_store.add_memory(sanitized_full, metadata=meta_out)
            maybe_summarize(memory_store)
        except Exception as e:
            logger.error(f"Memory add failed: {e}")
    return jsonify(resp)

import os
APP_VERSION = os.environ.get('LPS2_APP_VERSION', '0.1.0')

@chat_bp.route('/model', methods=['GET'])
def current_model():
    info = llm_client.get_model_info() or {}
    model_id = info.get('model') or llm_client.get_current_model() or 'Unknown'
    created = info.get('created')
    obj_type = info.get('object')
    avg_latency = None
    if _MODEL_LATENCIES:
        try:
            avg_latency = sum(_MODEL_LATENCIES) / len(_MODEL_LATENCIES)
        except Exception:
            avg_latency = None
    return jsonify({
        'model': model_id,
        'created': created,
        'object': obj_type,
        'app_version': APP_VERSION,
        'llm_endpoint': getattr(llm_client, 'server_base', None),
        'avg_latency': avg_latency
    })

@chat_bp.route('/admin/llm-endpoint', methods=['GET', 'POST'])
@require_api_key
def admin_llm_endpoint():
    """GET returns current endpoint; POST updates it.

    POST JSON: {"endpoint": "http://host:port", "persist": true}
    """
    if request.method == 'GET':
        return jsonify({
            'endpoint': getattr(llm_client, 'server_base', None),
            'api_url': getattr(llm_client, 'api_url', None)
        })
    # CSRF validation for modifying POST when session auth is used
    fail = _validate_csrf_if_session();
    if fail: return fail
    data = request.json or {}
    endpoint = data.get('endpoint')
    persist = bool(data.get('persist'))
    if not endpoint:
        return jsonify({'error': 'endpoint required'}), 400
    try:
        updated = _update_llm_endpoint(endpoint, persist=persist)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    audit('admin_llm_endpoint_update', endpoint=updated, persist=persist)
    return jsonify({'updated': updated, 'persisted': persist})

@chat_bp.route('/health/full', methods=['GET'])
def full_health():
    """Extended health: upstream reachability, simple latency, model id, stores status."""
    upstream = {
        'endpoint': getattr(llm_client, 'server_base', None),
        'reachable': False
    }
    import time as _time
    start = _time.time()
    try:
        # Attempt model listing for lightweight probe
        model_id = llm_client.get_current_model()
        elapsed = (_time.time() - start) * 1000.0
        upstream['latency_ms'] = round(elapsed, 1)
        upstream['reachable'] = model_id is not None
        upstream['model'] = model_id
    except Exception as e:
        upstream['error'] = str(e)
    mem_store = get_memory_store()
    kn_store = get_knowledge_store()
    memory_status = {'enabled': bool(mem_store)}
    if mem_store:
        try:
            memory_status['count'] = len(mem_store.list_memories())
        except Exception as e:
            memory_status['error'] = str(e)
    knowledge_status = {'enabled': bool(kn_store)}
    if kn_store:
        try:
            knowledge_status['documents'] = len(kn_store.list_documents())
        except Exception as e:
            knowledge_status['error'] = str(e)
    return jsonify({
        'status': 'ok',
        'upstream': upstream,
        'memory': memory_status,
        'knowledge': knowledge_status,
        'avg_latency': (sum(_MODEL_LATENCIES)/len(_MODEL_LATENCIES)) if _MODEL_LATENCIES else None
    })

@chat_bp.route('/memory/search', methods=['GET'])
def memory_search():
    q = request.args.get('q', '')
    top_k = int(request.args.get('k', '5'))
    store = get_memory_store()
    if not store:
        return jsonify({'results': [], 'enabled': False})
    results = store.search(q, top_k=top_k)
    return jsonify({'results': results, 'enabled': True})

@chat_bp.route('/memory/list', methods=['GET'])
def memory_list():
    limit = int(request.args.get('limit', '100'))
    store = get_memory_store()
    if not store:
        return jsonify({'memories': [], 'enabled': False})
    mems = store.list_memories()
    mems_sorted = sorted(mems, key=lambda m: m.get('created', 0), reverse=True)
    out = []
    for m in mems_sorted[:limit]:
        txt = m.get('text', '')
        if len(txt) > 160:
            txt_short = txt[:160] + '…'
        else:
            txt_short = txt
        meta = m.get('metadata', {})
        out.append({
            'id': m.get('id'),
            'text': txt_short,
            'is_summary': bool(meta.get('summary')),
            'created': m.get('created'),
            'file_type': meta.get('file_type'),
            'source_ids': meta.get('source_ids'),
            'suspicious': bool(meta.get('suspicious')),
            'pii_redacted': meta.get('pii_redacted')
        })
    return jsonify({'memories': out, 'count': len(mems), 'enabled': True})

@chat_bp.route('/memory/delete', methods=['POST'])
@require_api_key
def memory_delete():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    fail = _validate_csrf_if_session();
    if fail: return fail
    data = request.json or {}
    ids = data.get('ids') or []
    if not isinstance(ids, list):
        return jsonify({'deleted': 0, 'error': 'ids must be list'}), 400
    store = get_memory_store()
    if not store:
        return jsonify({'deleted': 0, 'enabled': False}), 500
    deleted = store.delete_many(ids)
    audit('memory_delete', ids=ids, deleted=deleted)
    return jsonify({'deleted': deleted})

# ---------------- Knowledge Base Endpoints (Phase 1) ----------------
@chat_bp.route('/kb/stats', methods=['GET'])
def kb_stats():
    store = get_knowledge_store()
    if not store:
        return jsonify({'enabled': False})
    base_stats = store.stats()
    # Obtain detailed documents list for model distribution
    docs_list = store.list_documents()
    base_stats['documents'] = len(docs_list)
    base_stats['embedding_models'] = list({d.get('embedding_model') for d in docs_list if d.get('embedding_model')})
    try:
        from utils.knowledge_store import CURRENT_EMBEDDING_MODEL_NAME as ACTIVE_MODEL
    except Exception:
        ACTIVE_MODEL = None
    base_stats['active_embedding_model'] = ACTIVE_MODEL
    return jsonify({'enabled': True, **base_stats})

@chat_bp.route('/kb/ingest', methods=['POST'])
@require_api_key
def kb_ingest():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    fail = _validate_csrf_if_session();
    if fail: return fail
    store = get_knowledge_store()
    if not store:
        return jsonify({'error': 'knowledge store unavailable'}), 500
    text = None
    source = None
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'file missing'}), 400
        source = file.filename or 'uploaded.txt'
        raw = file.read()
        # Basic size guard (10MB)
        if len(raw) > 10 * 1024 * 1024:
            return jsonify({'error': 'file too large (max 10MB)'}), 400
        fname_lower = (source or '').lower()
        ctype = (file.mimetype or file.content_type or '').lower()
        ocr_requested = (request.form.get('ocr') in ('1','true','on','yes'))
        if fname_lower.endswith('.pdf') or 'pdf' in ctype:
            # PDF extraction
            try:
                try:
                    import PyPDF2  # type: ignore
                except Exception as e:
                    return jsonify({'error': f'PDF support not available: {e}'}), 400
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(raw))
                pages = []
                for p in pdf_reader.pages:
                    try:
                        pages.append(p.extract_text() or '')
                    except Exception:
                        pages.append('')
                extracted = '\n\n'.join([p.strip() for p in pages if p and p.strip()])
                text = extracted
                # OCR fallback when no/low text or explicitly requested
                need_ocr = ocr_requested or (len((extracted or '').strip()) < 40)
                if need_ocr:
                    ocr_text = []
                    ocr_errors = []
                    try:
                        try:
                            from pdf2image import convert_from_bytes  # type: ignore
                            import pytesseract  # type: ignore
                        except Exception as e:
                            if not extracted.strip():
                                return jsonify({'error': f'no extractable text and OCR unavailable: {e}'}), 400
                            # Keep extracted text only
                        else:
                            max_pages = int(os.environ.get('LPS2_OCR_MAX_PAGES', '50'))
                            dpi = int(os.environ.get('LPS2_OCR_DPI', '200'))
                            try:
                                images = convert_from_bytes(raw, dpi=dpi, fmt='png', first_page=1, last_page=min(len(pages), max_pages))
                            except Exception as e:
                                images = []
                                ocr_errors.append(f'convert_failed:{e}')
                            if images:
                                for idx, img in enumerate(images, start=1):
                                    try:
                                        txt_page = pytesseract.image_to_string(img)
                                    except Exception as e:
                                        ocr_errors.append(f'page{idx}:{e}')
                                        txt_page = ''
                                    if txt_page and txt_page.strip():
                                        ocr_text.append(f"# OCR Page {idx}\n{txt_page.strip()}")
                            if ocr_text:
                                # Merge original extracted (if any) plus OCR
                                combined = []
                                if extracted.strip():
                                    combined.append('# Extracted Text (Parser)\n' + extracted.strip())
                                combined.append('\n'.join(ocr_text))
                                text = '\n\n'.join(combined)
                                if ocr_errors:
                                    text += f"\n\n# OCR Warnings\n{'; '.join(ocr_errors)}"
                            else:
                                if not extracted.strip():
                                    return jsonify({'error': 'no extractable text found (parser & OCR)'}), 400
                    except Exception as e:
                        if not extracted.strip():
                            return jsonify({'error': f'OCR process failed and no parser text: {e}'}), 400
            except Exception as e:
                return jsonify({'error': f'pdf parse failed: {e}'}), 400
        else:
            # Assume UTF-8 text
            try:
                text = raw.decode('utf-8', errors='replace')
            except Exception:
                return jsonify({'error': 'decode failed'}), 400
    else:
        data = request.json or {}
        text = data.get('text')
        source = data.get('source', 'inline')
    if not text:
        return jsonify({'error': 'no text provided'}), 400
    result = store.ingest_text(text, source=source)
    audit('kb_ingest', source=source, doc_id=result.get('doc_id'), quarantined=result.get('quarantined', False), chunks=result.get('chunks'))
    if 'error' in result:
        return jsonify(result), 400
    return jsonify(result)

@chat_bp.route('/kb/search', methods=['GET'])
def kb_search():
    q = request.args.get('q', '')
    k = int(request.args.get('k', '5'))
    store = get_knowledge_store()
    if not store:
        return jsonify({'results': [], 'enabled': False})
    res = store.search(q, top_k=k)
    # Truncate text for response preview
    out = []
    for r in res:
        txt = r['text']
        if len(txt) > 300:
            txt = txt[:300] + '...'
        out.append({k: v for k, v in r.items() if k != 'text'} | {'preview': txt})
    return jsonify({'results': out, 'enabled': True})

@chat_bp.route('/kb/documents', methods=['GET'])
def kb_documents():
    store = get_knowledge_store()
    if not store:
        return jsonify({'enabled': False, 'documents': []})
    return jsonify({'enabled': True, 'documents': store.list_documents()})

@chat_bp.route('/kb/delete', methods=['POST'])
@require_api_key
def kb_delete():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    fail = _validate_csrf_if_session();
    if fail: return fail
    data = request.json or {}
    ids = data.get('doc_ids') or []
    if not isinstance(ids, list):
        return jsonify({'deleted': 0, 'error': 'doc_ids must be list'}), 400
    store = get_knowledge_store()
    if not store:
        return jsonify({'deleted': 0, 'enabled': False}), 500
    removed = store.delete_documents(ids)
    audit('kb_delete', doc_ids=ids, removed=removed)
    return jsonify({'deleted': removed})

@chat_bp.route('/kb/reingest', methods=['POST'])
@require_api_key
def kb_reingest():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    fail = _validate_csrf_if_session();
    if fail: return fail
    store = get_knowledge_store()
    if not store:
        return jsonify({'error': 'knowledge store unavailable'}), 500
    data = request.json or {}
    doc_id = data.get('doc_id')
    text = data.get('text')
    source = data.get('source', f'reingest:{doc_id}')
    if not doc_id or not text:
        return jsonify({'error': 'doc_id and text required'}), 400
    result = store.ingest_text(text, source=source, doc_id=doc_id, replace=True)
    audit('kb_reingest', doc_id=doc_id, source=source, replaced=True, quarantined=result.get('quarantined', False))
    if 'error' in result:
        return jsonify(result), 400
    return jsonify(result)

@chat_bp.route('/kb/rebuild', methods=['POST'])
@require_api_key
def kb_rebuild():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    fail = _validate_csrf_if_session();
    if fail: return fail
    store = get_knowledge_store()
    if not store:
        return jsonify({'error': 'knowledge store unavailable'}), 500
    force = bool((request.json or {}).get('force'))
    status = store.rebuild_embeddings(force=force)
    return jsonify(status)

@chat_bp.route('/kb/rebuild/status', methods=['GET'])
def kb_rebuild_status():
    store = get_knowledge_store()
    if not store:
        return jsonify({'error': 'knowledge store unavailable'}), 500
    return jsonify(store.rebuild_status())

@chat_bp.route('/security/stats', methods=['GET'])
def security_stats():
    mem_store = get_memory_store()
    kn_store = get_knowledge_store()
    mem_suspicious = 0
    mem_total = 0
    if mem_store:
        try:
            for m in mem_store.list_memories():
                mem_total += 1
                meta = m.get('metadata', {})
                if meta.get('suspicious'):
                    mem_suspicious += 1
        except Exception:
            pass
    kb_docs = 0
    kb_chunks = 0
    kb_suspicious = 0
    if kn_store:
        try:
            docs = kn_store.list_documents()
            kb_docs = len(docs)
            # Need raw internal for chunk suspicion counts
            internal = getattr(kn_store, '_data', {}).get('documents', [])
            for d in internal:
                for c in d.get('chunks', []):
                    kb_chunks += 1
                    if c.get('suspicious'):
                        kb_suspicious += 1
        except Exception:
            pass
    return jsonify({
        'memory': {'total': mem_total, 'suspicious': mem_suspicious},
        'knowledge': {'documents': kb_docs, 'chunks': kb_chunks, 'suspicious_chunks': kb_suspicious}
    })

@chat_bp.route('/kb/quarantine', methods=['GET'])
@require_api_key
def kb_quarantine_list():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    store = get_knowledge_store()
    if not store:
        return jsonify({'enabled': False, 'records': []})
    qpath = store.path + '.quarantine'
    if not os.path.exists(qpath):
        return jsonify({'enabled': True, 'records': []})
    try:
        import json
        with open(qpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({'enabled': True, 'records': data})
    except Exception as e:
        return jsonify({'enabled': True, 'error': str(e), 'records': []}), 500

@chat_bp.route('/kb/quarantine/approve', methods=['POST'])
@require_api_key
def kb_quarantine_approve():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    fail = _validate_csrf_if_session();
    if fail: return fail
    store = get_knowledge_store()
    if not store:
        return jsonify({'error': 'knowledge store unavailable'}), 500
    data = request.json or {}
    doc_id = data.get('doc_id')
    if not doc_id:
        return jsonify({'error': 'doc_id required'}), 400
    qpath = store.path + '.quarantine'
    import json
    if not os.path.exists(qpath):
        return jsonify({'error': 'no quarantine file'}), 400
    try:
        with open(qpath, 'r', encoding='utf-8') as f:
            records = json.load(f)
    except Exception as e:
        return jsonify({'error': f'load failed: {e}'}), 500
    rec = None
    for r in records:
        if r.get('doc_id') == doc_id:
            rec = r
            break
    if not rec:
        return jsonify({'error': 'doc not in quarantine'}), 404
    new_records = [r for r in records if r.get('doc_id') != doc_id]
    try:
        with open(qpath + '.tmp', 'w', encoding='utf-8') as f:
            json.dump(new_records, f)
        os.replace(qpath + '.tmp', qpath)
    except Exception as e:
        return jsonify({'error': f'write failed: {e}'}), 500
    audit('kb_quarantine_approve', doc_id=doc_id)
    return jsonify({'approved': doc_id, 'note': 'quarantine record removed; re-ingest required to add content'})

@chat_bp.route('/kb/quarantine/discard', methods=['POST'])
@require_api_key
def kb_quarantine_discard():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    fail = _validate_csrf_if_session();
    if fail: return fail
    store = get_knowledge_store()
    if not store:
        return jsonify({'error': 'knowledge store unavailable'}), 500
    data = request.json or {}
    doc_id = data.get('doc_id')
    if not doc_id:
        return jsonify({'error': 'doc_id required'}), 400
    qpath = store.path + '.quarantine'
    import json
    if not os.path.exists(qpath):
        return jsonify({'error': 'no quarantine file'}), 400
    try:
        with open(qpath, 'r', encoding='utf-8') as f:
            records = json.load(f)
    except Exception as e:
        return jsonify({'error': f'load failed: {e}'}), 500
    if not any(r.get('doc_id') == doc_id for r in records):
        return jsonify({'error': 'doc not in quarantine'}), 404
    new_records = [r for r in records if r.get('doc_id') != doc_id]
    try:
        with open(qpath + '.tmp', 'w', encoding='utf-8') as f:
            json.dump(new_records, f)
        os.replace(qpath + '.tmp', qpath)
    except Exception as e:
        return jsonify({'error': f'write failed: {e}'}), 500
    audit('kb_quarantine_discard', doc_id=doc_id)
    return jsonify({'discarded': doc_id})

@chat_bp.route('/security/audit', methods=['GET'])
@require_api_key
def security_audit():
    if session.get('user') and os.environ.get('LPS2_ADMIN_USERS'):
        admins = {u.strip() for u in os.environ.get('LPS2_ADMIN_USERS','').split(',') if u.strip()}
        if session.get('user') not in admins:
            return jsonify({'error':'forbidden'}), 403
    limit = int(request.args.get('limit', '200'))
    events = read_audit(limit=limit)
    return jsonify({'events': events, 'count': len(events)})

@chat_bp.route('/conversation/clear', methods=['POST'])
def clear_conversation():
    """Clear the conversation history stored in the session."""
    fail = _validate_csrf_if_session()
    if fail: return fail
    
    # Clear conversation history
    if 'conversation_history' in session:
        session['conversation_history'] = []
        session.modified = True
    
    return jsonify({'status': 'success', 'message': 'Conversation history cleared'})

def init_chat_route(app):
    app.register_blueprint(chat_bp)