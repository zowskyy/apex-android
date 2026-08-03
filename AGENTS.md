# AGENTS.md — APEX

## Product principle (non-negotiable)

**Everything essential ships as part of the core product.**

Read `docs/PRINCIPLES.md` before planning work. It overrides roadmap sequencing
that would defer core capability.

### Global skill (every project)

Follow `.cursor/skills/finished-product-delivery/SKILL.md` (install per
`.cursor/skills/README.md`). It requires **GitHub CI validation** before any
slice is declared done — not only local tests.

## Architecture (this repo)

| Layer | Location | Role |
|---|---|---|
| Analysis | `apex/analysis.py` | ZIP (Rust), AXML/ARSC/DEX (Androguard + native DEX) |
| Workflows | `apex/workflows.py` | analyze, decompile, decode/build, verify, security |
| CLI | `apex/cli.py` | full command surface |
| Web UI | `apex/web.py` | loopback UI + Code Pilot chat |
| Edition / MCP / Agent | `apex/edition.py`, `apex/mcp_server.py`, `apex/agent/` | licensing, MCP, Code Pilot |
| Tools | `apex/tools.py` | shared registry for MCP + Code Pilot |
| Native | `core/zip_reader`, `core/dex_parser`, `core/dex_reader` | Rust hot paths |

## Development

```bash
./build.sh --skip-tests          # install + native extensions
scripts/validate_slice.sh        # mirror GitHub CI locally — run before push
scripts/check_github_ci.sh       # after push: verify Actions green on HEAD
scripts/check_github_ci.sh --apk # before mobile APK handoff: CI + standalone APK green
```

Equivalent manual steps:

```bash
pip install -e ".[dev,mcp]"
maturin develop --release -m core/zip_reader/Cargo.toml
maturin develop --release -m core/dex_reader/Cargo.toml
ruff check apex tests
pytest -q
cargo test --workspace
```

## Slice completion (required)

1. Implement and wire end-to-end (CLI + web + tests + docs).
2. `scripts/validate_slice.sh` — must pass.
3. `git push` to the PR branch.
4. GitHub Actions workflow **`CI`** must show **success** on the pushed `HEAD`.
5. `scripts/check_github_ci.sh` (or `gh run list`) — confirm before telling the
   user the slice is done or CI passes.
6. Update `docs/PROJECT_STATE.md`.

**Do not** claim "CI passes", "ready to ship", or "validated" without a green
GitHub Actions run on the current commit.
