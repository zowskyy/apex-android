use crate::access::access_flags_string;
use crate::class_data::EncodedMethod;
use crate::code::CodeUnit;
use crate::error::Result;
use crate::proto::{interface_descriptors, method_descriptor as build_method_descriptor};
use crate::reader::DexReader;
use crate::DexFile;

const INVOKE_OPCODES: [u8; 10] = [
    0x6e, // invoke-virtual
    0x6f, // invoke-super
    0x70, // invoke-direct
    0x71, // invoke-static
    0x72, // invoke-interface
    0x74, // invoke-virtual/range
    0x75, // invoke-super/range
    0x76, // invoke-direct/range
    0x77, // invoke-static/range
    0x78, // invoke-interface/range
];

#[derive(Debug, Clone)]
pub struct ClassMeta {
    pub dex: String,
    pub name: String,
    pub descriptor: String,
    pub super_descriptor: String,
    pub interfaces: Vec<String>,
    pub access: String,
    pub source_file_index: i32,
}

#[derive(Debug, Clone)]
pub struct MethodMeta {
    pub dex: String,
    pub class_name: String,
    pub name: String,
    pub descriptor: String,
    pub access: String,
    pub has_code: bool,
    pub instruction_count: u32,
    pub code_off: u32,
}

#[derive(Debug, Clone)]
pub struct EdgeMeta {
    pub caller_class: String,
    pub caller_method: String,
    pub callee: String,
    pub offset: u32,
}

#[derive(Debug, Clone)]
pub struct DexMetadata {
    pub dex: String,
    pub classes: Vec<ClassMeta>,
    pub methods: Vec<MethodMeta>,
    pub strings: Vec<String>,
    pub edges: Vec<EdgeMeta>,
}

fn descriptor_to_java(descriptor: &str) -> String {
    if descriptor.is_empty() {
        return String::new();
    }
    if descriptor.starts_with('L') && descriptor.ends_with(';') {
        return descriptor[1..descriptor.len() - 1].replace('/', ".");
    }
    match descriptor {
        "Z" => "boolean".to_string(),
        "B" => "byte".to_string(),
        "S" => "short".to_string(),
        "C" => "char".to_string(),
        "I" => "int".to_string(),
        "J" => "long".to_string(),
        "F" => "float".to_string(),
        "D" => "double".to_string(),
        "V" => "void".to_string(),
        _ => {
            if descriptor.starts_with('[') {
                return format!("{}[]", descriptor_to_java(&descriptor[1..]));
            }
            descriptor.to_string()
        }
    }
}

fn method_id_entry(dex: &DexFile<'_>, method_idx: u32) -> Result<(u32, u32, u32)> {
    let r = DexReader::new(dex.data);
    let entry = dex.header.method_ids_off as usize + (method_idx as usize) * 8;
    let class_idx = r.u16_at(entry)? as u32;
    let proto_idx = r.u16_at(entry + 2)? as u32;
    let name_idx = r.u32_at(entry + 4)?;
    Ok((class_idx, proto_idx, name_idx))
}

fn method_callee(dex: &DexFile<'_>, method_ids_index: u32) -> Option<String> {
    let (class_idx, proto_idx, name_idx) = method_id_entry(dex, method_ids_index).ok()?;
    let class_descriptor = dex.type_name(class_idx)?;
    let class_name = descriptor_to_java(class_descriptor);
    let name = dex.strings.get(name_idx as usize).map(|s| s.as_str()).unwrap_or("");
    let descriptor = build_method_descriptor(dex, proto_idx).unwrap_or_else(|_| "()".to_string());
    Some(format!("{class_name}::{name}{descriptor}"))
}

fn invoke_edges(
    dex: &DexFile<'_>,
    caller_class: &str,
    caller_method: &str,
    encoded: &EncodedMethod,
) -> Result<Vec<EdgeMeta>> {
    if encoded.code_off == 0 {
        return Ok(Vec::new());
    }
    let (item, units) = dex.decode_method(encoded.code_off)?;
    let mut edges = Vec::new();
    for unit in units {
        let insn = match unit {
            CodeUnit::Insn(i) => i,
            _ => continue,
        };
        if !INVOKE_OPCODES.contains(&insn.opcode) {
            continue;
        }
        if let Some(method_ids_index) = insn.index {
            if let Some(callee) = method_callee(dex, method_ids_index) {
                edges.push(EdgeMeta {
                    caller_class: caller_class.to_string(),
                    caller_method: caller_method.to_string(),
                    callee,
                    offset: insn.code_unit_offset,
                });
            }
        }
    }
    // Silence unused variable warning for registers_size etc. — item is parsed for integrity.
    let _ = item.registers_size;
    Ok(edges)
}

pub fn build_metadata(dex: &DexFile<'_>, dex_name: &str) -> Result<DexMetadata> {
    let mut classes = Vec::with_capacity(dex.class_defs.len());
    let mut methods = Vec::new();
    let mut edges = Vec::new();

    for def in &dex.class_defs {
        let descriptor = dex.type_name(def.class_idx).unwrap_or("").to_string();
        let class_name = descriptor_to_java(&descriptor);
        let super_descriptor = if def.superclass_idx == 0 {
            String::new()
        } else {
            dex.type_name(def.superclass_idx).unwrap_or("").to_string()
        };
        let interfaces = interface_descriptors(dex, def.interfaces_off)?
            .into_iter()
            .map(|item| descriptor_to_java(&item))
            .collect();

        classes.push(ClassMeta {
            dex: dex_name.to_string(),
            name: class_name.clone(),
            descriptor,
            super_descriptor,
            interfaces,
            access: access_flags_string(def.access_flags),
            source_file_index: def.source_file_idx as i32,
        });

        if def.class_data_off == 0 {
            continue;
        }
        let data = dex.class_data(def)?;
        for encoded in data
            .direct_methods
            .iter()
            .chain(data.virtual_methods.iter())
        {
            let (class_idx, proto_idx, name_idx) = method_id_entry(dex, encoded.method_idx)?;
            let method_name = dex.strings.get(name_idx as usize).map(|s| s.as_str()).unwrap_or("");
            let method_descriptor = build_method_descriptor(dex, proto_idx)?;
            let instruction_count = if encoded.code_off == 0 {
                0
            } else {
                let (_, units) = dex.decode_method(encoded.code_off)?;
                units
                    .iter()
                    .filter(|unit| matches!(unit, CodeUnit::Insn(_)))
                    .count() as u32
            };

            methods.push(MethodMeta {
                dex: dex_name.to_string(),
                class_name: descriptor_to_java(dex.type_name(class_idx).unwrap_or("")),
                name: method_name.to_string(),
                descriptor: method_descriptor,
                access: access_flags_string(encoded.access_flags),
                has_code: encoded.code_off != 0,
                instruction_count,
                code_off: encoded.code_off,
            });

            edges.extend(invoke_edges(dex, &class_name, method_name, encoded)?);
        }
    }

    let strings: Vec<String> = dex
        .strings
        .iter()
        .take(50_000)
        .map(|value| value.clone())
        .collect();

    Ok(DexMetadata {
        dex: dex_name.to_string(),
        classes,
        methods,
        strings,
        edges,
    })
}
