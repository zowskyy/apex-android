//! encoded_value / encoded_array parsing for class static values.

use crate::error::{DexError, Result};
use crate::reader::DexReader;

#[derive(Debug, Clone, PartialEq)]
pub enum EncodedValue {
    Byte(i8),
    Short(i16),
    Char(u16),
    Int(i32),
    Long(i64),
    Float(f32),
    Double(f64),
    MethodType(u32),
    MethodHandle(u32),
    String(u32),
    Type(u32),
    Field(u32),
    Method(u32),
    Enum(u32),
    Array(Vec<EncodedValue>),
    Annotation(EncodedAnnotation),
    Null,
    Boolean(bool),
}

#[derive(Debug, Clone, PartialEq)]
pub struct EncodedAnnotation {
    pub type_idx: u32,
    pub elements: Vec<AnnotationElement>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct AnnotationElement {
    pub name_idx: u32,
    pub value: EncodedValue,
}

const ENCODED_ARRAY_CAP: u32 = 1_000_000;
const ENCODED_RECURSION_CAP: usize = 64;

fn sign_extend(value: u64, bits: usize) -> i64 {
    let shift = 64usize.saturating_sub(bits);
    ((value << shift) as i64) >> shift
}

fn read_sized_value(r: &DexReader, pos: &mut usize, byte_count: usize) -> Result<u64> {
    let mut value = 0u64;
    for i in 0..byte_count {
        value |= (r.u8_at(*pos + i)? as u64) << (i * 8);
    }
    *pos += byte_count;
    Ok(value)
}

fn parse_value(r: &DexReader, pos: &mut usize, depth: usize) -> Result<EncodedValue> {
    if depth > ENCODED_RECURSION_CAP {
        return Err(DexError::CountTooLarge {
            offset: *pos,
            count: depth,
            cap: ENCODED_RECURSION_CAP,
        });
    }
    let header = r.u8_at(*pos)?;
    *pos += 1;
    let value_type = header & 0x1f;
    let value_arg = (header >> 5) as usize;
    let byte_count = value_arg + 1;

    Ok(match value_type {
        0x00 => EncodedValue::Byte(sign_extend(
            read_sized_value(r, pos, byte_count)?,
            byte_count * 8,
        ) as i8),
        0x02 => EncodedValue::Short(sign_extend(
            read_sized_value(r, pos, byte_count)?,
            byte_count * 8,
        ) as i16),
        0x03 => EncodedValue::Char(read_sized_value(r, pos, byte_count)? as u16),
        0x04 => EncodedValue::Int(
            sign_extend(read_sized_value(r, pos, byte_count)?, byte_count * 8) as i32,
        ),
        0x06 => EncodedValue::Long(sign_extend(
            read_sized_value(r, pos, byte_count)?,
            byte_count * 8,
        )),
        0x10 => {
            let bits = read_sized_value(r, pos, byte_count)? << ((4 - byte_count) * 8);
            EncodedValue::Float(f32::from_bits(bits as u32))
        }
        0x11 => {
            let bits = read_sized_value(r, pos, byte_count)? << ((8 - byte_count) * 8);
            EncodedValue::Double(f64::from_bits(bits))
        }
        0x15 => EncodedValue::MethodType(read_sized_value(r, pos, byte_count)? as u32),
        0x16 => EncodedValue::MethodHandle(read_sized_value(r, pos, byte_count)? as u32),
        0x17 => EncodedValue::String(read_sized_value(r, pos, byte_count)? as u32),
        0x18 => EncodedValue::Type(read_sized_value(r, pos, byte_count)? as u32),
        0x19 => EncodedValue::Field(read_sized_value(r, pos, byte_count)? as u32),
        0x1a => EncodedValue::Method(read_sized_value(r, pos, byte_count)? as u32),
        0x1b => EncodedValue::Enum(read_sized_value(r, pos, byte_count)? as u32),
        0x1c => EncodedValue::Array(parse_array_at_pos(r, pos, depth + 1)?),
        0x1d => {
            let (type_idx, c1) = r.uleb128_at(*pos)?;
            *pos += c1;
            let (size, c2) = r.uleb128_at(*pos)?;
            *pos += c2;
            if size > ENCODED_ARRAY_CAP {
                return Err(DexError::CountTooLarge {
                    offset: *pos,
                    count: size as usize,
                    cap: ENCODED_ARRAY_CAP as usize,
                });
            }
            let mut elements = Vec::with_capacity(size.min(4096) as usize);
            for _ in 0..size {
                let (name_idx, c3) = r.uleb128_at(*pos)?;
                *pos += c3;
                elements.push(AnnotationElement {
                    name_idx,
                    value: parse_value(r, pos, depth + 1)?,
                });
            }
            EncodedValue::Annotation(EncodedAnnotation { type_idx, elements })
        }
        0x1e => EncodedValue::Null,
        0x1f => EncodedValue::Boolean(value_arg != 0),
        _ => return Err(DexError::MalformedUleb128(*pos - 1)),
    })
}

fn parse_array_at_pos(r: &DexReader, pos: &mut usize, depth: usize) -> Result<Vec<EncodedValue>> {
    let (size, consumed) = r.uleb128_at(*pos)?;
    if size > ENCODED_ARRAY_CAP {
        return Err(DexError::CountTooLarge {
            offset: *pos,
            count: size as usize,
            cap: ENCODED_ARRAY_CAP as usize,
        });
    }
    *pos += consumed;
    let mut values = Vec::with_capacity(size.min(4096) as usize);
    for _ in 0..size {
        values.push(parse_value(r, pos, depth)?);
    }
    Ok(values)
}

pub fn parse_encoded_array(r: &DexReader, off: u32) -> Result<Vec<EncodedValue>> {
    if off == 0 {
        return Ok(Vec::new());
    }
    let mut pos = off as usize;
    parse_array_at_pos(r, &mut pos, 0)
}

impl EncodedValue {
    pub fn int_value(&self) -> Option<i64> {
        match self {
            EncodedValue::Byte(v) => Some(*v as i64),
            EncodedValue::Short(v) => Some(*v as i64),
            EncodedValue::Char(v) => Some(*v as i64),
            EncodedValue::Int(v) => Some(*v as i64),
            EncodedValue::Long(v) => Some(*v),
            _ => None,
        }
    }
}
