"""Load and validate hard-gate scanner weights from weights.toml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_WEIGHTS_PATH = Path(__file__).resolve().parent / "weights.toml"
_DEFAULT_WEIGHTS: dict[str, float] = {
    "manifest": 0.15,
    "dex": 0.10,
    "security": 0.15,
    "secrets": 0.15,
    "native": 0.15,
    "api_watch": 0.10,
    "netsec": 0.05,
    "lint": 0.05,
    "dependency": 0.05,
    "obfuscation": 0.05,
}


def _parse_toml_weights(text: str) -> dict[str, float]:
    weights: dict[str, float] = {}
    in_weights = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "[weights]":
            in_weights = True
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            in_weights = False
            continue
        if not in_weights or "=" not in stripped:
            continue
        key, raw = stripped.split("=", 1)
        key = key.strip()
        raw = raw.split("#", 1)[0].strip()
        try:
            weights[key] = float(raw)
        except ValueError:
            continue
    return weights


def load_scanner_weights(path: Path | None = None) -> dict[str, float]:
    """Return scanner→weight map; falls back to defaults if file missing."""
    weights_path = path or _WEIGHTS_PATH
    if not weights_path.is_file():
        return dict(_DEFAULT_WEIGHTS)
    try:
        parsed = _parse_toml_weights(weights_path.read_text(encoding="utf-8"))
    except OSError:
        return dict(_DEFAULT_WEIGHTS)
    if not parsed:
        return dict(_DEFAULT_WEIGHTS)
    validate_weights(parsed)
    return parsed


def validate_weights(weights: dict[str, float]) -> None:
    total = sum(weights.values())
    if abs(total - 1.0) > 0.001:
        raise ValueError(f"gate weights must sum to 1.0, got {total:.4f}")
    for key, value in weights.items():
        if value < 0:
            raise ValueError(f"negative weight for scanner {key}")


def weights_metadata(weights: dict[str, float]) -> dict[str, Any]:
    return {"scanners": list(weights.keys()), "sum": round(sum(weights.values()), 4)}
