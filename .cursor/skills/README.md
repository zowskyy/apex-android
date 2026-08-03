# Global agent skill — finished product delivery

One skill file for **every project**, on **every agent surface** (Cursor,
Claude Code desktop, Claude Code mobile).

## Install

### Cursor (global)

```bash
mkdir -p ~/.cursor/skills
cp -r .cursor/skills/finished-product-delivery ~/.cursor/skills/
cp -r .cursor/skills/mobile-hard-gate ~/.cursor/skills/
cp -r .cursor/skills/hard-gate ~/.cursor/skills/
```

Or symlink:

```bash
ln -sf "$(pwd)/.cursor/skills/finished-product-delivery" ~/.cursor/skills/
ln -sf "$(pwd)/.cursor/skills/mobile-hard-gate" ~/.cursor/skills/
ln -sf "$(pwd)/.cursor/skills/hard-gate" ~/.cursor/skills/
```

### Claude Code

Copy the same folder into your Claude Code skills directory, or paste
`finished-product-delivery/SKILL.md` into a project-level `CLAUDE.md` / skills
config. The file is self-contained — no other skill files required.

### Project reference

Point agents at the repo copy:

```text
.cursor/skills/finished-product-delivery/SKILL.md
.cursor/skills/mobile-hard-gate/SKILL.md   # Android/mobile hard gate before APK handoff
```

Project-specific rules live in `AGENTS.md` and `docs/PRINCIPLES.md`.

## Skills

| Skill | When to use |
|-------|-------------|
| `finished-product-delivery` | Every project — scope, wiring, CI, marketplace |
| `mobile-hard-gate` | Mobile APK, WebView shells, Chaquopy, store/Releases |
| `hard-gate` | 9-slice Phase 1–3 + ship (`scripts/hard_gate.sh`) |

## What it covers

| Pillar | Enforces |
|---|---|
| Complete suite | Ship full capability now — no withheld essentials |
| End-to-end wiring | Connect every layer before merge |
| Marketplace-ready | Public description matches reality |
| GitHub CI proof | Green Actions run on HEAD before claiming done |
| Mobile hard gate | APK/WebView/device smoke before mobile handoff (`mobile-hard-gate`) |

## One-sentence standard

**Ship a complete, honestly described, fully wired product — not a bun with a
roadmap for the patty.**
