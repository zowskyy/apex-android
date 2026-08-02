---
name: complete-suite-delivery
description: Use when planning, scoping, building, or shipping any application, feature set, or roadmap. Enforces delivering the complete usable suite up front instead of withholding essential capability as future improvements, paid add-ons, or optional extras. Apply to every project.
---

# Complete Suite Delivery

## Core principle

**If a capability makes the product easier, more effective, or more powerful for the user, it is essential and ships now.**

It is not a bonus. It is not a v2 feature. It is not an upsell. It is not a
"nice to have." It is part of what the product should have been from the start.

Users are not impressed when an obvious capability arrives later. They are
irritated, because they can tell it was always obvious. Staged drip-feeding of
core capability reads as manufactured progress, not real improvement.

## The finished-product test (hamburger stand)

Before you ship or declare scope complete, imagine opening a food stand and
advertising a hamburger. A customer who pays for that description expects:

- the bun **and** the patty **and** the condiments
- safe handling, labeling, and standards that match what you promised
- a meal they can actually eat end to end — not a bun with a note that says
  "meat coming in phase 2"

Software is the same. A marketplace listing, README, demo, or roadmap is a
promise. Shipping only part of the promised experience — backend without UI,
engine without CLI, feature without tests, workflow without error handling — is
not a minimum viable product. It is an incomplete product misrepresented as
ready.

**Do not sell the bun and call it a hamburger.**

## Rules

1. **No artificial staging.** Never split an essential capability across
   releases to manufacture a roadmap or the appearance of momentum.
2. **No "graceful degradation" as an excuse.** Handling a missing dependency
   without crashing is correct engineering. Shipping a hollow feature and
   calling the hollowness "degradation" is not.
3. **Build it in, don't require the user to supply it.** If the product can do
   the work itself, it must. Do not offload setup, installation, or
   integration onto the user when the product could handle it.
4. **Completeness over sequencing.** When scoping, ask "what does a user need
   for this to fully work?" and deliver that whole set, not the minimum
   demonstrable slice.
5. **Optional means genuinely optional.** A feature may be optional only if a
   real user would rationally choose not to have it, never because it was
   simply easier to defer.
6. **Roadmaps are for genuinely new frontiers.** Reserve future work for
   capability that requires new research, new hardware, or new user demand,
   not for parts of the current promise.
7. **Say what is missing, plainly.** If something truly cannot ship yet, state
   the real blocker. Never dress an unfinished essential as a future upgrade.
8. **Match the public description.** Everything advertised in docs, UI copy,
   store listings, and demos must work as described on day one.

## When scoping work

Before declaring scope complete, check every item:

- Does the user have to install, configure, or wire something the product
  could have done? → Build it in.
- Is any advertised capability only partially usable? → Finish it.
- Is anything deferred purely because it was more work? → Pull it forward.
- Would a reasonable user assume this already exists? → It must exist.
- Is any interface (CLI, API, UI) missing access to a capability that exists
  underneath? → Expose it everywhere.
- Would a competitor reviewer call this unfinished? → It is unfinished.
- Does the demo only work on a developer machine with secret setup? → Fix it.

## Anti-patterns to reject

| Anti-pattern | Correct behavior |
|---|---|
| "Coming in a future release" for an obvious core need | Ship it now |
| "Install X yourself to enable Y" | Implement Y natively or bundle X |
| "Available in the pro tier" for basic usability | Include it |
| "Phase 2: the actual useful part" | Phase 1 includes the useful part |
| Backend supports it, UI doesn't expose it | Expose in every interface |
| Feature works only if optional tool present | Provide a first-class built-in path |
| README promises a workflow the app cannot complete | Implement the workflow or fix the docs |
| Tests cover only the happy path | Cover real failure and edge paths users hit |

## Delivery standard

Every product surface must be:

- **Whole** — the full workflow works end to end, not just the happy path
- **Self-sufficient** — minimal external prerequisites; the product does the work
- **Consistent** — every capability reachable from every interface it belongs in
- **Efficient** — fast enough to use continuously, not just demo
- **Powerful** — full depth exposed, not a simplified subset
- **Honest** — what you ship matches what you describe

## Related skills

Apply together with:

- `end-to-end-wiring` — every layer connected; no orphan modules
- `marketplace-ready-release` — competitor-grade release checklist
