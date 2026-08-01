//! Resolved DEX id tables and Java-friendly name helpers.

use crate::class_def::ClassDef;
use crate::error::{DexError, Result};
use crate::reader::DexReader;
use crate::DexFile;

#[derive(Debug, Clone)]
pub struct ProtoId {
    pub shorty_idx: u32,
    pub return_type_idx: u32,
    pub parameters_off: u32,
}

#[derive(Debug, Clone)]
pub struct FieldId {
    pub class_idx: u16,
    pub type_idx: u16,
    pub name_idx: u32,
}

#[derive(Debug, Clone)]
pub struct MethodId {
    pub class_idx: u16,
    pub proto_idx: u16,
    pub name_idx: u32,
}

#[derive(Debug, Clone)]
pub struct ProtoRef {
    pub shorty: String,
    pub return_descriptor: String,
    pub return_type: String,
    pub parameter_descriptors: Vec<String>,
    pub parameters: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct FieldRef {
    pub class_descriptor: String,
    pub class_name: String,
    pub type_descriptor: String,
    pub type_name: String,
    pub name: String,
}

#[derive(Debug, Clone)]
pub struct MethodRef {
    pub class_descriptor: String,
    pub class_name: String,
    pub name: String,
    pub proto_idx: u16,
    pub return_descriptor: String,
    pub return_type: String,
    pub parameter_descriptors: Vec<String>,
    pub parameters: Vec<String>,
}

const ID_ITEM_CAP: usize = 8_000_000;
const TYPE_LIST_CAP: u32 = 1_000_000;

pub fn parse_proto_ids(r: &DexReader, off: u32, count: u32) -> Result<Vec<ProtoId>> {
    let count = count as usize;
    if count > ID_ITEM_CAP {
        return Err(DexError::CountTooLarge {
            offset: off as usize,
            count,
            cap: ID_ITEM_CAP,
        });
    }
    let mut ids = Vec::with_capacity(count.min(4096));
    let base = off as usize;
    for i in 0..count {
        let entry = base + i * 12;
        ids.push(ProtoId {
            shorty_idx: r.u32_at(entry)?,
            return_type_idx: r.u32_at(entry + 4)?,
            parameters_off: r.u32_at(entry + 8)?,
        });
    }
    Ok(ids)
}

pub fn parse_field_ids(r: &DexReader, off: u32, count: u32) -> Result<Vec<FieldId>> {
    let count = count as usize;
    if count > ID_ITEM_CAP {
        return Err(DexError::CountTooLarge {
            offset: off as usize,
            count,
            cap: ID_ITEM_CAP,
        });
    }
    let mut ids = Vec::with_capacity(count.min(4096));
    let base = off as usize;
    for i in 0..count {
        let entry = base + i * 8;
        ids.push(FieldId {
            class_idx: r.u16_at(entry)?,
            type_idx: r.u16_at(entry + 2)?,
            name_idx: r.u32_at(entry + 4)?,
        });
    }
    Ok(ids)
}

pub fn parse_method_ids(r: &DexReader, off: u32, count: u32) -> Result<Vec<MethodId>> {
    let count = count as usize;
    if count > ID_ITEM_CAP {
        return Err(DexError::CountTooLarge {
            offset: off as usize,
            count,
            cap: ID_ITEM_CAP,
        });
    }
    let mut ids = Vec::with_capacity(count.min(4096));
    let base = off as usize;
    for i in 0..count {
        let entry = base + i * 8;
        ids.push(MethodId {
            class_idx: r.u16_at(entry)?,
            proto_idx: r.u16_at(entry + 2)?,
            name_idx: r.u32_at(entry + 4)?,
        });
    }
    Ok(ids)
}

pub fn parse_type_list(r: &DexReader, off: u32) -> Result<Vec<u16>> {
    if off == 0 {
        return Ok(Vec::new());
    }
    let count = r.u32_at(off as usize)?;
    if count > TYPE_LIST_CAP {
        return Err(DexError::CountTooLarge {
            offset: off as usize,
            count: count as usize,
            cap: TYPE_LIST_CAP as usize,
        });
    }
    let mut out = Vec::with_capacity(count.min(4096) as usize);
    let base = off as usize + 4;
    for i in 0..count as usize {
        out.push(r.u16_at(base + i * 2)?);
    }
    Ok(out)
}

pub fn java_type(descriptor: &str) -> String {
    let mut array_depth = 0usize;
    let mut rest = descriptor;
    while let Some(stripped) = rest.strip_prefix('[') {
        array_depth += 1;
        rest = stripped;
    }

    let base = match rest {
        "V" => "void".to_string(),
        "Z" => "boolean".to_string(),
        "B" => "byte".to_string(),
        "S" => "short".to_string(),
        "C" => "char".to_string(),
        "I" => "int".to_string(),
        "J" => "long".to_string(),
        "F" => "float".to_string(),
        "D" => "double".to_string(),
        obj if obj.starts_with('L') && obj.ends_with(';') => {
            obj[1..obj.len() - 1].replace(['/', '$'], ".")
        }
        other => other.to_string(),
    };

    if array_depth == 0 {
        base
    } else {
        format!("{}{}", base, "[]".repeat(array_depth))
    }
}

pub fn short_name(name_or_descriptor: &str) -> String {
    let java = if name_or_descriptor.starts_with('L') || name_or_descriptor.starts_with('[') {
        java_type(name_or_descriptor)
    } else {
        name_or_descriptor.to_string()
    };

    if let Some(array_base) = java.strip_suffix("[]") {
        return format!("{}[]", short_name(array_base));
    }
    java.rsplit('.').next().unwrap_or(&java).to_string()
}

pub fn descriptor_simple_name(descriptor: &str) -> String {
    let trimmed = descriptor.trim_start_matches('L').trim_end_matches(';');
    trimmed
        .rsplit('/')
        .next()
        .unwrap_or(trimmed)
        .rsplit('$')
        .next()
        .unwrap_or(trimmed)
        .to_string()
}

pub fn access_flags_to_java(flags: u32) -> String {
    let mut parts = Vec::new();
    if flags & 0x0001 != 0 {
        parts.push("public");
    } else if flags & 0x0004 != 0 {
        parts.push("protected");
    } else if flags & 0x0002 != 0 {
        parts.push("private");
    }
    if flags & 0x0008 != 0 {
        parts.push("static");
    }
    if flags & 0x0010 != 0 {
        parts.push("final");
    }
    if flags & 0x0400 != 0 {
        parts.push("abstract");
    }
    parts.join(" ")
}

impl<'a> DexFile<'a> {
    pub fn proto(&self, proto_idx: u32) -> Result<ProtoRef> {
        let proto = self
            .proto_ids
            .get(proto_idx as usize)
            .ok_or(DexError::Truncated {
                offset: self.header.proto_ids_off as usize + proto_idx as usize * 12,
                needed: 12,
                len: self.data.len(),
            })?;
        let r = DexReader::new(self.data);
        let shorty = self
            .strings
            .get(proto.shorty_idx as usize)
            .cloned()
            .unwrap_or_default();
        let return_descriptor = self
            .type_name(proto.return_type_idx)
            .unwrap_or("")
            .to_string();
        let parameter_type_ids = parse_type_list(&r, proto.parameters_off)?;
        let mut parameter_descriptors = Vec::with_capacity(parameter_type_ids.len());
        let mut parameters = Vec::with_capacity(parameter_type_ids.len());
        for type_idx in parameter_type_ids {
            let descriptor = self.type_name(type_idx as u32).unwrap_or("").to_string();
            parameters.push(java_type(&descriptor));
            parameter_descriptors.push(descriptor);
        }
        Ok(ProtoRef {
            shorty,
            return_type: java_type(&return_descriptor),
            return_descriptor,
            parameter_descriptors,
            parameters,
        })
    }

    pub fn field_ref(&self, field_idx: u32) -> Result<FieldRef> {
        let field = self
            .field_ids
            .get(field_idx as usize)
            .ok_or(DexError::Truncated {
                offset: self.header.field_ids_off as usize + field_idx as usize * 8,
                needed: 8,
                len: self.data.len(),
            })?;
        let class_descriptor = self
            .type_name(field.class_idx as u32)
            .unwrap_or("")
            .to_string();
        let type_descriptor = self
            .type_name(field.type_idx as u32)
            .unwrap_or("")
            .to_string();
        Ok(FieldRef {
            class_name: java_type(&class_descriptor),
            class_descriptor,
            type_name: java_type(&type_descriptor),
            type_descriptor,
            name: self
                .strings
                .get(field.name_idx as usize)
                .cloned()
                .unwrap_or_default(),
        })
    }

    pub fn method_ref(&self, method_idx: u32) -> Result<MethodRef> {
        let method = self
            .method_ids
            .get(method_idx as usize)
            .ok_or(DexError::Truncated {
                offset: self.header.method_ids_off as usize + method_idx as usize * 8,
                needed: 8,
                len: self.data.len(),
            })?;
        let proto = self.proto(method.proto_idx as u32)?;
        let class_descriptor = self
            .type_name(method.class_idx as u32)
            .unwrap_or("")
            .to_string();
        Ok(MethodRef {
            class_name: java_type(&class_descriptor),
            class_descriptor,
            name: self
                .strings
                .get(method.name_idx as usize)
                .cloned()
                .unwrap_or_default(),
            proto_idx: method.proto_idx,
            return_descriptor: proto.return_descriptor,
            return_type: proto.return_type,
            parameter_descriptors: proto.parameter_descriptors,
            parameters: proto.parameters,
        })
    }

    pub fn interfaces(&self, def: &ClassDef) -> Result<Vec<String>> {
        let r = DexReader::new(self.data);
        let type_ids = parse_type_list(&r, def.interfaces_off)?;
        Ok(type_ids
            .into_iter()
            .filter_map(|idx| self.type_name(idx as u32))
            .map(java_type)
            .collect())
    }
}
