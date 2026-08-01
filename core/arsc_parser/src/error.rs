#[derive(thiserror::Error, Debug)]
pub enum ArscError {
    #[error("file too large: {0} bytes exceeds bounded-allocation cap")]
    TooLarge(usize),

    #[error("truncated resources.arsc: needed {needed} bytes at offset {offset}, buffer is {len} bytes")]
    Truncated { offset: usize, needed: usize, len: usize },

    #[error("bad top-level chunk type: expected RES_TABLE_TYPE (0x0002), got 0x{0:04x}")]
    NotATable(u16),

    #[error("bad string pool chunk type at offset {offset}: expected RES_STRING_POOL_TYPE (0x0001), got 0x{got:04x}")]
    NotAStringPool { offset: usize, got: u16 },

    #[error("unexpected chunk type at offset {offset}: expected 0x{expected:04x}, got 0x{got:04x}")]
    UnexpectedChunkType { offset: usize, expected: u16, got: u16 },

    #[error("ResTable_type at offset {0} uses FLAG_OFFSET16, which this parser doesn't implement")]
    UnsupportedOffset16(usize),

    #[error("count {count} at offset {offset} exceeds bounded-allocation cap {cap}")]
    CountTooLarge { offset: usize, count: usize, cap: usize },

    #[error("string index {index} out of range (pool has {count} strings)")]
    StringIndexOutOfRange { index: u32, count: usize },

    #[error("malformed string pool entry at offset {0}: length/encoding header doesn't fit in the chunk")]
    MalformedStringEntry(usize),

    #[error("invalid UTF-8 in string pool entry at offset {0}")]
    InvalidUtf8(usize),

    #[error("invalid UTF-16 in string pool entry at offset {0}")]
    InvalidUtf16(usize),

    #[error("chunk at offset {offset} declares headerSize {header_size} smaller than the minimum {min} for its type")]
    HeaderTooSmall { offset: usize, header_size: usize, min: usize },

    #[error("chunk at offset {offset} declares size {size} smaller than its own headerSize {header_size}")]
    ChunkSizeTooSmall { offset: usize, size: usize, header_size: usize },
}

pub type Result<T> = std::result::Result<T, ArscError>;
