"""iOS application analysis: IPA, Mach-O, Info.plist, and privacy manifest."""

from __future__ import annotations

from apex.ios.ipa import inspect_ipa
from apex.ios.macho import parse_macho
from apex.ios.privacy_manifest import analyze_privacy_manifest

__all__ = ["inspect_ipa", "parse_macho", "analyze_privacy_manifest"]
