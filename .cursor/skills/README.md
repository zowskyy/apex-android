# Global agent skill — finished product delivery

One skill file for **every project**, on **every agent surface** (Cursor,
Claude Code desktop, Claude Code mobile).

## Install

### Cursor (global)

```bash
mkdir -p ~/.cursor/skills
cp -r .cursor/skills/finished-product-delivery ~/.cursor/skills/
```

Or symlink:

```bash
ln -sf "$(pwd)/.cursor/skills/finished-product-delivery" ~/.cursor/skills/
```

### Claude Code

Copy the same folder into your Claude Code skills directory, or paste
`finished-product-delivery/SKILL.md` into a project-level `CLAUDE.md` / skills
config. The file is self-contained — no other skill files required.

### Project reference

Point agents at the repo copy:

```text
.cursor/skills/finished-product-delivery/SKILL.md
```

Project-specific rules live in `AGENTS.md` and `docs/PRINCIPLES.md`.

## What it covers

| Pillar | Enforces |
|---|---|
| Complete suite | Ship full capability now — no withheld essentials |
| End-to-end wiring | Connect every layer before merge |
| Marketplace-ready | Public description matches reality |

## One-sentence standard

**Ship a complete, honestly described, fully wired product — not a bun with a
roadmap for the patty.**
