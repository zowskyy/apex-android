CREATE TABLE IF NOT EXISTS devices (
  id INTEGER PRIMARY KEY,
  serial TEXT NOT NULL UNIQUE,
  model TEXT,
  sdk INTEGER,
  last_seen_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY,
  device_id INTEGER NOT NULL REFERENCES devices(id),
  user_id INTEGER NOT NULL,
  started_at INTEGER NOT NULL,
  finished_at INTEGER,
  status TEXT NOT NULL,
  error_json TEXT
);

CREATE TABLE IF NOT EXISTS package_snapshots (
  id INTEGER PRIMARY KEY,
  sync_run_id INTEGER NOT NULL REFERENCES sync_runs(id),
  package_name TEXT NOT NULL,
  version_code INTEGER,
  version_name TEXT,
  quick_fingerprint TEXT NOT NULL,
  artifact_sha256 TEXT,
  report_path TEXT,
  UNIQUE(sync_run_id, package_name)
);

CREATE TABLE IF NOT EXISTS artifacts (
  sha256 TEXT PRIMARY KEY,
  size_bytes INTEGER NOT NULL,
  local_path TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
