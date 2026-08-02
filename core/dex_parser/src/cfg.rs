//! Control-flow graph construction from a decoded instruction stream.
//!
//! This is the direct fix for the CFG bug found in dex-hybrid's ir.rs:
//! `BasicBlock.predecessors` was declared but nothing ever pushed to it
//! (only `.successors` was populated), so its phi-node insertion loop
//! (`for pred in &block.predecessors`) never ran — it wasn't computing SSA
//! form, just iterating an always-empty list. Predecessors are computed
//! here as the natural consequence of building successors first and then
//! inverting the edge list, so the two can never drift out of sync.
//!
//! Standard leader-based basic-block algorithm: an instruction starts a
//! new block if it's (1) the first instruction, (2) the target of some
//! branch, or (3) immediately follows a branch/return/throw instruction.
//! The one DEX-specific wrinkle is packed-switch/sparse-switch: their
//! `branch_offset` points to a *payload* data block (not a code target),
//! and the real jump targets live inside that payload's `targets` list,
//! each expressed as an offset relative to the switch instruction's own
//! address — not the payload's. Resolving that indirection correctly is
//! what makes switch statements work at all; getting it wrong would
//! silently produce a CFG with no edges out of every switch.

use std::collections::{BTreeMap, BTreeSet};

use crate::code::{CodeUnit, ExceptionData, Instruction};
use crate::opcode::Format;

#[derive(Debug, Clone)]
pub struct BasicBlock {
    pub id: u32,
    /// Code-unit offset of the first instruction (inclusive).
    pub start: u32,
    /// Code-unit offset one past the last instruction (exclusive).
    pub end: u32,
    pub instructions: Vec<Instruction>,
    pub successors: Vec<u32>,
    pub predecessors: Vec<u32>,
    /// Handler blocks reachable from this block by throwing. Exception edges
    /// are kept separate from normal control flow because they may be taken
    /// from *any* instruction in a protected range, not only its last one.
    pub exception_successors: Vec<u32>,
    /// Blocks whose protected range routes exceptions to this block.
    pub exception_predecessors: Vec<u32>,
    /// True when this block is the entry point of a catch handler.
    pub is_handler: bool,
}

/// One handler entry point reachable from a protected range.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HandlerTarget {
    /// `None` for a catch-all handler.
    pub type_idx: Option<u32>,
    pub addr: u32,
    pub catch_all: bool,
}

/// A `try` region mapped onto the block graph.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProtectedRange {
    pub start: u32,
    pub end: u32,
    pub handlers: Vec<HandlerTarget>,
}

#[derive(Debug, Clone, Default)]
pub struct ControlFlowGraph {
    pub blocks: Vec<BasicBlock>,
    pub protected_ranges: Vec<ProtectedRange>,
}

impl ControlFlowGraph {
    /// Blocks that are catch-handler entry points.
    pub fn handler_blocks(&self) -> Vec<&BasicBlock> {
        self.blocks.iter().filter(|b| b.is_handler).collect()
    }

    pub fn exception_edge_count(&self) -> usize {
        self.blocks.iter().map(|b| b.exception_successors.len()).sum()
    }
}

fn is_unconditional_exit(opcode: u8) -> bool {
    matches!(opcode,
        0x0e..=0x11 // return-void, return, return-wide, return-object
        | 0x27      // throw
        | 0x28 | 0x29 | 0x2a // goto, goto/16, goto/32
    )
}

fn is_conditional_branch(opcode: u8) -> bool {
    matches!(opcode, 0x32..=0x3d) // if-eq..if-lez
}

fn is_switch(opcode: u8) -> bool {
    matches!(opcode, 0x2b | 0x2c) // packed-switch, sparse-switch
}

/// Resolve the real jump targets of a packed-switch/sparse-switch
/// instruction by following its branch_offset to the payload block and
/// reading targets from there (each relative to `switch_offset`, per spec
/// - NOT relative to the payload's own position).
fn resolve_switch_targets(switch_offset: u32, branch_offset: i32, payloads_by_offset: &BTreeMap<u32, &CodeUnit>) -> Vec<u32> {
    let payload_offset = (switch_offset as i64 + branch_offset as i64) as u32;
    match payloads_by_offset.get(&payload_offset) {
        Some(CodeUnit::PackedSwitchPayload { targets, .. }) | Some(CodeUnit::SparseSwitchPayload { targets, .. }) => targets
            .iter()
            .map(|&t| (switch_offset as i64 + t as i64) as u32)
            .collect(),
        _ => Vec::new(), // malformed: switch_offset didn't actually point at a payload
    }
}

/// Build a CFG from one method's decoded code units. Only `CodeUnit::Insn`
/// entries become basic-block content; payload pseudo-instructions are data
/// referenced by switch/fill-array-data instructions, not control-flow
/// nodes themselves, so they're indexed separately and consulted only to
/// resolve switch targets.
pub fn build_cfg(units: &[CodeUnit]) -> ControlFlowGraph {
    build_cfg_with_exceptions(units, &ExceptionData::default())
}

/// Build a CFG that also models `try`/`catch` structure: protected range
/// boundaries and handler entries become block leaders, and every block inside
/// a protected range gains an exception edge to each of that range's handlers.
pub fn build_cfg_with_exceptions(
    units: &[CodeUnit],
    exceptions: &ExceptionData,
) -> ControlFlowGraph {
    let instructions: Vec<&Instruction> = units
        .iter()
        .filter_map(|u| match u {
            CodeUnit::Insn(i) => Some(i),
            _ => None,
        })
        .collect();

    if instructions.is_empty() {
        return ControlFlowGraph::default();
    }

    // decode_instructions doesn't stamp payload CodeUnits with their own
    // offset, so recompute positions by walking `units` in declaration
    // order and accumulating widths exactly as the decoder did.
    let payloads_by_offset: BTreeMap<u32, &CodeUnit> = {
        let mut map = BTreeMap::new();
        let mut pos: u32 = 0;
        for u in units {
            match u {
                CodeUnit::Insn(i) => pos += i.format.width(),
                CodeUnit::PackedSwitchPayload { targets, .. } => {
                    map.insert(pos, u);
                    pos += 4 + 2 * targets.len() as u32;
                }
                CodeUnit::SparseSwitchPayload { keys, .. } => {
                    map.insert(pos, u);
                    pos += 2 + 4 * keys.len() as u32;
                }
                CodeUnit::FillArrayDataPayload { data, .. } => {
                    map.insert(pos, u);
                    pos += 4 + (data.len() as u32).div_ceil(2);
                }
            }
        }
        map
    };

    let last_offset = instructions.last().unwrap().code_unit_offset + instructions.last().unwrap().format.width();

    // --- Rule 1 & 2: collect leaders (first instr + every branch target) ---
    let mut leaders: BTreeSet<u32> = BTreeSet::new();
    leaders.insert(instructions[0].code_unit_offset);

    for insn in &instructions {
        let next_offset = insn.code_unit_offset + insn.format.width();

        if is_switch(insn.opcode) {
            if let Some(bo) = insn.branch_offset {
                for target in resolve_switch_targets(insn.code_unit_offset, bo, &payloads_by_offset) {
                    leaders.insert(target);
                }
            }
            // switch falls through if no case matches - fallthrough is a leader too.
            if next_offset < last_offset {
                leaders.insert(next_offset);
            }
        } else if matches!(insn.format, Format::F10t | Format::F20t | Format::F30t) || is_conditional_branch(insn.opcode) || matches!(insn.format, Format::F21t | Format::F22t) {
            if let Some(bo) = insn.branch_offset {
                let target = (insn.code_unit_offset as i64 + bo as i64) as u32;
                leaders.insert(target);
            }
            // Rule 3: instruction after a branch (conditional or unconditional) is a leader.
            if next_offset < last_offset {
                leaders.insert(next_offset);
            }
        } else if is_unconditional_exit(insn.opcode) && next_offset < last_offset {
            leaders.insert(next_offset);
        }
    }

    // --- Exception structure: range boundaries and handler entries are
    // leaders too, otherwise a handler starts mid-block and can never be
    // referenced as a control-flow target.
    let mut ranges: Vec<ProtectedRange> = Vec::new();
    for item in &exceptions.tries {
        let mut targets: Vec<HandlerTarget> = Vec::new();
        if let Some(handler) = exceptions.handler_for(item) {
            for &(type_idx, addr) in &handler.typed {
                targets.push(HandlerTarget { type_idx: Some(type_idx), addr, catch_all: false });
            }
            if let Some(addr) = handler.catch_all_addr {
                targets.push(HandlerTarget { type_idx: None, addr, catch_all: true });
            }
        }
        if item.start_addr < last_offset {
            leaders.insert(item.start_addr);
        }
        let end = item.end_addr();
        if end < last_offset {
            leaders.insert(end);
        }
        for target in &targets {
            if target.addr < last_offset {
                leaders.insert(target.addr);
            }
        }
        ranges.push(ProtectedRange { start: item.start_addr, end, handlers: targets });
    }

    // --- Partition instructions into blocks at each leader boundary ---
    let leader_list: Vec<u32> = leaders.into_iter().collect();
    let mut blocks: Vec<BasicBlock> = Vec::with_capacity(leader_list.len());
    for (idx, &start) in leader_list.iter().enumerate() {
        let end = leader_list.get(idx + 1).copied().unwrap_or(last_offset);
        let block_insns: Vec<Instruction> = instructions
            .iter()
            .filter(|i| i.code_unit_offset >= start && i.code_unit_offset < end)
            .map(|&i| i.clone())
            .collect();
        blocks.push(BasicBlock {
            id: idx as u32,
            start,
            end,
            instructions: block_insns,
            successors: Vec::new(),
            predecessors: Vec::new(),
            exception_successors: Vec::new(),
            exception_predecessors: Vec::new(),
            is_handler: false,
        });
    }

    let block_id_at = |offset: u32, blocks: &[BasicBlock]| -> Option<u32> {
        blocks.iter().find(|b| b.start == offset).map(|b| b.id)
    };

    // --- Compute successors (and simultaneously the predecessor inverse) ---
    let mut edges: Vec<(u32, u32)> = Vec::new();
    for block in &blocks {
        let Some(last) = block.instructions.last() else { continue };
        let fallthrough_offset = block.end;

        if is_switch(last.opcode) {
            if let Some(bo) = last.branch_offset {
                for target in resolve_switch_targets(last.code_unit_offset, bo, &payloads_by_offset) {
                    if let Some(tid) = block_id_at(target, &blocks) {
                        edges.push((block.id, tid));
                    }
                }
            }
            if fallthrough_offset < last_offset {
                if let Some(tid) = block_id_at(fallthrough_offset, &blocks) {
                    edges.push((block.id, tid));
                }
            }
        } else if matches!(last.format, Format::F10t | Format::F20t | Format::F30t) {
            // unconditional goto: only the branch edge, no fallthrough.
            if let Some(bo) = last.branch_offset {
                let target = (last.code_unit_offset as i64 + bo as i64) as u32;
                if let Some(tid) = block_id_at(target, &blocks) {
                    edges.push((block.id, tid));
                }
            }
        } else if is_conditional_branch(last.opcode) || matches!(last.format, Format::F21t | Format::F22t) {
            if let Some(bo) = last.branch_offset {
                let target = (last.code_unit_offset as i64 + bo as i64) as u32;
                if let Some(tid) = block_id_at(target, &blocks) {
                    edges.push((block.id, tid));
                }
            }
            if fallthrough_offset < last_offset {
                if let Some(tid) = block_id_at(fallthrough_offset, &blocks) {
                    edges.push((block.id, tid));
                }
            }
        } else if is_unconditional_exit(last.opcode) {
            // return/throw: no successors.
        } else if fallthrough_offset < last_offset {
            if let Some(tid) = block_id_at(fallthrough_offset, &blocks) {
                edges.push((block.id, tid));
            }
        }
    }

    for &(from, to) in &edges {
        blocks[from as usize].successors.push(to);
        blocks[to as usize].predecessors.push(from);
    }

    // --- Exception edges: every block inside a protected range can transfer
    // control to each of that range's handlers. A throw may originate at any
    // instruction in the range, so the edge is attached per block rather than
    // only at the range's final block.
    let mut exception_edges: Vec<(u32, u32)> = Vec::new();
    for range in &ranges {
        for target in &range.handlers {
            let Some(handler_id) = block_id_at(target.addr, &blocks) else { continue };
            for block in &blocks {
                if block.start >= range.start && block.start < range.end {
                    exception_edges.push((block.id, handler_id));
                }
            }
        }
    }
    for &(from, to) in &exception_edges {
        if !blocks[from as usize].exception_successors.contains(&to) {
            blocks[from as usize].exception_successors.push(to);
        }
        if !blocks[to as usize].exception_predecessors.contains(&from) {
            blocks[to as usize].exception_predecessors.push(from);
        }
        blocks[to as usize].is_handler = true;
    }

    ControlFlowGraph { blocks, protected_ranges: ranges }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn insn(offset: u32, opcode: u8, format: Format, branch_offset: Option<i32>) -> Instruction {
        Instruction { code_unit_offset: offset, opcode, format, registers: Vec::new(), literal: None, branch_offset, index: None }
    }

    /// if (v0 == 0) { <else> } else-target skipped; <then>; goto end; <else>; end: return
    /// Compiled shape: if-eqz v0,+4 / nop(then) / goto+2 / nop(else) / return-void
    /// This is the exact bug dex-hybrid had: block3 (the join point) must end
    /// up with predecessors=[then_block, else_block] — dex-hybrid's
    /// `.predecessors` was always empty because nothing ever pushed to it.
    #[test]
    fn if_else_diamond_join_block_has_both_predecessors() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0x38, Format::F21t, Some(4))), // if-eqz v0, +4 -> target 4
            CodeUnit::Insn(insn(2, 0x00, Format::F10x, None)),    // nop (then)
            CodeUnit::Insn(insn(3, 0x28, Format::F10t, Some(2))), // goto +2 -> target 5
            CodeUnit::Insn(insn(4, 0x00, Format::F10x, None)),    // nop (else)
            CodeUnit::Insn(insn(5, 0x0e, Format::F10x, None)),    // return-void
        ];

        let cfg = build_cfg(&units);
        assert_eq!(cfg.blocks.len(), 4, "expected 4 blocks: [0,2) if-head, [2,4) then, [4,5) else, [5,6) join");

        let entry = &cfg.blocks[0];
        assert_eq!((entry.start, entry.end), (0, 2));
        assert_eq!(entry.predecessors, Vec::<u32>::new());

        let join = cfg.blocks.iter().find(|b| b.start == 5).expect("join block at offset 5");
        assert_eq!(join.end, 6);
        let mut preds = join.predecessors.clone();
        preds.sort();
        assert_eq!(preds.len(), 2, "join block must have exactly 2 predecessors (then + else), got {:?}", join.predecessors);

        // Every predecessor of the join block must list it back as a successor.
        for &p in &join.predecessors {
            assert!(cfg.blocks[p as usize].successors.contains(&join.id));
        }
    }

    /// Single-instruction infinite loop: nop; goto -1 (branches back to itself).
    /// Exercises a back-edge / self-loop: the block must be its own predecessor.
    #[test]
    fn self_loop_back_edge() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0x00, Format::F10x, None)),    // nop
            CodeUnit::Insn(insn(1, 0x28, Format::F10t, Some(-1))), // goto -1 -> target 0
        ];

        let cfg = build_cfg(&units);
        assert_eq!(cfg.blocks.len(), 1, "no other leaders exist, so this is a single self-looping block");
        let block = &cfg.blocks[0];
        assert_eq!(block.successors, vec![0]);
        assert_eq!(block.predecessors, vec![0]);
    }

    /// Straight-line code (no branches) must produce exactly one block with
    /// no edges at all - the common case, and a regression guard against
    /// over-eagerly splitting blocks where there's no leader to justify it.
    #[test]
    fn straight_line_code_is_one_block_no_edges() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0x12, Format::F11n, None)), // const/4
            CodeUnit::Insn(insn(1, 0x0e, Format::F10x, None)), // return-void
        ];
        let cfg = build_cfg(&units);
        assert_eq!(cfg.blocks.len(), 1);
        assert!(cfg.blocks[0].successors.is_empty());
        assert!(cfg.blocks[0].predecessors.is_empty());
    }

    /// A try range with three typed handlers plus a catch-all: every handler
    /// entry must become its own block with at least one exception predecessor.
    /// Before this slice the handler addresses were not leaders at all, so the
    /// handler entries were unreachable interior instructions.
    #[test]
    fn handlers_become_blocks_with_exception_predecessors() {
        use crate::code::{CatchHandler, ExceptionData, TryItem};

        // [0,3) protected; handlers at 4, 5, 6 and catch-all at 7.
        let units = vec![
            CodeUnit::Insn(insn(0, 0x00, Format::F10x, None)),
            CodeUnit::Insn(insn(1, 0x00, Format::F10x, None)),
            CodeUnit::Insn(insn(2, 0x28, Format::F10t, Some(6))), // goto -> 8
            CodeUnit::Insn(insn(3, 0x00, Format::F10x, None)),
            CodeUnit::Insn(insn(4, 0x0e, Format::F10x, None)), // handler A
            CodeUnit::Insn(insn(5, 0x0e, Format::F10x, None)), // handler B
            CodeUnit::Insn(insn(6, 0x0e, Format::F10x, None)), // handler C
            CodeUnit::Insn(insn(7, 0x0e, Format::F10x, None)), // catch-all
            CodeUnit::Insn(insn(8, 0x0e, Format::F10x, None)), // normal exit
        ];
        let exceptions = ExceptionData {
            tries: vec![TryItem { start_addr: 0, insn_count: 3, handler_off: 0 }],
            handlers: vec![CatchHandler {
                offset: 0,
                typed: vec![(1, 4), (2, 5), (3, 6)],
                catch_all_addr: Some(7),
            }],
        };

        let cfg = build_cfg_with_exceptions(&units, &exceptions);
        assert_eq!(cfg.protected_ranges.len(), 1);
        assert_eq!(cfg.protected_ranges[0].handlers.len(), 4, "3 typed + 1 catch-all");

        for addr in [4u32, 5, 6, 7] {
            let block = cfg
                .blocks
                .iter()
                .find(|b| b.start == addr)
                .unwrap_or_else(|| panic!("no block starts at handler address {addr}"));
            assert!(block.is_handler, "block at {addr} must be marked a handler");
            assert!(
                !block.exception_predecessors.is_empty(),
                "handler block at {addr} must have at least one exception predecessor"
            );
        }
        assert!(cfg.exception_edge_count() >= 4);
    }

    /// Nested/overlapping ranges must each keep their own handler set.
    #[test]
    fn overlapping_try_ranges_keep_distinct_handler_sets() {
        use crate::code::{CatchHandler, ExceptionData, TryItem};

        let units = vec![
            CodeUnit::Insn(insn(0, 0x00, Format::F10x, None)),
            CodeUnit::Insn(insn(1, 0x00, Format::F10x, None)),
            CodeUnit::Insn(insn(2, 0x00, Format::F10x, None)),
            CodeUnit::Insn(insn(3, 0x0e, Format::F10x, None)), // outer handler
            CodeUnit::Insn(insn(4, 0x0e, Format::F10x, None)), // inner handler
        ];
        let exceptions = ExceptionData {
            tries: vec![
                TryItem { start_addr: 0, insn_count: 3, handler_off: 0 },
                TryItem { start_addr: 1, insn_count: 1, handler_off: 4 },
            ],
            handlers: vec![
                CatchHandler { offset: 0, typed: vec![(1, 3)], catch_all_addr: None },
                CatchHandler { offset: 4, typed: vec![(2, 4)], catch_all_addr: None },
            ],
        };

        let cfg = build_cfg_with_exceptions(&units, &exceptions);
        assert_eq!(cfg.protected_ranges.len(), 2);
        assert_eq!(cfg.protected_ranges[0].handlers[0].addr, 3);
        assert_eq!(cfg.protected_ranges[1].handlers[0].addr, 4);

        // The block at offset 1 lies in both ranges, so it reaches both handlers.
        let inner = cfg.blocks.iter().find(|b| b.start == 1).expect("block at 1");
        assert_eq!(
            inner.exception_successors.len(),
            2,
            "block inside both ranges must reach both handlers"
        );
    }

    /// A method with no tries must produce exactly the pre-slice CFG.
    #[test]
    fn no_tries_leaves_graph_unchanged() {
        use crate::code::ExceptionData;

        let units = vec![
            CodeUnit::Insn(insn(0, 0x12, Format::F11n, None)),
            CodeUnit::Insn(insn(1, 0x0e, Format::F10x, None)),
        ];
        let plain = build_cfg(&units);
        let with_empty = build_cfg_with_exceptions(&units, &ExceptionData::default());
        assert_eq!(plain.blocks.len(), with_empty.blocks.len());
        assert!(with_empty.protected_ranges.is_empty());
        assert_eq!(with_empty.exception_edge_count(), 0);
        assert!(with_empty.blocks.iter().all(|b| !b.is_handler));
    }

    /// packed-switch's branch_offset points to a *payload* block, not a code
    /// target - the real targets live inside the payload, each expressed
    /// relative to the switch instruction's own offset (not the payload's).
    /// Getting this indirection wrong means every switch resolves to zero
    /// successors instead of one per case.
    #[test]
    fn resolve_switch_targets_follows_payload_indirection() {
        let switch_offset = 10u32;
        let payload_offset = 20u32; // switch_offset + branch_offset(10)
        let payload = CodeUnit::PackedSwitchPayload { first_key: 0, targets: vec![5, 8] };
        let mut map: BTreeMap<u32, &CodeUnit> = BTreeMap::new();
        map.insert(payload_offset, &payload);

        let resolved = resolve_switch_targets(switch_offset, 10, &map);
        // targets are relative to switch_offset (10), not payload_offset (20).
        assert_eq!(resolved, vec![15, 18]);
    }
}
