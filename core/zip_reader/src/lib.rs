mod entry;
mod error;
mod sanitize;

use std::fs;
use std::io::Read;
use std::path::PathBuf;

use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict};

use entry::EntryInfo;
use error::ApexZipError;

fn entry_to_dict<'py>(py: Python<'py>, info: &EntryInfo) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("name", &info.raw_name)?;
    dict.set_item("sanitized_name", info.sanitized_name.clone())?;
    dict.set_item("verdict", info.verdict)?;
    dict.set_item("reason", info.reason.clone())?;
    dict.set_item("compressed_size", info.compressed_size)?;
    dict.set_item("uncompressed_size", info.uncompressed_size)?;
    dict.set_item("crc32", info.crc32)?;
    dict.set_item("extracted", info.extracted)?;
    Ok(dict)
}

fn open_archive(apk_path: &str) -> Result<zip::ZipArchive<fs::File>, ApexZipError> {
    let file = fs::File::open(apk_path)?;
    let archive = zip::ZipArchive::new(file)?;
    if archive.len() > sanitize::MAX_ENTRIES {
        return Err(ApexZipError::Bounds(format!(
            "archive has {} entries, exceeds max {}",
            archive.len(),
            sanitize::MAX_ENTRIES
        )));
    }
    Ok(archive)
}

/// List every entry in a ZIP/APK with a CLEAN/WARN verdict per entry.
/// Never writes to disk. Bounded allocation: refuses archives with more
/// than `sanitize::MAX_ENTRIES` entries before iterating.
#[pyfunction]
fn read_entries(py: Python<'_>, apk_path: &str) -> PyResult<Vec<Py<PyAny>>> {
    let mut archive = open_archive(apk_path).map_err(PyErr::from)?;
    let mut results = Vec::with_capacity(archive.len());
    let mut running_total: u64 = 0;
    let mut cap_breached = false;

    for i in 0..archive.len() {
        let zfile = archive
            .by_index_raw(i)
            .map_err(ApexZipError::from)
            .map_err(PyErr::from)?;
        let raw_name = zfile.name().to_string();
        let mut info = EntryInfo::from_raw(
            &raw_name,
            zfile.compressed_size(),
            zfile.size(),
            zfile.crc32(),
        );

        if info.verdict == "CLEAN" {
            running_total = running_total.saturating_add(zfile.size());
            if running_total > sanitize::MAX_TOTAL_UNCOMPRESSED {
                cap_breached = true;
            }
            if cap_breached {
                info.verdict = "WARN";
                info.sanitized_name = None;
                info.reason = Some("cumulative uncompressed size exceeds archive cap".to_string());
            }
        }

        results.push(entry_to_dict(py, &info)?.into_any().unbind());
    }

    Ok(results)
}

/// Extract a ZIP/APK to `dest_dir`, sanitizing every entry name and
/// refusing (not extracting, not renaming) any entry that fails
/// path-traversal, absolute-path, or size-bound checks. Returns a report
/// dict: {"extracted": int, "warned": int, "entries": [...]}.
///
/// This is the direct replacement for `zipfile.extractall()` in
/// apex/__init__.py's `extract_apk()`.
#[pyfunction]
fn extract_apk(py: Python<'_>, apk_path: &str, dest_dir: &str) -> PyResult<Py<PyAny>> {
    let mut archive = open_archive(apk_path).map_err(PyErr::from)?;
    let dest_root = PathBuf::from(dest_dir);
    fs::create_dir_all(&dest_root).map_err(ApexZipError::from).map_err(PyErr::from)?;

    let mut entries = Vec::with_capacity(archive.len());
    let mut running_total: u64 = 0;
    let mut cap_breached = false;
    let mut extracted_count: u64 = 0;
    let mut warned_count: u64 = 0;

    for i in 0..archive.len() {
        let mut zfile = archive
            .by_index(i)
            .map_err(ApexZipError::from)
            .map_err(PyErr::from)?;
        let raw_name = zfile.name().to_string();
        let is_dir = zfile.is_dir();
        let mut info = EntryInfo::from_raw(
            &raw_name,
            zfile.compressed_size(),
            zfile.size(),
            zfile.crc32(),
        );

        if info.verdict == "CLEAN" {
            running_total = running_total.saturating_add(zfile.size());
            if running_total > sanitize::MAX_TOTAL_UNCOMPRESSED {
                cap_breached = true;
            }
            if cap_breached {
                info.verdict = "WARN";
                info.sanitized_name = None;
                info.reason = Some("cumulative uncompressed size exceeds archive cap".to_string());
            }
        }

        if info.verdict == "CLEAN" {
            let rel = info.sanitized_name.clone().unwrap();
            if !sanitize::resolves_within_root(&dest_root, &rel) {
                info.verdict = "WARN";
                info.reason = Some("resolved path escapes destination root".to_string());
            }
        }

        if info.verdict == "CLEAN" {
            let rel = info.sanitized_name.clone().unwrap();
            let out_path = dest_root.join(&rel);
            let write_result: Result<(), ApexZipError> = (|| {
                if is_dir {
                    fs::create_dir_all(&out_path)?;
                    return Ok(());
                }
                if let Some(parent) = out_path.parent() {
                    fs::create_dir_all(parent)?;
                }
                let mut out_file = fs::File::create(&out_path)?;
                let cap = sanitize::MAX_ENTRY_UNCOMPRESSED;
                // Read at most cap+1 bytes regardless of what the entry's
                // header claims — this guards against a declared size that
                // lies about the true decompressed length (zip bomb).
                let mut limited = (&mut zfile).take(cap + 1);
                let copied = std::io::copy(&mut limited, &mut out_file)?;
                if copied > cap {
                    drop(out_file);
                    let _ = fs::remove_file(&out_path);
                    return Err(ApexZipError::Bounds(format!(
                        "actual decompressed size exceeded declared cap {cap} (zip-bomb guard)"
                    )));
                }
                Ok(())
            })();

            match write_result {
                Ok(()) => {
                    info.extracted = true;
                    extracted_count += 1;
                }
                Err(e) => {
                    info.verdict = "WARN";
                    info.reason = Some(e.to_string());
                }
            }
        }

        if info.verdict == "WARN" {
            warned_count += 1;
        }
        entries.push(info);
    }

    let entry_dicts: PyResult<Vec<Py<PyAny>>> = entries
        .iter()
        .map(|info| entry_to_dict(py, info).map(|d| d.into_any().unbind()))
        .collect();

    let report = PyDict::new(py);
    report.set_item("total_entries", entries.len())?;
    report.set_item("extracted", extracted_count)?;
    report.set_item("warned", warned_count)?;
    report.set_item("entries", entry_dicts?)?;
    Ok(report.into_any().unbind())
}

#[pymodule]
fn apex_zip_reader(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(read_entries, m)?)?;
    m.add_function(wrap_pyfunction!(extract_apk, m)?)?;
    Ok(())
}
