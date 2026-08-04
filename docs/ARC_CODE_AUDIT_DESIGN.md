# ARC Code Audit Design — APEX

**Status:** Design (adapted from Universal ARC Engine PCB SOP)  
**Sources:** `.cursor/skills/universal-arc-engine/SKILL.md` (repo),
`zowskyy/bookish-bassoon` ARC PCB package (`SKILL.md`, `FEEDBACK_PROTOCOL.md`,
`audit_input.yaml`, `PCB_AUDIT_SOP.md`, `PHASE7_INTEGRATION.md`)  
**Applies to:** Software / APEX repository audits (`@cursor Run ARC`)

---

## 1. Iterative Zero-Findings Protocol

Copied from the ARC skill **CRITICAL RULE** (PCB package) and retained for
code audits:

> After you deliver an audit report with findings, the user will provide
> updated files/subjects. You MUST re-run the full 8-phase audit on the
> updated version. Repeat this cycle until the audit yields **ZERO findings**
> across all severity levels. Only then state:
> **"ARC: CLEAN – Zero Findings."**

### Operational rules (from `FEEDBACK_PROTOCOL.md`)

| Rule | Value |
|------|-------|
| Hard limit | `MAX_AUDIT_ITERATIONS = 3` (initial audit + up to 3 re-triggers) |
| Auto-pass | **Never** declare CLEAN while findings remain |
| After limit | Manual sign-off required; keep `requires-rework` |
| Regression | Fixed finding that reappears → escalate to **[SHOW-STOPPER]** |

### Cycle

```text
Golden Triad confirm
    → 8-phase audit → findings.json + report
    → fixes landed (push / PR)
    → re-audit (phases that had findings + regression check)
    → Resolved / Remaining / New
    → repeat until Remaining = []  OR  iteration == 3 (manual sign-off)
```

Clean exit comment:

```text
ARC: CLEAN – Zero Findings. All compliance checks passed.
```

Max-iteration exit:

```text
ARC: MAX ITERATIONS (3) reached — manual sign-off required before merge.
```

---

## 2. Golden Triad (code translation)

| Pillar | PCB | APEX / code |
|--------|-----|-------------|
| **Core Material** | Stackup, layers, copper, impedance | `apex/` + Rust `core/*` + Chaquopy Android + packaging (`pyproject.toml`, wheels) |
| **Critical Interfaces** | DDR/PCIe/USB, clocks, power, AFE | CLI / Web / MCP · `release.yml` DAG · gate scanners · Chaquopy pip · GitHub Releases |
| **Operating Envelope** | Temp, rise-time, EMC class | Version (e.g. v0.4.11) · gate candidate ≥60 · APK+AAB+desktop · audit trail · MTTR &lt;24h |

Do not start Phase 0 until the triad is confirmed for the subject under audit.

---

## 3. Eight-phase map (PCB → code audit)

Severity labels are **unchanged** from the ARC matrix (see §4).

| Phase | PCB focus | Code-audit focus (APEX) |
|-------|-----------|-------------------------|
| **0** Asset Integrity & Manifest | BOM vs schematic; NRND/EOL; derating | Declared vs actual modules/deps; lockfiles vs installs; EOL/deprecated APIs; version sync (`pyproject` / `version.py` / Gradle) |
| **1** Topology & Structural Logic | Power rails; clock topology; sequencing | Primary data/control flow; SPOFs in CI/release DAG; boot/install order (`build.sh`, maturin, Chaquopy) |
| **2** Partitioning & Placement | Digital/analog zones; ESD near connectors | Trust zones (loopback vs LAN); edition gates; unprotected external surfaces (MCP, upload paths) |
| **3** Connectivity & Return Paths | Reference planes; stitching; skew | Call/return paths; schema/API contracts; error propagation; path containment (ZIP/workspace) |
| **4** Energy / Resource Delivery | PDN caps/vias; PLL isolation | CPU/RAM/time budgets (gate scanners); CI minutes; shared noisy resources (runners, OSV API) |
| **5** External Emissions & Compliance | EMC loops; chassis bonding | SBOM / pip-audit / supply-chain; license/NOTICE; Acceptable Use; static-scan disclaimers |
| **6** Manufacturing & Assembly | DFM pads/fiducials; paste/drill | Reproducible builds; Docker digest; `--locked`; inspectability of scripts/workflows; acid-trap configs |
| **7** Output & Documentation | Netlist compare; fab notes | Docs vs reality; CHANGELOG; gate.json / Releases / SHA256SUMS; acceptance criteria; terminal demo |

Phase 8 (software subjects, from repo skill): terminal-first demo video after
countermeasures are verified — part of the audit gate, not a PCB fab step.

---

## 4. Severity matrix (as-is)

| Label | Meaning |
|-------|---------|
| **[SHOW-STOPPER]** | Guaranteed rework / recall / catastrophic failure. Quantify schedule/cost impact. |
| **[HIGH RISK]** | Degradation or &gt;5% yield loss. Fix before integration freeze. |
| **[MEDIUM]** | Margin / longevity / UX compromise. Fix if schedule allows. |
| **[LOW / ADVISORY]** | Best practice; future robustness. |

Every finding includes a **Cost-of-Fix (CoF)** delta: fix now vs after
integration/deployment (PCB skill uses “Fix now: $X vs Fix later: $10X”;
code audits may use engineer-hours or release-slip days).

---

## 5. Feedback schema (JSON)

Canonical protocol: [`.cursor/FEEDBACK_PROTOCOL.md`](../.cursor/FEEDBACK_PROTOCOL.md).  
Harness paths: `/tmp/findings.json`, `/tmp/findings_previous.json`, repo
`AUDIT_HISTORY.json`.

### 5.1 Finding

```json
{
  "id": "PHASE-3-01",
  "phase": 3,
  "severity": "[HIGH RISK]",
  "location": "apex/web.py:serve upload handler",
  "text": "Upload path joins user-controlled name without workspace containment check.",
  "cof": {
    "fix_now": "2h path normalize + test",
    "fix_later": "1d incident + CVE advisory + release yank"
  },
  "evidence": ["tests/test_web_security.py missing case for ../"],
  "status": "open"
}
```

`status`: `open` | `resolved` | `deferred` | `regression`

### 5.2 Suggested fix

```json
{
  "finding_id": "PHASE-3-01",
  "summary": "Contain upload destinations under workspace root",
  "patch_hints": [
    "Reuse workspace path helpers from gate/security path containment",
    "Add pytest case for traversal and absolute paths"
  ],
  "acceptance": [
    "pytest tests/test_web_security.py -q passes",
    "Re-audit Phase 3 clears PHASE-3-01"
  ],
  "owner": "unassigned"
}
```

### 5.3 Findings file (batch)

`/tmp/findings.json` — JSON **array** of finding objects (SOP format also
allows `fix` as a string field on each finding for report generation).

```json
[
  {
    "id": "PHASE-0-02",
    "severity": "[MEDIUM]",
    "location": "requirements.txt",
    "text": "Runtime deps unpinned; Docker/CI may drift.",
    "fix": "Commit requirements.lock and install with -r requirements.lock"
  }
]
```

### 5.4 Re-audit trigger

Posted as PR comment body or written to `/tmp/re_audit_trigger.json`:

```json
{
  "schema_version": 1,
  "trigger": "pr_comment",
  "phrase": "@cursor Run ARC",
  "pr": 13,
  "head_sha": "9dac083fd8f77b226f12e118a0422db84e50697c",
  "iteration": 2,
  "max_iterations": 3,
  "phases_to_rerun": [0, 3, 6],
  "previous_findings_path": "/tmp/findings_previous.json",
  "compare_history": true
}
```

### 5.5 Incremental report payload

```json
{
  "iteration": 2,
  "commit": "…",
  "resolved": ["PHASE-0-02"],
  "remaining": ["PHASE-3-01"],
  "new": [],
  "regressions": [],
  "clean": false,
  "message": null
}
```

When `remaining` and `new` and `regressions` are empty → `clean: true` and
message `"ARC: CLEAN – Zero Findings."`

### 5.6 Audit history entry

Appended to `AUDIT_HISTORY.json` (Phase 7 integration):

```json
{
  "timestamp": "2026-08-04T20:00:00Z",
  "commit": "9dac083",
  "findings_count": 0,
  "severities": {
    "SHOW-STOPPER": 0,
    "HIGH": 0,
    "MEDIUM": 0,
    "LOW": 0
  },
  "iteration": 1,
  "clean": true
}
```

Intermediate history commits may use `[skip ci]` so clean-check workflows do
not loop; the final clean commit that must satisfy branch protection omits
`[skip ci]`.

---

## 6. Test harness configuration (`audit_input.yaml`)

Template: [`.cursor/audit_input.yaml`](../.cursor/audit_input.yaml)  
(adapted from the PCB manifest: schematic/layout/BOM → code artifacts).

| PCB key | Code harness key | Purpose |
|---------|------------------|---------|
| `schematic` | `sources` | Trees to audit |
| `layout` | `workflows` | CI/release topology |
| `bom` | `lockfiles` / `manifests` | Dependency integrity |
| `stackup` | `native` | Rust/Android layers |
| `target_standard` | `target_standard` | Policy bar (e.g. ARC zero-findings) |
| `critical_nets` | `critical_paths` | High-stakes flows |

Harness steps (mirrors PCB SOP):

1. Read `.cursor/audit_input.yaml`
2. Materialize context under `/tmp/apex_arc_context/` (paths, versions, gate weights)
3. Load `.cursor/skills/universal-arc-engine/SKILL.md`
4. Run phases 0–7; write `/tmp/findings.json`
5. Emit `AUDIT_REPORT.md`; post as PR comment
6. On SHOW-STOPPER → label `requires-rework`
7. Re-audit per Zero-Findings protocol until CLEAN or max iterations

---

## 7. Definition of done

1. Golden Triad confirmed for the subject
2. All 8 phases documented with severity labels + CoF
3. Findings / fixes / triggers use the JSON schemas above
4. Countermeasures implemented or explicitly deferred
5. Re-verify after fixes (Zero-Findings loop)
6. Terminal demo when software review is complete (Phase 8)
7. Optional: self-ARC on `.cursor/` audit infrastructure

---

## 8. Related files

| File | Role |
|------|------|
| `.cursor/skills/universal-arc-engine/SKILL.md` | Agent skill (8 phases + severity + Zero-Findings) |
| `.cursor/FEEDBACK_PROTOCOL.md` | Iteration limits + re-audit behavior |
| `.cursor/audit_input.yaml` | Harness manifest for APEX |
| `docs/ARC_REVIEW_APEX_0.4.11.md` | Prior ARC review instance |
| `scripts/arc_demo_terminal.sh` | Terminal-first demo capture |
