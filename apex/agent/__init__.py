"""APEX Code Pilot — in-product agent for prompt-driven reverse engineering.

Paid Pro feature. Users describe what they want; Code Pilot selects and runs
APEX tools (inspect, security_scan, decompile, …) and explains the results.
"""

from __future__ import annotations

from .loop import run_code_pilot
from .providers import available_providers, resolve_provider

__all__ = ["available_providers", "resolve_provider", "run_code_pilot"]
