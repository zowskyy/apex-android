"""Cross-platform app intelligence: tracker and third-party library detection."""

from __future__ import annotations

from apex.intel.detect import detect_components, summarize_detections
from apex.intel.signatures import load_signatures, signature_stats

__all__ = [
    "detect_components",
    "summarize_detections",
    "load_signatures",
    "signature_stats",
]
