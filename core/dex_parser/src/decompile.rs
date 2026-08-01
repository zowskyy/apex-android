//! Dalvik register-machine expression reconstruction.

use std::collections::BTreeMap;

use crate::class_data::EncodedMethod;
use crate::class_def::ClassDef;
use crate::code::{CodeUnit, Instruction};
use crate::error::Result;
use crate::ids::{descriptor_simple_name, short_name, FieldRef, MethodRef};
use crate::DexFile;

#[derive(Debug, Clone)]
pub enum Expr {
    Reg(u16),
    Param(String),
    This,
    ConstInt(i64),
    ConstString(String),
    Null,
    Binary {
        op: String,
        left: Box<Expr>,
        right: Box<Expr>,
    },
    Unary {
        op: String,
        expr: Box<Expr>,
    },
    Cast {
        ty: String,
        expr: Box<Expr>,
    },
    FieldGet {
        target: Box<Expr>,
        field: FieldRef,
    },
    StaticFieldGet {
        field: FieldRef,
    },
    ArrayGet {
        array: Box<Expr>,
        index: Box<Expr>,
    },
    Call {
        kind: CallKind,
        method: MethodRef,
        target: Option<Box<Expr>>,
        args: Vec<Expr>,
    },
    NewInstance {
        class_name: String,
        args: Vec<Expr>,
    },
    NewArray {
        element_type: String,
        size: Box<Expr>,
    },
    ResourceRef(String),
    ClassLiteral(String),
    Unknown(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CallKind {
    Virtual,
    Super,
    Direct,
    Static,
    Interface,
}

#[derive(Debug, Clone)]
pub enum Stmt {
    Assign {
        target: String,
        value: Box<Expr>,
    },
    Expr(Box<Expr>),
    FieldPut {
        target: Box<Expr>,
        field: FieldRef,
        value: Box<Expr>,
    },
    StaticFieldPut {
        field: FieldRef,
        value: Box<Expr>,
    },
    ArrayPut {
        array: Box<Expr>,
        index: Box<Expr>,
        value: Box<Expr>,
    },
    Return(Option<Box<Expr>>),
    Throw(Box<Expr>),
    Comment(String),
}

#[derive(Debug, Clone)]
pub enum Terminator {
    FallThrough,
    Return(Option<Expr>),
    Goto(u32),
    If {
        condition: Expr,
        then_target: u32,
        else_target: u32,
    },
    Switch {
        value: Expr,
        cases: Vec<(i32, u32)>,
        default_target: u32,
    },
}

#[derive(Debug, Clone, Default)]
struct MethodState {
    regs: BTreeMap<u16, Expr>,
    pending_result: Option<Expr>,
}

pub fn decompile_method_statements(
    dex: &DexFile<'_>,
    class_def: &ClassDef,
    method: &EncodedMethod,
    resources: &BTreeMap<i64, String>,
) -> Result<Vec<Stmt>> {
    let (code, units) = dex.decode_method(method.code_off)?;
    let current_method = dex.method_ref(method.method_idx)?;
    let mut state = MethodState::default();
    seed_parameters(&mut state, &code, method.access_flags, &current_method);

    let mut out = Vec::new();
    let current_class_descriptor = dex.type_name(class_def.class_idx).unwrap_or("").to_string();
    for unit in units {
        let CodeUnit::Insn(insn) = unit else { continue };
        if !matches!(insn.opcode, 0x0a..=0x0c) {
            flush_pending_result(&mut state, &mut out);
        }
        handle_instruction(
            dex,
            &current_class_descriptor,
            &mut state,
            &mut out,
            &insn,
            resources,
        )?;
    }
    flush_pending_result(&mut state, &mut out);
    Ok(out)
}

fn seed_parameters(
    state: &mut MethodState,
    code: &crate::code::CodeItem,
    access_flags: u32,
    method: &MethodRef,
) {
    let is_static = access_flags & 0x0008 != 0;
    let mut reg = code.registers_size.saturating_sub(code.ins_size);
    if !is_static {
        state.regs.insert(reg, Expr::This);
        reg += 1;
    }
    for (param_idx, descriptor) in method.parameter_descriptors.iter().enumerate() {
        state.regs.insert(reg, Expr::Param(format!("p{param_idx}")));
        reg += if matches!(descriptor.as_str(), "J" | "D") {
            2
        } else {
            1
        };
    }
}

fn flush_pending_result(state: &mut MethodState, out: &mut Vec<Stmt>) {
    if let Some(expr) = state.pending_result.take() {
        out.push(Stmt::Expr(Box::new(expr)));
    }
}

fn read_reg(state: &MethodState, reg: u16) -> Expr {
    state.regs.get(&reg).cloned().unwrap_or(Expr::Reg(reg))
}

fn write_reg(state: &mut MethodState, reg: u16, expr: Expr) {
    state.regs.insert(reg, expr);
}

fn const_expr(opcode: u8, literal: i64, resources: &BTreeMap<i64, String>) -> Expr {
    let value = match opcode {
        0x15 => (literal >> 32) as i32 as i64,
        0x19 => literal,
        _ => literal,
    };
    resources
        .get(&value)
        .cloned()
        .map(Expr::ResourceRef)
        .unwrap_or(Expr::ConstInt(value))
}

fn handle_instruction(
    dex: &DexFile<'_>,
    current_class_descriptor: &str,
    state: &mut MethodState,
    out: &mut Vec<Stmt>,
    insn: &Instruction,
    resources: &BTreeMap<i64, String>,
) -> Result<()> {
    match insn.opcode {
        0x00 => {}
        0x01..=0x09 => {
            if let [dst, src, ..] = insn.registers.as_slice() {
                write_reg(state, *dst, read_reg(state, *src));
            }
        }
        0x0a..=0x0c => {
            if let Some(dst) = insn.registers.first().copied() {
                if let Some(expr) = state.pending_result.take() {
                    write_reg(state, dst, expr);
                }
            }
        }
        0x0e => out.push(Stmt::Return(None)),
        0x0f..=0x11 => {
            let value = insn
                .registers
                .first()
                .map(|reg| Box::new(read_reg(state, *reg)));
            out.push(Stmt::Return(value));
        }
        0x12..=0x19 => {
            if let (Some(dst), Some(lit)) = (insn.registers.first().copied(), insn.literal) {
                write_reg(state, dst, const_expr(insn.opcode, lit, resources));
            }
        }
        0x1a | 0x1b => {
            if let (Some(dst), Some(string_idx)) = (insn.registers.first().copied(), insn.index) {
                let value = dex
                    .strings
                    .get(string_idx as usize)
                    .cloned()
                    .unwrap_or_default();
                write_reg(state, dst, Expr::ConstString(value));
            }
        }
        0x1c => {
            if let (Some(dst), Some(type_idx)) = (insn.registers.first().copied(), insn.index) {
                write_reg(
                    state,
                    dst,
                    Expr::ClassLiteral(short_name(dex.type_name(type_idx).unwrap_or(""))),
                );
            }
        }
        0x1f => {
            if let (Some(reg), Some(type_idx)) = (insn.registers.first().copied(), insn.index) {
                let ty = short_name(dex.type_name(type_idx).unwrap_or(""));
                let expr = read_reg(state, reg);
                write_reg(
                    state,
                    reg,
                    Expr::Cast {
                        ty,
                        expr: Box::new(expr),
                    },
                );
            }
        }
        0x21 => {
            if let [dst, array, ..] = insn.registers.as_slice() {
                write_reg(
                    state,
                    *dst,
                    Expr::Unknown(format!(
                        "{}.length",
                        emit_expr(&read_reg(state, *array), resources)
                    )),
                );
            }
        }
        0x22 => {
            if let (Some(dst), Some(type_idx)) = (insn.registers.first().copied(), insn.index) {
                write_reg(
                    state,
                    dst,
                    Expr::NewInstance {
                        class_name: short_name(dex.type_name(type_idx).unwrap_or("")),
                        args: Vec::new(),
                    },
                );
            }
        }
        0x23 => {
            if let (Some(dst), Some(size_reg), Some(type_idx)) = (
                insn.registers.first().copied(),
                insn.registers.get(1).copied(),
                insn.index,
            ) {
                let descriptor = dex.type_name(type_idx).unwrap_or("");
                let element_type = short_name(descriptor.trim_start_matches('['));
                write_reg(
                    state,
                    dst,
                    Expr::NewArray {
                        element_type,
                        size: Box::new(read_reg(state, size_reg)),
                    },
                );
            }
        }
        0x27 => {
            if let Some(reg) = insn.registers.first().copied() {
                out.push(Stmt::Throw(Box::new(read_reg(state, reg))));
            }
        }
        0x28..=0x2a => {
            let target = branch_target(insn).unwrap_or(insn.code_unit_offset);
            out.push(Stmt::Comment(format!("goto L_{target:04x}")));
        }
        0x2b | 0x2c => {
            let value = insn
                .registers
                .first()
                .map(|reg| emit_expr(&read_reg(state, *reg), resources))
                .unwrap_or_else(|| "?".to_string());
            out.push(Stmt::Comment(format!("switch ({value})")));
        }
        0x32..=0x37 => {
            let condition = if let [a, b, ..] = insn.registers.as_slice() {
                Expr::Binary {
                    op: if_op(insn.opcode).to_string(),
                    left: Box::new(read_reg(state, *a)),
                    right: Box::new(read_reg(state, *b)),
                }
            } else {
                Expr::Unknown("condition".to_string())
            };
            let target = branch_target(insn).unwrap_or(insn.code_unit_offset);
            out.push(Stmt::Comment(format!(
                "if ({}) goto L_{target:04x}",
                emit_expr(&condition, resources)
            )));
        }
        0x38..=0x3d => {
            let condition = if let Some(reg) = insn.registers.first().copied() {
                Expr::Binary {
                    op: if_op(insn.opcode).to_string(),
                    left: Box::new(read_reg(state, reg)),
                    right: Box::new(Expr::ConstInt(0)),
                }
            } else {
                Expr::Unknown("condition".to_string())
            };
            let target = branch_target(insn).unwrap_or(insn.code_unit_offset);
            out.push(Stmt::Comment(format!(
                "if ({}) goto L_{target:04x}",
                emit_expr(&condition, resources)
            )));
        }
        0x44..=0x4a => {
            if let [dst, array, index, ..] = insn.registers.as_slice() {
                write_reg(
                    state,
                    *dst,
                    Expr::ArrayGet {
                        array: Box::new(read_reg(state, *array)),
                        index: Box::new(read_reg(state, *index)),
                    },
                );
            }
        }
        0x4b..=0x51 => {
            if let [value, array, index, ..] = insn.registers.as_slice() {
                out.push(Stmt::ArrayPut {
                    array: Box::new(read_reg(state, *array)),
                    index: Box::new(read_reg(state, *index)),
                    value: Box::new(read_reg(state, *value)),
                });
            }
        }
        0x52..=0x58 => {
            if let ([dst, obj, ..], Some(field_idx)) = (insn.registers.as_slice(), insn.index) {
                write_reg(
                    state,
                    *dst,
                    Expr::FieldGet {
                        target: Box::new(read_reg(state, *obj)),
                        field: dex.field_ref(field_idx)?,
                    },
                );
            }
        }
        0x59..=0x5f => {
            if let ([value, obj, ..], Some(field_idx)) = (insn.registers.as_slice(), insn.index) {
                out.push(Stmt::FieldPut {
                    target: Box::new(read_reg(state, *obj)),
                    field: dex.field_ref(field_idx)?,
                    value: Box::new(read_reg(state, *value)),
                });
            }
        }
        0x60..=0x66 => {
            if let (Some(dst), Some(field_idx)) = (insn.registers.first().copied(), insn.index) {
                write_reg(
                    state,
                    dst,
                    Expr::StaticFieldGet {
                        field: dex.field_ref(field_idx)?,
                    },
                );
            }
        }
        0x67..=0x6d => {
            if let (Some(value), Some(field_idx)) = (insn.registers.first().copied(), insn.index) {
                out.push(Stmt::StaticFieldPut {
                    field: dex.field_ref(field_idx)?,
                    value: Box::new(read_reg(state, value)),
                });
            }
        }
        0x6e..=0x72 | 0x74..=0x78 => {
            handle_invoke(dex, current_class_descriptor, state, out, insn)?;
        }
        0x7b..=0x8f => {
            if let [dst, src, ..] = insn.registers.as_slice() {
                let expr = match unary_op(insn.opcode) {
                    Some(("", cast_ty)) => Expr::Cast {
                        ty: cast_ty.to_string(),
                        expr: Box::new(read_reg(state, *src)),
                    },
                    Some((op, _)) => Expr::Unary {
                        op: op.to_string(),
                        expr: Box::new(read_reg(state, *src)),
                    },
                    None => read_reg(state, *src),
                };
                write_reg(state, *dst, expr);
            }
        }
        0x90..=0xaf => {
            if let [dst, left, right, ..] = insn.registers.as_slice() {
                write_reg(
                    state,
                    *dst,
                    Expr::Binary {
                        op: binary_op(insn.opcode).to_string(),
                        left: Box::new(read_reg(state, *left)),
                        right: Box::new(read_reg(state, *right)),
                    },
                );
            }
        }
        0xb0..=0xcf => {
            if let [left, right, ..] = insn.registers.as_slice() {
                let lhs = read_reg(state, *left);
                write_reg(
                    state,
                    *left,
                    Expr::Binary {
                        op: binary_op(insn.opcode - 0x20).to_string(),
                        left: Box::new(lhs),
                        right: Box::new(read_reg(state, *right)),
                    },
                );
            }
        }
        0xd0..=0xe2 => {
            if let (Some(dst), Some(left), Some(lit)) = (
                insn.registers.first().copied(),
                insn.registers.get(1).copied(),
                insn.literal,
            ) {
                write_reg(
                    state,
                    dst,
                    Expr::Binary {
                        op: binary_lit_op(insn.opcode).to_string(),
                        left: Box::new(read_reg(state, left)),
                        right: Box::new(Expr::ConstInt(lit)),
                    },
                );
            }
        }
        _ => out.push(Stmt::Comment(format!(
            "unsupported opcode 0x{:02x}",
            insn.opcode
        ))),
    }
    Ok(())
}

fn handle_invoke(
    dex: &DexFile<'_>,
    current_class_descriptor: &str,
    state: &mut MethodState,
    out: &mut Vec<Stmt>,
    insn: &Instruction,
) -> Result<()> {
    let Some(method_idx) = insn.index else {
        return Ok(());
    };
    let method = dex.method_ref(method_idx)?;
    let kind = match insn.opcode {
        0x6f | 0x75 => CallKind::Super,
        0x70 | 0x76 => CallKind::Direct,
        0x71 | 0x77 => CallKind::Static,
        0x72 | 0x78 => CallKind::Interface,
        _ => CallKind::Virtual,
    };

    if method.name == "<init>" {
        if let Some(receiver_reg) = insn.registers.first().copied() {
            let receiver = read_reg(state, receiver_reg);
            let args = insn
                .registers
                .iter()
                .skip(1)
                .map(|reg| read_reg(state, *reg))
                .collect::<Vec<_>>();
            if matches!(receiver, Expr::NewInstance { .. }) {
                write_reg(
                    state,
                    receiver_reg,
                    Expr::NewInstance {
                        class_name: descriptor_simple_name(&method.class_descriptor),
                        args,
                    },
                );
                return Ok(());
            }
            if matches!(receiver, Expr::This) {
                let ctor_kind = if method.class_descriptor == current_class_descriptor {
                    CallKind::Direct
                } else {
                    CallKind::Super
                };
                out.push(Stmt::Expr(Box::new(Expr::Call {
                    kind: ctor_kind,
                    method,
                    target: Some(Box::new(Expr::This)),
                    args,
                })));
                return Ok(());
            }
        }
    }

    let (target, args) = if kind == CallKind::Static {
        (
            None,
            insn.registers
                .iter()
                .map(|reg| read_reg(state, *reg))
                .collect(),
        )
    } else {
        let target = insn
            .registers
            .first()
            .map(|reg| Box::new(read_reg(state, *reg)));
        let args = insn
            .registers
            .iter()
            .skip(1)
            .map(|reg| read_reg(state, *reg))
            .collect();
        (target, args)
    };
    let expr = Expr::Call {
        kind,
        method: method.clone(),
        target,
        args,
    };
    if method.return_descriptor == "V" {
        out.push(Stmt::Expr(Box::new(expr)));
    } else {
        state.pending_result = Some(expr);
    }
    Ok(())
}

fn branch_target(insn: &Instruction) -> Option<u32> {
    insn.branch_offset
        .map(|offset| (insn.code_unit_offset as i64 + offset as i64) as u32)
}

fn if_op(opcode: u8) -> &'static str {
    match opcode {
        0x32 | 0x38 => "==",
        0x33 | 0x39 => "!=",
        0x34 | 0x3a => "<",
        0x35 | 0x3b => ">=",
        0x36 | 0x3c => ">",
        0x37 | 0x3d => "<=",
        _ => "!=",
    }
}

fn unary_op(opcode: u8) -> Option<(&'static str, &'static str)> {
    Some(match opcode {
        0x7b | 0x7d | 0x7f | 0x80 => ("-", ""),
        0x7c | 0x7e => ("~", ""),
        0x81 => ("", "long"),
        0x82 => ("", "float"),
        0x83 => ("", "double"),
        0x84 => ("", "int"),
        0x85 => ("", "float"),
        0x86 => ("", "double"),
        0x87 => ("", "int"),
        0x88 => ("", "long"),
        0x89 => ("", "double"),
        0x8a => ("", "int"),
        0x8b => ("", "long"),
        0x8c => ("", "float"),
        0x8d => ("", "byte"),
        0x8e => ("", "char"),
        0x8f => ("", "short"),
        _ => return None,
    })
}

fn binary_op(opcode: u8) -> &'static str {
    match opcode {
        0x90 | 0x91 | 0x92 | 0x93 | 0xb0 | 0xb1 | 0xb2 | 0xb3 => "+",
        0x94 | 0x95 | 0x96 | 0x97 | 0xb4 | 0xb5 | 0xb6 | 0xb7 => "-",
        0x98 | 0x99 | 0x9a | 0x9b | 0xb8 | 0xb9 | 0xba | 0xbb => "*",
        0x9c | 0x9d | 0x9e | 0x9f | 0xbc | 0xbd | 0xbe | 0xbf => "/",
        0xa0 | 0xa1 | 0xc0 | 0xc1 => "%",
        0xa2 | 0xa3 | 0xc2 | 0xc3 => "&",
        0xa4 | 0xa5 | 0xc4 | 0xc5 => "|",
        0xa6 | 0xa7 | 0xc6 | 0xc7 => "^",
        0xa8 | 0xa9 | 0xc8 | 0xc9 => "<<",
        0xaa | 0xab | 0xca | 0xcb => ">>",
        0xac | 0xad | 0xcc | 0xcd => ">>>",
        _ => "+",
    }
}

fn binary_lit_op(opcode: u8) -> &'static str {
    match opcode {
        0xd0 | 0xd8 => "+",
        0xd1 | 0xd9 => "-",
        0xd2 | 0xda => "*",
        0xd3 | 0xdb => "/",
        0xd4 | 0xdc => "%",
        0xd5 | 0xdd => "&",
        0xd6 | 0xde => "|",
        0xd7 | 0xdf => "^",
        0xe0 => "<<",
        0xe1 => ">>",
        0xe2 => ">>>",
        _ => "+",
    }
}

pub fn emit_stmt(stmt: &Stmt, resources: &BTreeMap<i64, String>) -> Option<String> {
    match stmt {
        Stmt::Assign { target, value } => {
            Some(format!("{target} = {};", emit_expr(value, resources)))
        }
        Stmt::Expr(expr) => Some(format!("{};", emit_expr(expr, resources))),
        Stmt::FieldPut {
            target,
            field,
            value,
        } => Some(format!(
            "{}.{} = {};",
            emit_expr(target, resources),
            field.name,
            emit_expr(value, resources)
        )),
        Stmt::StaticFieldPut { field, value } => Some(format!(
            "{}.{} = {};",
            short_name(&field.class_name),
            field.name,
            emit_expr(value, resources)
        )),
        Stmt::ArrayPut {
            array,
            index,
            value,
        } => Some(format!(
            "{}[{}] = {};",
            emit_expr(array, resources),
            emit_expr(index, resources),
            emit_expr(value, resources)
        )),
        Stmt::Return(None) => None,
        Stmt::Return(Some(value)) => Some(format!("return {};", emit_expr(value, resources))),
        Stmt::Throw(value) => Some(format!("throw {};", emit_expr(value, resources))),
        Stmt::Comment(text) => Some(format!("// {text}")),
    }
}

pub fn emit_expr(expr: &Expr, resources: &BTreeMap<i64, String>) -> String {
    match expr {
        Expr::Reg(reg) => format!("v{reg}"),
        Expr::Param(name) => name.clone(),
        Expr::This => "this".to_string(),
        Expr::ConstInt(value) => resources
            .get(value)
            .cloned()
            .unwrap_or_else(|| value.to_string()),
        Expr::ConstString(value) => format!("\"{}\"", escape_java_string(value)),
        Expr::Null => "null".to_string(),
        Expr::Binary { op, left, right } => format!(
            "({} {op} {})",
            emit_expr(left, resources),
            emit_expr(right, resources)
        ),
        Expr::Unary { op, expr } => format!("({op}{})", emit_expr(expr, resources)),
        Expr::Cast { ty, expr } => format!("(({ty}) {})", emit_expr(expr, resources)),
        Expr::FieldGet { target, field } => {
            format!("{}.{}", emit_expr(target, resources), field.name)
        }
        Expr::StaticFieldGet { field } => {
            format!("{}.{}", short_name(&field.class_name), field.name)
        }
        Expr::ArrayGet { array, index } => format!(
            "{}[{}]",
            emit_expr(array, resources),
            emit_expr(index, resources)
        ),
        Expr::Call {
            kind,
            method,
            target,
            args,
        } => emit_call(*kind, method, target.as_deref(), args, resources),
        Expr::NewInstance { class_name, args } => {
            format!(
                "new {}({})",
                class_name,
                args.iter()
                    .map(|arg| emit_expr(arg, resources))
                    .collect::<Vec<_>>()
                    .join(", ")
            )
        }
        Expr::NewArray { element_type, size } => {
            format!("new {element_type}[{}]", emit_expr(size, resources))
        }
        Expr::ResourceRef(name) => name.clone(),
        Expr::ClassLiteral(name) => format!("{name}.class"),
        Expr::Unknown(text) => text.clone(),
    }
}

fn emit_call(
    kind: CallKind,
    method: &MethodRef,
    target: Option<&Expr>,
    args: &[Expr],
    resources: &BTreeMap<i64, String>,
) -> String {
    let rendered_args = args
        .iter()
        .map(|arg| emit_expr(arg, resources))
        .collect::<Vec<_>>()
        .join(", ");
    if method.name == "<init>" {
        return match kind {
            CallKind::Super => format!("super({rendered_args})"),
            _ => format!("this({rendered_args})"),
        };
    }
    match kind {
        CallKind::Static => format!(
            "{}.{}({rendered_args})",
            short_name(&method.class_name),
            method.name
        ),
        CallKind::Super => format!("super.{}({rendered_args})", method.name),
        _ => match target {
            Some(Expr::This) => format!("{}({rendered_args})", method.name),
            Some(expr) => format!(
                "{}.{}({rendered_args})",
                emit_expr(expr, resources),
                method.name
            ),
            None => format!("{}({rendered_args})", method.name),
        },
    }
}

fn escape_java_string(value: &str) -> String {
    value
        .chars()
        .flat_map(|c| match c {
            '\\' => "\\\\".chars().collect::<Vec<_>>(),
            '"' => "\\\"".chars().collect(),
            '\n' => "\\n".chars().collect(),
            '\r' => "\\r".chars().collect(),
            '\t' => "\\t".chars().collect(),
            c => vec![c],
        })
        .collect()
}
