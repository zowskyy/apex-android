//! resources.arsc structural parser (Slice 1.2).
//!
//! Chunk-based binary format (AOSP `ResourceTypes.h`): a table header, a
//! global string pool (resource *values* that are strings), and one or more
//! package chunks — each with its own type-name pool, key-name pool, and a
//! `(typeSpec, type*)` chunk pair per resource type. Verified against
//! genuine `aapt2`-compiled output rather than the spec alone (no Android
//! SDK/framework jar is available in this environment, so the fixture's
//! `AndroidManifest.xml` is a bare `<manifest package="..."/>` with no
//! `android:` attributes — that limitation is about the *manifest*, not
//! resources.arsc, which is unaffected by it): see
//! `tests/fixtures/resources.arsc` and `tests/real_arsc.rs`.
//!
//! Scope for this slice: simple and complex (map/array) entries, both
//! string-pool encodings, dense and — per spec only, unverified against
//! real bytes since nothing in this environment can produce them — sparse
//! entry tables. `ResTable_config` qualifier bytes (locale/density/screen
//! size/etc.) are captured raw but not decoded field-by-field; only
//! "is this the default/no-qualifiers config" is exposed, since resolving
//! a specific device configuration against the qualifier bit layout is a
//! separate, sizable slice of its own.

pub mod axml;
pub mod entry;
pub mod error;
pub mod package;
pub mod reader;
pub mod string_pool;
pub mod value;

use error::{ArscError, Result};
use reader::{read_chunk_header, ArscReader, CHUNK_HEADER_SIZE};
use string_pool::StringPool;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict};

pub use axml::{axml_strings, decode_axml, is_binary_xml};

pub const RES_TABLE_TYPE: u16 = 0x0002;

/// Bounded allocation for `packageCount` — matches the project's
/// non-negotiable "check counts against the chunk before allocating" rule.
pub const MAX_PACKAGE_COUNT: u32 = 256;

#[derive(Debug, Clone)]
pub struct ResourceTable {
    pub global_strings: StringPool,
    pub packages: Vec<package::Package>,
}

pub fn parse(data: &[u8]) -> Result<ResourceTable> {
    let r = ArscReader::new(data);
    let header = read_chunk_header(&r, 0)?;
    if header.chunk_type != RES_TABLE_TYPE {
        return Err(ArscError::NotATable(header.chunk_type));
    }
    let package_count = r.u32_at(CHUNK_HEADER_SIZE)?;
    if package_count > MAX_PACKAGE_COUNT {
        return Err(ArscError::CountTooLarge {
            offset: CHUNK_HEADER_SIZE,
            count: package_count as usize,
            cap: MAX_PACKAGE_COUNT as usize,
        });
    }

    let global_strings = string_pool::parse_string_pool(&r, header.header_size as usize)?;

    let mut packages = Vec::with_capacity(package_count as usize);
    let mut offset = header.header_size as usize + global_strings.chunk_size as usize;
    for _ in 0..package_count {
        let pkg = package::parse_package(&r, offset)?;
        offset += pkg.chunk_size as usize;
        packages.push(pkg);
    }

    Ok(ResourceTable {
        global_strings,
        packages,
    })
}

impl ResourceTable {
    /// Resolve a `TYPE_STRING` value's `data` field (a global-pool index)
    /// to its text. Callers must check `Value::data_type == TYPE_STRING`
    /// first; a mismatched type would otherwise resolve an unrelated
    /// string by coincidence.
    pub fn resolve_string(&self, index: u32) -> Result<&str> {
        self.global_strings.get(index)
    }
}

#[pyfunction]
fn arsc_summary(py: Python<'_>, data: &[u8]) -> PyResult<Py<PyAny>> {
    let table = parse(data).map_err(|err| PyValueError::new_err(err.to_string()))?;
    let packages: PyResult<Vec<Py<PyAny>>> = table
        .packages
        .iter()
        .map(|pkg| {
            let pkg_dict = PyDict::new(py);
            pkg_dict.set_item("id", pkg.id)?;
            pkg_dict.set_item("name", &pkg.name)?;
            let types: PyResult<Vec<Py<PyAny>>> = pkg
                .types
                .iter()
                .map(|ty| {
                    let ty_dict = PyDict::new(py);
                    ty_dict.set_item("id", ty.id)?;
                    ty_dict.set_item("name", &ty.name)?;
                    ty_dict.set_item("entry_count", ty.spec_flags.len())?;
                    ty_dict.set_item("config_count", ty.configs.len())?;
                    Ok(ty_dict.into_any().unbind())
                })
                .collect();
            let entry_count: usize = pkg.types.iter().map(|ty| ty.spec_flags.len()).sum();
            let config_count: usize = pkg.types.iter().map(|ty| ty.configs.len()).sum();
            pkg_dict.set_item("entry_count", entry_count)?;
            pkg_dict.set_item("config_count", config_count)?;
            pkg_dict.set_item("types", types?)?;
            Ok(pkg_dict.into_any().unbind())
        })
        .collect();
    let dict = PyDict::new(py);
    dict.set_item("global_string_count", table.global_strings.strings.len())?;
    dict.set_item("packages", packages?)?;
    Ok(dict.into_any().unbind())
}

#[pyfunction(name = "decode_axml")]
fn py_decode_axml(data: &[u8]) -> PyResult<String> {
    axml::decode_axml(data).map_err(|err| PyValueError::new_err(err.to_string()))
}

#[pyfunction(name = "axml_strings")]
fn py_axml_strings(data: &[u8]) -> PyResult<Vec<String>> {
    axml::axml_strings(data).map_err(|err| PyValueError::new_err(err.to_string()))
}

#[pyfunction]
fn scan_string_pools(data: &[u8]) -> PyResult<Vec<String>> {
    let r = ArscReader::new(data);
    let mut strings = Vec::new();
    for offset in 0..data.len().saturating_sub(CHUNK_HEADER_SIZE - 1) {
        if data[offset] != (string_pool::RES_STRING_POOL_TYPE & 0xff) as u8
            || data[offset + 1] != (string_pool::RES_STRING_POOL_TYPE >> 8) as u8
        {
            continue;
        }
        if let Ok(pool) = string_pool::parse_string_pool(&r, offset) {
            strings.extend(pool.strings);
        }
    }
    Ok(strings)
}

#[pyfunction(name = "is_binary_xml")]
fn py_is_binary_xml(data: &[u8]) -> bool {
    axml::is_binary_xml(data)
}

#[pymodule]
fn apex_arsc_parser(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(arsc_summary, m)?)?;
    m.add_function(wrap_pyfunction!(py_decode_axml, m)?)?;
    m.add_function(wrap_pyfunction!(py_axml_strings, m)?)?;
    m.add_function(wrap_pyfunction!(scan_string_pools, m)?)?;
    m.add_function(wrap_pyfunction!(py_is_binary_xml, m)?)?;
    Ok(())
}
