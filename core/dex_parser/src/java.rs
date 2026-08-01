//! Class-level Java emission over reconstructed DEX method bodies.

use std::collections::BTreeMap;
use std::sync::Arc;

use rayon::prelude::*;

use crate::class_data::{ClassData, EncodedField, EncodedMethod};
use crate::class_def::ClassDef;
use crate::decompile::{decompile_method_statements, emit_stmt};
use crate::encoded::{parse_encoded_array, EncodedValue};
use crate::ids::{access_flags_to_java, descriptor_simple_name, java_type, short_name};
use crate::reader::DexReader;
use crate::DexFile;

#[derive(Debug, Clone)]
pub struct ClassSummary {
    pub descriptor: String,
    pub name: String,
    pub superclass: Option<String>,
    pub direct_methods: usize,
    pub virtual_methods: usize,
    pub static_fields: usize,
    pub instance_fields: usize,
}

pub fn decompile_class(dex: &DexFile<'_>, def: &ClassDef) -> String {
    let resources = build_resource_map(dex);
    decompile_class_with_resources(dex, def, &resources)
}

fn decompile_class_with_resources(
    dex: &DexFile<'_>,
    def: &ClassDef,
    resources: &BTreeMap<i64, String>,
) -> String {
    let descriptor = dex.type_name(def.class_idx).unwrap_or("");
    let class_name = descriptor_simple_name(descriptor);
    let mut out = Vec::new();

    let access = class_access_flags(def.access_flags);
    let kind = if def.access_flags & 0x0200 != 0 {
        "interface"
    } else {
        "class"
    };
    let mut header = if access.is_empty() {
        format!("{kind} {class_name}")
    } else {
        format!("{access} {kind} {class_name}")
    };

    if kind == "class" {
        if let Some(super_desc) = dex.type_name(def.superclass_idx) {
            if super_desc != "Ljava/lang/Object;" {
                header.push_str(&format!(" extends {}", short_name(super_desc)));
            }
        }
    }

    if let Ok(interfaces) = dex.interfaces(def) {
        if !interfaces.is_empty() {
            let names = interfaces
                .iter()
                .map(|name| short_name(name))
                .collect::<Vec<_>>()
                .join(", ");
            header.push_str(if kind == "interface" {
                " extends "
            } else {
                " implements "
            });
            header.push_str(&names);
        }
    }

    out.push(format!("{header} {{"));
    match dex.class_data(def) {
        Ok(data) => emit_class_data(dex, def, &data, resources, &class_name, &mut out),
        Err(err) => out.push(format!("    // class_data parse failed: {err}")),
    }
    out.push("}".to_string());
    out.join("\n")
}

pub fn decompile_all(dex: &DexFile<'_>) -> Vec<(String, String)> {
    let resources = Arc::new(build_resource_map(dex));
    dex.class_defs
        .par_iter()
        .map(|def| {
            let name = dex
                .type_name(def.class_idx)
                .map(java_type)
                .unwrap_or_default();
            (
                name,
                decompile_class_with_resources(dex, def, resources.as_ref()),
            )
        })
        .collect()
}

pub fn build_resource_map(dex: &DexFile<'_>) -> BTreeMap<i64, String> {
    let mut resources = BTreeMap::new();
    let r = DexReader::new(dex.data);
    for def in &dex.class_defs {
        let Some(descriptor) = dex.type_name(def.class_idx) else {
            continue;
        };
        let Some(resource_type) = resource_type_from_descriptor(descriptor) else {
            continue;
        };
        let Ok(data) = dex.class_data(def) else {
            continue;
        };
        let Ok(values) = parse_encoded_array(&r, def.static_values_off) else {
            continue;
        };
        for (field, value) in data.static_fields.iter().zip(values.iter()) {
            let Some(int_value) = value.int_value() else {
                continue;
            };
            let Ok(field_ref) = dex.field_ref(field.field_idx) else {
                continue;
            };
            resources.insert(int_value, format!("R.{resource_type}.{}", field_ref.name));
        }
    }
    resources
}

pub fn class_summaries(dex: &DexFile<'_>) -> Vec<ClassSummary> {
    dex.class_defs
        .iter()
        .map(|def| {
            let data = dex.class_data(def).unwrap_or_default();
            let descriptor = dex.type_name(def.class_idx).unwrap_or("").to_string();
            ClassSummary {
                name: java_type(&descriptor),
                descriptor,
                superclass: dex.type_name(def.superclass_idx).map(java_type),
                direct_methods: data.direct_methods.len(),
                virtual_methods: data.virtual_methods.len(),
                static_fields: data.static_fields.len(),
                instance_fields: data.instance_fields.len(),
            }
        })
        .collect()
}

fn emit_class_data(
    dex: &DexFile<'_>,
    def: &ClassDef,
    data: &ClassData,
    resources: &BTreeMap<i64, String>,
    class_name: &str,
    out: &mut Vec<String>,
) {
    let r = DexReader::new(dex.data);
    let static_values = parse_encoded_array(&r, def.static_values_off).unwrap_or_default();
    let mut emitted_member = false;

    for (idx, field) in data.static_fields.iter().enumerate() {
        if let Some(line) = emit_field(dex, field, static_values.get(idx), true) {
            out.push(format!("    {line}"));
            emitted_member = true;
        }
    }
    for field in &data.instance_fields {
        if let Some(line) = emit_field(dex, field, None, false) {
            out.push(format!("    {line}"));
            emitted_member = true;
        }
    }

    let methods = data
        .direct_methods
        .iter()
        .chain(data.virtual_methods.iter())
        .collect::<Vec<_>>();
    for method in methods {
        if method_name(dex, method) == "<clinit>" {
            continue;
        }
        if emitted_member {
            out.push(String::new());
        }
        emit_method(dex, def, method, resources, class_name, out);
        emitted_member = true;
    }
}

fn emit_field(
    dex: &DexFile<'_>,
    field: &EncodedField,
    value: Option<&EncodedValue>,
    is_static: bool,
) -> Option<String> {
    let field_ref = dex.field_ref(field.field_idx).ok()?;
    let mut access = access_flags_to_java(field.access_flags);
    if is_static && !access.split_whitespace().any(|part| part == "static") {
        if access.is_empty() {
            access.push_str("static");
        } else {
            access.push_str(" static");
        }
    }
    let ty = short_name(&field_ref.type_name);
    let mut line = if access.is_empty() {
        format!("{ty} {}", field_ref.name)
    } else {
        format!("{access} {ty} {}", field_ref.name)
    };
    if let Some(value) = value {
        if let Some(rendered) = render_encoded_value(dex, value) {
            line.push_str(" = ");
            line.push_str(&rendered);
        }
    }
    line.push(';');
    Some(line)
}

fn emit_method(
    dex: &DexFile<'_>,
    def: &ClassDef,
    method: &EncodedMethod,
    resources: &BTreeMap<i64, String>,
    class_name: &str,
    out: &mut Vec<String>,
) {
    let Ok(method_ref) = dex.method_ref(method.method_idx) else {
        out.push("    // unresolved method".to_string());
        return;
    };
    let signature = method_signature(method.access_flags, &method_ref, class_name);
    if method.code_off == 0 {
        out.push(format!("    {signature};"));
        return;
    }

    out.push(format!("    {signature} {{"));
    match decompile_method_statements(dex, def, method, resources) {
        Ok(statements) => {
            for stmt in &statements {
                if let Some(line) = emit_stmt(stmt, resources) {
                    out.push(format!("        {line}"));
                }
            }
        }
        Err(err) => out.push(format!("        // decompile failed: {err}")),
    }
    out.push("    }".to_string());
}

fn method_signature(flags: u32, method: &crate::ids::MethodRef, class_name: &str) -> String {
    let access = access_flags_to_java(flags);
    let params = method
        .parameters
        .iter()
        .enumerate()
        .map(|(idx, ty)| format!("{} p{idx}", short_name(ty)))
        .collect::<Vec<_>>()
        .join(", ");

    let base = if method.name == "<init>" {
        format!("{class_name}({params})")
    } else {
        format!(
            "{} {}({params})",
            short_name(&method.return_type),
            method.name
        )
    };
    if access.is_empty() {
        base
    } else {
        format!("{access} {base}")
    }
}

fn method_name(dex: &DexFile<'_>, method: &EncodedMethod) -> String {
    dex.method_name(method.method_idx).unwrap_or("").to_string()
}

fn class_access_flags(flags: u32) -> String {
    let mut parts = Vec::new();
    if flags & 0x0001 != 0 {
        parts.push("public");
    } else if flags & 0x0004 != 0 {
        parts.push("protected");
    } else if flags & 0x0002 != 0 {
        parts.push("private");
    }
    if flags & 0x0010 != 0 {
        parts.push("final");
    }
    if flags & 0x0400 != 0 {
        parts.push("abstract");
    }
    parts.join(" ")
}

fn render_encoded_value(dex: &DexFile<'_>, value: &EncodedValue) -> Option<String> {
    match value {
        EncodedValue::Byte(v) => Some(v.to_string()),
        EncodedValue::Short(v) => Some(v.to_string()),
        EncodedValue::Char(v) => Some(format!("'{}'", char::from_u32(*v as u32).unwrap_or('\0'))),
        EncodedValue::Int(v) => Some(v.to_string()),
        EncodedValue::Long(v) => Some(format!("{v}L")),
        EncodedValue::Float(v) => Some(format!("{v:?}f")),
        EncodedValue::Double(v) => Some(format!("{v:?}d")),
        EncodedValue::String(idx) => dex.strings.get(*idx as usize).map(|s| format!("\"{s}\"")),
        EncodedValue::Type(idx) => dex
            .type_name(*idx)
            .map(|ty| format!("{}.class", short_name(ty))),
        EncodedValue::Null => Some("null".to_string()),
        EncodedValue::Boolean(v) => Some(v.to_string()),
        _ => None,
    }
}

fn resource_type_from_descriptor(descriptor: &str) -> Option<String> {
    let inner = descriptor.strip_suffix(';')?.rsplit_once("$")?.1;
    if inner.is_empty() || inner == "styleable" {
        None
    } else {
        Some(inner.replace('$', "."))
    }
}
