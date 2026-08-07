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

pub mod access;
pub mod cfg;
pub mod class_data;
pub mod class_def;
pub mod code;
pub mod error;
pub mod header;
pub mod metadata;
pub mod opcode;
pub mod proto;
pub mod reader;
pub mod ssa;
pub mod strings;

use error::Result;
use reader::DexReader;

pub struct DexFile<'a> {
    pub data: &'a [u8],
    pub header: header::DexHeader,
    pub strings: Vec<String>,
    pub type_ids: Vec<u32>,
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
    let class_defs = class_def::parse_class_defs(&r, header.class_defs_off, header.class_defs_size)?;
    Ok(DexFile { data, header, strings, type_ids, class_defs })
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
        let r = DexReader::new(self.data);
        let entry = self.header.method_ids_off as usize + (method_idx as usize) * 8;
        let name_idx = r.u32_at(entry + 4)?;
        Ok(self.strings.get(name_idx as usize).map(|s| s.as_str()).unwrap_or(""))
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
