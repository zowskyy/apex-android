//! DEX file structural parser: header, string/type pools, class_defs, and
//! class_data (fields + methods with real indices).
//!
//! This is a from-scratch port from dex-hybrid (a separate personal Rust
//! project), keeping its architectural shape — header -> class_defs ->
//! class_data -> (eventually) instruction decode / IR — but fixing three
//! concrete bugs found in review against the authoritative spec
//! (source.android.com/docs/core/runtime/dex-format):
//!   1. header_item: dex-hybrid read only 4 fields starting at a hardcoded
//!      offset and mislabeled byte 0x2C (link_size) as map_off (the real
//!      map_off is at 0x34). This crate reads the full 23-field header at
//!      its correct offsets.
//!   2. class_def_item: dex-hybrid's ClassDef struct had 7 of the real 8
//!      fields (missing static_values_off), which would misalign every
//!      class after the first. Fixed here.
//!   3. class_data_item (encoded_field/encoded_method): dex-hybrid read
//!      these as fixed-width u32 fields; the real format is ULEB128 with
//!      delta-encoded indices. Fixed here (see class_data.rs, reader.rs).
//!
//! Deliberately NOT ported: dex-hybrid's instruction disassembler (its
//! opcode->operand-count table only covered 2 of ~30 Dalvik instruction
//! formats), its "SSA" IR builder (predecessor tracking was never wired up,
//! so its phi-node insertion was dead code), and its optimizer/AST layers
//! (every stage was a stub — see the review this port is based on). Real
//! bytecode decoding is Slice 1.5 proper, not something to fake here.

pub mod cfg;
pub mod class_data;
pub mod class_def;
pub mod code;
pub mod decompile;
pub mod defuse;
pub mod dominators;
pub mod encoded;
pub mod error;
pub mod header;
pub mod ids;
pub mod java;
pub mod opcode;
pub mod reader;
pub mod ssa;
pub mod strings;
pub mod structure;
pub mod tries;

use error::Result;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict};
use reader::DexReader;

pub struct DexFile<'a> {
    pub data: &'a [u8],
    pub header: header::DexHeader,
    pub strings: Vec<String>,
    pub type_ids: Vec<u32>,
    pub proto_ids: Vec<ids::ProtoId>,
    pub field_ids: Vec<ids::FieldId>,
    pub method_ids: Vec<ids::MethodId>,
    pub class_defs: Vec<class_def::ClassDef>,
}

/// Bounded allocation at the whole-file level, same philosophy as
/// core/zip_reader: refuse before reading rather than trusting a header
/// field to justify an unbounded allocation.
pub const MAX_DEX_FILE_SIZE: usize = 512 * 1024 * 1024;

pub fn parse(data: &[u8]) -> Result<DexFile<'_>> {
    if data.len() > MAX_DEX_FILE_SIZE {
        return Err(error::DexError::TooLarge(data.len()));
    }
    let r = DexReader::new(data);
    let header = header::read_header(&r)?;
    let strings = strings::read_all_strings(&r, header.string_ids_off, header.string_ids_size)?;
    let type_ids = strings::read_type_ids(&r, header.type_ids_off, header.type_ids_size)?;
    let proto_ids = ids::parse_proto_ids(&r, header.proto_ids_off, header.proto_ids_size)?;
    let field_ids = ids::parse_field_ids(&r, header.field_ids_off, header.field_ids_size)?;
    let method_ids = ids::parse_method_ids(&r, header.method_ids_off, header.method_ids_size)?;
    let class_defs =
        class_def::parse_class_defs(&r, header.class_defs_off, header.class_defs_size)?;
    Ok(DexFile {
        data,
        header,
        strings,
        type_ids,
        proto_ids,
        field_ids,
        method_ids,
        class_defs,
    })
}

impl<'a> DexFile<'a> {
    /// Resolve a type_idx to its descriptor string, e.g. "Lcom/foo/Bar;".
    pub fn type_name(&self, type_idx: u32) -> Option<&str> {
        let string_idx = *self.type_ids.get(type_idx as usize)?;
        self.strings.get(string_idx as usize).map(|s| s.as_str())
    }

    /// Parse the class_data_item for a given class_def (fields + methods).
    pub fn class_data(&self, def: &class_def::ClassDef) -> Result<class_data::ClassData> {
        let r = DexReader::new(self.data);
        class_data::parse_class_data(&r, def.class_data_off)
    }

    /// Resolve a method_ids table entry's name string, given a method_idx.
    /// method_id_item is a fixed 8-byte record: class_idx:u16, proto_idx:u16, name_idx:u32.
    pub fn method_name(&self, method_idx: u32) -> Result<&str> {
        let Some(method) = self.method_ids.get(method_idx as usize) else {
            return Ok("");
        };
        let name_idx = method.name_idx;
        Ok(self
            .strings
            .get(name_idx as usize)
            .map(|s| s.as_str())
            .unwrap_or(""))
    }

    /// Parse a method's code_item (from `EncodedMethod::code_off`, 0 means
    /// abstract/native — no code) and decode its instruction stream.
    pub fn decode_method(&self, code_off: u32) -> Result<(code::CodeItem, Vec<code::CodeUnit>)> {
        let r = DexReader::new(self.data);
        let item = code::parse_code_item(&r, code_off)?;
        let units = code::decode_instructions(&item.insns)?;
        Ok((item, units))
    }
}

#[pyfunction]
fn decompile_dex(data: &[u8]) -> PyResult<Vec<(String, String)>> {
    let dex = parse(data).map_err(|err| PyValueError::new_err(err.to_string()))?;
    Ok(java::decompile_all(&dex))
}

#[pyfunction]
fn dex_summary(py: Python<'_>, data: &[u8]) -> PyResult<Py<PyAny>> {
    let dex = parse(data).map_err(|err| PyValueError::new_err(err.to_string()))?;
    let classes: PyResult<Vec<Py<PyAny>>> = java::class_summaries(&dex)
        .into_iter()
        .map(|summary| {
            let dict = PyDict::new(py);
            dict.set_item("name", summary.name)?;
            dict.set_item("superclass", summary.superclass)?;
            dict.set_item(
                "method_count",
                summary.direct_methods + summary.virtual_methods,
            )?;
            dict.set_item(
                "field_count",
                summary.static_fields + summary.instance_fields,
            )?;
            Ok(dict.into_any().unbind())
        })
        .collect();
    let dict = PyDict::new(py);
    dict.set_item("class_count", dex.class_defs.len())?;
    dict.set_item("method_count", dex.method_ids.len())?;
    dict.set_item("string_count", dex.strings.len())?;
    dict.set_item("classes", classes?)?;
    Ok(dict.into_any().unbind())
}

#[pymodule]
fn apex_dex_parser(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(decompile_dex, m)?)?;
    m.add_function(wrap_pyfunction!(dex_summary, m)?)?;
    Ok(())
}
