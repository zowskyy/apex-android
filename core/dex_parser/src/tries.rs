//! code_item try/catch tail parsing.

use crate::error::{DexError, Result};
use crate::reader::DexReader;

#[derive(Debug, Clone)]
pub struct TryItem {
    pub start_addr: u32,
    pub insn_count: u16,
    pub handler_off: u16,
}

#[derive(Debug, Clone)]
pub struct EncodedTypeAddrPair {
    pub type_idx: u32,
    pub addr: u32,
}

#[derive(Debug, Clone)]
pub struct EncodedCatchHandler {
    pub offset: u32,
    pub handlers: Vec<EncodedTypeAddrPair>,
    pub catch_all_addr: Option<u32>,
}

#[derive(Debug, Clone, Default)]
pub struct TryCatchInfo {
    pub tries: Vec<TryItem>,
    pub handlers: Vec<EncodedCatchHandler>,
}

const TRY_ITEM_CAP: u16 = 8192;
const CATCH_HANDLER_CAP: u32 = 1_000_000;

fn sleb128_at(r: &DexReader, offset: usize) -> Result<(i32, usize)> {
    let mut result: i32 = 0;
    let mut shift = 0u32;
    let mut pos = offset;
    let mut byte;
    loop {
        if shift >= 35 {
            return Err(DexError::MalformedUleb128(offset));
        }
        byte = r.u8_at(pos)?;
        pos += 1;
        result |= ((byte & 0x7f) as i32) << shift;
        shift += 7;
        if byte & 0x80 == 0 {
            break;
        }
    }
    if shift < 32 && byte & 0x40 != 0 {
        result |= !0 << shift;
    }
    Ok((result, pos - offset))
}

pub fn parse_try_catch_info(
    r: &DexReader,
    code_off: u32,
    insns_size: u32,
    tries_size: u16,
) -> Result<TryCatchInfo> {
    if tries_size == 0 {
        return Ok(TryCatchInfo::default());
    }
    if tries_size > TRY_ITEM_CAP {
        return Err(DexError::CountTooLarge {
            offset: code_off as usize + 6,
            count: tries_size as usize,
            cap: TRY_ITEM_CAP as usize,
        });
    }

    let insns_end = code_off as usize + 16 + insns_size as usize * 2;
    let tries_base = if insns_size % 2 == 1 {
        insns_end + 2
    } else {
        insns_end
    };
    let handlers_base = tries_base + tries_size as usize * 8;

    let mut tries = Vec::with_capacity(tries_size as usize);
    for i in 0..tries_size as usize {
        let entry = tries_base + i * 8;
        tries.push(TryItem {
            start_addr: r.u32_at(entry)?,
            insn_count: r.u16_at(entry + 4)?,
            handler_off: r.u16_at(entry + 6)?,
        });
    }

    let (handler_count, consumed) = r.uleb128_at(handlers_base)?;
    if handler_count > CATCH_HANDLER_CAP {
        return Err(DexError::CountTooLarge {
            offset: handlers_base,
            count: handler_count as usize,
            cap: CATCH_HANDLER_CAP as usize,
        });
    }
    let mut pos = handlers_base + consumed;
    let mut handlers = Vec::with_capacity(handler_count.min(4096) as usize);
    for _ in 0..handler_count {
        let relative_offset = (pos - handlers_base) as u32;
        let (size, c1) = sleb128_at(r, pos)?;
        pos += c1;
        let typed_count = size.unsigned_abs();
        if typed_count > CATCH_HANDLER_CAP {
            return Err(DexError::CountTooLarge {
                offset: pos,
                count: typed_count as usize,
                cap: CATCH_HANDLER_CAP as usize,
            });
        }
        let mut pairs = Vec::with_capacity(typed_count.min(4096) as usize);
        for _ in 0..typed_count {
            let (type_idx, c2) = r.uleb128_at(pos)?;
            pos += c2;
            let (addr, c3) = r.uleb128_at(pos)?;
            pos += c3;
            pairs.push(EncodedTypeAddrPair { type_idx, addr });
        }
        let catch_all_addr = if size <= 0 {
            let (addr, c4) = r.uleb128_at(pos)?;
            pos += c4;
            Some(addr)
        } else {
            None
        };
        handlers.push(EncodedCatchHandler {
            offset: relative_offset,
            handlers: pairs,
            catch_all_addr,
        });
    }

    Ok(TryCatchInfo { tries, handlers })
}
