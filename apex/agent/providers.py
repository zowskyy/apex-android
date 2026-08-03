"""LLM providers for Code Pilot (cloud BYOK, Ollama, or offline heuristic)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Protocol


class AgentError(RuntimeError):
    """Raised when Code Pilot cannot reach a model provider."""


class LLMProvider(Protocol):
    name: str

    def complete(self, messages: list[dict[str, str]]) -> str: ...


class OpenAICompatibleProvider:
    """OpenAI Chat Completions API (also Azure/Groq/compatible gateways)."""

    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("APEX_AGENT_API_KEY") or os.environ.get(
            "OPENAI_API_KEY"
        )
        self.base_url = (
            base_url
            or os.environ.get("APEX_AGENT_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self.model = model or os.environ.get("APEX_AGENT_MODEL") or "gpt-4o-mini"
        if not self.api_key:
            raise AgentError(
                "Code Pilot needs APEX_AGENT_API_KEY or OPENAI_API_KEY "
                "(paid app may inject this later; for now set a key or use provider=heuristic)"
            )

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = json.dumps(
            {"model": self.model, "messages": messages, "temperature": 0.2}
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:500]
            raise AgentError(f"LLM HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise AgentError(f"LLM request failed: {exc}") from exc
        return str(data["choices"][0]["message"]["content"])


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or os.environ.get("APEX_AGENT_MODEL") or "qwen2.5:7b"
        self.host = (host or os.environ.get("APEX_OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip(
            "/"
        )

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = json.dumps(
            {"model": self.model, "messages": messages, "stream": False}
        ).encode()
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                data = json.loads(response.read().decode())
        except urllib.error.URLError as exc:
            raise AgentError(
                f"Ollama unreachable at {self.host}. Start Ollama or use provider=openai."
            ) from exc
        return str(data.get("message", {}).get("content", ""))


class HeuristicProvider:
    """Offline planner for tests and demos — no network, no API key."""

    name = "heuristic"

    def complete(self, messages: list[dict[str, str]]) -> str:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        lower = user.lower()
        path = _extract_path(user) or _extract_path(messages[0].get("content", "") if messages else "")

        # If last message is a tool result, produce an answer.
        if "Tool result" in user or user.strip().startswith("{"):
            return json.dumps(
                {
                    "answer": (
                        "I ran the requested APEX tools and summarized the structured result above. "
                        "Static findings are evidence for human review — not a malware verdict. "
                        "Next: ask me to decompile, decode, or compare builds if needed."
                    )
                }
            )

        if any(word in lower for word in ("doctor", "health", "ready", "setup")):
            return json.dumps({"tool": "doctor", "arguments": {}})
        if any(word in lower for word in ("security", "scan", "traversal", "zip bomb", "risk")):
            if not path:
                return json.dumps({"answer": "Tell me the APK path to security-scan."})
            return json.dumps({"tool": "security_scan", "arguments": {"path": path}})
        if any(word in lower for word in ("decompile", "java", "smali", "source")):
            if not path:
                return json.dumps({"answer": "Provide an APK path to decompile."})
            return json.dumps({"tool": "decompile", "arguments": {"path": path}})
        if any(word in lower for word in ("decode", "rebuild", "editable", "project")):
            if not path:
                return json.dumps({"answer": "Provide an APK path to decode."})
            return json.dumps({"tool": "decode", "arguments": {"path": path, "backend": "auto"}})
        if "diff" in lower or "compare" in lower:
            return json.dumps(
                {
                    "answer": "To compare packages, give me two APK paths (left and right)."
                }
            )
        if any(word in lower for word in ("inspect", "manifest", "what is", "package", "permissions")):
            if not path:
                return json.dumps({"answer": "Provide an APK path to inspect."})
            return json.dumps({"tool": "inspect", "arguments": {"path": path}})
        if path:
            return json.dumps({"tool": "inspect", "arguments": {"path": path}})
        return json.dumps(
            {
                "answer": (
                    "I can inspect, security-scan, analyze, decompile, decode, verify, "
                    "diff, or roundtrip APKs. Tell me what you want and include the APK path."
                )
            }
        )


_PATH_RE = re.compile(r"(/[^\s\"']+\.apk|[\w.:\\-]+\.apk)", re.IGNORECASE)


def _extract_path(text: str) -> str | None:
    match = _PATH_RE.search(text)
    return match.group(1) if match else None


def available_providers() -> list[str]:
    return ["openai", "ollama", "heuristic"]


def resolve_provider(name: str | None = None) -> LLMProvider:
    chosen = (name or os.environ.get("APEX_AGENT_PROVIDER") or "openai").lower()
    if chosen in {"openai", "openai-compatible", "cloud"}:
        return OpenAICompatibleProvider()
    if chosen == "ollama":
        return OllamaProvider()
    if chosen in {"heuristic", "offline", "demo"}:
        return HeuristicProvider()
    raise AgentError(f"unknown Code Pilot provider: {chosen}")
