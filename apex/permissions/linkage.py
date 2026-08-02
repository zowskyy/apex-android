"""Static permission-to-sensitive-API linkage."""

from __future__ import annotations

from typing import Any

PERMISSION_API_HINTS: dict[str, list[str]] = {
    "android.permission.CAMERA": ["android/hardware/Camera", "openCamera"],
    "android.permission.RECORD_AUDIO": ["MediaRecorder", "AudioRecord"],
    "android.permission.ACCESS_FINE_LOCATION": ["getLastKnownLocation", "requestLocationUpdates"],
    "android.permission.READ_CONTACTS": ["ContactsContract", "query("],
    "android.permission.READ_SMS": ["Telephony.Sms", "getMessageAt"],
    "android.permission.INTERNET": ["HttpURLConnection", "okhttp", "retrofit"],
}


def link_permissions_to_dex(
    permissions: list[str],
    methods: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    method_text = [
        f"{item.get('class', '')}.{item.get('name', '')} {item.get('descriptor', '')}"
        for item in methods
    ]
    joined = "\n".join(method_text)
    for permission in permissions:
        for hint in PERMISSION_API_HINTS.get(permission, []):
            if hint in joined:
                links.append(
                    {
                        "permission": permission,
                        "api_hint": hint,
                        "evidence": "static_method_reference",
                        "runtime_proven": False,
                    }
                )
    return links
