"""Reading a model's reply. Models wrap JSON in code fences and chatter, so this is tolerant about the wrapping and
strict about the shape: it returns the list found under one key, or raises ValueError."""
import json
import re


def parse_reply(text, key):
    """Pull the list under `key` (or a bare list) out of a model's reply. Raises ValueError if there is none."""
    candidate = text.strip()
    candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("the reply contains no JSON object")
        try:
            data = json.loads(candidate[start:end + 1])
        except json.JSONDecodeError as e:
            raise ValueError(f"the reply is not valid JSON: {e.msg}") from e
    items = data.get(key) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError(f'the reply has no "{key}" list')
    return items
