use crate::error::{DexError, Result};

/// Bounds-checked little-endian reader over a byte slice. Every read
/// validates the offset+length against the buffer before touching memory —
/// same bounded-allocation discipline as core/zip_reader/src/sanitize.rs,
/// applied here against a hostile/truncated DEX rather than a hostile ZIP.
pub struct DexReader<'a> {
    pub data: &'a [u8],
}

impl<'a> DexReader<'a> {
    pub fn new(data: &'a [u8]) -> Self {
        Self { data }
    }

    fn check(&self, offset: usize, needed: usize) -> Result<()> {
        if offset.checked_add(needed).is_none_or(|end| end > self.data.len()) {
            return Err(DexError::Truncated { offset, needed, len: self.data.len() });
        }
        Ok(())
    }

    pub fn bytes_at(&self, offset: usize, len: usize) -> Result<&'a [u8]> {
        self.check(offset, len)?;
        Ok(&self.data[offset..offset + len])
    }

    pub fn u8_at(&self, offset: usize) -> Result<u8> {
        self.check(offset, 1)?;
        Ok(self.data[offset])
    }

    pub fn u16_at(&self, offset: usize) -> Result<u16> {
        let b = self.bytes_at(offset, 2)?;
        Ok(u16::from_le_bytes([b[0], b[1]]))
    }

    pub fn u32_at(&self, offset: usize) -> Result<u32> {
        let b = self.bytes_at(offset, 4)?;
        Ok(u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
    }

    /// Read a ULEB128 value starting at `offset`. Returns (value, bytes_consumed).
    /// DEX uses ULEB128 for delta-encoded indices in class_data_item — this
    /// is the encoding dex-hybrid's parser skipped entirely (it read fixed
    /// u32 fields instead), which is why it misparsed real class data.
    pub fn uleb128_at(&self, offset: usize) -> Result<(u32, usize)> {
        let mut result: u32 = 0;
        let mut shift = 0u32;
        let mut pos = offset;
        loop {
            if shift >= 35 {
                return Err(DexError::MalformedUleb128(offset));
            }
            let byte = self.u8_at(pos)?;
            pos += 1;
            result |= ((byte & 0x7f) as u32) << shift;
            if byte & 0x80 == 0 {
                break;
            }
            shift += 7;
        }
        Ok((result, pos - offset))
    }

    /// Read a SLEB128 value starting at `offset`. Returns (value, bytes_consumed).
    /// `encoded_catch_handler.size` is SLEB128 and its *sign* carries meaning:
    /// a non-positive size means the typed handlers are followed by a
    /// catch-all handler. Reading it as unsigned silently loses the catch-all.
    pub fn sleb128_at(&self, offset: usize) -> Result<(i32, usize)> {
        let mut result: i32 = 0;
        let mut shift: u32 = 0;
        let mut pos = offset;
        loop {
            if shift >= 35 {
                return Err(DexError::MalformedUleb128(offset));
            }
            let byte = self.u8_at(pos)?;
            pos += 1;
            result |= ((byte & 0x7f) as i32) << shift;
            shift += 7;
            if byte & 0x80 == 0 {
                // Sign-extend when the final byte's sign bit (0x40) is set.
                if shift < 32 && (byte & 0x40) != 0 {
                    result |= -(1i32 << shift);
                }
                break;
            }
        }
        Ok((result, pos - offset))
    }
}
