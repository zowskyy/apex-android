"""Edition, licensing, and feature-gating for commercial APEX releases.

Community edition ships the full local CLI and web UI. Pro edition unlocks
automation surfaces (MCP server, batch workflows, PostgreSQL storage) and is
activated with a license key file or environment variable.

License validation is intentionally simple and offline-first so you can plug
in your own entitlement backend later without rewriting call sites.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from enum import Enum
from pathlib import Path
from typing import Any

from .version import PRODUCT_NAME, __version__


class Edition(str, Enum):
    COMMUNITY = "community"
    PRO = "pro"


class Feature(str, Enum):
    """Capabilities that can be gated per edition."""

    INSPECT = "inspect"
    ANALYZE = "analyze"
    DECOMPILE = "decompile"
    DECODE = "decode"
    BUILD = "build"
    VERIFY = "verify"
    ROUNDTRIP = "roundtrip"
    SECURITY_SCAN = "security_scan"
    DIFF = "diff"
    FRAMEWORK_CHECK = "framework_check"
    WEB_UI = "web_ui"
    # Pro automation & integration
    MCP_SERVER = "mcp_server"
    CODE_PILOT = "code_pilot"
    POSTGRES_STORE = "postgres_store"
    BATCH_WORKFLOWS = "batch_workflows"


COMMUNITY_FEATURES: frozenset[Feature] = frozenset(
    {
        Feature.INSPECT,
        Feature.ANALYZE,
        Feature.DECOMPILE,
        Feature.DECODE,
        Feature.BUILD,
        Feature.VERIFY,
        Feature.ROUNDTRIP,
        Feature.SECURITY_SCAN,
        Feature.DIFF,
        Feature.FRAMEWORK_CHECK,
        Feature.WEB_UI,
    }
)

PRO_FEATURES: frozenset[Feature] = COMMUNITY_FEATURES | frozenset(
    {
        Feature.MCP_SERVER,
        Feature.CODE_PILOT,
        Feature.POSTGRES_STORE,
        Feature.BATCH_WORKFLOWS,
    }
)

_LICENSE_PATTERN = re.compile(r"^APEX-PRO-[A-F0-9]{16}$")
_ENTITLEMENT_SALT = "apex-android-pro-v1"
_DEFAULT_LICENSE_DIR = Path.home() / ".apex"


class EditionError(RuntimeError):
    """Raised when a feature is not licensed for the active edition."""


def _license_dir() -> Path:
    override = os.environ.get("APEX_LICENSE_DIR")
    return Path(override).expanduser() if override else _DEFAULT_LICENSE_DIR


def license_file() -> Path:
    override = os.environ.get("APEX_LICENSE_FILE")
    return Path(override).expanduser() if override else _license_dir() / "license.json"


def _normalize_key(raw: str) -> str:
    return raw.strip().upper().replace(" ", "")


def generate_license_key(entitlement: str) -> str:
    """Derive a Pro license key from a customer entitlement identifier."""
    digest = hashlib.sha256(f"{_ENTITLEMENT_SALT}:{entitlement}".encode()).hexdigest().upper()[:16]
    return f"APEX-PRO-{digest}"


def _valid_pro_key(key: str, entitlement: str | None = None) -> bool:
    normalized = _normalize_key(key)
    if not _LICENSE_PATTERN.match(normalized):
        return False
    entitlement = entitlement or os.environ.get("APEX_ENTITLEMENT", "demo")
    return normalized == generate_license_key(entitlement)


def read_license_record() -> dict[str, Any] | None:
    env_key = os.environ.get("APEX_LICENSE_KEY")
    if env_key:
        normalized = _normalize_key(env_key)
        entitlement = os.environ.get("APEX_ENTITLEMENT", "demo")
        if _valid_pro_key(normalized, entitlement):
            return {
                "edition": Edition.PRO.value,
                "key": normalized,
                "entitlement": entitlement,
                "source": "environment",
            }
        return None

    path = license_file()
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    key = _normalize_key(str(record.get("key", "")))
    entitlement = str(record.get("entitlement", "demo"))
    if record.get("edition") == Edition.PRO.value and _valid_pro_key(key, entitlement):
        return {**record, "key": key, "entitlement": entitlement, "source": str(path)}
    return None


def active_edition() -> Edition:
    if read_license_record():
        return Edition.PRO
    return Edition.COMMUNITY


def edition_features(edition: Edition | None = None) -> frozenset[Feature]:
    edition = edition or active_edition()
    return PRO_FEATURES if edition == Edition.PRO else COMMUNITY_FEATURES


def has_feature(feature: Feature, edition: Edition | None = None) -> bool:
    return feature in edition_features(edition)


def require_feature(feature: Feature) -> None:
    edition = active_edition()
    if not has_feature(feature, edition):
        raise EditionError(
            f"{PRODUCT_NAME} {feature.value} requires the Pro edition. "
            f"Active edition: {edition.value}. "
            "Set APEX_LICENSE_KEY or place a license file at "
            f"{license_file()}."
        )


def edition_info() -> dict[str, Any]:
    record = read_license_record()
    edition = active_edition()
    return {
        "product": PRODUCT_NAME,
        "version": __version__,
        "edition": edition.value,
        "licensed": record is not None,
        "license_source": record.get("source") if record else None,
        "entitlement": record.get("entitlement") if record else None,
        "features": sorted(feature.value for feature in edition_features(edition)),
        "license_file": str(license_file()),
        "demo_license_key": generate_license_key("demo"),
    }


def generate_demo_license_key() -> str:
    """Create the built-in evaluation Pro key (entitlement: demo)."""
    return generate_license_key("demo")
