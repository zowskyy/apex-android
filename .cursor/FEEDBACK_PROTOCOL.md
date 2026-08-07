# Iterative Zero‑Findings Protocol

**Hard limit:** `MAX_AUDIT_ITERATIONS = 3` re-audit cycles per PR (initial audit + up to 3 re-triggers). There is no auto-pass to **ARC: CLEAN** when findings remain — only when the remaining list is empty, or after the limit when human sign-off is required (see step 7).

Canonical design + JSON schemas: [`docs/ARC_CODE_AUDIT_DESIGN.md`](../docs/ARC_CODE_AUDIT_DESIGN.md).

After the first audit report is posted:

1. Wait for user to push new commits addressing findings.
2. On re-trigger (new PR comment `@cursor Run ARC` or push):
   - Read previous `/tmp/findings.json` (save copy to `/tmp/findings_previous.json` before re-audit).
   - Re-run ONLY the phases that had findings (plus regression scan against history).
   - Re-check each specific location (file:line, workflow job, lockfile entry).
   - Increment iteration counter (track in PR comment or `AUDIT_HISTORY.json` length).
3. Generate incremental report with:
   - **Resolved**: list of fixed items.
   - **Remaining**: still‑unresolved.
   - **New**: newly introduced issues.
4. Post incremental report.
5. Exit condition: when remaining list is empty, comment:
   "ARC: CLEAN – Zero Findings. All compliance checks passed."
6. Remove `requires-rework` label automatically when clean.
7. **Max iterations:** If iteration count reaches **3** and findings remain, do **not** declare CLEAN or remove `requires-rework`. Post:
   "ARC: MAX ITERATIONS (3) reached — manual sign-off required before merge."
   Keep `requires-rework` until a human approves or a new audit cycle starts on a fresh PR.

## JSON shapes (summary)

**Finding** (`/tmp/findings.json` array element):

```json
{
  "id": "PHASE-X-YY",
  "severity": "[SHOW-STOPPER]|[HIGH RISK]|[MEDIUM]|[LOW / ADVISORY]",
  "location": "path or symbol",
  "text": "what is wrong",
  "fix": "suggested remediation"
}
```

**Suggested fix** (optional sidecar `/tmp/suggested_fixes.json`):

```json
{
  "finding_id": "PHASE-X-YY",
  "summary": "short fix title",
  "patch_hints": ["…"],
  "acceptance": ["…"]
}
```

**Re-audit trigger** (`/tmp/re_audit_trigger.json`):

```json
{
  "schema_version": 1,
  "trigger": "pr_comment",
  "phrase": "@cursor Run ARC",
  "iteration": 1,
  "max_iterations": 3,
  "phases_to_rerun": [0, 1],
  "previous_findings_path": "/tmp/findings_previous.json"
}
```
