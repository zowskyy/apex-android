//! Path-traversal and bounded-allocation checks for ZIP/APK entry names.
//!
//! Pure Rust, no PyO3 dependency, so this can be unit-tested and fuzzed in
//! isolation from the Python bridge. This is the direct fix for
//! CVE-2026-39973 (apktool path traversal via crafted entry names) and the
//! bounded-allocation requirement from docs/KNOWLEDGE_BASE.md.

pub const MAX_NAME_LEN: usize = 4096;
pub const MAX_ENTRIES: usize = 200_000;
/// Per-entry uncompressed size cap. Any single file in a real-world APK
/// larger than this is already suspicious; this is the zip-bomb guard.
pub const MAX_ENTRY_UNCOMPRESSED: u64 = 2 * 1024 * 1024 * 1024; // 2 GiB
/// Total uncompressed size cap across the whole archive.
pub const MAX_TOTAL_UNCOMPRESSED: u64 = 8 * 1024 * 1024 * 1024; // 8 GiB

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Verdict {
    Clean,
    Warn,
}

#[derive(Debug, Clone)]
pub struct SanitizeResult {
    pub verdict: Verdict,
    /// Safe, normalized, relative path to use on disk. `None` when the
    /// entry must be refused outright (verdict is always `Warn` in that case).
    pub sanitized_name: Option<String>,
    /// Present when verdict is `Warn`; human-readable reason for the CLI/report.
    pub reason: Option<String>,
}

impl SanitizeResult {
    fn clean(name: String) -> Self {
        Self {
            verdict: Verdict::Clean,
            sanitized_name: Some(name),
            reason: None,
        }
    }

    fn warn(reason: &str) -> Self {
        Self {
            verdict: Verdict::Warn,
            sanitized_name: None,
            reason: Some(reason.to_string()),
        }
    }
}

/// Check a single ZIP entry name. Does not touch the filesystem.
pub fn check_name(raw_name: &str) -> SanitizeResult {
    if raw_name.is_empty() {
        return SanitizeResult::warn("empty entry name");
    }
    if raw_name.len() > MAX_NAME_LEN {
        return SanitizeResult::warn("entry name exceeds max length");
    }
    if raw_name.as_bytes().contains(&0) {
        return SanitizeResult::warn("entry name contains embedded NUL byte");
    }

    // Normalize backslashes: malicious archives built for Windows targets
    // use `\` to smuggle traversal past `/`-only checks.
    let normalized = raw_name.replace('\\', "/");

    // Absolute path: leading slash, or a Windows drive letter / UNC prefix.
    if normalized.starts_with('/') {
        return SanitizeResult::warn("absolute path (leading slash)");
    }
    if normalized.len() >= 2 {
        let bytes = normalized.as_bytes();
        if bytes[1] == b':' && bytes[0].is_ascii_alphabetic() {
            return SanitizeResult::warn("absolute path (drive letter)");
        }
    }

    let mut clean_components: Vec<&str> = Vec::new();
    for component in normalized.split('/') {
        match component {
            "" | "." => continue, // collapse redundant separators / current-dir refs
            ".." => return SanitizeResult::warn("path traversal component ('..')"),
            c => clean_components.push(c),
        }
    }

    if clean_components.is_empty() {
        return SanitizeResult::warn("entry name has no path components after normalization");
    }

    SanitizeResult::clean(clean_components.join("/"))
}

/// Belt-and-suspenders re-check performed at extraction time: join the
/// already-sanitized relative name to the real destination root and verify
/// the lexically-normalized result still starts with that root. The name
/// has already passed `check_name`, so this should never fire in practice —
/// it exists to catch a future bug in `check_name` before it becomes a CVE.
pub fn resolves_within_root(root: &std::path::Path, sanitized_relative: &str) -> bool {
    let joined = root.join(sanitized_relative);
    let root = normalize_lexically(root);
    let joined = normalize_lexically(&joined);
    joined.starts_with(&root)
}

fn normalize_lexically(path: &std::path::Path) -> std::path::PathBuf {
    use std::path::Component;
    let mut out = std::path::PathBuf::new();
    for comp in path.components() {
        match comp {
            Component::CurDir => {}
            Component::ParentDir => {
                out.pop();
            }
            other => out.push(other.as_os_str()),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clean_relative_path_passes() {
        let r = check_name("res/layout/main.xml");
        assert_eq!(r.verdict, Verdict::Clean);
        assert_eq!(r.sanitized_name.unwrap(), "res/layout/main.xml");
    }

    #[test]
    fn cve_2026_39973_traversal_pattern_blocked() {
        // Reconstruction of the apktool CVE-2026-39973 pattern: an entry
        // name using ../ segments to escape the extraction directory.
        let malicious = "../../../../etc/cron.d/malicious";
        let r = check_name(malicious);
        assert_eq!(r.verdict, Verdict::Warn);
        assert!(r.sanitized_name.is_none());
        assert!(r.reason.unwrap().contains("traversal"));
    }

    #[test]
    fn backslash_traversal_blocked() {
        let r = check_name("..\\..\\Windows\\System32\\evil.dll");
        assert_eq!(r.verdict, Verdict::Warn);
    }

    #[test]
    fn absolute_unix_path_blocked() {
        let r = check_name("/etc/passwd");
        assert_eq!(r.verdict, Verdict::Warn);
    }

    #[test]
    fn absolute_windows_path_blocked() {
        let r = check_name("C:\\Windows\\System32\\evil.dll");
        assert_eq!(r.verdict, Verdict::Warn);
    }

    #[test]
    fn embedded_nul_blocked() {
        let r = check_name("res/layout/main.xml\0.png");
        assert_eq!(r.verdict, Verdict::Warn);
    }

    #[test]
    fn oversized_name_blocked() {
        let long_name = "a/".repeat(3000);
        let r = check_name(&long_name);
        assert_eq!(r.verdict, Verdict::Warn);
    }

    #[test]
    fn mixed_traversal_still_caught() {
        // Legit-looking prefix followed by a traversal component.
        let r = check_name("assets/../../secret.key");
        assert_eq!(r.verdict, Verdict::Warn);
    }

    #[test]
    fn resolves_within_root_true_for_clean_name() {
        let root = std::path::Path::new("/tmp/extract");
        assert!(resolves_within_root(root, "res/layout/main.xml"));
    }
}
