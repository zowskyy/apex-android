# Global Cursor skills — product delivery standards

These skills apply to **every project**, not just APEX. Install them into your
global Cursor skills directory so agents pick them up automatically:

```bash
mkdir -p ~/.cursor/skills
cp -r .cursor/skills/* ~/.cursor/skills/
```

Or symlink:

```bash
ln -sf "$(pwd)/.cursor/skills/complete-suite-delivery" ~/.cursor/skills/
ln -sf "$(pwd)/.cursor/skills/end-to-end-wiring" ~/.cursor/skills/
ln -sf "$(pwd)/.cursor/skills/marketplace-ready-release" ~/.cursor/skills/
```

## Skills

| Skill | When to apply |
|---|---|
| `complete-suite-delivery` | Planning, scoping, roadmaps — ship the full suite now |
| `end-to-end-wiring` | Implementation — connect every layer before merge |
| `marketplace-ready-release` | Pre-release — competitor-grade, description-faithful shipping |

## The standard in one sentence

**Ship a complete, honestly described, fully wired product — not a bun with
a roadmap for the patty.**

Project-specific guidance lives in `AGENTS.md` and `docs/PRINCIPLES.md`.
