# APEX documentation index

Start here if you are new to the repo.

| Doc | Audience | Purpose |
|-----|----------|---------|
| [../README.md](../README.md) | Users | Install, CLI, editions |
| [BLUEPRINT_GUIDE.md](BLUEPRINT_GUIDE.md) | Operators | Day-to-day workflows (v0.4.11) |
| [MASTER_NOTES_COPYPASTE.md](MASTER_NOTES_COPYPASTE.md) | Lead engineers | Scratch-to-finish single reference |
| [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) | PM / eng | Phased rollout (Phases 1–4) |
| [RISK_ASSESSMENT.md](RISK_ASSESSMENT.md) | Security | Risk matrix + blast radius |
| [RUNBOOKS.md](RUNBOOKS.md) | On-call | CVE / rollback / version drift |
| [COMPLIANCE.md](COMPLIANCE.md) | Governance | Audit trail + KPIs |
| [SECURITY.md](SECURITY.md) | Security | GPG signing + key rotation |
| [../SECURITY.md](../SECURITY.md) | Security | Vulnerability reporting (GitHub community file) |
| [REPRODUCIBILITY.md](REPRODUCIBILITY.md) | Release eng | Lockfiles, MSRV, Docker digest, SBOM |
| [../CHANGELOG.md](../CHANGELOG.md) | Everyone | Keep a Changelog release notes |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Contributors | Dev loop + PR expectations |
| [../CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) | Everyone | Contributor Covenant 2.1 |
| [AUDIT_RESPONSE_0.4.11.md](AUDIT_RESPONSE_0.4.11.md) | Maintainers | External audit findings + repo response |
| [AUDIT_REVIEW_860ed81.md](AUDIT_REVIEW_860ed81.md) | Maintainers | system-architect-audit review of audit commit |
| [ARC_REVIEW_APEX_0.4.11.md](ARC_REVIEW_APEX_0.4.11.md) | Maintainers | Universal-ARC-Engine 8-phase review |
| [COMPLETION_ROADMAP.md](COMPLETION_ROADMAP.md) | PM / eng | Capability matrix |
| [SLICE_TRUTH.md](SLICE_TRUTH.md) | Eng | Implementation status table |
| [CI_RELEASE_BLUEPRINT.md](CI_RELEASE_BLUEPRINT.md) | Release eng | CI DAG + artifacts |
| [BUILD_STANDALONE_APK.md](BUILD_STANDALONE_APK.md) | Mobile | Phone APK build |
| [HARD_GATE_SLICES.md](HARD_GATE_SLICES.md) | Security | Original gate design |
| [PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md) | Architects | Long-term vision |
| [PRINCIPLES.md](PRINCIPLES.md) | Contributors | Design principles |
| [ACCEPTABLE_USE.md](ACCEPTABLE_USE.md) | Everyone | Legal / ethical use |

**Quick paths**

- Run locally → `BLUEPRINT_GUIDE.md` § Quick start
- Ship a release → `CI_RELEASE_BLUEPRINT.md` + `scripts/release/sync_version.sh`
- Change gate policy → `apex/gate/weights.toml` + `SLICE_TRUTH.md`
