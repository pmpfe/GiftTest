"""
LLM client abstraction supporting Groq, Hugging Face, and Google Gemini.
All network calls use stdlib urllib to avoid extra dependencies.
"""

from typing import List, Optional, Tuple
import json
import urllib.request
import urllib.parse
import urllib.error
import datetime
from pathlib import Path

from .app_paths import get_http_log_path

GROQ_BASE = "https://api.groq.com/openai/v1"
HF_MODELS_LIST = "https://huggingface.co/api/models?pipeline_tag=text-generation&sort=downloads&direction=-1&limit=50"
HF_INFER_BASE = "https://router.huggingface.co/models"
GEMINI_LIST = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_GEN_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"


class LLMError(Exception):
    def __init__(self, message, status_code=None, headers=None, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.headers = headers
        self.body = body


class LLMClient:
    def __init__(self, provider: str, api_key: str, model: Optional[str] = None, system_prompt: Optional[str] = None):
        self.provider = provider
        # Sanitize API key: remove leading/trailing spaces and any control chars
        raw_key = (api_key or "").strip()
        self.api_key = "".join(ch for ch in raw_key if 32 <= ord(ch) <= 126)
        self.model = model or ""
        self.system_prompt = system_prompt or ""
        # Log file in a writable per-user location (Android and packaged apps).
        self._log_file = get_http_log_path()

    # --- Logging + HTTP helper ---
    def _http_request(
            self, req: urllib.request.Request,
            body: Optional[bytes] = None,
            timeout: int = 60) -> Tuple[int, dict, bytes]:
        """Perform HTTP request with detailed logging.

        Returns (status, headers, body_bytes).
        Logs request method, URL, headers, payload size and response
        details to http_log.txt.
        """
        ts = datetime.datetime.utcnow().isoformat() + "Z"
        try:
            # Request log
            req_headers = dict(req.headers) if hasattr(req, 'headers') else {}
            req_body_str = body.decode('utf-8', errors='replace') if body else ""
            log_req = [
                f"[{ts}] REQUEST",
                f"URL: {getattr(req, 'full_url', getattr(req, 'url', ''))}",
                f"Method: {getattr(req, 'method', 'POST' if body is not None else 'GET')}",
                f"Headers: {json.dumps(req_headers)}",
                f"BodyLen: {0 if body is None else len(body)}",
                f"Body: {req_body_str}",
            ]
            with self._log_file.open('a', encoding='utf-8') as f:
                f.write("\n".join(log_req) + "\n")

            # Execute
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_body = resp.read()
                status = getattr(resp, 'status', getattr(resp, 'code', 0))
                resp_headers = dict(resp.headers.items()) if hasattr(resp, 'headers') else {}

            # Response log
            resp_body_str = resp_body.decode('utf-8', errors='replace')
            log_resp = [
                f"[{ts}] RESPONSE",
                f"Status: {status}",
                f"Headers: {json.dumps(resp_headers)}",
                f"BodyLen: {len(resp_body)}",
                f"Body: {resp_body_str}",
            ]
            with self._log_file.open('a', encoding='utf-8') as f:
                f.write("\n".join(log_resp) + "\n\n")

            return status, resp_headers, resp_body
        except urllib.error.HTTPError as e:
            # Read error body
            try:
                err_body = e.read() or b""
            except Exception:
                err_body = b""
            status = getattr(e, 'code', 0)
            err_headers = dict(getattr(e, 'headers', {}).items()) if getattr(e, 'headers', None) else {}
            err_body_str = err_body.decode('utf-8', errors='replace')
            log_err = [
                f"[{ts}] ERROR",
                f"Status: {status}",
                f"Headers: {json.dumps(err_headers)}",
                f"BodyLen: {len(err_body)}",
                f"Body: {err_body_str}",
            ]
            with self._log_file.open('a', encoding='utf-8') as f:
                f.write("\n".join(log_err) + "\n\n")

            # Avoid dumping very large HTML error pages into the UI; full body remains in http_log.txt.
            preview = err_body_str
            if len(preview) > 800:
                preview = preview[:800] + "..."

            if status == 401 and ("cloudflare" in err_body_str.lower() or "authorization required" in err_body_str.lower()):
                preview = (
                    "401 Authorization Required (Perplexity). "
                    "Verifica a API key e se o teu utilizador está associado a um API Group. "
                    "Detalhes completos em http_log.txt.\n\n" + preview
                )

            raise LLMError(f"HTTP {status}: {preview}", status_code=status, headers=err_headers, body=err_body_str)
        except Exception as e:
            log_exc = [f"[{ts}] EXCEPTION", str(e)]
            with self._log_file.open('a', encoding='utf-8') as f:
                f.write("\n".join(log_exc) + "\n\n")
            raise

    def _normalize_perplexity_model(self, model: str) -> str:
        """Normalize Perplexity model names to the current Sonar catalog.

        Perplexity has historically used multiple naming schemes. The API reference
        currently documents: sonar, sonar-pro, sonar-deep-research, sonar-reasoning-pro.

        We accept older IDs and map them to the closest supported model.
        """
        raw = (model or "").strip()
        if not raw:
            return "sonar-pro"

        lower = raw.lower()
        allowed = {"sonar", "sonar-pro", "sonar-deep-research", "sonar-reasoning-pro"}
        if lower in allowed:
            # Preserve original casing from docs (all lowercase).
            return lower

        legacy_map = {
            "sonar-reasoning": "sonar-reasoning-pro",
            "sonar-reasoning": "sonar-reasoning-pro",
            "llama-3.1-sonar-small-128k-online": "sonar",
            "llama-3.1-sonar-large-128k-online": "sonar-pro",
            "llama-3.1-sonar-huge-128k-online": "sonar-pro",
        }
        if lower in legacy_map:
            return legacy_map[lower]

        # Best-effort fallbacks for unknown/legacy values.
        if "reason" in lower:
            return "sonar-reasoning-pro"
        if "deep" in lower or "research" in lower:
            return "sonar-deep-research"
        return "sonar-pro"

    # --- Listing models ---
    def list_models(self) -> List[dict]:
        """Returns list of dicts: {'id': str, 'description': str}."""
        if self.provider == "groq":
            return self._groq_list_models()
        if self.provider == "huggingface":
            return self._hf_list_models()
        if self.provider == "gemini":
            return self._gemini_list_models()
        if self.provider == "mistral":
            return self._mistral_list_models()
        if self.provider == "perplexity":
            return self._perplexity_list_models()
        if self.provider == "openrouter":
            return self._openrouter_list_models()
        if self.provider == "cloudflare":
            return self._cloudflare_list_models()
        return []

    def _groq_list_models(self) -> List[dict]:
        url = f"{GROQ_BASE}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "GIFT-Practice/1.0 (+https://example.local)"
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            status, resp_headers, resp_body = self._http_request(req, None, timeout=30)
            data = json.loads(resp_body.decode("utf-8"))
            models = []
            for m in data.get("data", []):
                if m.get("id"):
                    models.append({
                        'id': m.get("id"),
                        'description': f"Owner: {m.get('owned_by', '?')}"
                    })

            # Fallback if API returns unexpected content
            if not models:
                fallback = [
                    "llama-3.3-70b-versatile",
                    "llama-3.1-70b-versatile",
                    "llama-3.1-8b-instant",
                    "mixtral-8x7b-32768",
                    "gemma2-9b-it",
                ]
                models = [{'id': m, 'description': 'Fallback default'} for m in fallback]
            return models
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                err_body = str(e)
            raise LLMError(f"Groq /models falhou ({e.code}): {err_body}")
        except Exception as e:
            raise LLMError(f"Falha ao obter modelos Groq: {e}")

    def _hf_list_models(self) -> List[dict]:
        req = urllib.request.Request(HF_MODELS_LIST, headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})
        try:
            _, _, resp_body = self._http_request(req, None, timeout=30)
            data = json.loads(resp_body.decode("utf-8"))
            models = []
            for m in data:
                if m.get("pipeline_tag") == "text-generation" or True:
                    desc = f"Downloads: {m.get('downloads', 0)} | Likes: {m.get('likes', 0)}"
                    models.append({'id': m.get("modelId"), 'description': desc})
            return models
        except Exception as e:
            raise LLMError(f"Falha ao obter modelos HuggingFace: {e}")

    def _gemini_list_models(self) -> List[dict]:
        if not self.api_key:
            # Public listing might require key; return common defaults
            return [{'id': "gemini-1.5-flash", 'description': 'Fast and versatile'},
                    {'id': "gemini-1.5-pro", 'description': 'High performance'}]
        url = f"{GEMINI_LIST}?key={urllib.parse.quote(self.api_key)}"
        req = urllib.request.Request(url)
        try:
            _, _, resp_body = self._http_request(req, None, timeout=30)
            data = json.loads(resp_body.decode("utf-8"))
            models = []
            for m in data.get("models", []):
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    models.append({
                        'id': m.get("name", ""),
                        'description': m.get("description", "")
                    })
            # Fallback to known working models if none found
            if not models:
                models = [
                    {'id': "gemini-1.5-flash", 'description': 'Fast and versatile'},
                    {'id': "gemini-1.5-pro", 'description': 'High performance'}
                ]
            return models
        except Exception as e:
            # Return fallback models on error
            return [
                {'id': "gemini-1.5-flash", 'description': 'Fast and versatile'},
                {'id': "gemini-1.5-pro", 'description': 'High performance'}
            ]

    def _mistral_list_models(self) -> List[dict]:
        """List available Mistral models via API."""
        fallback = [
            "mistral-large-latest", "mistral-medium-latest",
            "mistral-small-latest", "codestral-latest", "open-mixtral-8x7b"
        ]
        fallback_dicts = [
            {'id': m, 'description': 'Mistral Model'} for m in fallback
        ]

        if not self.api_key:
            return fallback_dicts
        url = "https://api.mistral.ai/v1/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "GIFT-Practice/1.0"
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            _, _, resp_body = self._http_request(req, None, timeout=30)
            data = json.loads(resp_body.decode("utf-8"))
            models = []
            for m in data.get("data", []):
                if m.get("id"):
                    models.append({'id': m.get("id"), 'description': f"Owned by {m.get('owned_by', '?')}"})
            return models if models else fallback_dicts
        except Exception:
            return fallback_dicts

    def _perplexity_list_models(self) -> List[dict]:
        """Return curated list of Perplexity models (no public API endpoint)."""
        # Perplexity does not provide a public model listing endpoint.
        # Keep this list aligned with the official API reference.
        models = [
            "sonar",
            "sonar-pro",
            "sonar-deep-research",
            "sonar-reasoning-pro",
        ]
        return [{'id': m, 'description': 'Perplexity Sonar Model'} for m in models]

    def _openrouter_list_models(self) -> List[dict]:
        """List available OpenRouter models (public endpoint)."""
        fallback = [
            "meta-llama/llama-3.1-8b-instruct",
            "mistralai/mixtral-8x7b-instruct",
            "google/gemma-2-9b-it"
        ]
        fallback_dicts = [{'id': m, 'description': 'OpenRouter Model'} for m in fallback]

        url = "https://openrouter.ai/api/v1/models"
        headers = {
            "Accept": "application/json",
            "User-Agent": "GIFT-Practice/1.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(url, headers=headers)
        try:
            _, _, resp_body = self._http_request(req, None, timeout=30)
            data = json.loads(resp_body.decode("utf-8"))
            models = []
            for m in data.get("data", []):
                if m.get("id"):
                    models.append({
                        'id': m.get("id"),
                        'description': m.get("description") or f"Context: {m.get('context_length', '?')}"
                    })
            # Limit to first 100 to avoid overwhelming the UI
            return models[:100] if models else fallback_dicts
        except Exception:
            return fallback_dicts

    def _cloudflare_list_models(self) -> List[dict]:
        """List available Cloudflare Workers AI text generation models.

        Uses the Cloudflare API if credentials are available (ACCOUNT_ID:API_TOKEN format).
        """
        fallback = [
            "@cf/meta/llama-3-8b-instruct",
            "@cf/meta/llama-3.1-8b-instruct",
            "@cf/meta/llama-3.2-3b-instruct",
            "@cf/mistral/mistral-7b-instruct-v0.1",
            "@cf/microsoft/phi-2",
            "@cf/qwen/qwen1.5-7b-chat-awq",
            "@cf/google/gemma-7b-it-lora"
        ]
        fallback_dicts = [{'id': m, 'description': 'Cloudflare Model'} for m in fallback]

        if not self.api_key or ":" not in self.api_key:
            return fallback_dicts

        # Parse ACCOUNT_ID:API_TOKEN
        account_id, api_token = self.api_key.split(":", 1)
        account_id = account_id.strip()
        api_token = api_token.strip()

        if not account_id or not api_token:
            return fallback_dicts

        # Fetch models from Cloudflare API
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/models/search"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
            "User-Agent": "GIFT-Practice/1.0"
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            _, _, resp_body = self._http_request(req, None, timeout=30)
            data = json.loads(resp_body.decode("utf-8"))

            if not data.get("success", False):
                return fallback_dicts

            # Filter for text generation models
            models = []
            for m in data.get("result", []):
                model_name = m.get("name", "")
                task = m.get("task", {})
                task_name = task.get("name", "") if isinstance(task, dict) else ""
                # Include text generation models
                if task_name in ("Text Generation", "Text-to-Text") or "instruct" in model_name.lower():
                    models.append({
                        'id': model_name,
                        'description': m.get("description", "")
                    })

            return models if models else fallback_dicts
        except Exception:
            return fallback_dicts

    # --- Generation ---
    def generate(self, prompt: str) -> str:
        if not prompt.strip():
            raise LLMError("Prompt vazio.")
        if self.provider == "groq":
            return self._groq_generate(prompt)
        if self.provider == "huggingface":
            return self._hf_generate(prompt)
        if self.provider == "gemini":
            return self._gemini_generate(prompt)
        if self.provider in {"mistral", "perplexity", "openrouter"}:
            return self._generic_openai_chat(prompt)
        if self.provider == "cloudflare":
            return self._cloudflare_generate(prompt)
        raise LLMError(f"Provedor desconhecido: {self.provider}")

    def _generic_openai_chat(self, prompt: str) -> str:
        model = self.model
        if not model:
            models = self.list_models()
            if models:
                first = models[0]
                model = first['id'] if isinstance(first, dict) else first
        model = (model or "").strip()
        if self.provider == "perplexity":
            model = self._normalize_perplexity_model(model)

        if not self.api_key:
            raise LLMError(f"API key em falta para {self.provider}.")
        base_map = {
            "mistral": "https://api.mistral.ai/v1/chat/completions",
            "perplexity": "https://api.perplexity.ai/chat/completions",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        }
        url = base_map[self.provider]
        messages = [{"role": "user", "content": prompt}]
        if self.provider == "perplexity" and self.system_prompt:
            messages.insert(0, {"role": "system", "content": self.system_prompt})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1024
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "GIFT-Practice/1.0"
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            _, _, resp_body = self._http_request(req, body, timeout=60)
            data = json.loads(resp_body.decode("utf-8"))
            msg = data.get("choices", [{}])[0].get("message", {}).get("content")
            if not msg:
                raise LLMError(f"Resposta sem conteúdo válido: {json.dumps(data)[:400]}")
            return msg
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            error_msg = f"Falha na geração {self.provider}: {e}"
            raise LLMError(error_msg)

    def _groq_generate(self, prompt: str) -> str:
        # Basic validation
        if not self.api_key:
            raise LLMError("Groq API key em falta nas definições.")
        # Ensure model is set; if empty, try to pick the first available
        model = (self.model or "").strip()
        if not model:
            try:
                models = self._groq_list_models()
                if models:
                    first = models[0]
                    model = first['id'] if isinstance(first, dict) else first
            except Exception:
                model = "llama-3.3-70b-versatile"

        url = f"{GROQ_BASE}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 1024
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "GIFT-Practice/1.0 (+https://example.local)"
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            _, _, resp_body = self._http_request(req, body, timeout=60)
            data = json.loads(resp_body.decode("utf-8"))
            msg = data.get("choices", [{}])[0].get("message", {}).get("content")
            if not msg:
                raise LLMError(f"Groq respondeu sem conteúdo válido: {json.dumps(data)[:500]}")
            return msg
        except urllib.error.HTTPError as e:
            # Fallback to /completions if chat endpoint rejects payload (some deployments)
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                err_body = ""
            if e.code == 400:
                try:
                    url2 = f"{GROQ_BASE}/completions"
                    payload2 = {
                        "model": model,
                        "prompt": prompt,
                        "temperature": 0.2,
                        "max_tokens": 1024,
                    }
                    body2 = json.dumps(payload2).encode("utf-8")
                    req2 = urllib.request.Request(url2, data=body2, headers=headers)
                    _, _, resp_body2 = self._http_request(req2, body2, timeout=60)
                    data2 = json.loads(resp_body2.decode("utf-8"))
                    text = data2.get("choices", [{}])[0].get("text")
                    if text:
                        return text
                except Exception:
                    # if fallback also fails, proceed to raise original error below
                    pass
            # Enrich error with headers and URL to aid debugging
            hdrs = getattr(e, 'headers', None)
            hdrs_str = "\n".join([f"{k}: {v}" for k, v in (hdrs.items() if hdrs else [])])
            details = []
            details.append(f"URL: {url}")
            details.append(f"Modelo: {model}")
            if hdrs_str:
                details.append(f"Headers: {hdrs_str}")
            if not err_body:
                err_body = "<corpo de erro vazio>"
            raise LLMError(f"Groq chat/completions falhou ({e.code}). {' | '.join(details)}\nResposta: {err_body}")
        except Exception as e:
            raise LLMError(f"Falha na geração Groq: {e}")

    def _hf_generate(self, prompt: str) -> str:
        model = (self.model or "meta-llama/Llama-3.1-8B-Instruct").strip()
        if self.system_prompt:
            prompt = self.system_prompt + "\n\n" + prompt
        url = f"{HF_INFER_BASE}/{urllib.parse.quote(model)}"
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 512, "return_full_text": False}
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            _, _, resp_body = self._http_request(req, body, timeout=60)
            data = json.loads(resp_body.decode("utf-8"))
            # HF can return list or dict
            if isinstance(data, list) and data:
                item = data[0]
                if isinstance(item, dict):
                    return item.get("generated_text") or item.get("summary_text") or json.dumps(item)
            if isinstance(data, dict):
                return data.get("generated_text") or data.get("summary_text") or json.dumps(data)
            return str(data)
        except Exception as e:
            raise LLMError(f"Falha na geração HuggingFace: {e}")

    def _gemini_generate(self, prompt: str) -> str:
        model = self.model or "gemini-1.5-flash"
        # Gemini endpoint expects raw model id (e.g., "gemini-1.5-flash"), template adds "models/".
        model_id = model.replace("models/", "")
        url = GEMINI_GEN_TEMPLATE.format(model=urllib.parse.quote(model_id), key=urllib.parse.quote(self.api_key))
        if self.system_prompt:
            prompt = self.system_prompt + "\n\n" + prompt
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024}
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            status, _, resp_body = self._http_request(req, body, timeout=60)
            data = json.loads(resp_body.decode("utf-8"))
            # Surface error details if present
            err = data.get("error") if isinstance(data, dict) else None
            if err:
                code = err.get("code", status)
                msg = err.get("message", "")
                raise LLMError(f"Gemini erro ({code}): {msg}")
            # Extract text from candidates
            cands = data.get("candidates", [])
            if cands and isinstance(cands, list):
                content = cands[0].get("content", {})
                parts = content.get("parts", [])
                if parts and isinstance(parts, list):
                    text = parts[0].get("text", "")
                    if text:
                        return text
            # If no text found, raise error with raw response preview
            raise LLMError(f"Gemini devolveu resposta sem texto: {json.dumps(data)[:300]}")
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Falha na geração Gemini: {e}")

    def _cloudflare_generate(self, prompt: str) -> str:
        """Generate text using Cloudflare Workers AI.

        API key format: ACCOUNT_ID:API_TOKEN (separated by colon).
        """
        if not self.api_key or ":" not in self.api_key:
            raise LLMError("Cloudflare requer credenciais no formato ACCOUNT_ID:API_TOKEN")

        # Split on first colon only (API token may contain colons)
        account_id, api_token = self.api_key.split(":", 1)
        account_id = account_id.strip()
        api_token = api_token.strip()

        if not account_id or not api_token:
            raise LLMError("ACCOUNT_ID e API_TOKEN não podem estar vazios")

        model = (self.model or "@cf/meta/llama-3-8b-instruct").strip()

        # Cloudflare Workers AI endpoint
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

        payload = {
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
            "User-Agent": "GIFT-Practice/1.0"
        }
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            _, _, resp_body = self._http_request(req, body, timeout=60)
            data = json.loads(resp_body.decode("utf-8"))

            # Cloudflare returns {success: bool, result: {response: "..."}, errors: [...]}
            if not data.get("success", False):
                errors = data.get("errors", [])
                err_msg = errors[0].get("message", "Erro desconhecido") if errors else "Erro desconhecido"
                raise LLMError(f"Cloudflare erro: {err_msg}")

            result = data.get("result", {})
            response = result.get("response", "")
            if not response:
                raise LLMError(f"Cloudflare devolveu resposta sem texto: {json.dumps(data)[:300]}")
            return response
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Falha na geração Cloudflare: {e}")
