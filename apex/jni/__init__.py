"""JNI correlation between Dalvik methods and native library exports."""

from __future__ import annotations

from apex.jni.mangle import jni_long_name, jni_short_name, mangle
from apex.jni.xref import build_jni_graph

__all__ = ["mangle", "jni_short_name", "jni_long_name", "build_jni_graph"]
