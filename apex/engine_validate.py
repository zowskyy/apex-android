"""Runtime parser validation for embedded Android engine (Chaquopy)."""

from __future__ import annotations

from pathlib import Path

_DATA = Path(__file__).resolve().parent / "data"
_SMOKE_MANIFEST = _DATA / "smoke_manifest.bin"


def validate_on_device_parsers() -> dict[str, str]:
    """Fail fast when manifest parsers cannot run on this device."""
    if not _SMOKE_MANIFEST.is_file():
        return {"ok": "true", "note": "smoke manifest fixture missing — skipped"}

    manifest_raw = _SMOKE_MANIFEST.read_bytes()
    package = ""

    try:
        from apex.analysis import _manifest_summary

        summary = _manifest_summary(manifest_raw)
        package = str(summary.get("package") or "")
        if not package:
            error = summary.get("error", "unknown")
            return {"ok": "false", "error": f"manifest parser returned no package ({error})"}
    except Exception as exc:
        return {"ok": "false", "error": f"manifest parser failed: {exc}"}

    return {"ok": "true", "package": package}
