"""Reflection / dynamic loading watchlist (blueprint API-3)."""

from __future__ import annotations

from apex.api_watch import WatchEntry

REFLECTION_WATCHLIST: list[WatchEntry] = [
    WatchEntry(
        "dalvik/system/DexClassLoader",
        "<init>",
        "dynamic-dex-loader",
        "DexClassLoader — review dynamic code loading",
        severity="WARN",
    ),
    WatchEntry(
        "dalvik/system/PathClassLoader",
        "<init>",
        "dynamic-path-loader",
        "PathClassLoader — review dynamic code loading",
        severity="WARN",
    ),
    WatchEntry(
        "java/lang/Class",
        "forName",
        "reflection-forname",
        "Class.forName — review reflection usage",
        severity="WARN",
    ),
    WatchEntry(
        "java/lang/reflect/Method",
        "invoke",
        "reflection-invoke",
        "Method.invoke — review reflective invocation",
        severity="WARN",
    ),
]
