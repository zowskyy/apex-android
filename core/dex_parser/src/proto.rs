use crate::error::{DexError, Result};
use crate::reader::DexReader;
use crate::DexFile;

pub const MAX_PROTO_PARAMS: usize = 4096;

/// Build a JVM method descriptor such as `(ILjava/lang/String;)V`.
pub fn method_descriptor(dex: &DexFile<'_>, proto_idx: u32) -> Result<String> {
    let r = DexReader::new(dex.data);
    let entry = dex.header.proto_ids_off as usize + (proto_idx as usize) * 12;
    let return_type_idx = r.u32_at(entry + 4)?;
    let parameters_off = r.u32_at(entry + 8)?;

    let mut descriptor = String::from("(");
    if parameters_off != 0 {
        let base = parameters_off as usize;
        let size = r.u32_at(base)? as usize;
        if size > MAX_PROTO_PARAMS {
            return Err(DexError::CountTooLarge {
                offset: base,
                count: size,
                cap: MAX_PROTO_PARAMS,
            });
        }
        for index in 0..size {
            let type_idx = r.u16_at(base + 4 + index * 2)?;
            descriptor.push_str(dex.type_name(type_idx as u32).unwrap_or("?"));
        }
    }
    descriptor.push(')');
    descriptor.push_str(dex.type_name(return_type_idx).unwrap_or("?"));
    Ok(descriptor)
}

/// Read interface type descriptors from a class_def's interfaces_off.
pub fn interface_descriptors(dex: &DexFile<'_>, interfaces_off: u32) -> Result<Vec<String>> {
    if interfaces_off == 0 {
        return Ok(Vec::new());
    }
    let r = DexReader::new(dex.data);
    let base = interfaces_off as usize;
    let size = r.u32_at(base)? as usize;
    if size > MAX_PROTO_PARAMS {
        return Err(DexError::CountTooLarge {
            offset: base,
            count: size,
            cap: MAX_PROTO_PARAMS,
        });
    }
    let mut out = Vec::with_capacity(size);
    for index in 0..size {
        let type_idx = r.u16_at(base + 4 + index * 2)?;
        if let Some(name) = dex.type_name(type_idx as u32) {
            out.push(name.to_string());
        }
    }
    Ok(out)
}
