//! code_item parsing and Dalvik instruction decoding.
//!
//! code_item's 16-byte header (registers_size, ins_size, outs_size,
//! tries_size, debug_info_off, insns_size) is the one part of dex-hybrid's
//! parser.rs that *was* correct — it matches the real layout exactly. What
//! it got wrong was everything after: it read the `insns` stream as
//! opcode-byte-plus-raw-4-byte-operands instead of properly formatted
//! 16-bit code units (see opcode.rs). This module replaces that with a
//! real per-format decoder.

use crate::error::{DexError, Result};
use crate::opcode::{format_of, Format};
use crate::reader::DexReader;

#[derive(Debug, Clone)]
pub struct CodeItem {
    pub registers_size: u16,
    pub ins_size: u16,
    pub outs_size: u16,
    pub tries_size: u16,
    pub debug_info_off: u32,
    pub insns: Vec<u16>,
}

/// Bounded allocation: refuse a declared insns_size implying more than this
/// many 16-bit code units (128 MiB of bytecode) before allocating.
pub const MAX_INSNS_SIZE: u32 = 64 * 1024 * 1024;

pub fn parse_code_item(r: &DexReader, code_off: u32) -> Result<CodeItem> {
    let base = code_off as usize;
    let registers_size = r.u16_at(base)?;
    let ins_size = r.u16_at(base + 2)?;
    let outs_size = r.u16_at(base + 4)?;
    let tries_size = r.u16_at(base + 6)?;
    let debug_info_off = r.u32_at(base + 8)?;
    let insns_size = r.u32_at(base + 12)?;

    if insns_size > MAX_INSNS_SIZE {
        return Err(DexError::CountTooLarge { offset: base + 12, count: insns_size as usize, cap: MAX_INSNS_SIZE as usize });
    }

    let mut insns = Vec::with_capacity((insns_size as usize).min(65536));
    let insns_base = base + 16;
    for i in 0..insns_size as usize {
        insns.push(r.u16_at(insns_base + i * 2)?);
    }

    Ok(CodeItem { registers_size, ins_size, outs_size, tries_size, debug_info_off, insns })
}

/// One entry of the `try_item` array: a protected instruction range and the
/// byte offset of its handler within the `encoded_catch_handler_list`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TryItem {
    /// First protected instruction, in 16-bit code units.
    pub start_addr: u32,
    /// Number of protected code units.
    pub insn_count: u16,
    /// Byte offset from the start of the handler list (NOT an index).
    pub handler_off: u16,
}

impl TryItem {
    /// One past the last protected code unit.
    pub fn end_addr(&self) -> u32 {
        self.start_addr + self.insn_count as u32
    }

    pub fn covers(&self, addr: u32) -> bool {
        addr >= self.start_addr && addr < self.end_addr()
    }
}

/// One `encoded_catch_handler`: typed handlers plus an optional catch-all.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CatchHandler {
    /// Byte offset of this handler within the handler list, matching
    /// `TryItem::handler_off`.
    pub offset: u16,
    /// `(type_idx, handler_addr)` pairs in declaration order.
    pub typed: Vec<(u32, u32)>,
    /// Present when the encoded size was non-positive.
    pub catch_all_addr: Option<u32>,
}

impl CatchHandler {
    /// Every handler entry address, typed handlers first then the catch-all.
    pub fn addresses(&self) -> Vec<u32> {
        let mut out: Vec<u32> = self.typed.iter().map(|&(_, addr)| addr).collect();
        if let Some(addr) = self.catch_all_addr {
            out.push(addr);
        }
        out
    }
}

/// The exception tables that follow a method's instruction stream.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct ExceptionData {
    pub tries: Vec<TryItem>,
    pub handlers: Vec<CatchHandler>,
}

impl ExceptionData {
    pub fn is_empty(&self) -> bool {
        self.tries.is_empty()
    }

    /// Resolve a `try_item`'s `handler_off` to its handler entry.
    pub fn handler_for(&self, item: &TryItem) -> Option<&CatchHandler> {
        self.handlers.iter().find(|h| h.offset == item.handler_off)
    }
}

/// Bounded allocation for attacker-controlled table sizes.
pub const MAX_TRIES: usize = 65_535;
pub const MAX_HANDLERS: usize = 65_535;
pub const MAX_TYPED_PER_HANDLER: usize = 65_535;

/// Parse the `try_item` array and `encoded_catch_handler_list` that follow a
/// method's instructions.
///
/// Layout, per the DEX spec: the instruction stream ends at
/// `code_off + 16 + insns_size * 2`. When `insns_size` is odd a two-byte
/// padding unit follows so the `try_item` array starts 4-byte aligned. The
/// handler list begins immediately after the `try_item` array, and each
/// `try_item.handler_off` is a *byte offset from the start of that list*, not
/// an index into it.
pub fn parse_exception_data(
    r: &DexReader,
    code_off: u32,
    item: &CodeItem,
) -> Result<ExceptionData> {
    if item.tries_size == 0 {
        return Ok(ExceptionData::default());
    }
    let tries_size = (item.tries_size as usize).min(MAX_TRIES);
    let base = code_off as usize;
    let insns_size = item.insns.len();
    let mut tries_base = base + 16 + insns_size * 2;
    if insns_size % 2 == 1 {
        tries_base += 2; // padding code unit to reach 4-byte alignment
    }

    let mut tries = Vec::with_capacity(tries_size);
    for index in 0..tries_size {
        let entry = tries_base + index * 8;
        tries.push(TryItem {
            start_addr: r.u32_at(entry)?,
            insn_count: r.u16_at(entry + 4)?,
            handler_off: r.u16_at(entry + 6)?,
        });
    }

    let handlers_base = tries_base + tries_size * 8;
    let (list_size, header_len) = r.uleb128_at(handlers_base)?;
    let mut pos = handlers_base + header_len;
    let count = (list_size as usize).min(MAX_HANDLERS);
    let mut handlers = Vec::with_capacity(count);
    for _ in 0..count {
        let offset = (pos - handlers_base) as u16;
        let (size, consumed) = r.sleb128_at(pos)?;
        pos += consumed;
        let typed_count = (size.unsigned_abs() as usize).min(MAX_TYPED_PER_HANDLER);
        let mut typed = Vec::with_capacity(typed_count);
        for _ in 0..typed_count {
            let (type_idx, a) = r.uleb128_at(pos)?;
            pos += a;
            let (addr, b) = r.uleb128_at(pos)?;
            pos += b;
            typed.push((type_idx, addr));
        }
        // A non-positive size means a catch-all handler follows the typed list.
        let catch_all_addr = if size <= 0 {
            let (addr, consumed) = r.uleb128_at(pos)?;
            pos += consumed;
            Some(addr)
        } else {
            None
        };
        handlers.push(CatchHandler { offset, typed, catch_all_addr });
    }

    Ok(ExceptionData { tries, handlers })
}

#[derive(Debug, Clone)]
pub struct Instruction {
    pub code_unit_offset: u32,
    pub opcode: u8,
    pub format: Format,
    /// Registers in the format's natural order (vA, vB, vC... ; for the
    /// range forms 3rc/4rcc this is the expanded [vCCCC, vCCCC+1, ...]).
    pub registers: Vec<u16>,
    pub literal: Option<i64>,
    pub branch_offset: Option<i32>,
    /// string/type/field/method/proto/callsite pool index, for the *c/cc formats.
    pub index: Option<u32>,
}

#[derive(Debug, Clone)]
pub enum CodeUnit {
    Insn(Instruction),
    PackedSwitchPayload { first_key: i32, targets: Vec<i32> },
    SparseSwitchPayload { keys: Vec<i32>, targets: Vec<i32> },
    FillArrayDataPayload { element_width: u16, data: Vec<u8> },
}

/// Sign-extend a value of `bits` width held in the low bits of `v`.
fn sign_extend(v: u32, bits: u32) -> i64 {
    let shift = 32 - bits;
    (((v << shift) as i32) >> shift) as i64
}

/// Bounds-checked code-unit access. Payload pseudo-instructions (packed-
/// switch/sparse-switch/fill-array-data) carry attacker-influenced sizes;
/// indexing `insns` directly on those would panic on truncated/malformed
/// input instead of failing gracefully like the rest of this crate does.
fn get(insns: &[u16], i: usize) -> Result<u16> {
    insns.get(i).copied().ok_or(DexError::Truncated { offset: i * 2, needed: 2, len: insns.len() * 2 })
}

/// Decode a full insns stream into a sequence of CodeUnits (instructions and
/// any inline switch/array-data payloads). Fails on the first opcode whose
/// format/width can't be determined confidently rather than guessing — a
/// wrong guess here silently desyncs every instruction after it.
pub fn decode_instructions(insns: &[u16]) -> Result<Vec<CodeUnit>> {
    let mut out = Vec::new();
    let mut pos: usize = 0;

    while pos < insns.len() {
        let unit0 = insns[pos];
        let opcode = (unit0 & 0xff) as u8;
        let hi = (unit0 >> 8) as u8;

        // nop (0x00) with a nonzero high byte that matches a payload marker
        // is actually a packed-switch/sparse-switch/fill-array-data payload,
        // not a real nop — these are inline data blocks the verifier skips
        // over via padding, and they have their own variable-length shape.
        if opcode == 0x00 && hi != 0x00 {
            match hi {
                0x01 => {
                    let size = get(insns, pos + 1)? as usize;
                    let first_key = (get(insns, pos + 2)? as i32) | ((get(insns, pos + 3)? as i32) << 16);
                    let mut targets = Vec::with_capacity(size.min(1 << 16));
                    let mut p = pos + 4;
                    for _ in 0..size {
                        let lo = get(insns, p)? as i32;
                        let hi16 = get(insns, p + 1)? as i32;
                        targets.push(lo | (hi16 << 16));
                        p += 2;
                    }
                    out.push(CodeUnit::PackedSwitchPayload { first_key, targets });
                    pos = p;
                    continue;
                }
                0x02 => {
                    let size = get(insns, pos + 1)? as usize;
                    let mut p = pos + 2;
                    let mut keys = Vec::with_capacity(size.min(1 << 16));
                    for _ in 0..size {
                        keys.push((get(insns, p)? as i32) | ((get(insns, p + 1)? as i32) << 16));
                        p += 2;
                    }
                    let mut targets = Vec::with_capacity(size.min(1 << 16));
                    for _ in 0..size {
                        targets.push((get(insns, p)? as i32) | ((get(insns, p + 1)? as i32) << 16));
                        p += 2;
                    }
                    out.push(CodeUnit::SparseSwitchPayload { keys, targets });
                    pos = p;
                    continue;
                }
                0x03 => {
                    let element_width = get(insns, pos + 1)?;
                    let size = (get(insns, pos + 2)? as u32) | ((get(insns, pos + 3)? as u32) << 16);
                    let data_bytes = (size as usize).saturating_mul(element_width as usize);
                    let mut data = Vec::with_capacity(data_bytes.min(1 << 20));
                    let mut p = pos + 4;
                    let mut remaining = data_bytes;
                    while remaining > 0 {
                        let u = get(insns, p)?;
                        data.push((u & 0xff) as u8);
                        remaining -= 1;
                        if remaining > 0 {
                            data.push((u >> 8) as u8);
                            remaining -= 1;
                        }
                        p += 1;
                    }
                    out.push(CodeUnit::FillArrayDataPayload { element_width, data });
                    pos = p;
                    continue;
                }
                _ => return Err(DexError::MalformedUleb128(pos)), // unrecognized nop-family marker
            }
        }

        let format = format_of(opcode).unwrap_or(Format::F10x); // reserved/unused opcodes are documented 10x width
        let width = format.width() as usize;
        if pos + width > insns.len() {
            return Err(DexError::Truncated { offset: pos * 2, needed: width * 2, len: insns.len() * 2 });
        }

        let unit1 = if width > 1 { insns[pos + 1] } else { 0 };
        let unit2 = if width > 2 { insns[pos + 2] } else { 0 };
        let unit3 = if width > 3 { insns[pos + 3] } else { 0 };

        let mut registers = Vec::new();
        let mut literal = None;
        let mut branch_offset = None;
        let mut index = None;

        match format {
            Format::F10x => {}
            Format::F12x => {
                registers.push((hi & 0x0f) as u16); // A
                registers.push((hi >> 4) as u16); // B
            }
            Format::F11n => {
                registers.push((hi & 0x0f) as u16); // A
                literal = Some(sign_extend((hi >> 4) as u32, 4)); // B, signed 4-bit
            }
            Format::F11x => {
                registers.push(hi as u16); // AA
            }
            Format::F10t => {
                branch_offset = Some((hi as i8) as i32); // AA, signed 8-bit
            }
            Format::F20t => {
                branch_offset = Some((unit1 as i16) as i32); // AAAA, signed 16-bit
            }
            Format::F20bc => {
                registers.push(hi as u16); // AA (error kind, reused as "register" slot)
                index = Some(unit1 as u32);
            }
            Format::F22x => {
                registers.push(hi as u16); // AA
                registers.push(unit1); // BBBB
            }
            Format::F21t => {
                registers.push(hi as u16); // AA
                branch_offset = Some((unit1 as i16) as i32); // BBBB signed
            }
            Format::F21s => {
                registers.push(hi as u16); // AA
                literal = Some((unit1 as i16) as i64); // BBBB signed
            }
            Format::F21h => {
                registers.push(hi as u16); // AA
                // BBBB occupies bits 48-63 of the result, all lower bits
                // zero-filled — always stored this way regardless of
                // whether the opcode is the 32-bit form (const/high16,
                // 0x15) or the 64-bit form (const-wide/high16, 0x19).
                // Callers must check the opcode to know which: for the
                // 32-bit form the real value is `(literal >> 32) as i32`
                // (BBBB occupies its top 16 bits); for the 64-bit form
                // it's `literal` as-is.
                literal = Some((unit1 as i64) << 48);
            }
            Format::F21c => {
                registers.push(hi as u16); // AA
                index = Some(unit1 as u32); // BBBB
            }
            Format::F23x => {
                registers.push(hi as u16); // AA
                registers.push(unit1 & 0xff); // BB
                registers.push(unit1 >> 8); // CC
            }
            Format::F22b => {
                registers.push(hi as u16); // AA
                registers.push(unit1 & 0xff); // BB
                literal = Some(sign_extend((unit1 >> 8) as u32, 8)); // CC signed 8-bit
            }
            Format::F22t => {
                registers.push((hi & 0x0f) as u16); // A
                registers.push((hi >> 4) as u16); // B
                branch_offset = Some((unit1 as i16) as i32); // CCCC signed
            }
            Format::F22s => {
                registers.push((hi & 0x0f) as u16); // A
                registers.push((hi >> 4) as u16); // B
                literal = Some((unit1 as i16) as i64); // CCCC signed
            }
            Format::F22c | Format::F22cs => {
                registers.push((hi & 0x0f) as u16); // A
                registers.push((hi >> 4) as u16); // B
                index = Some(unit1 as u32); // CCCC (field/type ref, or field offset if quickened)
            }
            Format::F30t => {
                branch_offset = Some((unit1 as i32) | ((unit2 as i32) << 16)); // AAAAAAAA signed
            }
            Format::F32x => {
                registers.push(unit1); // AAAA
                registers.push(unit2); // BBBB
            }
            Format::F31i => {
                registers.push(hi as u16); // AA
                literal = Some(sign_extend((unit1 as u32) | ((unit2 as u32) << 16), 32));
            }
            Format::F31t => {
                registers.push(hi as u16); // AA
                branch_offset = Some((unit1 as i32) | ((unit2 as i32) << 16)); // BBBBBBBB signed
            }
            Format::F31c => {
                registers.push(hi as u16); // AA
                index = Some((unit1 as u32) | ((unit2 as u32) << 16)); // BBBBBBBB
            }
            Format::F35c => {
                // unit0 hi byte: high nibble = A (arg count 0-5), low nibble = G
                let arg_count = (hi >> 4) & 0x0f;
                let g = hi & 0x0f;
                index = Some(unit1 as u32); // BBBB
                let c = unit2 & 0x0f;
                let d = (unit2 >> 4) & 0x0f;
                let e = (unit2 >> 8) & 0x0f;
                let f = (unit2 >> 12) & 0x0f;
                let all = [c, d, e, f, g as u16];
                registers = all[..arg_count as usize].to_vec();
            }
            Format::F3rc => {
                let count = hi as u32; // AA
                index = Some(unit1 as u32); // BBBB
                let first_reg = unit2; // CCCC
                registers = (0..count).map(|i| first_reg.wrapping_add(i as u16)).collect();
            }
            Format::F45cc => {
                let arg_count = (hi >> 4) & 0x0f;
                let g = hi & 0x0f;
                index = Some(unit1 as u32); // BBBB (method ref)
                let c = unit2 & 0x0f;
                let d = (unit2 >> 4) & 0x0f;
                let e = (unit2 >> 8) & 0x0f;
                let f = (unit2 >> 12) & 0x0f;
                let all = [c, d, e, f, g as u16];
                registers = all[..arg_count as usize].to_vec();
                literal = Some(unit3 as i64); // HHHH proto idx, stashed in literal
            }
            Format::F4rcc => {
                let count = hi as u32;
                index = Some(unit1 as u32);
                let first_reg = unit2;
                registers = (0..count).map(|i| first_reg.wrapping_add(i as u16)).collect();
                literal = Some(unit3 as i64); // HHHH proto idx
            }
            Format::F51l => {
                registers.push(hi as u16); // AA
                let lo = insns[pos + 1] as u64;
                let mid_lo = insns[pos + 2] as u64;
                let mid_hi = insns[pos + 3] as u64;
                let hi64 = insns[pos + 4] as u64;
                literal = Some((lo | (mid_lo << 16) | (mid_hi << 32) | (hi64 << 48)) as i64);
            }
        }

        out.push(CodeUnit::Insn(Instruction {
            code_unit_offset: pos as u32,
            opcode,
            format,
            registers,
            literal,
            branch_offset,
            index,
        }));
        pos += width;
    }

    Ok(out)
}

#[cfg(test)]
mod exception_tests {
    use super::*;

    fn uleb(value: u32, out: &mut Vec<u8>) {
        let mut v = value;
        loop {
            let mut byte = (v & 0x7f) as u8;
            v >>= 7;
            if v != 0 {
                byte |= 0x80;
            }
            out.push(byte);
            if v == 0 {
                break;
            }
        }
    }

    /// Build a code_item with `insns_size` nops followed by an exception table.
    ///
    /// `tries` entries are `(start_addr, insn_count, handler_index)`; the
    /// handler index is resolved to the handler's real byte offset within the
    /// list, which is what a real `try_item.handler_off` stores. Note that the
    /// list begins with its ULEB128 size, so the first handler is NOT at
    /// offset 0.
    fn build_code_item(
        insns_size: usize,
        tries: &[(u32, u16, usize)],
        handlers: &[(Vec<(u32, u32)>, Option<u32>)],
    ) -> (Vec<u8>, Vec<u16>) {
        let mut buf = Vec::new();
        buf.extend_from_slice(&2u16.to_le_bytes()); // registers_size
        buf.extend_from_slice(&0u16.to_le_bytes()); // ins_size
        buf.extend_from_slice(&0u16.to_le_bytes()); // outs_size
        buf.extend_from_slice(&(tries.len() as u16).to_le_bytes());
        buf.extend_from_slice(&0u32.to_le_bytes()); // debug_info_off
        buf.extend_from_slice(&(insns_size as u32).to_le_bytes());
        for _ in 0..insns_size {
            buf.extend_from_slice(&0u16.to_le_bytes()); // nop
        }
        if insns_size % 2 == 1 {
            buf.extend_from_slice(&0u16.to_le_bytes()); // alignment padding
        }
        // Lay out the handler list first so each handler's real byte offset is
        // known before the try_item array references it.
        let mut list = Vec::new();
        uleb(handlers.len() as u32, &mut list);
        let mut handler_offsets: Vec<u16> = Vec::new();
        for (typed, catch_all) in handlers {
            handler_offsets.push(list.len() as u16);
            // sleb128 for small magnitudes: positive => typed only,
            // negative => typed plus catch-all.
            let size: i32 = if catch_all.is_some() {
                -(typed.len() as i32)
            } else {
                typed.len() as i32
            };
            list.push((size & 0x7f) as u8);
            for &(type_idx, addr) in typed {
                uleb(type_idx, &mut list);
                uleb(addr, &mut list);
            }
            if let Some(addr) = catch_all {
                uleb(*addr, &mut list);
            }
        }
        for &(start, count, handler_index) in tries {
            buf.extend_from_slice(&start.to_le_bytes());
            buf.extend_from_slice(&count.to_le_bytes());
            buf.extend_from_slice(&handler_offsets[handler_index].to_le_bytes());
        }
        buf.extend_from_slice(&list);
        (buf, handler_offsets)
    }

    #[test]
    fn parses_typed_handlers_and_catch_all() {
        let (data, _) = build_code_item(
            4,
            &[(0, 3, 0)],
            &[(vec![(7, 10), (8, 12)], Some(14))],
        );
        let reader = DexReader::new(&data);
        let item = parse_code_item(&reader, 0).expect("code item");
        assert_eq!(item.tries_size, 1);
        let exceptions = parse_exception_data(&reader, 0, &item).expect("exception data");
        assert_eq!(exceptions.tries.len(), 1);
        assert_eq!(exceptions.tries[0].start_addr, 0);
        assert_eq!(exceptions.tries[0].end_addr(), 3);
        assert!(exceptions.tries[0].covers(2));
        assert!(!exceptions.tries[0].covers(3));

        let handler = exceptions.handler_for(&exceptions.tries[0]).expect("handler");
        assert_eq!(handler.typed, vec![(7, 10), (8, 12)]);
        assert_eq!(handler.catch_all_addr, Some(14));
        assert_eq!(handler.addresses(), vec![10, 12, 14]);
    }

    #[test]
    fn positive_size_means_no_catch_all() {
        let (data, _) = build_code_item(2, &[(0, 2, 0)], &[(vec![(1, 5)], None)]);
        let reader = DexReader::new(&data);
        let item = parse_code_item(&reader, 0).unwrap();
        let exceptions = parse_exception_data(&reader, 0, &item).unwrap();
        let handler = exceptions.handler_for(&exceptions.tries[0]).unwrap();
        assert_eq!(handler.typed, vec![(1, 5)]);
        assert_eq!(handler.catch_all_addr, None);
    }

    /// An odd insns_size inserts a padding code unit before the try table.
    /// Getting this wrong shifts every try_item by two bytes.
    #[test]
    fn odd_insns_size_padding_is_honored() {
        let (data, _) = build_code_item(3, &[(1, 2, 0)], &[(vec![(4, 9)], None)]);
        let reader = DexReader::new(&data);
        let item = parse_code_item(&reader, 0).unwrap();
        let exceptions = parse_exception_data(&reader, 0, &item).unwrap();
        assert_eq!(exceptions.tries[0].start_addr, 1);
        assert_eq!(exceptions.tries[0].insn_count, 2);
        assert_eq!(
            exceptions.handler_for(&exceptions.tries[0]).unwrap().typed,
            vec![(4, 9)]
        );
    }

    /// handler_off is a byte offset into the list, not an index.
    #[test]
    fn handler_off_is_a_byte_offset() {
        let (data, offsets) = build_code_item(
            2,
            &[(0, 1, 0), (1, 1, 1)],
            &[(vec![(1, 6)], None), (vec![(2, 7)], None)],
        );
        let reader = DexReader::new(&data);
        let item = parse_code_item(&reader, 0).unwrap();
        let exceptions = parse_exception_data(&reader, 0, &item).unwrap();
        assert_eq!(exceptions.handlers.len(), 2);
        // The list starts with its ULEB128 size, so the first handler is at
        // byte offset 1 and the second follows it — offsets, not indices.
        assert_eq!(exceptions.handlers[0].offset, offsets[0]);
        assert_eq!(exceptions.handlers[1].offset, offsets[1]);
        assert_eq!(offsets[0], 1);
        assert!(offsets[1] > offsets[0]);
        assert_eq!(
            exceptions.handler_for(&exceptions.tries[1]).unwrap().typed,
            vec![(2, 7)]
        );
    }

    #[test]
    fn no_tries_returns_empty_without_reading_further() {
        let (data, _) = build_code_item(2, &[], &[]);
        let reader = DexReader::new(&data);
        let item = parse_code_item(&reader, 0).unwrap();
        let exceptions = parse_exception_data(&reader, 0, &item).unwrap();
        assert!(exceptions.is_empty());
    }

    #[test]
    fn sleb128_sign_extension() {
        let reader = DexReader::new(&[0x7f]); // -1
        assert_eq!(reader.sleb128_at(0).unwrap(), (-1, 1));
        let reader = DexReader::new(&[0x3f]); // 63
        assert_eq!(reader.sleb128_at(0).unwrap(), (63, 1));
        let reader = DexReader::new(&[0x40]); // -64
        assert_eq!(reader.sleb128_at(0).unwrap(), (-64, 1));
    }
}
