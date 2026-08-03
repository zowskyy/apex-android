"""Path containment for the APEX web API (blocks arbitrary local file read)."""

from __future__ import annotations

from pathlib import Path

from apex.analysis import ApexError


def path_is_under_workspace(path: Path, workspace: Path) -> bool:
    """Return True when ``path`` resolves to a location inside ``workspace``."""
    try:
        path.resolve().relative_to(workspace.resolve())
        return True
    except (ValueError, OSError):
        return False


def resolve_client_package_path(
    raw: str,
    workspace: Path,
    *,
    enforce_workspace: bool,
) -> Path:
    """Resolve a client-supplied path for analyze/decompile/agent handlers."""
    cleaned = str(raw or "").strip()
    if not cleaned:
        raise ApexError("path is required")

    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    raw_path = Path(cleaned)

    if enforce_workspace:
        candidate = (
            raw_path.resolve() if raw_path.is_absolute() else (workspace / raw_path).resolve()
        )
        if not path_is_under_workspace(candidate, workspace):
            raise ApexError(
                "path must stay inside the APEX workspace — upload the APK instead of "
                "supplying an absolute path"
            )
    else:
        candidate = raw_path.expanduser().resolve()

    if not candidate.is_file():
        raise ApexError(f"package not found: {candidate}")
    return candidate
