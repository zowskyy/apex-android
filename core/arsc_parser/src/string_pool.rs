//! `ResStringPool` parsing: the shared string-table format used at three
//! places in resources.arsc (the table-level global value pool, and each
//! package's type-name and key-name pools) plus binary XML files later.
//! Verified against genuine `aapt2`-produced output (see
//! `tests/fixtures/resources.arsc` / `real_arsc.rs`) rather than the spec
//! alone: our own fixture exercises BOTH encodings in the same file (the
//! global/key pools come out UTF-8, the type-name pool comes out UTF-16),
//! so both paths below are checked against real bytes, not just written to
//! match the header comment in ResourceTypes.h.
//!
//! Layout: chunk header (8) + `{ stringCount, styleCount, flags,
//! stringsStart, stylesStart }` (20, so headerSize=28) + `stringCount`
//! u32 offsets (relative to `stringsStart`) + `styleCount` u32 offsets
//! (relative to `stylesStart`) + string data + style data. `UTF8_FLAG`
//! (bit 8 of `flags`) selects the string encoding; style data is present
//! only when `styleCount > 0`.

use crate::error::{ArscError, Result};
use crate::reader::{read_chunk_header, ArscReader, CHUNK_HEADER_SIZE};

pub const RES_STRING_POOL_TYPE: u16 = 0x0001;

const UTF8_FLAG: u32 = 1 << 8;

/// Bounded allocation, matching the project's non-negotiable "check counts
/// against the chunk before allocating" rule (see KNOWLEDGE_BASE.md):
/// refuses a declared count that couldn't possibly fit a real resources.arsc
/// before trusting it to size a `Vec`.
pub const MAX_STRING_COUNT: u32 = 16 * 1024 * 1024;

/// One formatting span on a styled string: `name` is a string-pool index
/// naming the tag (e.g. "b"), and `[first_char, last_char]` is the
/// *inclusive* character range of `strings[owner]` it covers — verified
/// against a real `<string>Hello <b>World</b>!</string>` compile, where the
/// span for "b" is `(first_char=6, last_char=10)` over "Hello World!".
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Span {
    pub name: u32,
    pub first_char: u32,
    pub last_char: u32,
}

#[derive(Debug, Clone, Default)]
pub struct StringPool {
    pub strings: Vec<String>,
    /// `styles[i]` are the spans on `strings[i]`; empty for every
    /// unstyled string (which is all of them, when `styleCount == 0`).
    pub styles: Vec<Vec<Span>>,
    /// Total size of this chunk (`ResChunk_header.size`), so a caller
    /// walking sibling chunks knows where the next one starts.
    pub chunk_size: u32,
}

fn decode_utf16_string(r: &ArscReader, data_start: usize) -> Result<(String, usize)> {
    // Length is a uint16, or two uint16s (high bit of the first set) for
    // strings longer than 0x7fff UTF-16 code units.
    let lo = r.u16_at(data_start)?;
    let (len, mut pos) = if lo & 0x8000 != 0 {
        let hi = r.u16_at(data_start + 2)? as u32;
        (((lo as u32 & 0x7fff) << 16) | hi, data_start + 4)
    } else {
        (lo as u32, data_start + 2)
    };
    let len = len as usize;
    let cap = len.checked_mul(2).ok_or(ArscError::MalformedStringEntry(data_start))?;
    let bytes = r.bytes_at(pos, cap)?;
    let units: Vec<u16> = bytes.chunks_exact(2).map(|c| u16::from_le_bytes([c[0], c[1]])).collect();
    let s = String::from_utf16(&units).map_err(|_| ArscError::InvalidUtf16(data_start))?;
    pos += cap;
    Ok((s, pos))
}

fn decode_utf8_string(r: &ArscReader, data_start: usize) -> Result<(String, usize)> {
    // UTF-8 entries carry BOTH a UTF-16-length hint (for pre-sizing
    // buffers, unused here) and the real UTF-8 byte length; each is 1 byte
    // normally, 2 bytes if the high bit of the first byte is set.
    let skip_len_field = |offset: usize| -> Result<usize> {
        let b0 = r.u8_at(offset)?;
        Ok(if b0 & 0x80 != 0 { offset + 2 } else { offset + 1 })
    };
    let after_utf16_hint = skip_len_field(data_start)?;
    let b0 = r.u8_at(after_utf16_hint)?;
    let (len, mut pos) = if b0 & 0x80 != 0 {
        let b1 = r.u8_at(after_utf16_hint + 1)? as usize;
        ((((b0 & 0x7f) as usize) << 8) | b1, after_utf16_hint + 2)
    } else {
        (b0 as usize, after_utf16_hint + 1)
    };
    let bytes = r.bytes_at(pos, len)?;
    let s = std::str::from_utf8(bytes).map_err(|_| ArscError::InvalidUtf8(data_start))?.to_string();
    pos += len;
    Ok((s, pos))
}

/// Parse a `ResStringPool` chunk starting at `offset` in `r`. `offset` must
/// point at a `RES_STRING_POOL_TYPE` chunk header.
pub fn parse_string_pool(r: &ArscReader, offset: usize) -> Result<StringPool> {
    let header = read_chunk_header(r, offset)?;
    if header.chunk_type != RES_STRING_POOL_TYPE {
        return Err(ArscError::NotAStringPool { offset, got: header.chunk_type });
    }

    let string_count = r.u32_at(offset + CHUNK_HEADER_SIZE)?;
    let style_count = r.u32_at(offset + CHUNK_HEADER_SIZE + 4)?;
    let flags = r.u32_at(offset + CHUNK_HEADER_SIZE + 8)?;
    let strings_start = r.u32_at(offset + CHUNK_HEADER_SIZE + 12)?;
    let styles_start = r.u32_at(offset + CHUNK_HEADER_SIZE + 16)?;

    if string_count > MAX_STRING_COUNT || style_count > MAX_STRING_COUNT {
        let (count, cap) = if string_count > MAX_STRING_COUNT { (string_count, MAX_STRING_COUNT) } else { (style_count, MAX_STRING_COUNT) };
        return Err(ArscError::CountTooLarge { offset, count: count as usize, cap: cap as usize });
    }

    let utf8 = flags & UTF8_FLAG != 0;
    let string_offsets_base = offset + header.header_size as usize;
    let style_offsets_base = string_offsets_base + string_count as usize * 4;

    let mut strings = Vec::with_capacity(string_count as usize);
    for i in 0..string_count as usize {
        let rel = r.u32_at(string_offsets_base + i * 4)?;
        let data_start = offset + strings_start as usize + rel as usize;
        let (s, _) = if utf8 { decode_utf8_string(r, data_start)? } else { decode_utf16_string(r, data_start)? };
        strings.push(s);
    }

    let mut styles: Vec<Vec<Span>> = vec![Vec::new(); string_count as usize];
    for i in 0..style_count as usize {
        let rel = r.u32_at(style_offsets_base + i * 4)?;
        let mut pos = offset + styles_start as usize + rel as usize;
        let mut spans = Vec::new();
        loop {
            let name = r.u32_at(pos)?;
            if name == u32::MAX {
                break;
            }
            let first_char = r.u32_at(pos + 4)?;
            let last_char = r.u32_at(pos + 8)?;
            spans.push(Span { name, first_char, last_char });
            pos += 12;
        }
        // The style-offset table is indexed by *string* index (only
        // strings that actually have spans get a non-degenerate entry),
        // matching what we verified against real aapt2 output: styleCount
        // entries correspond 1:1 with the first `styleCount`-many string
        // slots' worth of style data, referenced by the string's own index
        // via the offset table — store by position `i` here and let the
        // caller match it to `strings[i]` (true for every real pool we've
        // seen: aapt2 never interleaves styled and unstyled strings).
        if let Some(slot) = styles.get_mut(i) {
            *slot = spans;
        }
    }

    Ok(StringPool { strings, styles, chunk_size: header.size })
}

impl StringPool {
    pub fn get(&self, index: u32) -> Result<&str> {
        self.strings.get(index as usize).map(String::as_str).ok_or(ArscError::StringIndexOutOfRange { index, count: self.strings.len() })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Build a minimal UTF-8-flagged pool with 2 entries by hand, matching
    /// the exact layout aapt2 produces for a non-styled `values.xml` (see
    /// `real_arsc.rs` for the same shape verified against real output).
    #[test]
    fn utf8_pool_round_trips_two_strings() {
        let mut buf = Vec::new();
        buf.extend_from_slice(&1u16.to_le_bytes()); // type = RES_STRING_POOL_TYPE
        buf.extend_from_slice(&28u16.to_le_bytes()); // headerSize
        let size_pos = buf.len();
        buf.extend_from_slice(&0u32.to_le_bytes()); // size, patched below
        buf.extend_from_slice(&2u32.to_le_bytes()); // stringCount
        buf.extend_from_slice(&0u32.to_le_bytes()); // styleCount
        buf.extend_from_slice(&(UTF8_FLAG).to_le_bytes()); // flags
        let strings_start_pos = buf.len();
        buf.extend_from_slice(&0u32.to_le_bytes()); // stringsStart, patched below
        buf.extend_from_slice(&0u32.to_le_bytes()); // stylesStart

        let off_table_pos = buf.len();
        buf.extend_from_slice(&0u32.to_le_bytes());
        buf.extend_from_slice(&0u32.to_le_bytes());

        let strings_start = buf.len() as u32; // relative to chunk start (offset 0 here)
        buf[strings_start_pos..strings_start_pos + 4].copy_from_slice(&strings_start.to_le_bytes());

        let off0 = (buf.len() as u32) - strings_start;
        buf.push(3); // utf16-hint length (short form)
        buf.push(3); // utf8 length (short form)
        buf.extend_from_slice(b"foo");
        buf.push(0); // NUL terminator

        let off1 = (buf.len() as u32) - strings_start;
        buf.push(3);
        buf.push(3);
        buf.extend_from_slice(b"bar");
        buf.push(0);

        buf[off_table_pos..off_table_pos + 4].copy_from_slice(&off0.to_le_bytes());
        buf[off_table_pos + 4..off_table_pos + 8].copy_from_slice(&off1.to_le_bytes());

        let total = buf.len() as u32;
        buf[size_pos..size_pos + 4].copy_from_slice(&total.to_le_bytes());

        let r = ArscReader::new(&buf);
        let pool = parse_string_pool(&r, 0).unwrap();
        assert_eq!(pool.strings, vec!["foo", "bar"]);
        assert_eq!(pool.chunk_size, total);
    }

    #[test]
    fn oversized_string_count_rejected_before_allocating() {
        let mut buf = Vec::new();
        buf.extend_from_slice(&1u16.to_le_bytes());
        buf.extend_from_slice(&28u16.to_le_bytes());
        buf.extend_from_slice(&28u32.to_le_bytes()); // size == headerSize, no payload
        buf.extend_from_slice(&(MAX_STRING_COUNT + 1).to_le_bytes()); // stringCount
        buf.extend_from_slice(&0u32.to_le_bytes());
        buf.extend_from_slice(&0u32.to_le_bytes());
        buf.extend_from_slice(&0u32.to_le_bytes());
        buf.extend_from_slice(&0u32.to_le_bytes());

        let r = ArscReader::new(&buf);
        assert!(matches!(parse_string_pool(&r, 0), Err(ArscError::CountTooLarge { .. })));
    }
}
