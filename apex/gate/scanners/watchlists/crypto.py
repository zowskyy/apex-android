"""Crypto-misuse watchlist (blueprint API-2)."""

from __future__ import annotations

from apex.api_watch import WatchEntry

CRYPTO_WATCHLIST: list[WatchEntry] = [
    WatchEntry(
        "javax/crypto/Cipher",
        "getInstance",
        "crypto-weak-cipher",
        "Cipher.getInstance usage — verify mode is not ECB/DES/RC4",
        severity="WARN",
        string_hint=r"ECB|/DES|RC4",
    ),
    WatchEntry(
        "java/security/MessageDigest",
        "getInstance",
        "crypto-weak-digest",
        "MessageDigest.getInstance — verify MD5/SHA-1 are not used for security-sensitive hashing",
        severity="WARN",
        string_hint=r"MD5|SHA-1|SHA1",
    ),
    WatchEntry(
        "javax/crypto/spec/SecretKeySpec",
        "<init>",
        "crypto-hardcoded-key",
        "SecretKeySpec constructed — review for hardcoded key material",
        severity="WARN",
    ),
    WatchEntry(
        "javax/crypto/spec/IvParameterSpec",
        "<init>",
        "crypto-hardcoded-iv",
        "IvParameterSpec constructed — review for hardcoded IV",
        severity="WARN",
    ),
    WatchEntry(
        "java/security/SecureRandom",
        "<init>",
        "crypto-weak-random",
        "SecureRandom constructed — verify seed source is not predictable",
        severity="WARN",
        string_hint=r"new SecureRandom\\(\\)|setSeed",
    ),
    WatchEntry(
        "java/security/SecureRandom",
        "getInstance",
        "crypto-weak-random",
        "SecureRandom.getInstance — verify algorithm is not SHA1PRNG default misuse",
        severity="WARN",
        string_hint=r"SHA1PRNG|setSeed",
    ),
]
