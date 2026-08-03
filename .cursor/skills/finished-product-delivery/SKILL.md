---
name: finished-product-delivery
description: Apply to every project when planning, building, reviewing, or shipping software. One standard for complete suites (no withheld essentials), end-to-end wiring (every layer connected), marketplace-ready release (description matches reality), and GitHub CI validation before claiming done. Use on Cursor, Claude Code, and Claude mobile.
---

# Finished Product Delivery

> **One rule:** Ship a complete, honestly described, fully wired product — not a
> bun with a roadmap for the patty.

Use this skill for **all** software work: scoping, implementation, review, and
release. It replaces separate "complete suite", "wiring", and "marketplace"
checklists with a single standard.

---

## 1. Complete suite — ship it all now

**If a capability makes the product easier, more effective, or more powerful for
the user, it is essential and ships now.**

Not v2. Not an upsell. Not "phase 2." Not "nice to have."

### Hamburger test

You advertise a hamburger. The customer expects the bun, patty, condiments, and
safe handling — not a bun with "meat coming later." A README, store listing,
demo, or roadmap is the same kind of promise.

Shipping backend without UI, engine without CLI, or workflow without error
handling is **not** an MVP. It is an incomplete product misrepresented as
ready.

### Rules

1. No artificial staging across releases to fake momentum.
2. "Graceful degradation" means not crashing — not shipping hollow features.
3. Build it in; do not make users install or wire what the product can do.
4. Scope the **whole** workflow users need, not the minimum demo slice.
5. "Optional" only when a real user would rationally skip it.
6. Roadmaps are for new research/hardware/demand — not current promises.
7. State real blockers plainly; never dress unfinished work as a future upgrade.
8. Everything in docs, UI, listings, and demos must work on day one.

---

## 2. End-to-end wiring — connect every layer

**A capability in only one layer is a stub, not a shipped feature.**

### Wiring path

Trace every user-facing capability:

```text
User → CLI / web / API → services → domain logic → persistence / providers
     → response → presentation → tests → docs
```

Any broken link = not done.

### Rules

1. No orphan modules — everything reachable from a user entry point.
2. Interface parity — wire CLI, API, and UI in the same change when all apply.
3. Shared services — no duplicated business logic in handlers or argparse.
4. Data flows both ways — ingest and query use the same schema.
5. Errors propagate with actionable messages; no silent empty panels.
6. Configuration centralized — one place for paths, versions, flags.
7. Tests run the wired path a user would actually take.

### Wiring checklist

| Layer | Must pass |
|---|---|
| Domain logic | Correct output |
| Service API | Single callable surface for all interfaces |
| CLI | User can invoke it |
| Web/API | User can invoke it (when applicable) |
| Persistence | State survives restart (when applicable) |
| Providers | External tools optional; native fallback exists |
| Tests | CI covers user-facing path; GitHub Actions `CI` green on HEAD before done |
| Docs | README/help match behavior |

Skip a row only when that surface genuinely does not apply. Never skip because
"we'll add it later."

---

## 3. Marketplace-ready release — match what you promise

**You release a product people compare to alternatives — not source code.**

### Marketplace test

*If this shipped tomorrow next to the category leader, what would a reviewer say
in five minutes?*

"Where is…", "doesn't work unless…", "half the UI is empty", or "description
lied" = not ready.

### Release pillars

**Description fidelity** — listings, README, screenshots, and demos are true
today. Optional tools are optional; core value never depends on them.

**First-run success** — a new user follows published install steps and completes
the primary workflow without insider help.

**Safety** — local-by-default where appropriate; no silent network calls;
dangerous ops need explicit user action; security findings are evidence, not
verdicts; permissions scoped and documented.

**Quality bar** — no truncated UI data, broken layout, or placeholder panels;
stable CLI/JSON; fast enough for daily use; CI green; single version source.

**Policy awareness** — third-party licenses documented; store policies met;
no liability claims (malware verdicts, compliance certs) without basis. Flag
gaps; do not ship and hope. (Not legal advice.)

---

## 4. GitHub CI validation — prove claims before finishing

**Local tests passing is not sufficient if GitHub Actions differs.**

CI runners use their own venv, dependency resolution, and toolchain paths.
Claims like "tests pass", "CI green", or "ready to merge" require evidence from
**GitHub Actions on the PR branch HEAD commit** — not only local `pytest`.

### Rules

1. After push, wait for workflow `CI` to complete (do not assume success from push alone).
2. Verify `conclusion: success` on the commit you are finishing — use GitHub UI or `gh run list`.
3. Run `scripts/validate_slice.sh` locally before push (mirrors `.github/workflows/ci.yml`).
4. After push, run `scripts/check_github_ci.sh` when `gh` is available (`--apk` before any mobile APK handoff).
5. Never tell the user CI passed if the latest run on HEAD failed or is still `in_progress`.
6. Never give users APK download links or “install this build” unless `scripts/check_github_ci.sh --apk` passes on that commit.
7. If CI fails, fix, push again, and re-verify — do not declare the slice done on a failed run.
8. For mobile/Android: also follow `.cursor/skills/mobile-hard-gate/SKILL.md` (WebView file picker, Chaquopy deps, device smoke, Releases gate).

### Slice exit (Salami cycle)

```text
Implement → scripts/validate_slice.sh → git push → GitHub CI green on HEAD →
update PROJECT_STATE.md → mark slice done
```

---

## Master checklist — run before declaring done

### Scope (complete suite)

- [ ] User does not install/configure something the product could do itself
- [ ] No advertised capability is only partially usable
- [ ] Nothing deferred only because it was more work
- [ ] Reasonable user assumptions are met
- [ ] Every interface exposes capabilities that exist in the engine

### Wiring

- [ ] No `TODO: wire to UI` or orphan modules in merged code
- [ ] CLI and web call the same services
- [ ] API returns real data, not mocks
- [ ] Errors show helpful messages, not blank screens or stack traces
- [ ] At least one test exercises the user-facing path

### Release (marketplace)

- [ ] Primary journey works on a clean machine from published install steps
- [ ] No demo/mock/hardcoded data in production paths
- [ ] Doctor/health/status reports environment accurately (when applicable)
- [ ] Sensitive values redacted from logs and reports
- [ ] Version bumped in one canonical place; changelog matches reality
- [ ] Known limitations stated plainly — not hidden as "coming soon"
- [ ] Manual smoke test on actual UI (when applicable)

### CI (GitHub Actions)

- [ ] `scripts/validate_slice.sh` passed locally before push
- [ ] Changes pushed to the PR/feature branch
- [ ] GitHub Actions workflow `CI` **success** on current `HEAD` (verified via UI or `scripts/check_github_ci.sh`)
- [ ] Mobile APK handoff only if `Android standalone APK` **success** on same `HEAD` (`scripts/check_github_ci.sh --apk`)
- [ ] No "ready to ship" / "CI passes" claim without the green run URL or check output

---

## Anti-patterns — reject all of these

| Anti-pattern | Correct behavior |
|---|---|
| "Coming in a future release" for obvious core need | Ship now |
| "Install X yourself to enable Y" | Native path or bundle X |
| "Phase 2: the useful part" | Phase 1 includes it |
| Backend done, UI later | Wire all interfaces together |
| Feature only works with optional tool | First-class built-in fallback |
| README promises workflow app cannot run | Implement or fix docs |
| Demo data in production UI | Real data or remove feature |
| v1.0 on a vertical slice | Finish or re-label honestly |
| Security tool phones home silently | Local-first; explicit export only |

---

## Definition of done

Done is **not** "code merged." Done is:

1. **Complete** — full suite, no withheld essentials
2. **Wired** — every layer connected end to end
3. **Described** — public materials match reality
4. **Verified** — `scripts/validate_slice.sh` passed; GitHub Actions CI green on HEAD; smoke test passed
5. **Honest** — limitations stated; no fake completeness

**Do not sell the bun and call it a hamburger.**
