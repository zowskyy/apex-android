use crate::error::{DexError, Result};
use crate::reader::DexReader;

pub const MAX_STRING_IDS: usize = 5_000_000;
/// A single string_data_item claiming more UTF-16 code units than this is
/// not a real Android string constant — bounded-allocation guard.
pub const MAX_STRING_UTF16_LEN: u32 = 10_000_000;

/// string_ids is an array of `string_data_off: u32` (4 bytes each) at
/// header.string_ids_off, one per string_ids_size.
pub fn read_string_data_offsets(r: &DexReader, off: u32, count: u32) -> Result<Vec<u32>> {
    let count = count as usize;
    if count > MAX_STRING_IDS {
        return Err(DexError::CountTooLarge { offset: off as usize, count, cap: MAX_STRING_IDS });
    }
    let mut out = Vec::with_capacity(count.min(4096));
    let base = off as usize;
    for i in 0..count {
        out.push(r.u32_at(base + i * 4)?);
    }
    Ok(out)
}

/// Decode a string_data_item at `offset`: a ULEB128 utf16_size followed by
/// Modified UTF-8 (MUTF-8) bytes, NUL-terminated. MUTF-8 matches standard
/// UTF-8 except: NUL is encoded as the two-byte sequence 0xC0 0x80 (so an
/// embedded NUL doesn't terminate the string early), and code points above
/// U+FFFF are encoded as a surrogate pair, each half individually
/// 3-byte-encoded (CESU-8 style) rather than UTF-8's single 4-byte form.
pub fn decode_mutf8_string(r: &DexReader, offset: u32) -> Result<String> {
    let (utf16_len, consumed) = r.uleb128_at(offset as usize)?;
    if utf16_len > MAX_STRING_UTF16_LEN {
        return Err(DexError::CountTooLarge { offset: offset as usize, count: utf16_len as usize, cap: MAX_STRING_UTF16_LEN as usize });
    }
    let mut pos = offset as usize + consumed;
    let mut units: Vec<u16> = Vec::with_capacity(utf16_len.min(4096) as usize);

    for _ in 0..utf16_len {
        let b0 = r.u8_at(pos)?;
        pos += 1;
        if b0 == 0 {
            break; // NUL terminator reached before utf16_len units decoded
        }
        let unit: u16 = if b0 & 0x80 == 0 {
            b0 as u16
        } else if b0 & 0xE0 == 0xC0 {
            let b1 = r.u8_at(pos)?;
            pos += 1;
            (((b0 & 0x1F) as u16) << 6) | ((b1 & 0x3F) as u16)
        } else {
            let b1 = r.u8_at(pos)?;
            pos += 1;
            let b2 = r.u8_at(pos)?;
            pos += 1;
            (((b0 & 0x0F) as u16) << 12) | (((b1 & 0x3F) as u16) << 6) | ((b2 & 0x3F) as u16)
        };
        units.push(unit);
    }

    Ok(String::from_utf16_lossy(&units))
}

pub fn read_all_strings(r: &DexReader, string_ids_off: u32, string_ids_size: u32) -> Result<Vec<String>> {
    let offsets = read_string_data_offsets(r, string_ids_off, string_ids_size)?;
    offsets.into_iter().map(|off| decode_mutf8_string(r, off)).collect()
}

/// type_ids is an array of `descriptor_idx: u32` (index into string_ids),
/// one per type_ids_size, at header.type_ids_off.
pub fn read_type_ids(r: &DexReader, off: u32, count: u32) -> Result<Vec<u32>> {
    let count = count as usize;
    if count > MAX_STRING_IDS {
        return Err(DexError::CountTooLarge { offset: off as usize, count, cap: MAX_STRING_IDS });
    }
    let mut out = Vec::with_capacity(count.min(4096));
    let base = off as usize;
    for i in 0..count {
        out.push(r.u32_at(base + i * 4)?);
    }
    Ok(out)
}
