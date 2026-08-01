//! Lightweight control-flow structuring for decompiled blocks.
//!
//! The current decompiler uses this as a conservative surface: straight-line
//! blocks are emitted as statements, while unstructured edges remain visible as
//! labels/comments instead of being hidden behind incorrect Java.

use std::collections::BTreeMap;

use crate::decompile::{emit_expr, emit_stmt, Expr, Stmt, Terminator};

#[derive(Debug, Clone)]
pub struct EmittedBlock {
    pub label: u32,
    pub statements: Vec<Stmt>,
    pub terminator: Terminator,
}

pub fn structure_blocks(blocks: &[EmittedBlock], resources: &BTreeMap<i64, String>) -> Vec<String> {
    let mut lines = Vec::new();
    for block in blocks {
        if blocks.len() > 1 {
            lines.push(format!("L_{:04x}:", block.label));
        }
        for stmt in &block.statements {
            if let Some(line) = emit_stmt(stmt, resources) {
                lines.push(line);
            }
        }
        match &block.terminator {
            Terminator::FallThrough => {}
            Terminator::Return(None) => lines.push("return;".to_string()),
            Terminator::Return(Some(value)) => {
                lines.push(format!("return {};", emit_expr(value, resources)))
            }
            Terminator::Goto(target) => lines.push(format!("// goto L_{target:04x}")),
            Terminator::If {
                condition,
                then_target,
                else_target,
            } => lines.push(format!(
                "if ({}) {{ // goto L_{then_target:04x} }} else {{ // goto L_{else_target:04x} }}",
                emit_expr(condition, resources)
            )),
            Terminator::Switch {
                value,
                cases,
                default_target,
            } => {
                lines.push(format!("switch ({}) {{", emit_expr(value, resources)));
                for (key, target) in cases {
                    lines.push(format!("case {key}: // goto L_{target:04x}"));
                }
                lines.push(format!("default: // goto L_{default_target:04x}"));
                lines.push("}".to_string());
            }
        }
    }
    lines
}

pub fn fallback_goto(target: u32) -> Stmt {
    Stmt::Comment(format!("goto L_{target:04x}"))
}

pub fn while_loop_header(condition: Expr) -> Stmt {
    Stmt::Comment(format!(
        "while ({})",
        emit_expr(&condition, &BTreeMap::new())
    ))
}
