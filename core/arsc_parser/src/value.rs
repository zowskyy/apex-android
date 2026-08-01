//! `Res_value`: `{ uint16 size; uint8 res0; uint8 dataType; uint32 data; }`
//! (8 bytes) — the leaf value type for every simple entry and every map
//! entry inside a complex one. `data`'s meaning depends entirely on
//! `data_type`; only `TYPE_STRING` (a global-string-pool index) is resolved
//! by this crate today, matching what's exercised by the fixture.

use crate::error::Result;
use crate::reader::ArscReader;

pub const TYPE_NULL: u8 = 0x00;
pub const TYPE_REFERENCE: u8 = 0x01;
pub const TYPE_ATTRIBUTE: u8 = 0x02;
pub const TYPE_STRING: u8 = 0x03;
pub const TYPE_FLOAT: u8 = 0x04;
pub const TYPE_DIMENSION: u8 = 0x05;
pub const TYPE_FRACTION: u8 = 0x06;
pub const TYPE_DYNAMIC_REFERENCE: u8 = 0x07;
pub const TYPE_DYNAMIC_ATTRIBUTE: u8 = 0x08;
pub const TYPE_INT_DEC: u8 = 0x10;
pub const TYPE_INT_HEX: u8 = 0x11;
pub const TYPE_INT_BOOLEAN: u8 = 0x12;
pub const TYPE_INT_COLOR_ARGB8: u8 = 0x1c;
pub const TYPE_INT_COLOR_RGB8: u8 = 0x1d;
pub const TYPE_INT_COLOR_ARGB4: u8 = 0x1e;
pub const TYPE_INT_COLOR_RGB4: u8 = 0x1f;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Value {
    pub data_type: u8,
    pub data: u32,
}

/// Size of the on-disk `Res_value` struct: verified against real aapt2
/// output (every entry we decoded has `size == 8`); the `size` field itself
/// is read and used to find where the *next* structure starts, rather than
/// assumed, so a future/variant encoding with a larger declared size would
/// still be walked correctly even though only `dataType`/`data` are parsed.
pub fn read_value(r: &ArscReader, offset: usize) -> Result<(Value, usize)> {
    let size = r.u16_at(offset)?;
    let data_type = r.u8_at(offset + 3)?;
    let data = r.u32_at(offset + 4)?;
    Ok((Value { data_type, data }, offset + size as usize))
}
