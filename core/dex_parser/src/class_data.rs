use crate::error::{DexError, Result};
use crate::reader::DexReader;

/// dex-hybrid's `parse_methods` read `method_idx`/`access_flags`/`code_off`
/// as fixed 4-byte fields directly out of class_data_off. Real class_data_item
/// is entirely ULEB128, and method/field indices are delta-encoded relative
/// to the previous entry (starting from 0) — not absolute. Reading it as
/// fixed-width fields desyncs after the very first byte that isn't a
/// single-byte ULEB128.
#[derive(Debug, Clone)]
pub struct EncodedField {
    pub field_idx: u32,
    pub access_flags: u32,
}

#[derive(Debug, Clone)]
pub struct EncodedMethod {
    pub method_idx: u32,
    pub access_flags: u32,
    pub code_off: u32,
}

#[derive(Debug, Clone, Default)]
pub struct ClassData {
    pub static_fields: Vec<EncodedField>,
    pub instance_fields: Vec<EncodedField>,
    pub direct_methods: Vec<EncodedMethod>,
    pub virtual_methods: Vec<EncodedMethod>,
}

/// Bounded allocation: a single class_data_item claiming more than this many
/// members is not a real Android class — refuse rather than allocate.
pub const MAX_MEMBERS_PER_LIST: u32 = 1_000_000;

fn read_count(r: &DexReader, pos: &mut usize) -> Result<u32> {
    let (val, consumed) = r.uleb128_at(*pos)?;
    if val > MAX_MEMBERS_PER_LIST {
        return Err(DexError::CountTooLarge { offset: *pos, count: val as usize, cap: MAX_MEMBERS_PER_LIST as usize });
    }
    *pos += consumed;
    Ok(val)
}

fn read_fields(r: &DexReader, pos: &mut usize, count: u32) -> Result<Vec<EncodedField>> {
    let mut out = Vec::with_capacity(count.min(4096) as usize);
    let mut running_idx: u32 = 0;
    for _ in 0..count {
        let (idx_diff, c1) = r.uleb128_at(*pos)?;
        *pos += c1;
        let (access_flags, c2) = r.uleb128_at(*pos)?;
        *pos += c2;
        running_idx = running_idx.wrapping_add(idx_diff);
        out.push(EncodedField { field_idx: running_idx, access_flags });
    }
    Ok(out)
}

fn read_methods(r: &DexReader, pos: &mut usize, count: u32) -> Result<Vec<EncodedMethod>> {
    let mut out = Vec::with_capacity(count.min(4096) as usize);
    let mut running_idx: u32 = 0;
    for _ in 0..count {
        let (idx_diff, c1) = r.uleb128_at(*pos)?;
        *pos += c1;
        let (access_flags, c2) = r.uleb128_at(*pos)?;
        *pos += c2;
        let (code_off, c3) = r.uleb128_at(*pos)?;
        *pos += c3;
        running_idx = running_idx.wrapping_add(idx_diff);
        out.push(EncodedMethod { method_idx: running_idx, access_flags, code_off });
    }
    Ok(out)
}

/// Parse a class_data_item at `class_data_off`. Returns `ClassData::default()`
/// (all empty) for `class_data_off == 0`, per spec — that means the class
/// has no fields or methods of its own (e.g. a marker interface).
pub fn parse_class_data(r: &DexReader, class_data_off: u32) -> Result<ClassData> {
    if class_data_off == 0 {
        return Ok(ClassData::default());
    }
    let mut pos = class_data_off as usize;
    let static_fields_size = read_count(r, &mut pos)?;
    let instance_fields_size = read_count(r, &mut pos)?;
    let direct_methods_size = read_count(r, &mut pos)?;
    let virtual_methods_size = read_count(r, &mut pos)?;

    Ok(ClassData {
        static_fields: read_fields(r, &mut pos, static_fields_size)?,
        instance_fields: read_fields(r, &mut pos, instance_fields_size)?,
        direct_methods: read_methods(r, &mut pos, direct_methods_size)?,
        virtual_methods: read_methods(r, &mut pos, virtual_methods_size)?,
    })
}
