use crate::sanitize::{self, Verdict};

#[derive(Debug, Clone)]
pub struct EntryInfo {
    pub raw_name: String,
    pub sanitized_name: Option<String>,
    pub verdict: &'static str, // "CLEAN" | "WARN"
    pub reason: Option<String>,
    pub compressed_size: u64,
    pub uncompressed_size: u64,
    pub crc32: u32,
    pub extracted: bool,
}

impl EntryInfo {
    /// Build an entry record from a raw name and its declared sizes. This
    /// runs the name through `sanitize::check_name` and additionally flags
    /// entries whose declared uncompressed size exceeds the bounded-
    /// allocation cap (zip-bomb guard), even if the name itself is clean.
    pub fn from_raw(
        raw_name: &str,
        compressed_size: u64,
        uncompressed_size: u64,
        crc32: u32,
    ) -> Self {
        let name_check = sanitize::check_name(raw_name);

        let (verdict, sanitized_name, reason) = match name_check.verdict {
            Verdict::Warn => ("WARN", None, name_check.reason),
            Verdict::Clean if uncompressed_size > sanitize::MAX_ENTRY_UNCOMPRESSED => (
                "WARN",
                None,
                Some(format!(
                    "declared uncompressed size {uncompressed_size} exceeds per-entry cap {}",
                    sanitize::MAX_ENTRY_UNCOMPRESSED
                )),
            ),
            Verdict::Clean => ("CLEAN", name_check.sanitized_name, None),
        };

        Self {
            raw_name: raw_name.to_string(),
            sanitized_name,
            verdict,
            reason,
            compressed_size,
            uncompressed_size,
            crc32,
            extracted: false,
        }
    }
}
