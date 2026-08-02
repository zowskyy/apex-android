# AGENTS.md — APEX

## Product principle (non-negotiable)

**Everything essential ships as part of the core product.**

APEX does not withhold capability to create the appearance of future
improvement. If a capability makes APEX easier, more effective, or more
powerful for the user, it is implemented as an essential part of the suite,
not as a later addition, optional extra, or premium tier.

Read `docs/PRINCIPLES.md` before planning any work. It governs scope decisions
and overrides any roadmap sequencing that would defer core capability.

### Global skills (apply to every project)

Install and follow the skills in `.cursor/skills/` (see
`.cursor/skills/README.md`). These are the canonical, version-controlled
copies; symlink or copy them to `~/.cursor/skills/` for global agent use.

| Skill | Purpose |
|---|---|
| `complete-suite-delivery` | Ship the full suite now — no withheld essentials |
| `end-to-end-wiring` | Wire every layer before merge — no orphan modules |
| `marketplace-ready-release` | Release only what matches the public description |

**The finished-product test:** you cannot sell a hamburger with only the bun
and lettuce. Every advertised workflow must work end to end, across every
interface, with the safety and polish expected of a marketplace competitor.

Practical consequences for contributors and agents:

- Do not defer an obvious user need to a future phase.
- Do not require the user to install a third-party tool for a capability APEX
  can implement itself. Native implementation is the default path; external
  tools are cross-checks or accelerators.
- Do not implement a capability in one interface only. If it exists in the
  engine, expose it in the CLI, the JSON API, and the web UI.
- Do not merge code that is not wired through services → CLI → web → tests.
- Do not ship UI with placeholder data, truncated values, or silent empty states.
- "Handles a missing dependency without crashing" is required engineering.
  It is never a substitute for the capability itself.

## Architecture

| Layer | Location | Role |
|---|---|---|
| Analysis primitives | `apex/analysis.py` | ZIP, AXML/ARSC, DEX via Androguard + Rust ZIP |
| Workflows | `apex/workflows.py` | analyze, decompile, decode/build, verify, diff, security |
| Providers | `apex/providers/` | native + external engines with provenance |
| Signing | `apex/signing/` | native certificate parsing, presentation |
| Device | `apex/device/` | ADB discovery, pull, sync |
| Corpus | `apex/corpus/` | SQLite device/app index |
| Permissions | `apex/permissions/` | catalog, granted state, code linkage |
| Reporting | `apex/reporting/` | SARIF and machine-readable outputs |
| Services | `apex/services.py` | shared CLI/web application layer |
| CLI | `apex/cli.py` | complete command surface |
| Web | `apex/web.py` | loopback UI over the same services |
| Native | `core/zip_reader`, `core/dex_parser` | Rust hot paths |

## Development

```bash
pip install -e .
python -m pytest tests/ -q
cargo test --workspace
ruff check apex tests
```

When Rust ZIP code changes:

```bash
cargo clippy -p apex_zip_reader --all-targets -- -D warnings
bash scripts/audit_slice_1_1.sh
```

## Code conventions

- Python 3.10+, `from __future__ import annotations`
- Errors surfaced to users raise `ApexError` with actionable text
- Never use `shell=True`; all subprocess calls go through `apex/providers/runner.py`
- Redact secrets in commands, logs, provenance, and reports
- Every report carries `schema_version` and `provenance`
- Security findings are evidence-first and never presented as a malware verdict

## Testing expectations

- New capability requires tests in `tests/`
- External-tool paths must also have a native or fallback path that is tested
- Tests must not require a connected device or an installed Android SDK
- Optional live-device tests use the `adb` marker and skip cleanly
