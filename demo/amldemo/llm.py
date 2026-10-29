"""One small interface to the language model: complete(system, user, task) returns text.

Providers:
  mock    replays canned responses from samples/mock/<task>.json. For tests and offline runs; it is NOT a model.
  ollama  a model running on this machine (default qwen3.5:9b), through Ollama's own chat API.
  zai     the Z.ai / Zhipu GLM API (OpenAI-compatible). Needs Z_AI_API_KEY in demo/.env. Not yet tried end to end.

Nothing here looks at the content of a prompt or a reply; checking the reply is the validator's job.
"""
import json
import urllib.error
import urllib.request

from . import config


class LLMError(RuntimeError):
    """The model could not be reached or answered with something unusable as text."""


def _post_json(url, payload, headers=None, timeout=600):
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise LLMError(f"{url} answered HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from e
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise LLMError(f"could not reach {url}: {e}") from e
    except json.JSONDecodeError as e:
        raise LLMError(f"{url} did not return JSON: {e}") from e


class MockLLM:
    name = "mock"
    model = "canned"

    def complete(self, system, user, task):
        path = config.MOCK_DIR / f"{task}.json"
        if not path.exists():
            raise LLMError(f"no canned response for task {task!r} (expected {path})")
        return path.read_text(encoding="utf-8")


class OllamaLLM:
    name = "ollama"

    def __init__(self, model=None, url=None):
        self.model = model or config.LLM_MODEL or config.OLLAMA_DEFAULT_MODEL
        self.url = (url or config.OLLAMA_URL).rstrip("/")

    def complete(self, system, user, task):
        data = _post_json(f"{self.url}/api/chat", {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "think": False,          # a reasoning model would otherwise spend minutes thinking
            "format": "json",
            "options": {"temperature": 0, "num_ctx": 16384},   # the default window (4096) cuts off a prompt that lists many indicators
        })
        text = (data.get("message") or {}).get("content")
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Ollama returned an empty answer")
        return text


class ZaiLLM:
    name = "zai"

    def __init__(self, model=None):
        self.model = model or config.LLM_MODEL or config.Z_AI_CHAT_MODEL
        if not config.Z_AI_API_KEY:
            raise LLMError("Z_AI_API_KEY is not set; put it in demo/.env (see .env.example)")
        if not self.model:
            raise LLMError("no model name; set Z_AI_CHAT_MODEL in demo/.env")

    def complete(self, system, user, task):
        data = _post_json(
            f"{config.Z_AI_BASE_URL.rstrip('/')}/chat/completions",
            {"model": self.model, "temperature": 0,
             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            headers={"Authorization": f"Bearer {config.Z_AI_API_KEY}"})
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"unexpected response shape from the GLM API: {str(data)[:200]}") from e
        if not isinstance(text, str) or not text.strip():
            raise LLMError("the GLM API returned an empty answer")
        return text


PROVIDERS = {"mock": MockLLM, "ollama": OllamaLLM, "zai": ZaiLLM}


def make_llm(provider=None):
    name = provider or config.LLM_PROVIDER
    if name not in PROVIDERS:
        raise LLMError(f"unknown LLM provider {name!r}; choose one of {', '.join(PROVIDERS)}")
    return PROVIDERS[name]()
