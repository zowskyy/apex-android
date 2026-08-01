//! Android binary XML (`AndroidManifest.xml`, `res/*.xml`) decoder.

use std::collections::BTreeSet;

use crate::error::{ArscError, Result};
use crate::reader::{read_chunk_header, ArscReader};
use crate::string_pool::{parse_string_pool, StringPool};
use crate::value::{
    Value, TYPE_ATTRIBUTE, TYPE_DIMENSION, TYPE_DYNAMIC_ATTRIBUTE, TYPE_DYNAMIC_REFERENCE,
    TYPE_FLOAT, TYPE_FRACTION, TYPE_INT_BOOLEAN, TYPE_INT_COLOR_ARGB4, TYPE_INT_COLOR_ARGB8,
    TYPE_INT_COLOR_RGB4, TYPE_INT_COLOR_RGB8, TYPE_INT_DEC, TYPE_INT_HEX, TYPE_NULL,
    TYPE_REFERENCE, TYPE_STRING,
};

pub const RES_XML_TYPE: u16 = 0x0003;
const RES_XML_RESOURCE_MAP_TYPE: u16 = 0x0180;
const RES_XML_START_NAMESPACE_TYPE: u16 = 0x0100;
const RES_XML_END_NAMESPACE_TYPE: u16 = 0x0101;
const RES_XML_START_ELEMENT_TYPE: u16 = 0x0102;
const RES_XML_END_ELEMENT_TYPE: u16 = 0x0103;
const RES_XML_CDATA_TYPE: u16 = 0x0104;

const NO_INDEX: u32 = u32::MAX;
const NODE_HEADER_SIZE: usize = 16;
const START_ELEMENT_EXT_SIZE: usize = 20;
const ATTRIBUTE_SIZE: usize = 20;
const MAX_ATTRIBUTES: u16 = 16_384;
const ANDROID_URI: &str = "http://schemas.android.com/apk/res/android";

#[derive(Debug, Clone)]
struct Namespace {
    prefix: String,
    uri: String,
}

#[derive(Debug)]
struct Attribute {
    namespace_uri: Option<String>,
    name: String,
    value: String,
}

#[derive(Debug)]
struct PendingElement {
    name: String,
    start: String,
}

pub fn is_binary_xml(data: &[u8]) -> bool {
    data.len() >= 8 && u16::from_le_bytes([data[0], data[1]]) == RES_XML_TYPE
}

pub fn axml_strings(data: &[u8]) -> Result<Vec<String>> {
    let r = ArscReader::new(data);
    let header = read_chunk_header(&r, 0)?;
    if header.chunk_type != RES_XML_TYPE {
        return Err(ArscError::UnexpectedChunkType {
            offset: 0,
            expected: RES_XML_TYPE,
            got: header.chunk_type,
        });
    }
    let pool = parse_string_pool(&r, header.header_size as usize)?;
    Ok(pool.strings)
}

pub fn decode_axml(data: &[u8]) -> Result<String> {
    let r = ArscReader::new(data);
    let tree_header = read_chunk_header(&r, 0)?;
    if tree_header.chunk_type != RES_XML_TYPE {
        return Err(ArscError::UnexpectedChunkType {
            offset: 0,
            expected: RES_XML_TYPE,
            got: tree_header.chunk_type,
        });
    }

    let string_pool_offset = tree_header.header_size as usize;
    let string_pool = parse_string_pool(&r, string_pool_offset)?;
    let mut resource_map = Vec::new();
    let mut offset = string_pool_offset + string_pool.chunk_size as usize;
    let end = tree_header.size as usize;

    let mut out = String::new();
    let mut stack: Vec<String> = Vec::new();
    let mut pending_element: Option<PendingElement> = None;
    let mut namespaces: Vec<Namespace> = Vec::new();
    let mut pending_namespaces: Vec<Namespace> = Vec::new();

    while offset < end {
        let chunk = read_chunk_header(&r, offset)?;
        match chunk.chunk_type {
            RES_XML_RESOURCE_MAP_TYPE => {
                resource_map = parse_resource_map(
                    &r,
                    offset,
                    chunk.header_size as usize,
                    chunk.size as usize,
                )?;
            }
            RES_XML_START_NAMESPACE_TYPE => {
                let ns = parse_namespace(&r, &string_pool, offset)?;
                namespaces.push(ns.clone());
                pending_namespaces.push(ns);
            }
            RES_XML_END_NAMESPACE_TYPE => {
                let ns = parse_namespace(&r, &string_pool, offset)?;
                if let Some(pos) = namespaces
                    .iter()
                    .rposition(|active| active.prefix == ns.prefix && active.uri == ns.uri)
                {
                    namespaces.remove(pos);
                }
            }
            RES_XML_START_ELEMENT_TYPE => {
                flush_pending_open(&mut out, &mut stack, &mut pending_element);
                let pending_ns = std::mem::take(&mut pending_namespaces);
                let element = parse_start_element(
                    &r,
                    &string_pool,
                    &resource_map,
                    &namespaces,
                    pending_ns,
                    offset,
                    stack.len(),
                )?;
                pending_element = Some(element);
            }
            RES_XML_END_ELEMENT_TYPE => {
                let name = parse_end_element(&r, &string_pool, &namespaces, offset)?;
                if let Some(pending) = pending_element.take() {
                    if pending.name == name {
                        out.push_str(&pending.start);
                        out.push_str("/>\n");
                    } else {
                        out.push_str(&pending.start);
                        out.push_str(">\n");
                        stack.push(pending.name);
                        write_end_element(&mut out, &mut stack, &name);
                    }
                } else {
                    write_end_element(&mut out, &mut stack, &name);
                }
            }
            RES_XML_CDATA_TYPE => {
                flush_pending_open(&mut out, &mut stack, &mut pending_element);
                let text = string_ref(&string_pool, r.u32_at(offset + NODE_HEADER_SIZE)?)
                    .unwrap_or_default();
                out.push_str(&"  ".repeat(stack.len()));
                out.push_str(&escape_text(text));
                out.push('\n');
            }
            other => {
                return Err(ArscError::UnexpectedChunkType {
                    offset,
                    expected: RES_XML_START_ELEMENT_TYPE,
                    got: other,
                });
            }
        }
        offset += chunk.size as usize;
    }
    flush_pending_open(&mut out, &mut stack, &mut pending_element);
    Ok(out)
}

fn parse_resource_map(
    r: &ArscReader<'_>,
    offset: usize,
    header_size: usize,
    size: usize,
) -> Result<Vec<u32>> {
    let count = (size - header_size) / 4;
    let mut map = Vec::with_capacity(count);
    let mut pos = offset + header_size;
    for _ in 0..count {
        map.push(r.u32_at(pos)?);
        pos += 4;
    }
    Ok(map)
}

fn parse_namespace(r: &ArscReader<'_>, pool: &StringPool, offset: usize) -> Result<Namespace> {
    let prefix_idx = r.u32_at(offset + NODE_HEADER_SIZE)?;
    let uri_idx = r.u32_at(offset + NODE_HEADER_SIZE + 4)?;
    Ok(Namespace {
        prefix: string_ref(pool, prefix_idx).unwrap_or_default().to_string(),
        uri: string_ref(pool, uri_idx).unwrap_or_default().to_string(),
    })
}

fn parse_start_element(
    r: &ArscReader<'_>,
    pool: &StringPool,
    resource_map: &[u32],
    namespaces: &[Namespace],
    pending_namespaces: Vec<Namespace>,
    offset: usize,
    depth: usize,
) -> Result<PendingElement> {
    let ext = offset + NODE_HEADER_SIZE;
    let ns_idx = r.u32_at(ext)?;
    let name_idx = r.u32_at(ext + 4)?;
    let attr_start = r.u16_at(ext + 8)? as usize;
    let attr_size = r.u16_at(ext + 10)? as usize;
    let attr_count = r.u16_at(ext + 12)?;
    if attr_count > MAX_ATTRIBUTES {
        return Err(ArscError::CountTooLarge {
            offset: ext + 12,
            count: attr_count as usize,
            cap: MAX_ATTRIBUTES as usize,
        });
    }
    let attr_size = attr_size.max(ATTRIBUTE_SIZE);
    let attr_base = ext + attr_start;
    if attr_start < START_ELEMENT_EXT_SIZE {
        return Err(ArscError::HeaderTooSmall {
            offset: ext,
            header_size: attr_start,
            min: START_ELEMENT_EXT_SIZE,
        });
    }

    let element_name = qname(pool, namespaces, ns_idx, name_idx, None);
    let mut attrs = Vec::with_capacity(attr_count as usize);
    for i in 0..attr_count as usize {
        attrs.push(parse_attribute(
            r,
            pool,
            resource_map,
            namespaces,
            attr_base + i * attr_size,
        )?);
    }

    let mut start = format!("{}<{}", "  ".repeat(depth), element_name);
    let mut declared_prefixes = BTreeSet::new();
    for ns in &pending_namespaces {
        if ns.prefix.is_empty() {
            start.push_str(&format!(" xmlns=\"{}\"", escape_attr(&ns.uri)));
            declared_prefixes.insert(String::new());
        } else {
            start.push_str(&format!(
                " xmlns:{}=\"{}\"",
                ns.prefix,
                escape_attr(&ns.uri)
            ));
            declared_prefixes.insert(ns.prefix.clone());
        }
    }
    if needs_android_namespace(pool, namespaces, ns_idx, &attrs)
        && !namespace_declared(namespaces, &pending_namespaces, "android", ANDROID_URI)
        && !declared_prefixes.contains("android")
    {
        start.push_str(&format!(" xmlns:android=\"{}\"", ANDROID_URI));
    }
    for attr in attrs {
        let name = match attr
            .namespace_uri
            .as_deref()
            .and_then(|uri| namespace_prefix(namespaces, uri))
        {
            Some(prefix) if !prefix.is_empty() => format!("{prefix}:{}", attr.name),
            _ => attr.name,
        };
        start.push_str(&format!(" {name}=\"{}\"", escape_attr(&attr.value)));
    }
    Ok(PendingElement {
        name: element_name,
        start,
    })
}

fn parse_end_element(
    r: &ArscReader<'_>,
    pool: &StringPool,
    namespaces: &[Namespace],
    offset: usize,
) -> Result<String> {
    let ext = offset + NODE_HEADER_SIZE;
    let ns_idx = r.u32_at(ext)?;
    let name_idx = r.u32_at(ext + 4)?;
    Ok(qname(pool, namespaces, ns_idx, name_idx, None))
}

fn parse_attribute(
    r: &ArscReader<'_>,
    pool: &StringPool,
    resource_map: &[u32],
    namespaces: &[Namespace],
    offset: usize,
) -> Result<Attribute> {
    let ns_idx = r.u32_at(offset)?;
    let name_idx = r.u32_at(offset + 4)?;
    let raw_value_idx = r.u32_at(offset + 8)?;
    let value = Value {
        data_type: r.u8_at(offset + 15)?,
        data: r.u32_at(offset + 16)?,
    };
    let name = attr_name(pool, resource_map, name_idx);
    let namespace_uri = string_ref(pool, ns_idx).map(str::to_string);
    let rendered = render_attribute_value(pool, &name, raw_value_idx, value);
    let _ = namespaces;
    Ok(Attribute {
        namespace_uri,
        name,
        value: rendered,
    })
}

fn write_end_element(out: &mut String, stack: &mut Vec<String>, name: &str) {
    if !stack.is_empty() {
        stack.pop();
    }
    out.push_str(&"  ".repeat(stack.len()));
    out.push_str("</");
    out.push_str(name);
    out.push_str(">\n");
}

fn flush_pending_open(
    out: &mut String,
    stack: &mut Vec<String>,
    pending_element: &mut Option<PendingElement>,
) {
    if let Some(pending) = pending_element.take() {
        out.push_str(&pending.start);
        out.push_str(">\n");
        stack.push(pending.name);
    }
}

fn qname(
    pool: &StringPool,
    namespaces: &[Namespace],
    ns_idx: u32,
    name_idx: u32,
    fallback: Option<&str>,
) -> String {
    let local = string_ref(pool, name_idx).or(fallback).unwrap_or("unknown");
    match string_ref(pool, ns_idx).and_then(|uri| namespace_prefix(namespaces, uri)) {
        Some(prefix) if !prefix.is_empty() => format!("{prefix}:{local}"),
        _ => local.to_string(),
    }
}

fn attr_name(pool: &StringPool, resource_map: &[u32], name_idx: u32) -> String {
    if let Some(name) = string_ref(pool, name_idx).filter(|name| !name.is_empty()) {
        return name.to_string();
    }
    if let Some(name) = resource_map
        .get(name_idx as usize)
        .and_then(|res_id| android_attr_name(*res_id))
    {
        name.to_string()
    } else {
        format!("attr_0x{name_idx:08x}")
    }
}

fn render_attribute_value(
    pool: &StringPool,
    attr_name: &str,
    raw_value_idx: u32,
    value: Value,
) -> String {
    if let Some(symbolic) = symbolic_value(attr_name, value) {
        return symbolic;
    }
    if value.data_type == TYPE_STRING {
        return string_ref(pool, value.data).unwrap_or_default().to_string();
    }
    if let Some(raw) = string_ref(pool, raw_value_idx) {
        return raw.to_string();
    }
    render_typed_value(value)
}

fn render_typed_value(value: Value) -> String {
    match value.data_type {
        TYPE_NULL => String::new(),
        TYPE_REFERENCE | TYPE_DYNAMIC_REFERENCE => format!("@0x{:08x}", value.data),
        TYPE_ATTRIBUTE | TYPE_DYNAMIC_ATTRIBUTE => format!("?0x{:08x}", value.data),
        TYPE_FLOAT => format_compact_float(f32::from_bits(value.data)),
        TYPE_DIMENSION => format!(
            "{}{}",
            format_complex(value.data),
            dimension_unit(value.data & 0xf)
        ),
        TYPE_FRACTION => format!(
            "{}{}",
            format_complex(value.data),
            fraction_unit(value.data & 0xf)
        ),
        TYPE_INT_DEC => (value.data as i32).to_string(),
        TYPE_INT_HEX => format!("0x{:08x}", value.data),
        TYPE_INT_BOOLEAN => {
            if value.data == 0 {
                "false".to_string()
            } else {
                "true".to_string()
            }
        }
        TYPE_INT_COLOR_ARGB8 => format!("#{:08x}", value.data),
        TYPE_INT_COLOR_RGB8 => format!("#{:06x}", value.data & 0x00ff_ffff),
        TYPE_INT_COLOR_ARGB4 => format!("#{:04x}", value.data & 0xffff),
        TYPE_INT_COLOR_RGB4 => format!("#{:03x}", value.data & 0x0fff),
        _ => format!("0x{:08x}", value.data),
    }
}

fn symbolic_value(attr_name: &str, value: Value) -> Option<String> {
    let name = attr_name.rsplit(':').next().unwrap_or(attr_name);
    match name {
        "installLocation" => enum_value(
            value.data,
            &[(0, "auto"), (1, "internalOnly"), (2, "preferExternal")],
        ),
        "launchMode" => enum_value(
            value.data,
            &[
                (0, "standard"),
                (1, "singleTop"),
                (2, "singleTask"),
                (3, "singleInstance"),
                (4, "singleInstancePerTask"),
            ],
        ),
        "protectionLevel" => Some(flag_value(
            value.data,
            &[
                (0, "normal"),
                (1, "dangerous"),
                (2, "signature"),
                (3, "signatureOrSystem"),
            ],
            &[
                (0x10, "privileged"),
                (0x20, "development"),
                (0x40, "appop"),
                (0x80, "pre23"),
                (0x100, "installer"),
                (0x200, "verifier"),
                (0x400, "preinstalled"),
                (0x800, "setup"),
                (0x1000, "instant"),
                (0x2000, "runtime"),
                (0x4000, "oem"),
                (0x8000, "vendorPrivileged"),
            ],
            0x0f,
        )),
        "foregroundServiceType" => Some(flag_value(
            value.data,
            &[(0, "none"), (u32::MAX, "manifest")],
            &[
                (0x1, "dataSync"),
                (0x2, "mediaPlayback"),
                (0x4, "phoneCall"),
                (0x8, "location"),
                (0x10, "connectedDevice"),
                (0x20, "mediaProjection"),
                (0x40, "camera"),
                (0x80, "microphone"),
                (0x100, "health"),
                (0x200, "remoteMessaging"),
                (0x400, "systemExempted"),
                (0x800, "shortService"),
            ],
            0,
        )),
        "configChanges" => Some(flag_value(
            value.data,
            &[(0, "0")],
            &[
                (0x1, "mcc"),
                (0x2, "mnc"),
                (0x4, "locale"),
                (0x8, "touchscreen"),
                (0x10, "keyboard"),
                (0x20, "keyboardHidden"),
                (0x40, "navigation"),
                (0x80, "orientation"),
                (0x100, "screenLayout"),
                (0x200, "uiMode"),
                (0x400, "screenSize"),
                (0x800, "smallestScreenSize"),
                (0x1000, "density"),
                (0x2000, "layoutDirection"),
                (0x4000, "colorMode"),
                (0x4000_0000, "fontScale"),
            ],
            0,
        )),
        _ => None,
    }
}

fn enum_value(value: u32, entries: &[(u32, &str)]) -> Option<String> {
    entries
        .iter()
        .find_map(|(candidate, name)| (*candidate == value).then(|| (*name).to_string()))
}

fn flag_value(
    value: u32,
    base_entries: &[(u32, &str)],
    flag_entries: &[(u32, &str)],
    base_mask: u32,
) -> String {
    if let Some(name) = base_entries
        .iter()
        .find_map(|(candidate, name)| (*candidate == value).then_some(*name))
    {
        return name.to_string();
    }
    let mut remaining = value;
    let mut parts = Vec::new();
    if base_mask != 0 {
        let base = value & base_mask;
        if let Some(name) = base_entries
            .iter()
            .find_map(|(candidate, name)| (*candidate == base).then_some(*name))
        {
            parts.push(name.to_string());
            remaining &= !base_mask;
        }
    }
    for (flag, name) in flag_entries {
        if remaining & *flag != 0 {
            parts.push((*name).to_string());
            remaining &= !*flag;
        }
    }
    if remaining != 0 {
        parts.push(format!("0x{remaining:x}"));
    }
    if parts.is_empty() {
        value.to_string()
    } else {
        parts.join("|")
    }
}

fn format_complex(data: u32) -> String {
    const RADIX_MULTS: [f32; 4] = [
        1.0 / 256.0,
        1.0 / 32768.0,
        1.0 / 8_388_608.0,
        1.0 / 2_147_483_648.0,
    ];
    let mantissa = (data as i32 & -256) as f32;
    let radix = ((data >> 4) & 0x3) as usize;
    format_compact_float(mantissa * RADIX_MULTS[radix])
}

fn format_compact_float(value: f32) -> String {
    let mut rendered = format!("{value:.6}");
    while rendered.contains('.') && rendered.ends_with('0') {
        rendered.pop();
    }
    if rendered.ends_with('.') {
        rendered.pop();
    }
    rendered
}

fn dimension_unit(unit: u32) -> &'static str {
    match unit {
        0 => "px",
        1 => "dp",
        2 => "sp",
        3 => "pt",
        4 => "in",
        5 => "mm",
        _ => "",
    }
}

fn fraction_unit(unit: u32) -> &'static str {
    match unit {
        0 => "%",
        1 => "%p",
        _ => "",
    }
}

fn needs_android_namespace(
    pool: &StringPool,
    namespaces: &[Namespace],
    element_ns_idx: u32,
    attrs: &[Attribute],
) -> bool {
    string_ref(pool, element_ns_idx) == Some(ANDROID_URI)
        || attrs
            .iter()
            .any(|attr| attr.namespace_uri.as_deref() == Some(ANDROID_URI))
        || namespaces
            .iter()
            .any(|ns| ns.prefix == "android" && ns.uri == ANDROID_URI)
}

fn namespace_declared(
    namespaces: &[Namespace],
    pending: &[Namespace],
    prefix: &str,
    uri: &str,
) -> bool {
    namespaces
        .iter()
        .chain(pending.iter())
        .any(|ns| ns.prefix == prefix && ns.uri == uri)
}

fn namespace_prefix<'a>(namespaces: &'a [Namespace], uri: &str) -> Option<&'a str> {
    namespaces
        .iter()
        .rev()
        .find(|ns| ns.uri == uri)
        .map(|ns| ns.prefix.as_str())
        .or_else(|| (uri == ANDROID_URI).then_some("android"))
}

fn string_ref(pool: &StringPool, index: u32) -> Option<&str> {
    if index == NO_INDEX {
        None
    } else {
        pool.strings.get(index as usize).map(String::as_str)
    }
}

fn android_attr_name(res_id: u32) -> Option<&'static str> {
    Some(match res_id {
        0x0101_0000 => "theme",
        0x0101_0001 => "label",
        0x0101_0002 => "icon",
        0x0101_0003 => "name",
        0x0101_0006 => "permission",
        0x0101_0008 => "writePermission",
        0x0101_0009 => "protectionLevel",
        0x0101_000b => "sharedUserId",
        0x0101_000c => "hasCode",
        0x0101_000e => "enabled",
        0x0101_000f => "debuggable",
        0x0101_0010 => "exported",
        0x0101_0011 => "process",
        0x0101_001c => "priority",
        0x0101_001d => "launchMode",
        0x0101_001f => "configChanges",
        0x0101_0020 => "description",
        0x0101_0021 => "targetPackage",
        0x0101_0024 => "value",
        0x0101_0025 => "resource",
        0x0101_0026 => "mimeType",
        0x0101_0027 => "scheme",
        0x0101_0028 => "host",
        0x0101_0029 => "port",
        0x0101_002a => "path",
        0x0101_002b => "pathPrefix",
        0x0101_002c => "pathPattern",
        0x0101_020c => "minSdkVersion",
        0x0101_021b => "versionCode",
        0x0101_021c => "versionName",
        0x0101_026c => "anyDensity",
        0x0101_0270 => "targetSdkVersion",
        0x0101_0271 => "maxSdkVersion",
        0x0101_0281 => "glEsVersion",
        0x0101_0284 => "smallScreens",
        0x0101_0285 => "normalScreens",
        0x0101_0286 => "largeScreens",
        0x0101_02b7 => "installLocation",
        0x0101_0364 => "xlargeScreens",
        0x0101_0599 => "foregroundServiceType",
        _ => return None,
    })
}

fn escape_attr(value: &str) -> String {
    value
        .chars()
        .flat_map(|c| match c {
            '&' => "&amp;".chars().collect::<Vec<_>>(),
            '"' => "&quot;".chars().collect(),
            '\'' => "&apos;".chars().collect(),
            '<' => "&lt;".chars().collect(),
            '>' => "&gt;".chars().collect(),
            c => vec![c],
        })
        .collect()
}

fn escape_text(value: &str) -> String {
    value
        .chars()
        .flat_map(|c| match c {
            '&' => "&amp;".chars().collect::<Vec<_>>(),
            '<' => "&lt;".chars().collect(),
            '>' => "&gt;".chars().collect(),
            c => vec![c],
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn minimal_manifest_decodes_package_min_sdk_and_xmlns() {
        let data = minimal_manifest();
        let xml = decode_axml(&data).unwrap();
        assert!(xml.contains(r#"<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example">"#), "{xml}");
        assert!(
            xml.contains(r#"<uses-sdk android:minSdkVersion="21"/>"#),
            "{xml}"
        );
        assert_eq!(axml_strings(&data).unwrap()[2], "manifest");
    }

    fn minimal_manifest() -> Vec<u8> {
        let mut buf = Vec::new();
        let tree_size_pos = begin_chunk(&mut buf, RES_XML_TYPE, 8);
        append_string_pool(
            &mut buf,
            &[
                "android",
                ANDROID_URI,
                "manifest",
                "package",
                "com.example",
                "uses-sdk",
                "minSdkVersion",
            ],
        );
        append_namespace(&mut buf, RES_XML_START_NAMESPACE_TYPE, 0, 1);
        append_start_element(&mut buf, NO_INDEX, 2, &[(NO_INDEX, 3, 4, TYPE_STRING, 4)]);
        append_start_element(&mut buf, NO_INDEX, 5, &[(1, 6, NO_INDEX, TYPE_INT_DEC, 21)]);
        append_end_element(&mut buf, NO_INDEX, 5);
        append_end_element(&mut buf, NO_INDEX, 2);
        append_namespace(&mut buf, RES_XML_END_NAMESPACE_TYPE, 0, 1);
        patch_chunk_size(&mut buf, tree_size_pos);
        buf
    }

    fn begin_chunk(buf: &mut Vec<u8>, chunk_type: u16, header_size: u16) -> usize {
        buf.extend_from_slice(&chunk_type.to_le_bytes());
        buf.extend_from_slice(&header_size.to_le_bytes());
        let size_pos = buf.len();
        buf.extend_from_slice(&0u32.to_le_bytes());
        size_pos
    }

    fn patch_chunk_size(buf: &mut [u8], size_pos: usize) {
        let size = buf.len() as u32;
        buf[size_pos..size_pos + 4].copy_from_slice(&size.to_le_bytes());
    }

    fn append_string_pool(buf: &mut Vec<u8>, strings: &[&str]) {
        let start = buf.len();
        let size_pos = begin_chunk(buf, crate::string_pool::RES_STRING_POOL_TYPE, 28);
        buf.extend_from_slice(&(strings.len() as u32).to_le_bytes());
        buf.extend_from_slice(&0u32.to_le_bytes());
        buf.extend_from_slice(&(1u32 << 8).to_le_bytes());
        let strings_start_pos = buf.len();
        buf.extend_from_slice(&0u32.to_le_bytes());
        buf.extend_from_slice(&0u32.to_le_bytes());
        let offsets_pos = buf.len();
        for _ in strings {
            buf.extend_from_slice(&0u32.to_le_bytes());
        }
        let strings_start = (buf.len() - start) as u32;
        buf[strings_start_pos..strings_start_pos + 4].copy_from_slice(&strings_start.to_le_bytes());
        for (i, s) in strings.iter().enumerate() {
            let rel = (buf.len() - start) as u32 - strings_start;
            buf[offsets_pos + i * 4..offsets_pos + i * 4 + 4].copy_from_slice(&rel.to_le_bytes());
            buf.push(s.chars().count() as u8);
            buf.push(s.len() as u8);
            buf.extend_from_slice(s.as_bytes());
            buf.push(0);
        }
        while buf.len() % 4 != 0 {
            buf.push(0);
        }
        let size = (buf.len() - start) as u32;
        buf[size_pos..size_pos + 4].copy_from_slice(&size.to_le_bytes());
    }

    fn append_namespace(buf: &mut Vec<u8>, chunk_type: u16, prefix: u32, uri: u32) {
        let start = buf.len();
        let size_pos = begin_chunk(buf, chunk_type, 16);
        buf.extend_from_slice(&0u32.to_le_bytes());
        buf.extend_from_slice(&NO_INDEX.to_le_bytes());
        buf.extend_from_slice(&prefix.to_le_bytes());
        buf.extend_from_slice(&uri.to_le_bytes());
        let size = (buf.len() - start) as u32;
        buf[size_pos..size_pos + 4].copy_from_slice(&size.to_le_bytes());
    }

    fn append_start_element(
        buf: &mut Vec<u8>,
        ns: u32,
        name: u32,
        attrs: &[(u32, u32, u32, u8, u32)],
    ) {
        let start = buf.len();
        let size_pos = begin_chunk(buf, RES_XML_START_ELEMENT_TYPE, 16);
        buf.extend_from_slice(&0u32.to_le_bytes());
        buf.extend_from_slice(&NO_INDEX.to_le_bytes());
        buf.extend_from_slice(&ns.to_le_bytes());
        buf.extend_from_slice(&name.to_le_bytes());
        buf.extend_from_slice(&20u16.to_le_bytes());
        buf.extend_from_slice(&20u16.to_le_bytes());
        buf.extend_from_slice(&(attrs.len() as u16).to_le_bytes());
        buf.extend_from_slice(&0u16.to_le_bytes());
        buf.extend_from_slice(&0u16.to_le_bytes());
        buf.extend_from_slice(&0u16.to_le_bytes());
        for (attr_ns, attr_name, raw_value, data_type, data) in attrs {
            buf.extend_from_slice(&attr_ns.to_le_bytes());
            buf.extend_from_slice(&attr_name.to_le_bytes());
            buf.extend_from_slice(&raw_value.to_le_bytes());
            buf.extend_from_slice(&8u16.to_le_bytes());
            buf.push(0);
            buf.push(*data_type);
            buf.extend_from_slice(&data.to_le_bytes());
        }
        let size = (buf.len() - start) as u32;
        buf[size_pos..size_pos + 4].copy_from_slice(&size.to_le_bytes());
    }

    fn append_end_element(buf: &mut Vec<u8>, ns: u32, name: u32) {
        let start = buf.len();
        let size_pos = begin_chunk(buf, RES_XML_END_ELEMENT_TYPE, 16);
        buf.extend_from_slice(&0u32.to_le_bytes());
        buf.extend_from_slice(&NO_INDEX.to_le_bytes());
        buf.extend_from_slice(&ns.to_le_bytes());
        buf.extend_from_slice(&name.to_le_bytes());
        let size = (buf.len() - start) as u32;
        buf[size_pos..size_pos + 4].copy_from_slice(&size.to_le_bytes());
    }
}
