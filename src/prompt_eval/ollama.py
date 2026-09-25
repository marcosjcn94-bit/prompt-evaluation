"""Small Ollama HTTP client with an actionable unavailable-service error."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .prompts import SCHEMA, TOOL_SPEC, render_prompt, tool_result

OLLAMA_URL = "http://localhost:11434"


class OllamaUnavailable(RuntimeError):
    pass


def _request(path, payload=None, timeout=180):
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(f"{OLLAMA_URL}{path}", data=data,
                      headers={"Content-Type": "application/json"} if data else {})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except (URLError, TimeoutError, HTTPError, json.JSONDecodeError) as error:
        detail = getattr(error, "reason", error)
        raise OllamaUnavailable(
            f"Não foi possível acessar o Ollama em {OLLAMA_URL} ({detail}). "
            "Instale/inicie o Ollama e baixe o modelo com `ollama pull qwen3:4b`; "
            "para validar o dataset sem modelo, use `py -3.13 scripts/prompt_eval.py validate`."
        ) from None


def check_model(model):
    response = _request("/api/tags")
    models = response.get("models", [])
    selected = next((item for item in models if item.get("name") == model), None)
    if selected is None:
        raise OllamaUnavailable(
            f"Modelo `{model}` não encontrado. Baixe-o com `ollama pull {model}`."
        )
    return {"name": selected.get("name"), "digest": selected.get("digest")}


def generate(model, prompt_name, job_text):
    messages = [{"role": "user", "content": render_prompt(prompt_name, job_text)}]
    payload = {"model": model, "messages": messages, "stream": False,
               "options": {"temperature": 0, "seed": 20260925}}
    if prompt_name == "json_schema":
        payload["format"] = SCHEMA
    tool_calls = []
    if prompt_name == "tool_instructions":
        payload["tools"] = TOOL_SPEC
        for _ in range(3):
            response = _request("/api/chat", payload)
            message = response.get("message", {})
            calls = message.get("tool_calls", [])
            if not calls:
                return message.get("content", ""), tool_calls, response
            messages.append(message)
            for call in calls:
                name = call.get("function", {}).get("name", "")
                tool_calls.append(name)
                result = tool_result(call["function"].get("arguments", {})) if name == "lookup_skill_taxonomy" else "Ferramenta não autorizada."
                messages.append({"role": "tool", "name": name, "content": result})
            payload["messages"] = messages
        return "", tool_calls, {"error": "tool_call_limit"}
    response = _request("/api/chat", payload)
    return response.get("message", {}).get("content", ""), tool_calls, response
