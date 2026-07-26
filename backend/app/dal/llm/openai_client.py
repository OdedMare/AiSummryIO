"""OpenAI-compatible JSON-mode LLM client.

Model, API key, and base URL come from the runtime settings store on EVERY
call, so changes saved in the UI settings panel apply immediately. Works
against OpenAI itself and OpenAI-compatible servers (Ollama, vLLM, Groq...)
— the main model is Gemma 4 31B served through Ollama.

Robustness policy, matching LocatoAI:
- no API key required when a custom base_url is set (local servers)
- asks for JSON mode when the server supports it, falls back if not
- merges the system prompt into the user turn for servers/models that
  reject a system role (some Gemma deployments)
- strips markdown fences from the reply
- retries once with the parse error appended before giving up
"""

import json

import httpx
from openai import BadRequestError, OpenAI

from app.common.errors import AgentError
from app.dal.llm.completion_retry import create_with_retry
from app.dal.llm.json_response_parser import extract_json
from app.dal.llm.message_merger import merge_system_into_user
from app.dal.llm.model_id_extractor import extract_model_ids

# One initial attempt + one retry with the parse error appended.
_MAX_JSON_ATTEMPTS = 2
_DIET_MAX_COMPLETION_TOKENS = 1200
# The SDK requires a non-empty key; local servers/gateways ignore it.
_LOCAL_SERVER_KEY_PLACEHOLDER = "null"
_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIJsonClient:
    def __init__(self, settings_store):
        self._store = settings_store
        self._cached_client = None
        self._cached_key = None

    def complete_json(self, system: str, user: str, schema=None) -> dict:
        settings = self._store.get()
        if not settings.openai_api_key and not settings.llm_base_url:
            raise AgentError("לא הוגדר מפתח API או שרת תואם OpenAI")
        client = self._client_for(settings.openai_api_key, settings.llm_base_url)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        last_error = "unknown"
        max_tokens = (
            _DIET_MAX_COMPLETION_TOKENS if settings.llm_diet_mode else None
        )
        for _attempt in range(_MAX_JSON_ATTEMPTS):
            content, current = self._complete(
                client, settings.llm_model, messages, max_tokens, schema,
            )
            for key in usage:
                usage[key] += current.get(key, 0)
            try:
                result = extract_json(content)
                if usage["total_tokens"]:
                    result["_usage"] = usage
                return result
            except json.JSONDecodeError as exc:
                last_error = str(exc)
                messages += [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": (
                        "The response was not valid JSON. Return only one JSON object."
                    )},
                ]
        raise AgentError("המודל החזיר JSON לא תקין פעמיים: " + last_error)

    def list_models(self, base_url_override=None, api_key_override=None):
        settings = self._store.get()
        base = base_url_override or settings.llm_base_url
        key = api_key_override or settings.openai_api_key
        if not key and not base:
            raise AgentError("לא הוגדר חיבור למודל")
        try:
            response = httpx.get(
                (base or _DEFAULT_BASE_URL).rstrip("/") + "/models",
                headers={"Authorization": "Bearer " + (key or _LOCAL_SERVER_KEY_PLACEHOLDER)},
                timeout=30,
            )
            response.raise_for_status()
            return extract_model_ids(response.json())
        except Exception as exc:
            raise AgentError("לא ניתן לטעון מודלים: " + str(exc))

    def _client_for(self, api_key, base_url):
        cache_key = (api_key, base_url)
        if self._cached_client is None or self._cached_key != cache_key:
            self._cached_client = OpenAI(
                api_key=api_key or _LOCAL_SERVER_KEY_PLACEHOLDER, base_url=base_url or None
            )
            self._cached_key = cache_key
        return self._cached_client

    @staticmethod
    def _complete(client, model, messages, max_tokens, schema):
        attempts = []
        if schema:
            attempts.append({
                "messages": messages,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "summary_response", "schema": schema},
                },
            })
        attempts += [
            {"messages": messages, "response_format": {"type": "json_object"}},
            {"messages": messages},
            {"messages": merge_system_into_user(messages)},
        ]
        if max_tokens:
            attempts = [
                dict(item, max_tokens=max_tokens) for item in attempts
            ]
        last_error = None
        for kwargs in attempts:
            try:
                response = create_with_retry(client, model, kwargs)
                content = response.choices[0].message.content
                if not content:
                    raise AgentError("המודל החזיר תשובה ריקה")
                raw = response.usage
                usage = {
                    "prompt_tokens": raw.prompt_tokens if raw else 0,
                    "completion_tokens": raw.completion_tokens if raw else 0,
                    "total_tokens": raw.total_tokens if raw else 0,
                }
                return content, usage
            except BadRequestError as exc:
                last_error = exc
            except AgentError:
                raise
            except Exception as exc:
                raise AgentError("שגיאת מודל: " + str(exc))
        raise AgentError("שגיאת מודל: " + str(last_error))

