use crate::error::{ArscError, Result};

/// Bounds-checked little-endian reader over a byte slice. Every read
/// validates the offset+length against the buffer before touching memory —
/// same bounded-allocation discipline as core/zip_reader/src/sanitize.rs and
/// core/dex_parser/src/reader.rs, applied here against a hostile/truncated
/// resources.arsc.
pub struct ArscReader<'a> {
    pub data: &'a [u8],
}

impl<'a> ArscReader<'a> {
    pub fn new(data: &'a [u8]) -> Self {
        Self { data }
    }

    fn check(&self, offset: usize, needed: usize) -> Result<()> {
        if offset.checked_add(needed).is_none_or(|end| end > self.data.len()) {
            return Err(ArscError::Truncated { offset, needed, len: self.data.len() });
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
}

/// The 8-byte `ResChunk_header` common to every chunk in the format:
/// `{ uint16 type; uint16 headerSize; uint32 size; }`. `size` includes
/// `headerSize` (i.e. it's the whole chunk, header + payload).
#[derive(Debug, Clone, Copy)]
pub struct ChunkHeader {
    pub chunk_type: u16,
    pub header_size: u16,
    pub size: u32,
}

pub const CHUNK_HEADER_SIZE: usize = 8;

pub fn read_chunk_header(r: &ArscReader, offset: usize) -> Result<ChunkHeader> {
    let chunk_type = r.u16_at(offset)?;
    let header_size = r.u16_at(offset + 2)?;
    let size = r.u32_at(offset + 4)?;
    if (header_size as usize) < CHUNK_HEADER_SIZE {
        return Err(ArscError::HeaderTooSmall { offset, header_size: header_size as usize, min: CHUNK_HEADER_SIZE });
    }
    if (size as usize) < header_size as usize {
        return Err(ArscError::ChunkSizeTooSmall { offset, size: size as usize, header_size: header_size as usize });
    }
    // Bound-check that the whole chunk actually fits, so every downstream
    // consumer that trusts `size` (e.g. "next chunk starts at offset+size")
    // never walks past the buffer on malformed/truncated input.
    r.bytes_at(offset, size as usize)?;
    Ok(ChunkHeader { chunk_type, header_size, size })
}
