# APEX implementation guide

Date: 2026-08-02  
Applies to: APEX v0.3 and later  
Status: execution guide for the audited strategy in
[`COMPETITIVE_STRATEGY.md`](COMPETITIVE_STRATEGY.md)

---

## 1. Purpose

This guide turns the product strategy into an implementation contract. It is
intended to answer, before a slice starts:

- which existing code should change
- which provider owns each capability
- what APEX returns when a provider is absent or fails
- how provenance is represented
- how device data is indexed without weakening privacy
- which automated and optional integration tests close the slice

The governing architectural rule is:

> APEX owns orchestration, normalization, evidence, privacy, and UX. Mature
> Android tools remain the correctness engines until a native replacement has
> demonstrated a measurable advantage on a conformance corpus.

The ordered delivery plan is in [`ROADMAP.md`](ROADMAP.md).

**Agent and contributor standards:** before scoping or shipping work, read
[`PRINCIPLES.md`](PRINCIPLES.md) and apply the global skills in
[`.cursor/skills/`](../.cursor/skills/) — especially `complete-suite-delivery`,
`end-to-end-wiring`, and `marketplace-ready-release`. Do not defer essential
capability, merge unwired modules, or release features that do not match their
public description.

---

## 2. Current baseline

APEX v0.2 is a working local application, not a scaffold.

| Area | Current implementation | Extension seam |
|---|---|---|
| CLI | `apex/cli.py` | add provider selection, tool and device commands |
| Analysis | `apex/analysis.py` | keep Androguard metadata/DEX path; enrich normalized results |
| Workflows | `apex/workflows.py` | extract external-tool logic into provider modules |
| Reports | `analyze_apk()` schema v2 | migrate to schema v3 with operation provenance |
| Decode/build | raw archive backend plus optional apktool | preserve both; move apktool invocation into provider |
| Signing | optional apksigner for signing; Androguard verification summary | add apksigner verification oracle |
| Storage | report-section key/value SQLite/PostgreSQL stores | create a separate normalized corpus store |
| Web UI | loopback `apex/web.py` | consume the same application services as the CLI |
| Native code | Rust ZIP extension; Rust DEX library | keep ZIP on product path; DEX remains validation/R&D |
| Tests | Python workflow/CLI/web tests and Rust unit/integration tests | add contract, golden-output and optional-tool tests |

Do not rewrite the application before adding providers. The existing workflow
functions are the compatibility facade while their internals are migrated.

---

## 3. Target module layout

Add modules by capability; do not reproduce the aspirational directory tree
from the original blueprint.

```text
apex/
├── analysis.py                 # current normalized Python analysis
├── workflows.py                # stable public workflow facade
├── cli.py
├── web.py
├── providers/
│   ├── __init__.py
│   ├── types.py                # common result/provenance/tool contracts
│   ├── runner.py               # bounded subprocess execution
│   ├── registry.py             # provider discovery and fallback ordering
│   ├── androguard.py
│   ├── rust_zip.py
│   ├── jadx.py
│   ├── apktool.py
│   ├── apksigner.py
│   ├── apkanalyzer.py
│   └── bundletool.py
├── device/
│   ├── adb.py
│   ├── models.py
│   ├── pull.py
│   └── sync.py
├── corpus/
│   ├── schema.sql
│   ├── store.py
│   └── stats.py
├── permissions/
│   ├── catalog.py
│   ├── enrich.py
│   └── linkage.py
└── signing/
    ├── normalize.py
    └── display.py
```

Rules:

1. `workflows.py` remains backward compatible while delegating to services.
2. Provider modules normalize tool output; they do not contain UI code.
3. CLI and web handlers call the same workflow/application service.
4. `CorpusStore` is not an extension of the existing key/value `SQLiteStore`.
5. Rust work must not block provider, device, permission, or signing slices.

---

## 4. Provider contract

### 4.1 Capabilities

Use narrow capabilities rather than one universal provider method:

```text
archive.inventory
archive.extract
manifest.decode
resources.summarize
dex.index
decompile.java
decode.resources
build.resources
sign.apk
verify.signatures
bundle.build_apks
bundle.dump_manifest
benchmark.apkanalyzer
```

Initial preference order:

| Capability | Preferred | Fallback |
|---|---|---|
| archive inventory/extract | Rust ZIP | bounded Python ZIP |
| manifest/resources/DEX metadata | Androguard | explicit unavailable/error |
| Java decompile | jadx CLI | Androguard DAD |
| compiled resources decode/build | apktool 3.x | raw backend only for archive-safe operations |
| signature verification | apksigner | Androguard summary |
| AAB/APKS operations | bundletool | existing shallow ZIP inspection where valid |
| official output comparison | apkanalyzer | skipped benchmark, never product failure |

### 4.2 Shared types

Implement Python 3.10-compatible dataclasses and protocols in
`apex/providers/types.py`:

```python
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

T = TypeVar("T")
ProviderStatus = Literal["ok", "fallback", "unavailable", "error"]


@dataclass(frozen=True)
class ProvenanceRecord:
    operation: str
    provider: str
    provider_version: str | None
    status: ProviderStatus
    duration_ms: int | None = None
    fallback_from: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    data: T
    provenance: ProvenanceRecord
```

Do not put raw passwords, keystore secrets, device authorization material, or
unredacted signing commands into provenance. Diagnostic commands, when useful,
must use a redacted argument list.

### 4.3 Provider selection

The registry resolves:

```python
registry.resolve("decompile.java", requested="auto")
registry.resolve("verify.signatures", requested="apksigner")
```

Selection behavior:

- `auto`: try providers in preference order and record fallback.
- explicit provider: fail with an actionable `ApexError` if unavailable.
- benchmark provider: skip with `status=unavailable`; never alter product truth.
- a provider returning invalid application data is not “unavailable”; preserve
  the invalid result and its evidence.

Fallbacks must never be silent. A successful Androguard fallback after jadx
times out records `status=fallback`, `fallback_from=jadx`, and the safe reason.

### 4.4 External process runner

Move `_command_path()` and `_run()` out of `workflows.py` into
`apex/providers/runner.py`.

Required behavior:

- pass an argument list; never use `shell=True`
- configurable timeout per capability
- bounded captured stdout/stderr
- UTF-8 decoding with replacement
- elapsed time and return code
- explicit working directory
- environment allowlist/overlay rather than copying arbitrary secrets
- clear timeout and executable-not-found exceptions
- redaction for password-bearing arguments

Resolution precedence:

1. explicit CLI/configured path
2. capability-specific environment override
3. APEX managed tools directory, if the user explicitly installed tools
4. `PATH`

Core analysis must not make a network request. If managed downloads are added,
they belong behind an explicit `apex tools install` command with pinned
checksums, license notices, atomic writes, and no automatic update.

---

## 5. Provenance and report schema v3

### 5.1 Contract

Migrate `analyze_apk()` from schema v2 to schema v3. Every derived section must
be attributable to one or more operations.

```json
{
  "schema_version": 3,
  "provenance": [
    {
      "operation": "archive.extract",
      "provider": "rust",
      "provider_version": "0.1.0",
      "status": "ok",
      "duration_ms": 18,
      "fallback_from": null,
      "reason": null
    },
    {
      "operation": "dex.index",
      "provider": "androguard",
      "provider_version": "4.1.4",
      "status": "ok",
      "duration_ms": 91,
      "fallback_from": null,
      "reason": null
    }
  ],
  "meta": {},
  "security": {},
  "resources": {},
  "native": {},
  "dex": {},
  "crossrefs": {},
  "reachability": {},
  "bundle": {}
}
```

Use a list, not a provider-keyed object: one report can contain repeated
operations for multiple DEX files or signer blocks.

### 5.2 Outputs covered

The same `ProvenanceRecord` shape must appear in:

- `report.json`
- `decompile-index.json`
- `apex-project.json`
- `verify` JSON
- `security-scan` JSON when a provider contributes evidence
- AAB/APKS operation results
- device sync analysis metadata

HTML should show a compact “Produced by” section rather than dumping raw
commands.

### 5.3 Compatibility

- Existing top-level report fields remain through v0.x.
- Additive readers must tolerate absent provenance from schema v2.
- Store the schema version with corpus analyses.
- Do not rewrite old reports in place.
- Add a fixture for the last supported schema and a migration/reader test.

---

## 6. Tool adapters

### 6.1 jadx

Purpose: preferred readable Java output.

Implementation:

- resolve executable/JAR and probe `--version`
- full export for `apex decompile`
- `--single-class` plus `--single-class-output` for lazy web viewing
- use an isolated temporary/cache directory per operation
- bound execution time and output
- preserve Androguard DAD fallback
- normalize generated paths into the existing decompile index

CLI:

```text
apex decompile app.apk --provider auto
apex decompile app.apk --provider jadx
apex decompile app.apk --provider androguard
```

Acceptance:

- `auto` selects jadx when available.
- The real DEX fixture yields all seven known classes.
- `MainActivity.java` contains `class MainActivity` and `onCreate`.
- forced missing/timeout paths use Androguard only in `auto` mode.
- provenance identifies selected provider and fallback reason.

Do not embed jadx-core in Python during this phase. A subprocess boundary is
simpler to version, isolate, time out, and replace.

### 6.2 apktool 3.x

Purpose: compiled-resource/smali decode and rebuild.

Implementation:

- move `_apktool_command()` and invocation parsing into its provider
- probe and parse version before decode/build
- make 3.x/aapt2-only assumptions explicit
- support executable and JAR overrides
- retain the raw backend for lossless archive workflows
- store provider version and source hash in `apex-project.json`

APEX must not route edited compiled resources through the raw backend.
Unsupported apktool versions return a specific compatibility error and do not
make raw rebuild appear equivalent.

### 6.3 apksigner

Purpose: signing correctness oracle and signing implementation.

Keep signing and verification as separate methods. Verification invokes:

```text
apksigner verify --verbose --print-certs app.apk
```

The parser normalizes:

```json
{
  "status": "valid",
  "schemes": {"v1": true, "v2": true, "v3": false},
  "signers": [
    {
      "index": 1,
      "subject": "...",
      "sha256": "...",
      "sha1": "..."
    }
  ],
  "warnings": []
}
```

Requirements:

- preserve raw tool output in a bounded diagnostic field or sidecar
- golden-output tests for every supported output family
- tolerate additional lines from newer SDK versions
- never turn parser uncertainty into “valid”
- use Androguard only as a clearly labeled fallback summary
- report v4 only when a corresponding `.idsig` context exists
- report certificate lineage/validity as unavailable when the provider cannot
  establish it

No keystore password may appear in logs, reports, provenance, or exceptions.

### 6.4 Android SDK `apkanalyzer`

Purpose: conformance/benchmark oracle for manifest, files, DEX, resources, and
size comparison.

It is not the signing provider and is not required for normal analysis.

Store comparisons under a benchmark namespace:

```json
{
  "benchmarks": {
    "apkanalyzer": {
      "status": "match",
      "provider_version": "...",
      "differences": []
    }
  }
}
```

The adapter must not overwrite APEX output to make a benchmark pass. Differences
are evidence used to fix or document normalization behavior.

### 6.5 bundletool

Purpose: official `.aab` to `.apks` workflows, manifest/resource dumps, and
device-targeted APK generation.

Initial commands:

```text
apex bundle inspect app.aab
apex bundle build-apks app.aab --out app.apks [--device-spec spec.json]
apex bundle extract app.apks --out splits/
```

Requirements:

- record bundletool version and command capability
- do not claim installable universal output when signing/device inputs are
  insufficient
- analyze generated base/split APKs through existing APEX workflows
- preserve the current shallow AAB ZIP inspection as a distinct capability,
  not as a substitute for bundletool

---

## 7. Doctor and tool management

Change `doctor()` from path-or-null output to a normalized status document:

```json
{
  "schema_version": 2,
  "apex": "0.3.0",
  "ready": true,
  "tools": {
    "jadx": {
      "status": "ok",
      "path": "/opt/jadx/bin/jadx",
      "version": "...",
      "source": "path",
      "install_hint": null
    },
    "bundletool": {
      "status": "missing",
      "path": null,
      "version": null,
      "source": null,
      "install_hint": "Install bundletool or set APEX_BUNDLETOOL_JAR"
    }
  },
  "capabilities": {
    "decompile.java": {"status": "ready", "provider": "jadx"},
    "verify.signatures": {"status": "degraded", "provider": "androguard"},
    "bundle.build_apks": {"status": "unavailable", "provider": null}
  }
}
```

`ready` means core APK inspection works. Missing optional providers produce
degraded capabilities, not a false global failure.

Tools to report:

- Java
- jadx
- apktool
- apksigner
- apkanalyzer
- bundletool
- adb
- aapt2
- Androguard
- native ZIP extension

---

## 8. Device and corpus implementation

### 8.1 ADB boundary

All ADB calls go through `apex/device/adb.py`. Every operation takes an
explicit serial after device selection; never rely on an ambiguous default
when multiple devices are connected.

Initial operations:

```python
list_devices() -> list[DeviceInfo]
list_packages(serial: str, user_id: int = 0) -> list[DevicePackage]
package_paths(serial: str, package: str, user_id: int = 0) -> list[str]
pull_package(serial: str, package: str, destination: Path, user_id: int = 0) -> PullResult
package_state(serial: str, package: str, user_id: int = 0) -> PackageState
```

Use:

- `adb devices -l` for connection state
- `cmd package`/`pm` for package and path discovery
- `dumpsys package` only for fields not available through stable package
  commands
- `adb pull` into a temporary directory followed by atomic rename

Validate package names, remote paths, split names, and destination containment.
An offline/unauthorized device is a typed state, not a generic parser failure.

### 8.2 Deterministic pulled layout

```text
~/.apex/devices/<safe-serial>/<user>/<package>/<version>-<sha-prefix>/
├── base.apk
├── splits/
│   ├── config.arm64_v8a.apk
│   └── config.en.apk
└── pull.json
```

`pull.json` records source paths, hashes, device/user, package/version, pull
time, and provenance. Never include authorization keys.

### 8.3 Corpus database

Create a dedicated SQLite database at `~/.apex/corpus.db` by default, overridable
with `--db` or `APEX_CORPUS_DB`.

Minimum normalized model:

```sql
CREATE TABLE devices (
  id INTEGER PRIMARY KEY,
  serial TEXT NOT NULL UNIQUE,
  model TEXT,
  sdk INTEGER,
  last_seen_at INTEGER NOT NULL
);

CREATE TABLE sync_runs (
  id INTEGER PRIMARY KEY,
  device_id INTEGER NOT NULL REFERENCES devices(id),
  user_id INTEGER NOT NULL,
  started_at INTEGER NOT NULL,
  finished_at INTEGER,
  status TEXT NOT NULL,
  error TEXT
);

CREATE TABLE package_snapshots (
  id INTEGER PRIMARY KEY,
  sync_run_id INTEGER NOT NULL REFERENCES sync_runs(id),
  package_name TEXT NOT NULL,
  version_code INTEGER,
  version_name TEXT,
  enabled INTEGER,
  system_app INTEGER,
  quick_fingerprint TEXT,
  UNIQUE(sync_run_id, package_name)
);

CREATE TABLE artifacts (
  sha256 TEXT PRIMARY KEY,
  size_bytes INTEGER NOT NULL,
  local_path TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE snapshot_artifacts (
  snapshot_id INTEGER NOT NULL REFERENCES package_snapshots(id),
  artifact_sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
  split_name TEXT NOT NULL,
  is_base INTEGER NOT NULL,
  PRIMARY KEY(snapshot_id, split_name)
);

CREATE TABLE analyses (
  artifact_sha256 TEXT NOT NULL REFERENCES artifacts(sha256),
  schema_version INTEGER NOT NULL,
  report_path TEXT NOT NULL,
  status TEXT NOT NULL,
  analyzed_at INTEGER NOT NULL,
  PRIMARY KEY(artifact_sha256, schema_version)
);
```

Use SQLite foreign keys, WAL mode, explicit transactions, and migrations.
Store large reports on disk with paths in SQLite; do not duplicate every JSON
blob into the database.

### 8.4 Incremental sync algorithm

1. Select connected device and Android user.
2. Start a `sync_runs` transaction record.
3. List packages and retrieve version/path metadata.
4. Compare a quick fingerprint with the last successful snapshot.
5. Reuse unchanged artifact associations.
6. Pull changed candidates to a temporary directory.
7. Hash locally and deduplicate by SHA-256.
8. Analyze artifacts missing the current report schema.
9. Commit the snapshot and mark the run successful.
10. Preserve a failed run with a bounded error; do not publish partial state as
    the latest successful snapshot.

Version code alone is not a content identity. A `--strict` mode may request a
remote hash when available; it must fall back to pull-and-hash rather than
pretending a remote hash exists on every Android build.

### 8.5 Device CLI

```text
apex device list
apex device packages --serial SERIAL [--user 0]
apex device pull PACKAGE --serial SERIAL [--user 0] --out DIR
apex device sync --serial SERIAL [--user 0] [--db PATH] [--strict]
apex device stats [--serial SERIAL] [--db PATH]
```

Every command emits stable JSON with `--output`; human summary output can be
added without changing the machine-readable schema.

---

## 9. Permission intelligence

### 9.1 Catalog

Generate and commit a deterministic permission catalog from a pinned AOSP
revision. The generation manifest must record:

- AOSP tag/commit
- source files
- generation script version
- license/notice
- Android API coverage

Do not hand-maintain descriptions as the primary source.

Normalized permission:

```json
{
  "name": "android.permission.CAMERA",
  "label": "Camera",
  "description": "...",
  "protection_level": ["dangerous"],
  "flags": [],
  "declared": true,
  "granted": true,
  "grant_source": "adb.dumpsys",
  "catalog_status": "matched"
}
```

OEM/custom permissions remain visible with `catalog_status=unknown`; absence
from AOSP is not a parser error.

### 9.2 Granted state

Granted state exists only with device context. Static APK reports must use
`granted=null` and explain that the value is unavailable.

Maintain versioned `dumpsys package` fixtures from multiple Android versions.
The parser must ignore unknown sections and fail fields independently.

### 9.3 Permission-to-code linkage

Build on existing DEX methods/edges and cross-references:

1. maintain a versioned permission-to-API mapping
2. find sensitive API references
3. link call sites to declared permission
4. show evidence (class, method, referenced API)
5. distinguish “declared”, “API referenced”, and “runtime use proven”

Static linkage is evidence, not proof that a code path executes.

---

## 10. Signing UX

The report/UI presents:

- overall verification status
- schemes established by the provider
- signer certificate subject/issuer when available
- SHA-256 fingerprint (primary)
- SHA-1 fingerprint (compatibility)
- certificate validity when established from certificate data
- rotation/lineage only when established
- warnings and unsupported fields with reasons

Never infer signer trust from “cryptographically valid.” A valid signature
proves APK integrity relative to its signer, not publisher reputation.

Rebuilt APK signing must require explicit key selection. A future convenience
debug key can be opt-in and clearly labeled; APEX must not silently publish a
debug-signed artifact as production-ready.

---

## 11. Web application

Refactor the web handler gradually; do not duplicate analysis logic.

Application services:

```text
AnalysisService
DecompileService
DeviceService
CorpusService
```

Planned API:

```text
GET  /api/health
POST /api/open
POST /api/upload
POST /api/decompile/class
GET  /api/devices
GET  /api/devices/{serial}/packages
POST /api/devices/{serial}/sync
GET  /api/corpus/stats
GET  /api/corpus/packages/{package}
```

Requirements:

- bind to loopback by default
- preserve upload and request-size bounds
- never expose arbitrary file reads through paths returned by jadx/apktool
- validate all device serial/package route values
- keep long provider/device operations out of request threads; return job IDs
- show provider/fallback badges
- show permission/certificate unsupported states explicitly

The Devices tab starts only after the corpus API is stable. The UI is a client
of the same contracts tested through CLI/service tests.

---

## 12. Testing strategy

### 12.1 Test layers

| Layer | Test style | Required evidence |
|---|---|---|
| contracts | unit tests | provider selection, provenance, schema readers |
| tool parsers | golden stdout/stderr fixtures | output normalization across known versions |
| workflows | existing synthetic APK + real DEX fixture | fallback and report behavior |
| optional tools | skip when executable absent | actual jadx/apksigner/apktool/bundletool conformance |
| device | recorded ADB/dumpsys fixtures | deterministic parsers without a live phone |
| live device | explicit `adb` marker | list/pull/sync on user-selected device |
| web | HTTP service tests | same normalized fields as CLI |
| Rust | cargo tests | ZIP safety and DEX validation |

### 12.2 Provider test rules

- Mock process execution only to test failure/timeout/selection paths.
- Parse real captured tool output in golden tests.
- Keep a small, redistributable APK fixture for end-to-end tests.
- Skip optional executable tests with a reason; do not mark missing tools as
  passing conformance.
- Compare normalized semantics, not unstable line ordering.

### 12.3 Slice command bar

```bash
python -m pytest tests/ -v
cargo test --workspace
```

When Rust ZIP code changes:

```bash
cargo clippy -p apex_zip_reader --all-targets -- -D warnings
bash scripts/audit_slice_1_1.sh
```

When an optional provider changes, run its marked integration suite in an
environment where that tool exists and attach the normalized output to the
slice evidence.

### 12.4 Performance

Measure separately:

- fast inspect latency
- full metadata/DEX indexing
- first vs cached single-class decompile
- full Java export
- initial vs incremental device sync
- corpus-only statistics
- peak resident memory for worker processes

Do not reuse the original “10x” claims as acceptance criteria. Record hardware,
fixture hash, provider version, warm/cold state, sample count, median and p95.

---

## 13. Security and privacy requirements

These are release gates, not follow-up cleanup:

- no telemetry by default
- no network needed for core analysis
- explicit user action for device sync
- local corpus database and artifacts
- bounded archives, subprocess output, request bodies and timeouts
- path containment for ZIP, tool output, ADB pulls and exports
- no shell interpolation
- secret redaction in all paths
- evidence-first security findings
- no claim that installed-app inventory is available from a Play companion by
  default
- no execution of analyzed APK code

For wireless ADB, explain pairing and trusted-network implications. Do not
persist a connection or authorization beyond normal ADB behavior without
explicit user control.

---

## 14. Dependency and packaging policy

- Remove `networkx` until a shipped call-graph implementation imports it.
- Treat Androguard transitive packages as implementation details, not direct
  APEX capabilities.
- Add a dependency directly if APEX imports it directly.
- Pin external tool versions in a release manifest, not Python dependencies.
- Record tool license/source/checksum for managed downloads.
- Keep optional tools optional; package installation must retain core inspect
  and Androguard analysis.
- Consolidate the duplicated APEX version source during provider foundation
  work (`setup.py`, CLI, doctor, web server currently drift independently).

---

## 15. Definition of done for every slice

A slice is done only when:

1. its public JSON shape is documented
2. auto, explicit-provider, missing-provider and failure behavior are tested
3. provenance is present
4. existing workflow compatibility is preserved or migration is documented
5. security bounds and secret handling are reviewed
6. default automated tests pass
7. optional conformance evidence is recorded when relevant
8. `doctor()` reflects the capability
9. README/state/roadmap are updated
10. unsupported cases are explicit

The implementation order and release gates are defined in
[`ROADMAP.md`](ROADMAP.md).
