//! PyO3 bridge exposing APEX's own DEX parser to Python.
//!
//! Kept as a separate crate so `apex_dex_parser` stays a dependency-free rlib
//! that can be unit-tested without linking against libpython. This bridge is
//! what makes the native exception/CFG analysis reachable from the CLI and the
//! web UI, rather than being an internal Rust-only capability.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use apex_dex_parser::cfg::build_cfg_with_exceptions;
use apex_dex_parser::code::{decode_instructions, parse_code_item, parse_exception_data};
use apex_dex_parser::parse;
use apex_dex_parser::reader::DexReader;

/// Convert a type descriptor such as `Lcom/foo/Bar;` to `com.foo.Bar`.
fn descriptor_to_java(descriptor: &str) -> String {
    if descriptor.starts_with('L') && descriptor.ends_with(';') {
        descriptor[1..descriptor.len() - 1].replace('/', ".")
    } else {
        descriptor.to_string()
    }
}

/// Analyze every method in a DEX image and report its exception structure.
///
/// Returns a list of dicts, one per method that declares at least one `try`
/// range, plus aggregate counters describing the whole file.
#[pyfunction]
fn exception_summary(py: Python<'_>, data: &[u8]) -> PyResult<Py<PyAny>> {
    let dex = match parse(data) {
        Ok(dex) => dex,
        Err(err) => {
            let out = PyDict::new(py);
            out.set_item("valid", false)?;
            out.set_item("error", err.to_string())?;
            out.set_item("methods", PyList::empty(py))?;
            return Ok(out.into_any().unbind());
        }
    };

    let reader = DexReader::new(data);
    let methods = PyList::empty(py);
    let mut method_count: usize = 0;
    let mut protected_methods: usize = 0;
    let mut try_total: usize = 0;
    let mut handler_total: usize = 0;
    let mut exception_edge_total: usize = 0;
    let mut unreachable_handlers: usize = 0;

    for def in &dex.class_defs {
        if def.class_data_off == 0 {
            continue;
        }
        let Ok(class_data) = dex.class_data(def) else { continue };
        let class_name = dex
            .type_name(def.class_idx)
            .map(descriptor_to_java)
            .unwrap_or_default();

        let all_methods = class_data
            .direct_methods
            .iter()
            .chain(class_data.virtual_methods.iter());
        for method in all_methods {
            if method.code_off == 0 {
                continue;
            }
            method_count += 1;
            let Ok(item) = parse_code_item(&reader, method.code_off) else { continue };
            if item.tries_size == 0 {
                continue;
            }
            let Ok(exceptions) = parse_exception_data(&reader, method.code_off, &item) else {
                continue;
            };
            let Ok(units) = decode_instructions(&item.insns) else { continue };
            let graph = build_cfg_with_exceptions(&units, &exceptions);

            let handler_blocks = graph.handler_blocks();
            let edge_count = graph.exception_edge_count();
            let declared_handler_addrs: usize = exceptions
                .handlers
                .iter()
                .map(|h| h.addresses().len())
                .sum();
            let orphaned = declared_handler_addrs.saturating_sub(handler_blocks.len());

            protected_methods += 1;
            try_total += exceptions.tries.len();
            handler_total += declared_handler_addrs;
            exception_edge_total += edge_count;
            unreachable_handlers += orphaned;

            let ranges = PyList::empty(py);
            for range in &graph.protected_ranges {
                let entry = PyDict::new(py);
                entry.set_item("start", range.start)?;
                entry.set_item("end", range.end)?;
                let targets = PyList::empty(py);
                for handler in &range.handlers {
                    let target = PyDict::new(py);
                    target.set_item("addr", handler.addr)?;
                    target.set_item("catch_all", handler.catch_all)?;
                    match handler.type_idx {
                        Some(idx) => {
                            target.set_item("type_idx", idx)?;
                            target.set_item(
                                "type",
                                dex.type_name(idx).map(descriptor_to_java).unwrap_or_default(),
                            )?;
                        }
                        None => {
                            target.set_item("type_idx", py.None())?;
                            target.set_item("type", "<any>")?;
                        }
                    }
                    targets.append(target)?;
                }
                entry.set_item("handlers", targets)?;
                ranges.append(entry)?;
            }

            let record = PyDict::new(py);
            record.set_item("class", &class_name)?;
            record.set_item(
                "method",
                dex.method_name(method.method_idx).unwrap_or_default(),
            )?;
            record.set_item("try_count", exceptions.tries.len())?;
            record.set_item("handler_count", declared_handler_addrs)?;
            record.set_item("handler_blocks", handler_blocks.len())?;
            record.set_item("block_count", graph.blocks.len())?;
            record.set_item("exception_edges", edge_count)?;
            record.set_item("unreachable_handlers", orphaned)?;
            record.set_item("protected_ranges", ranges)?;
            methods.append(record)?;
        }
    }

    let out = PyDict::new(py);
    out.set_item("valid", true)?;
    out.set_item("provider", "apex-dex-parser")?;
    out.set_item("method_count", method_count)?;
    out.set_item("methods_with_handlers", protected_methods)?;
    out.set_item("try_count", try_total)?;
    out.set_item("handler_count", handler_total)?;
    out.set_item("exception_edges", exception_edge_total)?;
    out.set_item("unreachable_handlers", unreachable_handlers)?;
    out.set_item("methods", methods)?;
    Ok(out.into_any().unbind())
}

#[pymodule]
fn apex_dex_bridge(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(exception_summary, m)?)?;
    Ok(())
}
