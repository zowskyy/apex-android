use crate::error::{DexError, Result};
use crate::reader::DexReader;

/// Full DEX header_item, per source.android.com/docs/core/runtime/dex-format
/// (verified field-by-field against the spec — the version this replaces,
/// ported from dex-hybrid's parser.rs, only read 4 of these 23 fields and
/// mislabeled byte offset 0x2C [link_size] as map_offset, which is actually
/// at 0x34).
#[derive(Debug, Clone)]
pub struct DexHeader {
    pub magic: [u8; 8],
    pub checksum: u32,
    pub signature: [u8; 20],
    pub file_size: u32,
    pub header_size: u32,
    pub endian_tag: u32,
    pub link_size: u32,
    pub link_off: u32,
    pub map_off: u32,
    pub string_ids_size: u32,
    pub string_ids_off: u32,
    pub type_ids_size: u32,
    pub type_ids_off: u32,
    pub proto_ids_size: u32,
    pub proto_ids_off: u32,
    pub field_ids_size: u32,
    pub field_ids_off: u32,
    pub method_ids_size: u32,
    pub method_ids_off: u32,
    pub class_defs_size: u32,
    pub class_defs_off: u32,
    pub data_size: u32,
    pub data_off: u32,
}

const DEX_MAGIC_PREFIX: &[u8; 4] = b"dex\n";
const ENDIAN_CONSTANT: u32 = 0x12345678;

pub fn read_header(r: &DexReader) -> Result<DexHeader> {
    let magic: [u8; 8] = r.bytes_at(0x00, 8)?.try_into().unwrap();
    if &magic[0..4] != DEX_MAGIC_PREFIX {
        return Err(DexError::BadMagic(magic));
    }

    let endian_tag = r.u32_at(0x28)?;
    if endian_tag != ENDIAN_CONSTANT {
        return Err(DexError::UnsupportedEndian(endian_tag));
    }

    Ok(DexHeader {
        magic,
        checksum: r.u32_at(0x08)?,
        signature: r.bytes_at(0x0c, 20)?.try_into().unwrap(),
        file_size: r.u32_at(0x20)?,
        header_size: r.u32_at(0x24)?,
        endian_tag,
        link_size: r.u32_at(0x2c)?,
        link_off: r.u32_at(0x30)?,
        map_off: r.u32_at(0x34)?,
        string_ids_size: r.u32_at(0x38)?,
        string_ids_off: r.u32_at(0x3c)?,
        type_ids_size: r.u32_at(0x40)?,
        type_ids_off: r.u32_at(0x44)?,
        proto_ids_size: r.u32_at(0x48)?,
        proto_ids_off: r.u32_at(0x4c)?,
        field_ids_size: r.u32_at(0x50)?,
        field_ids_off: r.u32_at(0x54)?,
        method_ids_size: r.u32_at(0x58)?,
        method_ids_off: r.u32_at(0x5c)?,
        class_defs_size: r.u32_at(0x60)?,
        class_defs_off: r.u32_at(0x64)?,
        data_size: r.u32_at(0x68)?,
        data_off: r.u32_at(0x6c)?,
    })
}
