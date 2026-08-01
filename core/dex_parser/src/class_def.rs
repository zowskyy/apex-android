use crate::error::{DexError, Result};
use crate::reader::DexReader;

/// class_def_item is a fixed 32-byte (8 x u32) record. dex-hybrid's ClassDef
/// was missing `static_values_off` (only 7 of these 8 fields) — every class
/// after the first would be read starting 4 bytes short, misaligning the
/// rest of the table.
#[derive(Debug, Clone)]
pub struct ClassDef {
    pub class_idx: u32,
    pub access_flags: u32,
    pub superclass_idx: u32,
    pub interfaces_off: u32,
    pub source_file_idx: u32,
    pub annotations_off: u32,
    pub class_data_off: u32,
    pub static_values_off: u32,
}

pub const CLASS_DEF_ITEM_SIZE: usize = 32;

/// Bounded allocation: refuse to iterate a class_defs_size so large that
/// `class_defs_size * CLASS_DEF_ITEM_SIZE` alone would already exceed a
/// realistic DEX file, before ever touching the file offsets it implies.
pub const MAX_CLASS_DEFS: usize = 2_000_000;

pub fn parse_class_defs(r: &DexReader, off: u32, count: u32) -> Result<Vec<ClassDef>> {
    let count = count as usize;
    if count > MAX_CLASS_DEFS {
        return Err(DexError::CountTooLarge {
            offset: off as usize,
            count,
            cap: MAX_CLASS_DEFS,
        });
    }
    let mut defs = Vec::with_capacity(count.min(4096));
    let base = off as usize;
    for i in 0..count {
        let entry = base + i * CLASS_DEF_ITEM_SIZE;
        defs.push(ClassDef {
            class_idx: r.u32_at(entry)?,
            access_flags: r.u32_at(entry + 4)?,
            superclass_idx: r.u32_at(entry + 8)?,
            interfaces_off: r.u32_at(entry + 12)?,
            source_file_idx: r.u32_at(entry + 16)?,
            annotations_off: r.u32_at(entry + 20)?,
            class_data_off: r.u32_at(entry + 24)?,
            static_values_off: r.u32_at(entry + 28)?,
        });
    }
    Ok(defs)
}
