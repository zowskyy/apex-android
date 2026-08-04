# Changelog

All notable changes to APEX are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Python lockfiles (`requirements.lock`, `requirements-dev.lock`) and
  `scripts/generate_lockfiles.sh`
- Declared Rust MSRV (`rust-version = "1.74"`) on the Cargo workspace
- Global CLI `-v` / `--verbose` logging (`-v` INFO, `-vv` DEBUG)
- `build.sh --verbose` and standalone Android `--verbose` passthrough
- Community health docs: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, root
  `SECURITY.md`
- This changelog
- ARC code-audit design (`docs/ARC_CODE_AUDIT_DESIGN.md`),
  `.cursor/FEEDBACK_PROTOCOL.md`, `.cursor/audit_input.yaml`, and Iterative
  Zero-Findings rule in `universal-arc-engine` skill

### Changed

- Docker image pins `python:3.12-slim-bookworm` by digest, installs from
  `requirements.lock`, builds native wheels with `maturin --locked`, and runs
  as a non-root `apex` user
- Reproducibility docs updated for lockfiles, MSRV, and pinned Docker base

## [0.4.11] — 2026-08-03

### Added

- Hard gate through CVE advisory scanners (manifest, dex, security, secrets,
  native, api_watch, netsec, lint, obfuscation, dependency)
- Audit trail (hash-chained gate log) and monthly compliance reports
- Unified release factory (`release.yml` DAG) with SBOM + SHA256SUMS
- `apex update-db` / `--osv` for CVE library refresh
- Universal-ARC-Engine skill, terminal demo script, monitor-gates fix

### Changed

- Release verify uses venv for maturin; security-scan normalizes WARN severity
- Windows desktop zip packaging uses `pwd -W` paths for Compress-Archive

## [0.4.10] — 2026-08-02

### Added

- Blueprint slices: SECRETS-2, gate weights, native ELF, dex watch

## [0.4.9] — 2026-08-01

### Added

- Workspace path containment and secret scanner

[Unreleased]: https://github.com/zowskyy/apex-android/compare/v0.4.11...HEAD
[0.4.11]: https://github.com/zowskyy/apex-android/releases/tag/v0.4.11
[0.4.10]: https://github.com/zowskyy/apex-android/releases/tag/v0.4.10
[0.4.9]: https://github.com/zowskyy/apex-android/releases/tag/v0.4.9
