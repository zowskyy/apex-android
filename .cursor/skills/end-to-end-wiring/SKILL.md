---
name: end-to-end-wiring
description: Use when implementing features, refactoring architecture, or reviewing code before release. Ensures every capability is wired through all relevant layers — data model, services, CLI, API, UI, tests, and docs — so nothing ships as a disconnected fragment. Apply to every project.
---

# End-to-End Wiring

## Core principle

**A capability that exists in only one layer is not shipped. It is a stub.**

Software for real users is a connected system. Building the engine without
exposing it, building the UI without a service behind it, or writing docs for
a workflow the app cannot run are all the same failure mode: disconnected
parts that do not compose into a product.

## The wiring test

For every user-facing capability, trace the full path:

```text
User action → interface (CLI / web / API) → service layer → domain logic →
persistence / external provider → response → presentation → tests → docs
```

If any link in that chain is missing, broken, or only works in a developer's
local environment, the feature is not done.

## Rules

1. **No orphan modules.** New code must be imported, called, and reachable from
   at least one user-facing entry point. Dead code that "will be wired later"
   is not acceptable.
2. **Interface parity.** If a capability belongs in multiple surfaces, wire it
   in all of them in the same change — not "CLI first, UI later."
3. **Shared services, not duplicated logic.** CLI and UI call the same service
   functions. Business logic does not live in route handlers or argparse
   blocks.
4. **Data flows both ways.** Reads and writes use the same schema. A corpus
   that ingests on sync but cannot be queried from the UI is half-wired.
5. **Errors propagate with context.** Every layer translates failures into
   actionable user messages. Silent failures and empty panels with no
   explanation are wiring bugs.
6. **Configuration is centralized.** Paths, versions, feature flags, and tool
   resolution live in one place. Scattered env-var reads across modules are a
   wiring smell.
7. **Tests exercise the wired path.** Unit tests on isolated functions are not
   enough. At least one test must run through the same entry point a user
   would use.

## Wiring checklist (run before declaring done)

| Layer | Question | Must be yes |
|---|---|---|
| Domain | Does the core logic produce correct output? | ✓ |
| Service | Is there a single callable API the interfaces share? | ✓ |
| CLI | Can a user invoke this from the command line? | ✓ |
| Web/API | Can a user invoke this from the UI or HTTP API? | ✓ |
| Persistence | Is state saved and reloadable where expected? | ✓ |
| Provider | Are external tools optional with a native fallback? | ✓ |
| Provenance | Is it recorded which engine produced each result? | ✓ |
| Tests | Does CI cover the user-facing path? | ✓ |
| Docs | Do README/help text match actual behavior? | ✓ |

Skip a row only when that surface genuinely does not apply (e.g. a headless
batch job needs no web UI). Never skip because "we'll add it later."

## Anti-patterns to reject

| Anti-pattern | Correct behavior |
|---|---|
| `TODO: wire to UI` left in merged code | Wire it before merge |
| Duplicate logic in CLI and web handlers | Extract to shared service |
| API endpoint returns mock/placeholder data | Return real data or remove endpoint |
| Feature flag permanently hiding unfinished work | Finish or delete |
| Module exists but nothing imports it | Connect or remove |
| Docs describe commands that don't exist | Implement commands or fix docs |
| Web tab shows empty state with no error | Surface the real failure reason |

## Integration standard

A properly wired feature:

- Works the same whether invoked from CLI, API, or UI
- Survives restart (persisted state reloads correctly)
- Degrades with a clear message when a dependency is missing
- Appears in help text, OpenAPI/schema, and user docs where relevant
- Has at least one automated test on the wired path

## Related skills

Apply together with:

- `complete-suite-delivery` — ship the full capability, not a fragment
- `marketplace-ready-release` — release checklist for competitor products
