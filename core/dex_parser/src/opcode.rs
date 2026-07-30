//! Dalvik opcode -> instruction-format table.
//!
//! This is what dex-hybrid's parser.rs never really implemented: it read
//! every "instruction" as 1 opcode byte + a fixed lookup of 0-2 raw 4-byte
//! operands (`opcode_operands`), which only happens to look plausible for a
//! couple of opcode ranges and silently misdecodes (desyncs) everything
//! else — since DEX instructions are 16-bit code units with per-format bit
//! layouts, not byte-opcode-plus-word-operands.
//!
//! Source: source.android.com/docs/core/runtime/dalvik-bytecode (the format
//! table itself has been stable since Android 1.0; only the high end
//! — invoke-polymorphic/invoke-custom/const-method-handle/const-method-type,
//! DEX version 038+ — was added later). Width (in 16-bit code units) is the
//! safety-critical fact here: get it wrong and every instruction after it
//! desyncs. Exact operand *semantics* for the quickened/ODEX-only opcodes
//! (0xe3-0xf9 range) matter far less for us since APKs never ship quickened
//! bytecode (that's an on-device ART optimization, not present in
//! build-time DEX) — those are decoded with correct width and raw operand
//! bits captured, but not semantically interpreted.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Format {
    F10x,
    F12x,
    F11n,
    F11x,
    F10t,
    F20t,
    F20bc,
    F22x,
    F21t,
    F21s,
    F21h,
    F21c,
    F23x,
    F22b,
    F22t,
    F22s,
    F22c,
    F22cs,
    F30t,
    F32x,
    F31i,
    F31t,
    F31c,
    F35c,
    F3rc,
    F45cc,
    F4rcc,
    F51l,
}

impl Format {
    /// Width in 16-bit code units. This is the safety-critical property —
    /// every opcode MUST map to the correct width or all subsequent
    /// decoding in the method desyncs.
    pub fn width(self) -> u32 {
        match self {
            Format::F10x | Format::F12x | Format::F11n | Format::F11x | Format::F10t => 1,
            Format::F20t | Format::F20bc | Format::F22x | Format::F21t | Format::F21s
            | Format::F21h | Format::F21c | Format::F23x | Format::F22b | Format::F22t
            | Format::F22s | Format::F22c | Format::F22cs => 2,
            Format::F30t | Format::F32x | Format::F31i | Format::F31t | Format::F31c
            | Format::F35c | Format::F3rc => 3,
            Format::F45cc | Format::F4rcc => 4,
            Format::F51l => 5,
        }
    }
}

/// Returns `None` for opcodes explicitly reserved/unused in the spec
/// (0x3e-0x43, 0x73, 0x79-0x7a) — these are documented as fixed-width 10x
/// (1 code unit) even though unused, so callers should still advance by 1,
/// not treat `None` as "unknown width".
pub fn format_of(opcode: u8) -> Option<Format> {
    use Format::*;
    Some(match opcode {
        0x00 => F10x, // nop (also payload marker - see code.rs)
        0x01 | 0x04 | 0x07 => F12x, // move, move-wide, move-object
        0x02 | 0x05 | 0x08 => F22x, // move/from16 variants
        0x03 | 0x06 | 0x09 => F32x, // move/16 variants
        0x0a..=0x0d => F11x, // move-result*, move-exception
        0x0e => F10x, // return-void
        0x0f..=0x11 => F11x, // return, return-wide, return-object
        0x12 => F11n, // const/4
        0x13 => F21s, // const/16
        0x14 => F31i, // const
        0x15 => F21h, // const/high16
        0x16 => F21s, // const-wide/16
        0x17 => F31i, // const-wide/32
        0x18 => F51l, // const-wide
        0x19 => F21h, // const-wide/high16
        0x1a => F21c, // const-string
        0x1b => F31c, // const-string/jumbo
        0x1c => F21c, // const-class
        0x1d | 0x1e => F11x, // monitor-enter/exit
        0x1f => F21c, // check-cast
        0x20 => F22c, // instance-of
        0x21 => F12x, // array-length
        0x22 => F21c, // new-instance
        0x23 => F22c, // new-array
        0x24 => F35c, // filled-new-array
        0x25 => F3rc, // filled-new-array/range
        0x26 => F31t, // fill-array-data
        0x27 => F11x, // throw
        0x28 => F10t, // goto
        0x29 => F20t, // goto/16
        0x2a => F30t, // goto/32
        0x2b | 0x2c => F31t, // packed-switch, sparse-switch
        0x2d..=0x31 => F23x, // cmpl/cmpg/cmp-long
        0x32..=0x37 => F22t, // if-eq..if-le
        0x38..=0x3d => F21t, // if-eqz..if-lez
        0x3e..=0x43 => return None, // unused (still 10x width)
        0x44..=0x51 => F23x, // aget*/aput*
        0x52..=0x5f => F22c, // iget*/iput*
        0x60..=0x6d => F21c, // sget*/sput*
        0x6e..=0x72 => F35c, // invoke-virtual/super/direct/static/interface
        0x73 => return None, // unused
        0x74..=0x78 => F3rc, // invoke-*/range
        0x79 | 0x7a => return None, // unused
        0x7b..=0x8f => F12x, // unary ops (neg-*, not-*, *-to-*)
        0x90..=0xaf => F23x, // binop (vAA = vBB op vCC)
        0xb0..=0xcf => F12x, // binop/2addr (vA = vA op vB)
        0xd0..=0xd7 => F22s, // binop/lit16
        0xd8..=0xe2 => F22b, // binop/lit8
        // 0xe3-0xf9: quickened/ODEX-only opcodes (iget-quick, invoke-*-quick,
        // etc). Never present in build-time/APK-shipped DEX, only in
        // on-device ART-optimized ODEX. Width per historical Dalvik VM
        // source (vm/mterp): quick field accessors are 22cs (2 units, field
        // offset instead of field ref), quick invokes are 35ms/3rms (3
        // units) shaped identically in width to 35c/3rc.
        0xe3..=0xe9 => F22cs, // iget/iput-quick family
        0xea..=0xeb => F35c,  // invoke-virtual-quick (shape: like 35c, vtable idx)
        0xec..=0xed => F3rc,  // invoke-virtual-quick/range
        0xee..=0xf9 => F22cs, // remaining quickened field accessors (boolean/byte/char/short)
        0xfa => F45cc, // invoke-polymorphic
        0xfb => F4rcc, // invoke-polymorphic/range
        0xfc => F35c,  // invoke-custom
        0xfd => F3rc,  // invoke-custom/range
        0xfe | 0xff => F21c, // const-method-handle, const-method-type
    })
}
