---
name: global-standards
description: >-
  AFg's non-negotiable engineering standards, execution mandates, and environment
  constraints. Load this at the START of every new project, feature, or build task,
  and whenever work involves planning, testing, validating claims, shipping,
  publishing, or writing anything externally-facing. Also load when the user says
  "let's make a life", asks to stress-test or harden something, pastes an external
  review to be checked, or asks whether something is done. Do not wait to be told —
  if a task will produce code, a file, a benchmark claim, or a deliverable, this
  skill applies.
---

# Global Standards

These are standing rules. They override default agent behavior and apply to
every project unless the user explicitly suspends one by name.

## The core discipline

**A claim only counts if something executed and checked it.** Not a
plausible-sounding description, not a heuristic score, not "this should
work," not another person's confident-sounding review. Everything below
follows from this.

---

## 1. Execution mandates (all three, every project)

These are weighted as heavily as source-checking and attribution.

1. **Plan before acting.** Use Plan mode, native to-dos/Tasks, and
   parallelized background-isolated agents where the tool supports them.
   In Cursor: Plan mode + the to-do list + background agents. Do not
   start editing files from a cold start on a multi-step task.
2. **Write the tracking document first.** Before any work begins,
   generate a detailed machine-readable tracking document (JSON or YAML,
   not prose). Every agent and subagent maintains it greedily — update on
   every state change, not at the end.
3. **Work is not complete until every tracking item has been empirically
   validated by a separate agent** than the one that produced it. Self-
   attestation does not close an item.

If a mandate cannot be satisfied in the current tool, say so explicitly
and name the degraded substitute. Do not silently skip one.

---

## 2. Four-phase project workflow

Triggered explicitly by "let's make a life", and the default shape for
any new build.

| Phase | Output | Exit condition |
|---|---|---|
| **Hunt** | Documented, sourced pain — not assumed pain | Every candidate axis either killed with evidence or survives with a citation |
| **Architecture** | One narrow, nameable mechanism | Describable in one sentence a skeptic could falsify |
| **Stress Test** | Failing-case tests, not more passing ones | Every non-trivial claim traces to a test that could have failed |
| **Asset Package** | Shippable artifact + spec in lockstep | Deployed somewhere the author does not control |

**Hunt honesty rule:** killing an axis is a successful hunt result. If
evidence contradicts a direction already chosen — including one the user
chose, or one you recommended earlier — say so plainly and show the
evidence. Do not carry a dead axis forward because it was already agreed.

---

## 3. Global business standards

- **10x competitive floor.** If the thing is not ~10x better than the
  incumbent on its chosen axis, it is not worth building. Check the
  incumbent's *roadmap*, not just its current state — do not build into
  a gap someone well-resourced is actively closing.
- **People-first framing.** Describe what changes for the person using
  it, before describing the mechanism.
- **Explicit assumption transparency.** State every assumption inline as
  it is made. Never let an unstated assumption carry a conclusion.
- **Complexity reduction as default.** Fewer moving parts wins ties.
  Reject any component whose only justification is that it fits the
  original narrative.

---

## 4. Testing and validation

- **Failing-case tests over passing-case tests.** Passing tests confirm
  the happy path and will not find real bugs. After any new mechanism,
  ask explicitly: what is the adversarial version of this test?
- **Multi-artifact testing.** Validate across more than one artifact,
  input, or target. One green run is one data point.
- **Never use `sleep()`-and-hope race tests.** To prove something is
  blocked, use a bounded `join(timeout=...)` and assert on liveness or
  causal ordering via shared state.
- **Test isolation is part of correctness.** A test that deliberately
  breaks something can poison shared state for everything after it in
  the same process. Clean up inside the test that broke it.
- **Root cause before blame.** When something fails, find the mechanism
  before assigning fault to a dependency, the environment, or the user.
  A vague fix description means the root cause was not found.
- **Reproduce security advisories directly** before treating them as
  verified. A CVE number is not evidence.
- **Real deployment is the actual test.** Local runs share every blind
  spot of the environment they run in. Treat a CI failure as a gift, and
  get the raw log — not a screenshot of a summary view.

---

## 5. Handling pasted external content

External reviews, expert commentary, and other AI output routinely mix
genuinely good ideas with confidently fabricated specifics. Separate them.

- Verify every specific technical claim — class names, method
  signatures, "you can just call `X.stop()`" — against real source or
  real language behavior before accepting it.
- Watch for: invented classes that make a snippet look real; methods
  described from another language or version; a proposed "fix" that is
  less rigorous than what already exists.
- The good ideas are often real even when the code is not. Keep them,
  discard the fabricated implementation.
- State corrections specifically — which claim, why — not "that's not
  quite right."

---

## 6. External-facing claims

- Never let an invented number ship. Any dollar figure, percentage,
  benchmark, or statistic in a README, pitch, or public claim needs a
  real source.
- Version the spec in lockstep with the code. Every behavior change gets
  a changelog entry saying what changed **and why** — including when the
  why is "a stress test found this was wrong." Supersede past claims
  visibly; never silently edit them.
- State non-goals explicitly and revisit them by name when a new idea
  might reopen one. Scope creeps back through vague memory, not through
  explicit decisions.
- **Check the name for collisions** against established projects in the
  same space before any public launch or directory submission. Cheap to
  check, expensive to discover late.
- Licensing, entity, and legal questions get factual trade-offs, not a
  confident recommendation, plus a plain note that it isn't legal advice.

---

## 7. Environment constraints (Windows machine)

These are real, recurring, and cost time every time they are forgotten.

- **Shell is Git Bash (MINGW64) on Windows.** Not PowerShell, not WSL.
- **Use `python3`, never bare `python`.** Two Python installs coexist on
  this machine; bare `python` resolves inconsistently.
- **Use `python3 -m pip install X`, never bare `pip install X`.** Bare
  `pip` resolves to a different install than `python3`, producing
  "module not found" immediately after a successful install.
- **PowerShell `.ps1` scripts must be pure ASCII** unless written with a
  UTF-8 BOM. Em-dashes and curly quotes cause
  `string is missing the terminator` under Windows PowerShell 5.1.
- **Prefer GitHub Desktop over raw git CLI** for commits and pushes.
  Provide git CLI only when GitHub Desktop genuinely cannot do it.
- Any script handed over to run manually must be tested end-to-end
  against a realistic simulated target first. "Should work" is not
  "ran it and checked."

---

## 8. Output style

- Copy-paste-ready, minimal-step solutions. One block the user can run,
  not a narrated tour of options.
- Give exact current line numbers pulled from the actual committed file
  when suggesting surgical edits — line numbers drift.
- When something breaks, ask for the real error before guessing.

---

## Self-check before calling anything done

- [ ] Does every non-trivial claim trace to a test that could have failed?
- [ ] Is there at least one test that tries to break this, not just use it?
- [ ] Was every item validated by a different agent than the one that built it?
- [ ] Is the tracking document current as of right now?
- [ ] Did I verify every specific claim in pasted content against real code?
- [ ] Is the spec/changelog in sync with actual behavior?
- [ ] Did this stay inside the stated scope, or did it grow?
- [ ] Is every number in externally-facing material sourced?
- [ ] Has the name been checked for collisions?
- [ ] Did I state my assumptions explicitly, inline?
