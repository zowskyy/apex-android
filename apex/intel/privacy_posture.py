"""Unified cross-platform privacy posture.

Correlates what an app *declares* (permissions, entitlements, Apple privacy
manifest) against what it *contains* (detected trackers, network posture) and
surfaces discrepancies. This is APEX's differentiator: one evidence-backed
privacy verdict for both Android and iOS, computed entirely offline.

Nothing here is a malware verdict. A discrepancy means declared intent and
observed content disagree, which is a review signal, not an accusation.
"""

from __future__ import annotations

from typing import Any

# High-risk Android runtime permissions (dangerous protection level subset).
_DANGEROUS_ANDROID = {
    "android.permission.READ_CONTACTS",
    "android.permission.WRITE_CONTACTS",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
    "android.permission.READ_SMS",
    "android.permission.SEND_SMS",
    "android.permission.RECEIVE_SMS",
    "android.permission.READ_CALL_LOG",
    "android.permission.WRITE_CALL_LOG",
    "android.permission.READ_PHONE_STATE",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.BODY_SENSORS",
    "android.permission.GET_ACCOUNTS",
    "android.permission.READ_CALENDAR",
    "android.permission.WRITE_CALENDAR",
}


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def assess_posture(
    *,
    platform: str,
    permissions: list[str] | None = None,
    detections: list[dict[str, Any]] | None = None,
    cleartext: bool = False,
    privacy_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a cross-platform privacy posture assessment."""
    permissions = permissions or []
    detections = detections or []
    trackers = [d for d in detections if d.get("kind") == "tracker"]

    categories: dict[str, int] = {}
    for tracker in trackers:
        for category in tracker.get("categories", []):
            categories[category] = categories.get(category, 0) + 1

    dangerous = sorted(p for p in permissions if p in _DANGEROUS_ANDROID)

    discrepancies: list[dict[str, Any]] = []

    if privacy_manifest and privacy_manifest.get("valid"):
        if trackers and not privacy_manifest.get("tracking"):
            discrepancies.append(
                {
                    "severity": "high",
                    "message": (
                        f"{len(trackers)} tracker SDK(s) detected but the privacy manifest "
                        "declares NSPrivacyTracking=false"
                    ),
                }
            )
        declared_domains = privacy_manifest.get("tracking_domains", [])
        if trackers and privacy_manifest.get("tracking") and not declared_domains:
            discrepancies.append(
                {
                    "severity": "medium",
                    "message": "tracking is declared but no tracking domains are listed",
                }
            )

    if trackers and cleartext:
        discrepancies.append(
            {
                "severity": "medium",
                "message": "tracker SDKs are present and cleartext traffic is permitted",
            }
        )

    if platform == "android" and trackers:
        if "android.permission.INTERNET" not in permissions:
            discrepancies.append(
                {
                    "severity": "low",
                    "message": "tracker SDKs are present without an explicit INTERNET permission",
                }
            )

    score = 100
    score -= min(len(trackers) * 4, 40)
    score -= min(len(dangerous) * 3, 20)
    if cleartext:
        score -= 15
    score -= sum(
        {"high": 12, "medium": 8, "low": 4}.get(d["severity"], 5) for d in discrepancies
    )
    score = max(0, min(100, score))

    return {
        "platform": platform,
        "grade": _grade(score),
        "score": score,
        "signals": {
            "tracker_count": len(trackers),
            "tracker_categories": dict(sorted(categories.items())),
            "dangerous_permissions": dangerous,
            "dangerous_permission_count": len(dangerous),
            "cleartext_traffic": cleartext,
        },
        "discrepancies": discrepancies,
        "summary": (
            f"{platform} app: {len(trackers)} tracker(s), {len(dangerous)} high-risk "
            f"permission(s), {len(discrepancies)} declared-vs-actual discrepancy(ies); "
            f"posture grade {_grade(score)}"
        ),
        "disclaimer": (
            "Privacy posture is an evidence-based review signal, not a malware or "
            "compliance verdict."
        ),
    }
