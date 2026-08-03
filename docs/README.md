# APEX documentation index

Start here if you are new to the repo.

| Doc | Audience | Purpose |
|-----|----------|---------|
| [../README.md](../README.md) | Users | Install, CLI, editions |
| [BLUEPRINT_GUIDE.md](BLUEPRINT_GUIDE.md) | Operators | Day-to-day workflows (v0.4.11) |
| [MASTER_NOTES_COPYPASTE.md](MASTER_NOTES_COPYPASTE.md) | Lead engineers | Scratch-to-finish single reference |
| [AUDIT_RESPONSE_0.4.11.md](AUDIT_RESPONSE_0.4.11.md) | Maintainers | External audit findings + repo response |
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
