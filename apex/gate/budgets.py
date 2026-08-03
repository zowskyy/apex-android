"""Per-scanner time budgets for hard-gate execution."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

# Seconds — lightweight fallbacks kick in on timeout for DEX-heavy scanners.
SCANNER_BUDGETS: dict[str, float] = {
    "manifest": 15.0,
    "dex": 30.0,
    "security": 20.0,
    "secrets": 45.0,
    "native": 30.0,
    "api_watch": 60.0,
    "netsec": 15.0,
    "lint": 180.0,
    "obfuscation": 30.0,
    "dependency": 45.0,
}


def run_with_budget(
    scanner: str,
    fn: Callable[[], T],
    *,
    fallback: Callable[[], T] | None = None,
    timeout: float | None = None,
) -> T:
    """Run a scanner callable with a wall-clock timeout."""
    limit = timeout if timeout is not None else SCANNER_BUDGETS.get(scanner, 60.0)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=limit)
        except concurrent.futures.TimeoutError:
            if fallback is not None:
                return fallback()
            raise TimeoutError(f"scanner {scanner} exceeded budget of {limit}s")
