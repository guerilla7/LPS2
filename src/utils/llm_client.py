import requests
import os
import time
from config import MAX_OUTPUT_TOKENS, AUTO_CONTINUE, CONTINUE_ROUNDS, GEN_TEMPERATURE, TOP_P

# Clean up duplicate imports and unused modules.

class LLMClient:
    def __init__(self, server_url):
        self.api_url = server_url.rstrip('/') + '/v1/chat/completions'
        self.server_base = server_url.rstrip('/')

    def get_tools(self):
        # Only support Wikipedia web search tool
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search Wikipedia and fetch the introduction of the most relevant article.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query for Wikipedia"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

    def send_prompt(self, prompt, file_content=None, file_type=None, messages=None, system_content=None,
                    auto_continue=None, continue_rounds=None,
                    _continuation_round=0, _accumulated=None,
                    _start_time=None, _first_token_time=None,
                    _usage_acc=None):
        """Send a prompt to the local LLM with optional auto continuation overrides."""
        attempted_multimodal = False
        if _start_time is None:
            _start_time = time.time()
        if messages is None:
            if file_content and file_type and file_type.startswith('image'):
                # First try OpenAI-style multimodal parts
                attempted_multimodal = True
                data_url = f"data:{file_type};base64,{file_content}"
                user_msg = {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
                messages = []
                if system_content:
                    messages.append({"role": "system", "content": system_content})
                messages.append(user_msg)
            else:
                if file_content and file_type and file_type.startswith('text'):
                    augmented = f"{prompt}\n\n---\nAttached file content:\n{file_content}\n---"
                else:
                    augmented = prompt
                messages = []
                if system_content:
                    messages.append({"role": "system", "content": system_content})
                messages.append({"role": "user", "content": augmented})
        payload = {
            "model": "gpt-3.5-turbo",  # Adjust / override if LM Studio exposes a different id
            "messages": messages,
            "tools": self.get_tools(),
            # Generation controls (some backends use max_tokens, others max_new_tokens; include both)
            "max_tokens": MAX_OUTPUT_TOKENS,
            "max_new_tokens": MAX_OUTPUT_TOKENS,
            "temperature": GEN_TEMPERATURE,
            "top_p": TOP_P
        }
        fallback_used = False
        data = None
        request_start = time.time()
        try:
            import copy
            send_payload = copy.deepcopy(payload)
            response = requests.post(self.api_url, json=send_payload)
            if response.status_code == 400 and attempted_multimodal:
                # Fallback: embed truncated base64 inside text to satisfy legacy server
                truncated_limit = 8192  # chars of base64 to include
                total_len = len(file_content) if file_content else 0
                truncated = file_content[:truncated_limit]
                omitted = total_len - truncated_limit if total_len > truncated_limit else 0
                note = f"(base64 truncated, {omitted} chars omitted)" if omitted > 0 else ""
                augmented = f"{prompt}\n\n---\nAttached image base64:\n{truncated}{'...' if omitted>0 else ''}\n{note}\n---"
                messages = [{"role": "user", "content": augmented}]
                payload["messages"] = messages
                fallback_used = True
                response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            now = time.time()
            duration = now - _start_time
            ttft = (_first_token_time - _start_time) if _first_token_time else duration
            return {"response": f"Request error: {e}", "tool_calls": None, "raw": data, "multimodal_fallback": fallback_used, "messages_used": payload.get('messages'),
                    "metrics": {
                        "started": _start_time,
                        "completed": now,
                        "duration": duration,
                        "ttft": ttft,
                        "token_total": 0,
                        "token_input": 0,
                        "token_output": 0,
                        "approx": True
                    }}
        # Parse normal success
        tool_calls = None
        finish_reason = None
        segment = "No response"
        usage = None
        if data and "choices" in data and data["choices"]:
            choice0 = data["choices"][0]
            segment = choice0.get("message", {}).get("content", segment)
            tool_calls = choice0.get("message", {}).get("tool_calls")
            finish_reason = choice0.get("finish_reason")
            usage = data.get('usage')  # May include prompt_tokens, completion_tokens, total_tokens
        if _accumulated:
            accumulated = _accumulated + ("\n" if segment and not segment.startswith('\n') else "") + segment
        else:
            accumulated = segment
        # Record first token time (approximate: when first successful response parsed)
        if _first_token_time is None:
            _first_token_time = time.time()

        # --- Token accounting ---
        def approx_count(text: str) -> int:
            # Simple heuristic: whitespace split * 1.3 typical char/token ratio fudge (optional)
            # We'll just use whitespace count as baseline to avoid overestimation.
            if not text:
                return 0
            return max(1, len(text.strip().split()))

        if _usage_acc is None:
            _usage_acc = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "approx": False}
        if usage:
            # Accumulate real usage (some servers return cumulative per call; treat each call independently)
            pt = usage.get('prompt_tokens') or 0
            ct = usage.get('completion_tokens') or 0
            tt = usage.get('total_tokens') or (pt + ct)
            # Only add prompt tokens for first round (avoid double counting on continuations)
            if _continuation_round == 0 and _usage_acc['prompt_tokens'] == 0:
                _usage_acc['prompt_tokens'] += pt
            _usage_acc['completion_tokens'] += ct
            _usage_acc['total_tokens'] = _usage_acc['prompt_tokens'] + _usage_acc['completion_tokens']
        else:
            # Approximate tokens for this segment only (output)
            seg_tokens = approx_count(segment)
            _usage_acc['completion_tokens'] += seg_tokens
            if _continuation_round == 0 and _usage_acc['prompt_tokens'] == 0:
                # Approximate prompt tokens from user/system messages
                joined = []
                for m in (messages or []):
                    c = m.get('content')
                    if isinstance(c, str):
                        joined.append(c)
                    elif isinstance(c, list):
                        # multimodal: count text parts only
                        for part in c:
                            if isinstance(part, dict) and part.get('type') == 'text':
                                joined.append(part.get('text',''))
                if prompt:
                    joined.append(prompt)
                _usage_acc['prompt_tokens'] = approx_count("\n".join(joined))
            _usage_acc['total_tokens'] = _usage_acc['prompt_tokens'] + _usage_acc['completion_tokens']
            _usage_acc['approx'] = True

        # Determine effective continuation settings
        effective_auto = AUTO_CONTINUE if auto_continue is None else auto_continue
        effective_rounds = CONTINUE_ROUNDS if continue_rounds is None else continue_rounds
        # Auto-continuation if model stopped due to length
        if finish_reason == 'length' and effective_auto and _continuation_round < effective_rounds:
            # Prepare continuation: append assistant segment then user 'Continue.'
            cont_messages = list(messages)
            # Ensure last assistant part is present
            if not cont_messages or cont_messages[-1].get('role') != 'assistant':
                cont_messages.append({"role": "assistant", "content": segment})
            else:
                # merge content if assistant already last
                cont_messages[-1]['content'] = (cont_messages[-1].get('content','') or '') + segment
            cont_messages.append({"role": "user", "content": "Continue."})
            return self.send_prompt(prompt, file_content=file_content, file_type=file_type, messages=cont_messages,
                                     system_content=system_content, auto_continue=effective_auto, continue_rounds=effective_rounds,
                                     _continuation_round=_continuation_round+1, _accumulated=accumulated,
                                     _start_time=_start_time, _first_token_time=_first_token_time, _usage_acc=_usage_acc)
        completed_time = time.time()
        duration = completed_time - _start_time
        ttft = (_first_token_time - _start_time) if _first_token_time else duration
        metrics = {
            "started": _start_time,
            "completed": completed_time,
            "duration": duration,
            "ttft": ttft,
            "token_total": _usage_acc.get('total_tokens', 0),
            "token_input": _usage_acc.get('prompt_tokens', 0),
            "token_output": _usage_acc.get('completion_tokens', 0),
            "approx": _usage_acc.get('approx', False)
        }
        return {
            "response": accumulated,
            "tool_calls": tool_calls,
            "raw": data,
            "finish_reason": finish_reason,
            "continuation_rounds": _continuation_round,
            "multimodal_fallback": fallback_used,
            "messages_used": payload.get('messages'),
            "metrics": metrics
        }

    def execute_tool(self, tool_call):
        import datetime, math, os
        name = tool_call["function"]["name"]
        args = tool_call["function"].get("arguments")
        import json
        try:
            args = json.loads(args) if args else {}
        except Exception:
            args = {}
        if name == "search_web":
            # Wikipedia search
            import urllib.parse, urllib.request, json
            query = args.get("query", "")
            try:
                # Search for most relevant article
                search_url = "https://en.wikipedia.org/w/api.php"
                search_params = {
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": 1,
                }
                url = f"{search_url}?{urllib.parse.urlencode(search_params)}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CopilotBot/1.0)"})
                with urllib.request.urlopen(req) as response:
                    search_data = json.loads(response.read().decode())
                if not search_data["query"]["search"]:
                    return f"No Wikipedia article found for '{query}'"
                normalized_title = search_data["query"]["search"][0]["title"]
                # Fetch the actual content
                content_params = {
                    "action": "query",
                    "format": "json",
                    "titles": normalized_title,
                    "prop": "extracts",
                    "exintro": "true",
                    "explaintext": "true",
                    "redirects": 1,
                }
                url = f"{search_url}?{urllib.parse.urlencode(content_params)}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CopilotBot/1.0)"})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                pages = data["query"]["pages"]
                page_id = list(pages.keys())[0]
                if page_id == "-1":
                    return f"No Wikipedia article found for '{query}'"
                content = pages[page_id]["extract"].strip()
                title = pages[page_id]["title"]
                # Add Wikipedia source link (plain text and markdown clickable)
                wiki_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                return f"Wikipedia article: {title}\n---\n{content}\n\nSource: [{wiki_url}]({wiki_url})"
            except Exception as e:
                return f"Error fetching Wikipedia content: {str(e)}"
        else:
            return "Tool not implemented."

    def get_current_model(self):
        """Attempt to fetch current model id from LM Studio server via /v1/models.

        Returns the first model id if available, else None.
        """
        try:
            url = self.server_base.rstrip('/') + '/v1/models'
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return None
            data = resp.json()
            models = data.get('data') or []
            if not models:
                return None
            # Prefer a single model; if multiple, take the first
            model_id = models[0].get('id') if isinstance(models[0], dict) else None
            return model_id
        except Exception:
            return None

    def get_model_info(self):
        """Return richer model info dictionary from /v1/models (first entry).

        Keys: model, created, object, raw_fields (original dict minus noisy large fields if any).
        """
        try:
            url = self.server_base.rstrip('/') + '/v1/models'
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return {}
            data = resp.json()
            models = data.get('data') or []
            if not models:
                return {}
            first = models[0] if isinstance(models[0], dict) else {}
            cleaned = {k: v for k, v in first.items() if k not in {'permissions', 'owned_by'}}
            return {
                'model': cleaned.get('id'),
                'created': cleaned.get('created'),
                'object': cleaned.get('object'),
                'raw_fields': cleaned
            }
        except Exception:
            return {}