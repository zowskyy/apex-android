"""Opening disclaimer — science / education first; user bears misuse liability."""

from __future__ import annotations

import json
import os
from pathlib import Path

DISCLAIMER_VERSION = 1

DISCLAIMER_TITLE = "APEX Acceptable Use Notice"

DISCLAIMER_TEXT = """APEX is built for science, innovation, education, security research, \
defensive analysis, and constructive software engineering. Its reverse-engineering \
and rebuild capabilities are intentionally broad so legitimate researchers and \
creators are not artificially blocked.

APEX must NOT be used to harm people, steal, defraud, stalk, harass, distribute \
malware, violate computer-crime laws, or otherwise cause unlawful damage. The \
authors and distributors do not authorize, encourage, or condone such use, and \
accept no responsibility for how you choose to use this program if you use it \
to cause harm.

You alone are responsible for complying with applicable law. Misuse may result \
in civil legal action and, where applicable, criminal investigation and \
prosecution by the proper authorities. The authors and rights holders intend to \
pursue available civil remedies and to cooperate with law enforcement to the \
fullest extent permitted by law.

Capability is unrestricted because this project prioritizes positive productivity \
and creation — not because harmful use is tolerated. Any attempt to use APEX \
outside that spirit may be pursued to the fullest extent of the law.

By continuing, you agree to use APEX only for education, research, and constructive innovation."""


def disclaimer_path() -> Path:
    override = os.environ.get("APEX_LICENSE_DIR")
    root = Path(override).expanduser() if override else Path.home() / ".apex"
    return root / "disclaimer_accepted.json"


def disclaimer_accepted() -> bool:
    path = disclaimer_path()
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return int(data.get("version", 0)) >= DISCLAIMER_VERSION and bool(data.get("accepted"))


def accept_disclaimer() -> None:
    path = disclaimer_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": DISCLAIMER_VERSION,
                "accepted": True,
                "title": DISCLAIMER_TITLE,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def require_disclaimer_acceptance(*, interactive: bool = True) -> None:
    """Block CLI entry until the opening notice is accepted."""
    if disclaimer_accepted() or os.environ.get("APEX_DISCLAIMER_ACCEPTED") == "1":
        return
    print("=" * 72)
    print(DISCLAIMER_TITLE)
    print("=" * 72)
    print(DISCLAIMER_TEXT)
    print("=" * 72)
    if not interactive:
        raise SystemExit(
            "APEX opening disclaimer not accepted. "
            "Re-run interactively or set APEX_DISCLAIMER_ACCEPTED=1 after review."
        )
    answer = input("Type YES to agree and continue (anything else exits): ").strip()
    if answer.upper() != "YES":
        raise SystemExit("Disclaimer declined. Exiting.")
    accept_disclaimer()
