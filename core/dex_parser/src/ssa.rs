//! SSA construction — phi-node insertion at CFG join points.
//!
//! Uses `cfg::BasicBlock::predecessors` (populated by `build_cfg`) so phi
//! insertion actually runs; dex-hybrid's predecessor list was always empty.

use std::collections::{BTreeMap, BTreeSet};

use crate::cfg::{BasicBlock, ControlFlowGraph};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PhiOperand {
    pub predecessor_block: u32,
    pub register: u16,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PhiNode {
    pub block_id: u32,
    pub target_register: u16,
    pub operands: Vec<PhiOperand>,
}

#[derive(Debug, Clone, Default)]
pub struct SsaForm {
    pub phi_nodes: Vec<PhiNode>,
}

/// Insert phi nodes at every block with multiple predecessors.
/// Registers are inferred from defs in predecessor terminators (minimal slice:
/// one phi per register def seen in any predecessor instruction).
pub fn build_ssa(cfg: &ControlFlowGraph) -> SsaForm {
    let mut phi_nodes = Vec::new();

    for block in &cfg.blocks {
        if block.predecessors.len() < 2 {
            continue;
        }
        let mut regs: BTreeSet<u16> = BTreeSet::new();
        for &pred_id in &block.predecessors {
            if let Some(pred) = cfg.blocks.get(pred_id as usize) {
                collect_defs(pred, &mut regs);
            }
        }
        for reg in regs {
            let operands: Vec<PhiOperand> = block
                .predecessors
                .iter()
                .map(|&pred_id| PhiOperand {
                    predecessor_block: pred_id,
                    register: reg,
                })
                .collect();
            phi_nodes.push(PhiNode {
                block_id: block.id,
                target_register: reg,
                operands,
            });
        }
    }

    SsaForm { phi_nodes }
}

fn collect_defs(block: &BasicBlock, out: &mut BTreeSet<u16>) {
    for insn in &block.instructions {
        for &reg in &insn.registers {
            out.insert(reg);
        }
    }
}

/// Map block id → phi nodes at that block (handy for IR → Java backend).
pub fn phi_by_block(ssa: &SsaForm) -> BTreeMap<u32, Vec<&PhiNode>> {
    let mut map: BTreeMap<u32, Vec<&PhiNode>> = BTreeMap::new();
    for phi in &ssa.phi_nodes {
        map.entry(phi.block_id).or_default().push(phi);
    }
    map
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cfg::build_cfg;
    use crate::code::{CodeUnit, Instruction};
    use crate::opcode::Format;

    fn insn(offset: u32, opcode: u8, format: Format, branch_offset: Option<i32>, registers: Vec<u16>) -> Instruction {
        Instruction {
            code_unit_offset: offset,
            opcode,
            format,
            registers,
            literal: None,
            branch_offset,
            index: None,
        }
    }

    #[test]
    fn join_block_gets_phi_for_defs_in_predecessors() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0x38, Format::F21t, Some(4), vec![0])),
            CodeUnit::Insn(insn(2, 0x12, Format::F11n, None, vec![1])),
            CodeUnit::Insn(insn(3, 0x28, Format::F10t, Some(2), vec![])),
            CodeUnit::Insn(insn(4, 0x12, Format::F11n, None, vec![2])),
            CodeUnit::Insn(insn(5, 0x0e, Format::F10x, None, vec![])),
        ];
        let cfg = build_cfg(&units);
        let ssa = build_ssa(&cfg);
        let join = cfg.blocks.iter().find(|b| b.start == 5).expect("join");
        assert!(join.predecessors.len() >= 2);
        assert!(
            !ssa.phi_nodes.is_empty(),
            "join with multiple preds must produce phi nodes, got {:?}",
            ssa.phi_nodes
        );
        assert!(ssa.phi_nodes.iter().any(|p| p.block_id == join.id));
    }
}
