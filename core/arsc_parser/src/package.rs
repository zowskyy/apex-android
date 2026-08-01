//! `ResTable_package` chunk parsing: one package's identity plus its
//! type-name pool, key-name pool, and `(typeSpec, type*)` chunks.
//!
//! `ResTable_package`'s header comes in two on-disk sizes: the legacy
//! layout (`headerSize == 0x11c` / 284 bytes, ending after
//! `lastPublicKey`) and the modern one (`headerSize == 0x120` / 288 bytes,
//! with an extra `typeIdOffset` field) — verified against real `aapt2`
//! output, which emits the modern 288-byte form (`id=127`,
//! `name="com.apex.arscfixture"`, `typeIdOffset=0`; see
//! `tests/real_arsc.rs`). Only `headerSize` is trusted to say which layout
//! is present, not the crate's own build date or a version guess.

use crate::entry::{
    parse_type_chunk, parse_type_spec, TypeChunk, TypeSpec, RES_TABLE_TYPE_SPEC_TYPE,
    RES_TABLE_TYPE_TYPE,
};
use crate::error::Result;
use crate::reader::{read_chunk_header, ArscReader, CHUNK_HEADER_SIZE};
use crate::string_pool::{parse_string_pool, StringPool};

pub const RES_TABLE_PACKAGE_TYPE: u16 = 0x0200;

/// Legacy `ResTable_package` header size (ends after `lastPublicKey`, no
/// `typeIdOffset` field).
const HEADER_SIZE_LEGACY: u16 = 0x11c;
/// Package name is a fixed `char16_t[128]` (256 bytes) regardless of layout.
const PACKAGE_NAME_BYTES: usize = 256;

#[derive(Debug, Clone)]
pub struct ResType {
    pub id: u8,
    pub name: String,
    pub spec_flags: Vec<u32>,
    pub configs: Vec<TypeChunk>,
}

#[derive(Debug, Clone)]
pub struct Package {
    pub id: u32,
    pub name: String,
    pub type_strings: StringPool,
    pub key_strings: StringPool,
    pub types: Vec<ResType>,
    pub chunk_size: u32,
}

impl Package {
    pub fn key_name(&self, key_index: u32) -> Result<&str> {
        self.key_strings.get(key_index)
    }
}

pub fn parse_package(r: &ArscReader, offset: usize) -> Result<Package> {
    let header = read_chunk_header(r, offset)?;
    if header.chunk_type != RES_TABLE_PACKAGE_TYPE {
        return Err(crate::error::ArscError::UnexpectedChunkType {
            offset,
            expected: RES_TABLE_PACKAGE_TYPE,
            got: header.chunk_type,
        });
    }

    // The fixed fields (id, name, typeStrings/lastPublicType,
    // keyStrings/lastPublicKey) must fit even under the legacy layout;
    // the only thing the modern layout adds beyond that is `typeIdOffset`,
    // which isn't needed for structural parsing here — every type's id is
    // read directly from its own typeSpec/type chunk regardless.
    if header.header_size < HEADER_SIZE_LEGACY {
        return Err(crate::error::ArscError::HeaderTooSmall {
            offset,
            header_size: header.header_size as usize,
            min: HEADER_SIZE_LEGACY as usize,
        });
    }

    let id = r.u32_at(offset + CHUNK_HEADER_SIZE)?;
    let name_bytes = r.bytes_at(offset + CHUNK_HEADER_SIZE + 4, PACKAGE_NAME_BYTES)?;
    let name_units: Vec<u16> = name_bytes
        .chunks_exact(2)
        .map(|c| u16::from_le_bytes([c[0], c[1]]))
        .collect();
    let name_end = name_units
        .iter()
        .position(|&u| u == 0)
        .unwrap_or(name_units.len());
    let name = String::from_utf16(&name_units[..name_end])
        .map_err(|_| crate::error::ArscError::InvalidUtf16(offset + CHUNK_HEADER_SIZE + 4))?;

    let fields_base = offset + CHUNK_HEADER_SIZE + 4 + PACKAGE_NAME_BYTES;
    let type_strings_rel = r.u32_at(fields_base)?;
    let key_strings_rel = r.u32_at(fields_base + 8)?;

    let type_strings = parse_string_pool(r, offset + type_strings_rel as usize)?;
    let key_strings = parse_string_pool(r, offset + key_strings_rel as usize)?;

    let mut types: Vec<ResType> = Vec::new();
    let pkg_end = offset + header.size as usize;
    let mut p = offset + key_strings_rel as usize + key_strings.chunk_size as usize;
    while p < pkg_end {
        let chunk = read_chunk_header(r, p)?;
        match chunk.chunk_type {
            RES_TABLE_TYPE_SPEC_TYPE => {
                let spec: TypeSpec = parse_type_spec(r, p)?;
                types.push(ResType {
                    id: spec.id,
                    name: type_name(&type_strings, spec.id)?,
                    spec_flags: spec.entry_flags,
                    configs: Vec::new(),
                });
                p += spec.chunk_size as usize;
            }
            RES_TABLE_TYPE_TYPE => {
                let type_chunk: TypeChunk = parse_type_chunk(r, p)?;
                match types.iter_mut().rev().find(|t| t.id == type_chunk.id) {
                    Some(t) => {
                        p += type_chunk.chunk_size as usize;
                        t.configs.push(type_chunk);
                    }
                    None => {
                        // A type chunk with no preceding typeSpec for its id
                        // (malformed, or a format variant this parser
                        // doesn't know about) — still record it under a
                        // synthesized entry with an empty spec rather than
                        // silently dropping real entry data.
                        let id = type_chunk.id;
                        p += type_chunk.chunk_size as usize;
                        types.push(ResType {
                            id,
                            name: type_name(&type_strings, id)?,
                            spec_flags: Vec::new(),
                            configs: vec![type_chunk],
                        });
                    }
                }
            }
            other => {
                return Err(crate::error::ArscError::UnexpectedChunkType {
                    offset: p,
                    expected: RES_TABLE_TYPE_SPEC_TYPE,
                    got: other,
                });
            }
        }
    }

    Ok(Package {
        id,
        name,
        type_strings,
        key_strings,
        types,
        chunk_size: header.size,
    })
}

/// Type names are 1-indexed by `id` (`id=1` is `type_strings[0]`), per the
/// AOSP convention verified against real output (`array`=id 1, `string`=id
/// 6 with the type-name pool `["array","bool","color","dimen","integer",
/// "string"]`).
fn type_name(type_strings: &StringPool, id: u8) -> Result<String> {
    type_strings.get(id as u32 - 1).map(str::to_string)
}
