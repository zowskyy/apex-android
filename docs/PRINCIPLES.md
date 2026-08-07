# APEX principles

These principles govern what APEX ships and how scope decisions are made. They
take precedence over roadmap sequencing. If a roadmap item conflicts with these
principles, the roadmap is wrong.

---

## 1. The complete suite principle

**If a capability makes APEX easier, more effective, or more powerful for the
user, it is essential and ships as part of the core product.**

Not as a future release. Not as an optional extra. Not as a premium tier. Not
as a "phase 2." It is part of what APEX should have been from the beginning.

### Why

Withholding obvious capability to release it later is a business tactic, not
engineering. Users recognize it immediately. Receiving something in version 3
that clearly should have existed in version 1 is not delightful; it is
irritating, because the delay was a choice, not a limitation.

APEX rejects that model. The user gets the whole thing.

### What this forbids

- Splitting an essential workflow across releases to manufacture momentum
- Shipping a capability in the engine but exposing it in only one interface
- Marking obvious user needs as "roadmap" when the real reason is effort
- Using "optional" to describe something a reasonable user would always want
- Presenting an unfinished essential as a planned future improvement

### What this requires

- Ship the full workflow, not the minimum demonstrable slice
- Expose every capability in every interface where it belongs
- State plainly and specifically when something genuinely cannot ship yet

---

## 2. Self-sufficiency over prerequisites

**APEX does the work itself wherever it can.**

A user should not have to install, configure, or wire up third-party tooling to
get core value. When APEX can implement a capability natively, it does.

External tools have exactly three legitimate roles:

1. **Cross-check** — an independent oracle to validate APEX's own output
2. **Accelerator** — better quality or speed than the native path, when present
3. **Irreducible dependency** — genuinely infeasible to reimplement correctly

A capability may never be *unavailable* solely because an external tool is
absent. If the tool is missing, APEX still produces the answer through its own
implementation, and records which engine produced it.

Handling a missing dependency without crashing is baseline correctness. It is
not a feature, and it does not excuse a hollow capability.

---

## 3. Interface parity

Every capability that exists in the engine is reachable from:

- the CLI, with stable JSON output
- the local web UI, when it has a visual dimension
- the Python API

A feature that exists only in one surface is unfinished.

---

## 4. Truthful reporting

- Every derived result records which engine produced it
- Unavailable data says why, specifically
- Static findings are evidence, never a verdict
- A cryptographically valid signature proves integrity relative to its signer,
  never publisher trustworthiness
- No claim ships without a test or measurement behind it

---

## 5. Privacy is structural

- Local-first by default
- No telemetry
- No network requirement for core analysis
- Device access is explicit, user-initiated, and scoped
- Sensitive inventory data stays on the user's machine

---

## 6. Power without friction

The complete depth of the tool is available, and the common path is fast:

- Full workflows work end to end, not only the happy path
- Fast operations stay fast enough for continuous use
- Deep analysis is available on demand without reconfiguration
- Automation surfaces are stable and machine-readable

---

## Applying these principles to scope

Before declaring any work complete, verify:

| Check | Required outcome |
|---|---|
| Does the user have to install something APEX could do itself? | Build it in |
| Is any advertised capability only partially usable? | Finish it |
| Is anything deferred only because it was more work? | Pull it forward |
| Would a reasonable user assume this already exists? | It must exist |
| Does the engine support something a UI or CLI does not expose? | Expose it |
| Is a real blocker preventing delivery? | State it plainly and specifically |

Genuinely future work is limited to capability requiring new research, new
hardware, or demonstrated new user demand — never parts of the current promise.

---

## 7. End-to-end wiring

**A capability in only one layer is a stub, not a shipped feature.**

Every user-facing capability must be wired through the full stack:

```text
User → CLI / web / API → services → domain logic → persistence / providers →
response → presentation → tests → docs
```

Rules:

- No orphan modules that nothing imports or calls
- CLI and web share the same service layer — no duplicated business logic
- API endpoints return real data, never mocks or permanent stub responses
- Errors propagate with actionable messages at every layer
- At least one test exercises the same path a user would take

See the global skill `finished-product-delivery` in
`.cursor/skills/finished-product-delivery/SKILL.md`.

---

## 8. Marketplace-ready release

**What we describe is what we ship.**

APEX is built to compete on merit in public. That means:

- README, help text, and UI copy match actual behavior
- A new user can install and complete the primary workflow from published steps
- No demo/mock data in production code paths
- UI is polished: no truncated hashes, broken layout, or unexplained empty panels
- Security findings are evidence-based; signing claims state what crypto proves
- Third-party licenses and bundled data provenance are documented
- Known limitations are stated plainly — never hidden behind vague future promises

Before declaring a release ready, run the checklist in
`finished-product-delivery` (`.cursor/skills/finished-product-delivery/SKILL.md`).

### The finished-product test

Imagine listing APEX on a marketplace next to the category leader. A reviewer
must be able to complete every advertised workflow in the first session without
undocumented setup, insider knowledge, or "install X yourself" steps for core
value.

You cannot sell a hamburger with only the bun. Ship the patty, condiments, and
the standards that make it safe to eat.

---

## 9. GitHub CI validation

**Local green is a pre-check, not proof.**

GitHub Actions may use different paths (venv, `maturin develop`, runner image).
Before declaring a slice complete or telling users CI passed:

1. Run `scripts/validate_slice.sh` (mirrors `.github/workflows/ci.yml`).
2. Push to the feature/PR branch.
3. Wait for workflow `CI` to finish.
4. Confirm `conclusion: success` on the `HEAD` commit (`scripts/check_github_ci.sh` or GitHub UI).
5. Before telling users to install a mobile APK: `scripts/check_github_ci.sh --apk` must pass (CI + **Android standalone APK** green on `HEAD`).

Never claim validation complete on failed or in-progress CI runs.
Never hand users an APK link or “download this” instructions unless step 5 passed for that commit.

Salami cycle:

```text
Slice → Implement → validate_slice.sh → Push → GitHub CI green → PROJECT_STATE.md → Commit message
```

