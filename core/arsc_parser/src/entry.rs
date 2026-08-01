//! `ResTable_typeSpec` and `ResTable_type` chunk parsing: per-resource-type
//! flags, and the actual entries (simple values and complex/map entries —
//! arrays, styles, plurals) for one configuration of that type.
//!
//! Verified against genuine `aapt2` output for: a simple string entry, a
//! simple bool entry (`TYPE_INT_BOOLEAN`, `true` stored as `data =
//! 0xFFFFFFFF`), a simple color entry (`TYPE_INT_COLOR_ARGB8`), a simple
//! dimension entry, a simple integer entry, and a complex/map entry (a
//! `<string-array>`, whose items are `ResTable_map`s with synthetic
//! sequential `name` values `0x01000001`, `0x01000002`, ... rather than
//! real attribute references). See `tests/real_arsc.rs`.
//!
//! NOT verified against real bytes (nothing in this sandboxed environment —
//! no Android framework jar — could make aapt2 emit it): `FLAG_SPARSE`
//! entry tables. Implemented per the AOSP `ResourceTypes.h` layout
//! (`ResTable_sparseTypeEntry { uint16 idx; uint16 offset; }`, offset in
//! 4-byte units) but flagged here exactly like `core/dex_parser`'s
//! quickened-opcode gap: treat as unverified if this parser is ever pointed
//! at resources.arsc built by a toolchain that actually emits sparse tables
//! (`aapt2 link --enable-sparse-encoding`, real devices targeting API 26+).
//! `FLAG_OFFSET16` (an even newer, 16-bit-offset dense variant) is
//! explicitly rejected rather than silently misparsed — same principle.

use crate::error::{ArscError, Result};
use crate::reader::{read_chunk_header, ArscReader};
use crate::value::{read_value, Value};

pub const RES_TABLE_TYPE_SPEC_TYPE: u16 = 0x0202;
pub const RES_TABLE_TYPE_TYPE: u16 = 0x0201;

pub const FLAG_COMPLEX: u16 = 0x0001;
const TYPE_FLAG_SPARSE: u8 = 0x01;
const TYPE_FLAG_OFFSET16: u8 = 0x02;

const NO_ENTRY: u32 = 0xffff_ffff;

/// Bounded allocation for entry/map counts, matching the project's
/// non-negotiable rule (see KNOWLEDGE_BASE.md).
pub const MAX_ENTRY_COUNT: u32 = 16 * 1024 * 1024;
pub const MAX_MAP_COUNT: u32 = 1024 * 1024;

#[derive(Debug, Clone)]
pub struct TypeSpec {
    pub id: u8,
    /// Per-resource-ID config-difference flags (which config axes vary
    /// across this resource's configs) — captured as-is; the individual
    /// bit meanings (`CONFIG_MCC`, `CONFIG_LOCALE`, ...) aren't decoded by
    /// this slice.
    pub entry_flags: Vec<u32>,
    pub chunk_size: u32,
}

pub fn parse_type_spec(r: &ArscReader, offset: usize) -> Result<TypeSpec> {
    let header = read_chunk_header(r, offset)?;
    if header.chunk_type != RES_TABLE_TYPE_SPEC_TYPE {
        return Err(ArscError::UnexpectedChunkType { offset, expected: RES_TABLE_TYPE_SPEC_TYPE, got: header.chunk_type });
    }
    let id = r.u8_at(offset + 8)?;
    let entry_count = r.u32_at(offset + 12)?;
    if entry_count > MAX_ENTRY_COUNT {
        return Err(ArscError::CountTooLarge { offset, count: entry_count as usize, cap: MAX_ENTRY_COUNT as usize });
    }
    let mut entry_flags = Vec::with_capacity(entry_count as usize);
    for i in 0..entry_count as usize {
        entry_flags.push(r.u32_at(offset + 16 + i * 4)?);
    }
    Ok(TypeSpec { id, entry_flags, chunk_size: header.size })
}

#[derive(Debug, Clone)]
pub struct MapEntry {
    /// For a style's items, a real attribute resource ID. For an
    /// array's items, a synthetic sequential ID (`0x01000001`,
    /// `0x01000002`, ...) that merely encodes item order, not a real
    /// attribute — verified against a real `<string-array>` compile.
    pub name: u32,
    pub value: Value,
}

#[derive(Debug, Clone)]
pub enum EntryValue {
    Simple(Value),
    Complex { parent: u32, entries: Vec<MapEntry> },
}

#[derive(Debug, Clone)]
pub struct ResourceEntry {
    /// Index into the package's key-string pool for this entry's name.
    pub key_index: u32,
    pub flags: u16,
    pub value: EntryValue,
}

fn parse_resource_entry(r: &ArscReader, entry_offset: usize) -> Result<ResourceEntry> {
    let size = r.u16_at(entry_offset)?;
    let flags = r.u16_at(entry_offset + 2)?;
    let key_index = r.u32_at(entry_offset + 4)?;

    if flags & FLAG_COMPLEX == 0 {
        let (value, _) = read_value(r, entry_offset + size as usize)?;
        return Ok(ResourceEntry { key_index, flags, value: EntryValue::Simple(value) });
    }

    let parent = r.u32_at(entry_offset + 8)?;
    let count = r.u32_at(entry_offset + 12)?;
    if count > MAX_MAP_COUNT {
        return Err(ArscError::CountTooLarge { offset: entry_offset, count: count as usize, cap: MAX_MAP_COUNT as usize });
    }
    let mut entries = Vec::with_capacity(count as usize);
    let mut p = entry_offset + size as usize;
    for _ in 0..count {
        let name = r.u32_at(p)?;
        let (value, next) = read_value(r, p + 4)?;
        entries.push(MapEntry { name, value });
        p = next;
    }
    Ok(ResourceEntry { key_index, flags, value: EntryValue::Complex { parent, entries } })
}

#[derive(Debug, Clone)]
pub struct TypeChunk {
    pub id: u8,
    /// Raw `ResTable_config` bytes (self-length-prefixed) — qualifier bits
    /// aren't decoded field-by-field in this slice.
    pub config: Vec<u8>,
    /// (resource-ID-within-type, entry) pairs for every present entry;
    /// holes (`NO_ENTRY` in a dense table) are simply absent rather than
    /// represented as `None`, since a dense table's total slot count is
    /// already available from the sibling `TypeSpec.entry_flags.len()`.
    pub entries: Vec<(u32, ResourceEntry)>,
    pub chunk_size: u32,
}

pub fn parse_type_chunk(r: &ArscReader, offset: usize) -> Result<TypeChunk> {
    let header = read_chunk_header(r, offset)?;
    if header.chunk_type != RES_TABLE_TYPE_TYPE {
        return Err(ArscError::UnexpectedChunkType { offset, expected: RES_TABLE_TYPE_TYPE, got: header.chunk_type });
    }
    let id = r.u8_at(offset + 8)?;
    let flags = r.u8_at(offset + 9)?;
    if flags & TYPE_FLAG_OFFSET16 != 0 {
        return Err(ArscError::UnsupportedOffset16(offset)); // not implemented, see module doc
    }
    let entry_count = r.u32_at(offset + 12)?;
    let entries_start = r.u32_at(offset + 16)?;
    if entry_count > MAX_ENTRY_COUNT {
        return Err(ArscError::CountTooLarge { offset, count: entry_count as usize, cap: MAX_ENTRY_COUNT as usize });
    }

    let config_len = header.header_size as usize - 20;
    let config = r.bytes_at(offset + 20, config_len)?.to_vec();

    let table_base = offset + header.header_size as usize;
    let entries_base = offset + entries_start as usize;
    let sparse = flags & TYPE_FLAG_SPARSE != 0;

    let mut entries = Vec::new();
    if sparse {
        for i in 0..entry_count as usize {
            let idx = r.u16_at(table_base + i * 4)? as u32;
            let word_offset = r.u16_at(table_base + i * 4 + 2)? as usize;
            let entry = parse_resource_entry(r, entries_base + word_offset * 4)?;
            entries.push((idx, entry));
        }
    } else {
        for i in 0..entry_count as usize {
            let entry_offset = r.u32_at(table_base + i * 4)?;
            if entry_offset == NO_ENTRY {
                continue;
            }
            let entry = parse_resource_entry(r, entries_base + entry_offset as usize)?;
            entries.push((i as u32, entry));
        }
    }

    Ok(TypeChunk { id, config, entries, chunk_size: header.size })
}

impl TypeChunk {
    /// True for the "default" configuration — no locale/density/screen/etc.
    /// qualifiers — i.e. every config byte after the self-describing size
    /// prefix is zero.
    pub fn is_default_config(&self) -> bool {
        // `config`'s own first 4 bytes are its self-describing size field
        // (e.g. 64 for the modern `ResTable_config`), which is never zero —
        // only the qualifier bytes *after* it indicate an actual
        // locale/density/screen/etc. qualifier.
        self.config.get(4..).is_some_and(|qualifiers| qualifiers.iter().all(|&b| b == 0))
    }
}
