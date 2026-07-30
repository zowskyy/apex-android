#[derive(thiserror::Error, Debug)]
pub enum DexError {
    #[error("file too large: {0} bytes exceeds bounded-allocation cap")]
    TooLarge(usize),

    #[error("truncated DEX: needed {needed} bytes at offset {offset}, file is {len} bytes")]
    Truncated { offset: usize, needed: usize, len: usize },

    #[error("bad magic: expected DEX magic, got {0:?}")]
    BadMagic([u8; 8]),

    #[error("unsupported endian_tag: 0x{0:08x} (only little-endian DEX is supported)")]
    UnsupportedEndian(u32),

    #[error("count {count} at offset {offset} exceeds bounded-allocation cap {cap}")]
    CountTooLarge { offset: usize, count: usize, cap: usize },

    #[error("malformed uleb128 at offset {0}: too many continuation bytes")]
    MalformedUleb128(usize),

    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
}

pub type Result<T> = std::result::Result<T, DexError>;
