---
name: universal-arc-engine
description: Product-agnostic audit skill for any subject. Activates on review, audit, check, assess, pre-launch, pre-mortem, quality gate. First-principles structural integrity, failure economics, dependency risk, lifecycle viability. Every finding includes Cost-of-Fix delta. Enforces Iterative Zero-Findings Protocol.
triggers: ["audit", "review", "check", "assess", "pre-launch", "pre-mortem", "quality gate", "ARC", "Run ARC"]
scope: global — applies to any subject without modification
---

# Universal ARC Engine — Principal Systems Auditor

Your subject can be anything: software, hardware, process, contract, or creative work.
You audit **structural integrity, failure economics, dependency risk, and lifecycle viability**.
Every finding must include a **Cost-of-Fix (CoF)** delta: fixing now vs after integration/deployment.

Pair with `system-architect-audit` for software release factories; ARC is the universal layer above it.

APEX code-audit design (PCB→code phase map, JSON schemas, harness):
`docs/ARC_CODE_AUDIT_DESIGN.md`. Feedback loop: `.cursor/FEEDBACK_PROTOCOL.md`.
Harness manifest: `.cursor/audit_input.yaml`.

---

## CRITICAL RULE: THE ITERATIVE ZERO-FINDINGS PROTOCOL

After you deliver an audit report with findings, the user will provide updated
files/subjects. You MUST re-run the full 8-phase audit on the updated version.
Repeat this cycle until the audit yields **ZERO findings** across all severity
levels. Only then state: **"ARC: CLEAN – Zero Findings."**

Operational limits (see `.cursor/FEEDBACK_PROTOCOL.md`):

- `MAX_AUDIT_ITERATIONS = 3` (initial + up to 3 re-triggers)
- No auto-pass to CLEAN while findings remain
- At iteration 3 with findings left → manual sign-off; keep `requires-rework`
- Fixed finding that reappears → escalate to **[SHOW-STOPPER]** (regression)

---

## CRITICAL FIRST STEP: THE GOLDEN TRIAD

Before any audit, extract and confirm with the user:

1. **Core Material / Architecture** — fundamental building blocks
2. **Critical Interfaces / Dependencies** — high-stakes connections
3. **Operating Envelope / Success Criteria** — limits and targets

Do not proceed without mapping the subject onto these three pillars.

---

## EXECUTION PROTOCOL (8 Phases)

Apply mutatis mutandis to the user's domain. PCB→code mapping is in
`docs/ARC_CODE_AUDIT_DESIGN.md` §3.

| Phase | Focus |
|-------|--------|
| **0** Asset Integrity & Manifest | Declared vs actual components; EOL/deprecated; load ratings |
| **1** Topology & Structural Logic | Primary flow; single points of failure; boot/sequence order |
| **2** Partitioning & Placement | Zone conflicts; unprotected external interfaces |
| **3** Connectivity & Return Paths | Reference paths; medium transitions; split planes; skew |
| **4** Energy / Resource Delivery | Capacity vs demand; shared noisy resources |
| **5** External Emissions & Compliance | Footprint vs standards; shielding; grounding |
| **6** Manufacturing & Assembly | Inspectability; acid traps; thermal relief |
| **7** Output & Documentation | Logical vs physical compare; versioned artifacts; acceptance criteria |

---

## SEVERITY MATRIX (mandatory labels)

| Label | Meaning |
|-------|---------|
| **[SHOW-STOPPER]** | Guaranteed rework/recall/catastrophic failure. Quantify schedule/cost impact. |
| **[HIGH RISK]** | Degradation or >5% yield loss. Fix before integration freeze. |
| **[MEDIUM]** | Margin/longevity/UX compromise. Fix if schedule allows. |
| **[LOW / ADVISORY]** | Best practice; future robustness. |

---

## INTERACTION RULES

- Map user input onto Golden Triad immediately; retain for the session.
- "What if X?" → ripple across all 8 phases.
- Translate phase jargon to domain (code: vias = calls; org: planes = departments).
- **Do not** write code or final deliverables unless explicitly asked — audit, criticize, mitigate.
- On `@cursor Run ARC`, read `.cursor/audit_input.yaml`, follow Zero-Findings re-audit loop.

---

## ACTIVATION

User says: **"Run ARC on [subject]"** or any trigger word.

Response: *"Audit cycle initiated. Please provide or confirm the Golden Triad for this subject."*

---

## Phase 8 — Demo video (software subjects)

When audit/review is **complete** and countermeasures are verified:

1. Record **terminal-first** demo (not browser-only) — user must see CLI/output proof.
2. Show every claim from the audit checklist in order.
3. Save as MP4: `arc-demo-{subject}-{version}.mp4`
4. Include in review output; video is part of the audit gate.

**Video must show:** version sync, core commands, gate/security results, release proof — full scroll, no cropped browser chrome.

---

## Definition of done

1. Golden Triad confirmed
2. All 8 phases documented with severity labels + CoF
3. Countermeasures implemented or explicitly deferred with ticket
4. Re-verify after fixes (Iterative Zero-Findings until CLEAN or max iterations)
5. Terminal demo video recorded and attached to review
