# APEX Compliance & Audit Trail

## Audit log

- Module: `apex/gate/audit_log.py`
- Path: `~/.apex/audit/gate_runs.jsonl` (override: `APEX_AUDIT_DIR`)
- Integrity: hash-chained entries; `verify_integrity()` before reports
- Rotation: `AuditLogger().rotate_logs(keep_days=30)`

Every `run_hard_gate()` call records an append-only entry (skip with `APEX_SKIP_AUDIT_LOG=1`).

## Compliance reports

- Module: `apex/gate/compliance_report.py`
- Output: `~/.apex/audit/compliance/compliance-YYYY-MM.json`
- Optional HMAC attestation when `APEX_AUDIT_KEY` or `APEX_COMPLIANCE_KEY` is set

```python
from apex.gate.compliance_report import generate_compliance_report
report = generate_compliance_report()
```

## KPIs (monthly targets)

| KPI | Target |
|-----|--------|
| Gate failure rate | &lt; 2% |
| MTTR | &lt; 24 hours |
| Unsigned releases | 0 (when GPG secrets configured) |
| Audit integrity | 100% |

## S3 archival (planned)

Monthly reports intended for 90-day S3 retention with server-side encryption — configure in your AWS account (not automated in v0.4.11 OSS repo).
