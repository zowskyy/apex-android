---
name: marketplace-ready-release
description: Use before publishing, listing, or declaring a product ready for users, app stores, or marketplace competition. Enforces that the shipped product matches its description, meets safety and quality standards, and can stand next to competitors without embarrassing gaps. Apply to every project.
---

# Marketplace-Ready Release

## Core principle

**You are not releasing source code. You are releasing a product people will
compare to alternatives and pay for with their time, money, or trust.**

A competitor on a marketplace must be complete, honest, safe, and polished
enough that a first-time user succeeds without insider knowledge. Partial
products create support burden, bad reviews, and — for regulated domains —
legal exposure when the listing overpromises.

## The marketplace test

Ask: *If this shipped tomorrow on a public store next to the category leader,
what would a reviewer say in the first five minutes?*

If the answer includes "where is…", "this doesn't work unless…", "why is half
the UI empty", or "the description lied", you are not ready to release.

## Release pillars

### 1. Description fidelity

Everything in the listing, README, landing page, screenshots, and demo must be
true on day one:

- Every advertised workflow completes end to end
- Every screenshot reflects current UI, not a mock
- Version numbers, requirements, and platform support are accurate
- "Optional" tools are optional; core value does not depend on them

### 2. First-run success

A new user with only the published install instructions can:

- Install without undocumented steps
- Complete the primary workflow without asking for help
- Understand failures when something is misconfigured
- Find where outputs and data are stored

### 3. Safety and responsibility

Especially for security, privacy, and device-access tools:

- Sensitive data stays local unless explicitly exported by the user
- No silent network calls for core functionality
- Dangerous operations require explicit user action
- Findings are evidence-based, not verdicts ("suspicious pattern" not "malware")
- Signing analysis states what cryptography proves and what it does not
- Permissions and device access are scoped and documented

### 4. Quality bar (competitor-grade)

| Area | Minimum standard |
|---|---|
| UI | No truncated data, broken layout, or placeholder panels |
| CLI | Stable JSON output, actionable errors, `--help` complete |
| Performance | Primary operations fast enough for daily use |
| Reliability | No crashes on malformed but common inputs |
| Tests | CI green; critical paths covered |
| Docs | Install, use, troubleshoot, and limitations documented |
| Versioning | Single source of truth; changelog matches reality |

### 5. Legal and policy awareness

Before public release, verify:

- Third-party tool licenses are respected and documented
- Bundled data (permission catalogs, signatures, etc.) has clear provenance
- Store policies are met (e.g. Play `QUERY_ALL_PACKAGES`, privacy declarations)
- You do not claim capabilities that create liability (malware verdicts,
  compliance certifications) without basis
- Terms of use and privacy policy exist when collecting any user data

This is not legal advice. When in doubt, flag the gap explicitly rather than
shipping and hoping.

## Pre-release checklist

Run this before any public release, store submission, or "v1.0" declaration:

- [ ] Primary user journey works on a clean machine from published install steps
- [ ] Every feature mentioned in README/listing is reachable and functional
- [ ] No mock data, lorem ipsum, or hardcoded demo values in production paths
- [ ] Error states show helpful messages, not stack traces or blank screens
- [ ] `doctor` / health / status command reports environment accurately
- [ ] All interfaces (CLI, API, UI) expose the same core capabilities
- [ ] Tests pass in CI without secrets or connected hardware
- [ ] Sensitive values redacted from logs, reports, and provenance
- [ ] Version bumped in one canonical location
- [ ] Changelog or release notes match what actually changed
- [ ] Known limitations stated plainly — not hidden behind "coming soon"
- [ ] Manual smoke test recorded or performed on the actual UI

## Anti-patterns that kill marketplace trust

| Anti-pattern | Why it fails |
|---|---|
| "Works on my machine" install | Users abandon immediately |
| Demo data in production UI | Looks fake; erodes trust |
| Core feature behind undocumented env var | Hidden capability = missing capability |
| Crashes on first real file | One-star review |
| README longer on roadmap than on usage | Signals vaporware |
| Security tool that phones home silently | Trust destroyed permanently |
| v1.0 label on a vertical slice | Users feel deceived |

## What "done" means for a competitor product

Done is not "code merged." Done is:

1. **Described** — public materials match reality
2. **Installed** — clean install path documented and tested
3. **Wired** — all layers connected (see `end-to-end-wiring`)
4. **Complete** — no withheld essentials (see `complete-suite-delivery`)
5. **Verified** — tests green, smoke test passed, polish issues fixed
6. **Honest** — limitations stated; no fake completeness

## Related skills

Apply together with:

- `complete-suite-delivery` — no withheld core features
- `end-to-end-wiring` — all layers connected
