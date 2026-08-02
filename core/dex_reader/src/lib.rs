use apex_dex_parser::code::CodeUnit;
use apex_dex_parser::metadata::{build_metadata, DexMetadata};
use apex_dex_parser::{parse, DexFile};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

fn dex_err(err: apex_dex_parser::error::DexError) -> PyErr {
    PyValueError::new_err(err.to_string())
}

fn metadata_to_dict<'py>(py: Python<'py>, metadata: &DexMetadata) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("dex", &metadata.dex)?;

    let classes = PyList::empty(py);
    for class in &metadata.classes {
        let item = PyDict::new(py);
        item.set_item("dex", &class.dex)?;
        item.set_item("name", &class.name)?;
        item.set_item("descriptor", &class.descriptor)?;
        item.set_item("super", &class.super_descriptor)?;
        item.set_item("interfaces", &class.interfaces)?;
        item.set_item("access", &class.access)?;
        item.set_item("source_file_index", class.source_file_index)?;
        classes.append(item)?;
    }
    dict.set_item("classes", classes)?;

    let methods = PyList::empty(py);
    for method in &metadata.methods {
        let item = PyDict::new(py);
        item.set_item("dex", &method.dex)?;
        item.set_item("class", &method.class_name)?;
        item.set_item("name", &method.name)?;
        item.set_item("descriptor", &method.descriptor)?;
        item.set_item("access", &method.access)?;
        item.set_item("has_code", method.has_code)?;
        item.set_item("instruction_count", method.instruction_count)?;
        item.set_item("code_off", method.code_off)?;
        methods.append(item)?;
    }
    dict.set_item("methods", methods)?;

    dict.set_item("strings", &metadata.strings)?;

    let edges = PyList::empty(py);
    for edge in &metadata.edges {
        let item = PyDict::new(py);
        item.set_item("caller_class", &edge.caller_class)?;
        item.set_item("caller_method", &edge.caller_method)?;
        item.set_item("callee", &edge.callee)?;
        item.set_item("offset", edge.offset)?;
        edges.append(item)?;
    }
    dict.set_item("edges", edges)?;

    Ok(dict)
}

fn header_to_dict<'py>(py: Python<'py>, dex: &DexFile<'_>) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);
    dict.set_item("file_size", dex.header.file_size)?;
    dict.set_item("header_size", dex.header.header_size)?;
    dict.set_item("string_ids_size", dex.header.string_ids_size)?;
    dict.set_item("type_ids_size", dex.header.type_ids_size)?;
    dict.set_item("proto_ids_size", dex.header.proto_ids_size)?;
    dict.set_item("field_ids_size", dex.header.field_ids_size)?;
    dict.set_item("method_ids_size", dex.header.method_ids_size)?;
    dict.set_item("class_defs_size", dex.header.class_defs_size)?;
    dict.set_item("data_size", dex.header.data_size)?;
    Ok(dict)
}

/// Parse a DEX file and return class/method metadata compatible with APEX Python.
#[pyfunction]
fn dex_metadata(py: Python<'_>, data: &[u8], dex_name: &str) -> PyResult<Py<PyAny>> {
    let dex = parse(data).map_err(dex_err)?;
    let metadata = build_metadata(&dex, dex_name).map_err(dex_err)?;
    Ok(metadata_to_dict(py, &metadata)?.into_any().unbind())
}

/// Return structural DEX header fields without building the full metadata index.
#[pyfunction]
fn parse_header(py: Python<'_>, data: &[u8]) -> PyResult<Py<PyAny>> {
    let dex = parse(data).map_err(dex_err)?;
    Ok(header_to_dict(py, &dex)?.into_any().unbind())
}

/// Decode one method's instruction stream from raw DEX bytes and a code_off.
#[pyfunction]
fn decode_method(py: Python<'_>, data: &[u8], code_off: u32) -> PyResult<Py<PyAny>> {
    let dex = parse(data).map_err(dex_err)?;
    let (item, units) = dex.decode_method(code_off).map_err(dex_err)?;

    let dict = PyDict::new(py);
    dict.set_item("registers_size", item.registers_size)?;
    dict.set_item("ins_size", item.ins_size)?;
    dict.set_item("outs_size", item.outs_size)?;
    dict.set_item("tries_size", item.tries_size)?;
    dict.set_item("insns_size", item.insns.len())?;

    let instructions = PyList::empty(py);
    for unit in units {
        if let CodeUnit::Insn(insn) = unit {
            let entry = PyDict::new(py);
            entry.set_item("offset", insn.code_unit_offset)?;
            entry.set_item("opcode", insn.opcode)?;
            entry.set_item("format", format!("{:?}", insn.format))?;
            entry.set_item("registers", &insn.registers)?;
            if let Some(literal) = insn.literal {
                entry.set_item("literal", literal)?;
            }
            if let Some(branch_offset) = insn.branch_offset {
                entry.set_item("branch_offset", branch_offset)?;
            }
            if let Some(index) = insn.index {
                entry.set_item("index", index)?;
            }
            instructions.append(entry)?;
        }
    }
    dict.set_item("instructions", instructions)?;
    Ok(dict.into_any().unbind())
}

#[pymodule]
fn apex_dex_reader(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(dex_metadata, m)?)?;
    m.add_function(wrap_pyfunction!(parse_header, m)?)?;
    m.add_function(wrap_pyfunction!(decode_method, m)?)?;
    Ok(())
}
