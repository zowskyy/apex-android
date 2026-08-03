"""Code Pilot agent loop: prompt → tool calls → answer."""

from __future__ import annotations

import json
import re
from typing import Any

from ..edition import Feature, require_feature
from ..tools import call_tool
from .prompts import PLAYBOOKS, build_system_prompt
from .providers import LLMProvider, resolve_provider

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_action(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_RE.search(text)
        if not match:
            return {"answer": text}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"answer": text}


def _truncate(data: Any, limit: int = 12_000) -> str:
    text = json.dumps(data, indent=2, default=str)
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n… (truncated)"


def run_code_pilot(
    prompt: str,
    *,
    apk_path: str | None = None,
    provider: LLMProvider | str | None = None,
    max_steps: int = 6,
    playbook: str | None = None,
) -> dict[str, Any]:
    """Run Code Pilot against a user prompt. Pro edition required."""
    require_feature(Feature.CODE_PILOT)
    if isinstance(provider, str) or provider is None:
        llm = resolve_provider(provider if isinstance(provider, str) else None)
    else:
        llm = provider

    context_bits = []
    if apk_path:
        context_bits.append(f"Active APK path: {apk_path}")
    if playbook and playbook in PLAYBOOKS:
        context_bits.append(f"Playbook: {PLAYBOOKS[playbook]}")
    user_message = prompt.strip()
    if context_bits:
        user_message = "\n".join(context_bits) + "\n\nUser request: " + user_message

    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": user_message},
    ]
    trace: list[dict[str, Any]] = []

    for step in range(max_steps):
        raw = llm.complete(messages)
        action = _parse_action(raw)
        if "answer" in action and "tool" not in action:
            return {
                "answer": str(action["answer"]),
                "steps": step + 1,
                "trace": trace,
                "provider": getattr(llm, "name", "unknown"),
            }
        tool_name = str(action.get("tool", ""))
        arguments = action.get("arguments") or {}
        if not tool_name:
            return {
                "answer": raw.strip() or "I could not determine the next step.",
                "steps": step + 1,
                "trace": trace,
                "provider": getattr(llm, "name", "unknown"),
            }
        if apk_path and "path" not in arguments and tool_name not in {"doctor", "diff"}:
            arguments = {**arguments, "path": apk_path}
        try:
            result = call_tool(tool_name, arguments)
            entry = {"tool": tool_name, "arguments": arguments, "ok": True, "result": result}
        except Exception as exc:  # surface tool errors to the model
            entry = {"tool": tool_name, "arguments": arguments, "ok": False, "error": str(exc)}
            result = {"error": str(exc)}
        trace.append(entry)
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {
                "role": "user",
                "content": f"Tool result for {tool_name}:\n{_truncate(result)}",
            }
        )

    return {
        "answer": (
            "I hit the step limit before finishing. Partial tool trace is included; "
            "try a narrower request."
        ),
        "steps": max_steps,
        "trace": trace,
        "provider": getattr(llm, "name", "unknown"),
    }
