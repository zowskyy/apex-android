"""Device package pull helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path

from apex.analysis import sha256_file

from .adb import pull_package
from .models import PullResult


def pull_to_layout(
    serial: str,
    package: str,
    root: Path,
    *,
    user_id: int = 0,
    version_name: str = "unknown",
    version_code: int = 0,
) -> PullResult:
    safe_serial = serial.replace("/", "_")
    sha_prefix = f"{package}-{version_code}"
    destination = root / safe_serial / str(user_id) / package / sha_prefix
    result = pull_package(serial, package, destination, user_id=user_id)
    hashes = []
    for artifact in result["artifacts"]:
        local = Path(artifact["local"])
        hashes.append({"split": artifact["split"], "sha256": sha256_file(local)})
    metadata = {
        "package": package,
        "serial": serial,
        "user_id": user_id,
        "version_name": version_name,
        "version_code": version_code,
        "pulled_at": int(time.time()),
        "artifacts": result["artifacts"],
        "hashes": hashes,
    }
    (destination / "pull.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return PullResult(package=package, destination=str(destination), artifact_count=len(hashes))
