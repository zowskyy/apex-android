//! Real SSA construction: dominance-frontier-based phi placement (Cytron et
//! al.) followed by dominator-tree-order variable renaming, on top of
//! `cfg::ControlFlowGraph` + `defuse::def_use`.
//!
//! This is the fix for the exact bug this whole area was built to avoid
//! repeating (see cfg.rs's module doc): dex-hybrid's phi-insertion loop
//! iterated `block.predecessors`, which was always empty because nothing
//! populated it. Here, phi placement is driven by the dominance frontier
//! (itself built from real predecessor/successor edges in dominators.rs),
//! and — critically — a phi's *operands* are filled in per-predecessor
//! during renaming, one value per edge, so a join block with the wrong
//! predecessor count would be caught immediately by a phi with the wrong
//! number of operands rather than silently producing no merge at all.
//!
//! Register versioning convention: version 0 for a vreg means "the value
//! live on entry to the method" (a parameter, or genuinely undefined if the
//! bytecode reads before writing) — real definitions start at version 1.
//! Disambiguating "parameter" from "undefined" would need `ins_size` from
//! the method's `CodeItem`, which this module doesn't have (it only sees
//! the CFG); not needed for def-use tracking, so left as version 0 for both.
//!
//! Scope note: blocks unreachable from the entry (dead code — e.g. the
//! instruction right after an unconditional `return` with nothing branching
//! to it) have no dominance relationship to the rest of the graph, so no
//! phi can be justified for them. They're still converted to
//! `SsaInstruction`s (for output completeness) but each is renamed in
//! isolation, with no cross-block merging and no phis of its own.

use std::collections::HashMap;

use crate::cfg::ControlFlowGraph;
use crate::defuse::def_use;
use crate::dominators::{dominance_frontiers, immediate_dominators, reverse_postorder, ENTRY};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct SsaValue {
    pub vreg: u16,
    /// 0 = value live on entry (parameter or undefined-read); real defs start at 1.
    pub version: u32,
}

#[derive(Debug, Clone)]
pub struct Phi {
    pub vreg: u16,
    pub result: SsaValue,
    /// One incoming value per predecessor edge, in the same order as
    /// `cfg.blocks[block].predecessors`.
    pub operands: Vec<SsaValue>,
}

#[derive(Debug, Clone)]
pub struct SsaInstruction {
    pub code_unit_offset: u32,
    pub defs: Vec<SsaValue>,
    pub uses: Vec<SsaValue>,
}

#[derive(Debug, Clone, Default)]
pub struct SsaBlock {
    pub phis: Vec<Phi>,
    pub instructions: Vec<SsaInstruction>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum UseSite {
    Instruction { block: u32, code_unit_offset: u32 },
    Phi { block: u32, vreg: u16 },
}

#[derive(Debug, Clone, Default)]
pub struct SsaFunction {
    pub blocks: HashMap<u32, SsaBlock>,
    /// Def-use chains: every site that reads a given SSA value. A value
    /// with no entry here is dead (defined but never read) — including,
    /// notably, most `move-result*` targets that only feed the very next
    /// instruction, and any def whose only "use" is being clobbered before
    /// a read.
    pub uses_of: HashMap<SsaValue, Vec<UseSite>>,
}

fn entry_value(vreg: u16) -> SsaValue {
    SsaValue { vreg, version: 0 }
}

fn fresh(vreg: u16, counters: &mut HashMap<u16, u32>) -> SsaValue {
    let counter = counters.entry(vreg).or_insert(0);
    *counter += 1;
    SsaValue {
        vreg,
        version: *counter,
    }
}

/// Cytron et al. minimal-SSA phi placement: for every register, insert a
/// phi at every block in the iterated dominance frontier of its def sites.
fn place_phis(
    cfg: &ControlFlowGraph,
    df: &HashMap<u32, std::collections::HashSet<u32>>,
    reachable: &std::collections::HashSet<u32>,
) -> HashMap<u32, SsaBlock> {
    let mut defsites: HashMap<u16, std::collections::HashSet<u32>> = HashMap::new();
    for block in &cfg.blocks {
        if !reachable.contains(&block.id) {
            continue;
        }
        for insn in &block.instructions {
            for &d in &def_use(insn).defs {
                defsites.entry(d).or_default().insert(block.id);
            }
        }
    }

    let mut blocks: HashMap<u32, SsaBlock> = HashMap::new();
    for &b in reachable {
        blocks.insert(b, SsaBlock::default());
    }

    for (&vreg, sites) in &defsites {
        let mut has_phi: std::collections::HashSet<u32> = std::collections::HashSet::new();
        let mut worklist: Vec<u32> = sites.iter().copied().collect();
        while let Some(d) = worklist.pop() {
            let Some(frontier) = df.get(&d) else { continue };
            for &y in frontier {
                if has_phi.insert(y) {
                    let preds_len = cfg.blocks[y as usize].predecessors.len();
                    blocks.get_mut(&y).unwrap().phis.push(Phi {
                        vreg,
                        result: entry_value(vreg), // placeholder; assigned during renaming
                        operands: vec![entry_value(vreg); preds_len],
                    });
                    if !sites.contains(&y) {
                        worklist.push(y);
                    }
                }
            }
        }
    }

    blocks
}

/// Dominator-tree-order renaming (Cytron et al.'s "Search" procedure,
/// iterative to avoid recursion depth issues on adversarial input).
fn rename(
    cfg: &ControlFlowGraph,
    idom: &HashMap<u32, u32>,
    blocks: &mut HashMap<u32, SsaBlock>,
    uses_of: &mut HashMap<SsaValue, Vec<UseSite>>,
) {
    let mut children: HashMap<u32, Vec<u32>> = HashMap::new();
    for (&b, &p) in idom {
        if b != ENTRY {
            children.entry(p).or_default().push(b);
        }
    }

    let mut stacks: HashMap<u16, Vec<u32>> = HashMap::new();
    let mut counters: HashMap<u16, u32> = HashMap::new();
    let top = |stacks: &HashMap<u16, Vec<u32>>, vreg: u16| -> SsaValue {
        match stacks.get(&vreg).and_then(|s| s.last()) {
            Some(&v) => SsaValue { vreg, version: v },
            None => entry_value(vreg),
        }
    };

    // Explicit stack DFS over the dominator tree; each frame remembers which
    // registers it pushed so they can be popped exactly once, on the way out.
    let mut stack: Vec<(u32, bool, Vec<u16>)> = vec![(ENTRY, false, Vec::new())];
    while let Some((block, entered, _)) = stack.last().cloned() {
        if !entered {
            let mut pushed: Vec<u16> = Vec::new();

            if let Some(ssa_block) = blocks.get_mut(&block) {
                for phi in &mut ssa_block.phis {
                    let v = fresh(phi.vreg, &mut counters);
                    stacks.entry(phi.vreg).or_default().push(v.version);
                    pushed.push(phi.vreg);
                    phi.result = v;
                }
            }

            let mut new_instructions = Vec::new();
            for insn in &cfg.blocks[block as usize].instructions {
                let du = def_use(insn);
                let mut use_vals = Vec::new();
                for &u in &du.uses {
                    let val = top(&stacks, u);
                    use_vals.push(val);
                    uses_of.entry(val).or_default().push(UseSite::Instruction {
                        block,
                        code_unit_offset: insn.code_unit_offset,
                    });
                }
                let mut def_vals = Vec::new();
                for &d in &du.defs {
                    let v = fresh(d, &mut counters);
                    stacks.entry(d).or_default().push(v.version);
                    pushed.push(d);
                    def_vals.push(v);
                }
                new_instructions.push(SsaInstruction {
                    code_unit_offset: insn.code_unit_offset,
                    defs: def_vals,
                    uses: use_vals,
                });
            }
            if let Some(ssa_block) = blocks.get_mut(&block) {
                ssa_block.instructions = new_instructions;
            }

            // Fill this block's outgoing phi operands now, while its
            // top-of-stack values are current (before recursing further, and
            // before this block's own pushes get popped).
            for &succ in &cfg.blocks[block as usize].successors {
                let Some(pred_index) = cfg.blocks[succ as usize]
                    .predecessors
                    .iter()
                    .position(|&p| p == block)
                else {
                    continue;
                };
                if let Some(succ_block) = blocks.get_mut(&succ) {
                    for phi in &mut succ_block.phis {
                        let val = top(&stacks, phi.vreg);
                        phi.operands[pred_index] = val;
                        uses_of.entry(val).or_default().push(UseSite::Phi {
                            block: succ,
                            vreg: phi.vreg,
                        });
                    }
                }
            }

            let last = stack.last_mut().unwrap();
            last.1 = true;
            last.2 = pushed;

            for &child in children.get(&block).unwrap_or(&Vec::new()) {
                stack.push((child, false, Vec::new()));
            }
        } else {
            for vreg in &stack.last().unwrap().2 {
                stacks.get_mut(vreg).unwrap().pop();
            }
            stack.pop();
        }
    }
}

/// Any block `build_cfg` produced that dominance analysis never reached
/// (dead code with no path from the method's entry) still gets converted to
/// `SsaInstruction`s, but in isolation: no phis, and every use defaults to
/// the block's own local version-0 rather than merging with the reachable
/// graph, since there's no dominance relationship to justify a merge.
fn rename_unreachable_blocks(
    cfg: &ControlFlowGraph,
    reachable: &std::collections::HashSet<u32>,
    blocks: &mut HashMap<u32, SsaBlock>,
) {
    for block in &cfg.blocks {
        if reachable.contains(&block.id) {
            continue;
        }
        let mut counters: HashMap<u16, u32> = HashMap::new();
        let mut stacks: HashMap<u16, u32> = HashMap::new();
        let mut instructions = Vec::new();
        for insn in &block.instructions {
            let du = def_use(insn);
            let uses = du
                .uses
                .iter()
                .map(|&u| SsaValue {
                    vreg: u,
                    version: stacks.get(&u).copied().unwrap_or(0),
                })
                .collect();
            let defs: Vec<SsaValue> = du
                .defs
                .iter()
                .map(|&d| {
                    let v = fresh(d, &mut counters);
                    stacks.insert(d, v.version);
                    v
                })
                .collect();
            instructions.push(SsaInstruction {
                code_unit_offset: insn.code_unit_offset,
                defs,
                uses,
            });
        }
        blocks.insert(
            block.id,
            SsaBlock {
                phis: Vec::new(),
                instructions,
            },
        );
    }
}

/// Build full SSA form for one method's CFG: phi placement at the iterated
/// dominance frontier of each register's def sites, then a renaming pass
/// that assigns a fresh version to every def and resolves every use to its
/// reaching definition (real def or phi), recording the resulting def-use
/// chains.
pub fn build_ssa(cfg: &ControlFlowGraph) -> SsaFunction {
    if cfg.blocks.is_empty() {
        return SsaFunction::default();
    }

    let rpo = reverse_postorder(cfg);
    let reachable: std::collections::HashSet<u32> = rpo.iter().copied().collect();
    let idom = immediate_dominators(cfg, &rpo);
    let df = dominance_frontiers(cfg, &idom);

    let mut blocks = place_phis(cfg, &df, &reachable);
    let mut uses_of = HashMap::new();
    rename(cfg, &idom, &mut blocks, &mut uses_of);
    rename_unreachable_blocks(cfg, &reachable, &mut blocks);

    SsaFunction { blocks, uses_of }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cfg::build_cfg;
    use crate::code::{CodeUnit, Instruction};
    use crate::opcode::Format;

    fn insn(
        offset: u32,
        opcode: u8,
        format: Format,
        registers: Vec<u16>,
        branch_offset: Option<i32>,
    ) -> Instruction {
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

    /// if (v0) v1 = const 1 else v1 = const 2; return v1
    /// Compiled shape: if-eqz v0,+? / then: const/4 v1,1 / goto join / else:
    /// const/4 v1,2 / join: return v1 (uses v1).
    /// The textbook phi case: v1's join-block use must resolve to a phi with
    /// exactly 2 operands, one per branch's distinct SSA version — this is
    /// the property dex-hybrid's dead predecessor-tracking made structurally
    /// impossible (no predecessors -> no phi could ever be placed).
    #[test]
    fn diamond_produces_phi_with_two_distinct_operands() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0x38, Format::F21t, vec![0], Some(4))), // if-eqz v0 -> 4
            CodeUnit::Insn(insn(2, 0x12, Format::F11n, vec![1], None)),    // const/4 v1, #1 (then)
            CodeUnit::Insn(insn(3, 0x28, Format::F10t, vec![], Some(2))),  // goto -> 5
            CodeUnit::Insn(insn(4, 0x12, Format::F11n, vec![1], None)),    // const/4 v1, #2 (else)
            CodeUnit::Insn(insn(5, 0x0f, Format::F11x, vec![1], None)),    // return v1 (join)
        ];
        let cfg = build_cfg(&units);
        let ssa = build_ssa(&cfg);

        let join_id = cfg.blocks.iter().find(|b| b.start == 5).unwrap().id;
        let join = &ssa.blocks[&join_id];
        assert_eq!(join.phis.len(), 1, "exactly one phi, for v1");
        let phi = &join.phis[0];
        assert_eq!(phi.vreg, 1);
        assert_eq!(phi.operands.len(), 2, "one operand per predecessor edge");
        assert_ne!(
            phi.operands[0], phi.operands[1],
            "then/else assign v1 in different blocks, so must carry distinct SSA versions"
        );
        for op in &phi.operands {
            assert_eq!(op.vreg, 1);
            assert_ne!(
                op.version, 0,
                "both operands come from real defs, not the entry/undefined value"
            );
        }

        // The join block's `return v1` must use the phi's result, not either branch's raw def.
        let ret = &join.instructions[0];
        assert_eq!(ret.uses, vec![phi.result]);

        // uses_of must record both the phi-operand use sites (from each
        // predecessor) and the return's use of the phi result.
        assert_eq!(ssa.uses_of.get(&phi.result).map(|v| v.len()), Some(1));
        for op in &phi.operands {
            let sites = ssa
                .uses_of
                .get(op)
                .expect("each branch's def must be recorded as read by the phi");
            assert!(sites.contains(&UseSite::Phi {
                block: join_id,
                vreg: 1
            }));
        }
    }

    /// Straight-line code: v0 = const 1; v0 = const 2; return v0. No phis
    /// (single predecessor path throughout); the return must use the SECOND
    /// def's version, not the first — i.e. renaming must track the most
    /// recent def within a single block, not just "some" def.
    #[test]
    fn straight_line_uses_most_recent_def_in_block() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0x12, Format::F11n, vec![0], None)), // const/4 v0, #1
            CodeUnit::Insn(insn(1, 0x12, Format::F11n, vec![0], None)), // const/4 v0, #2
            CodeUnit::Insn(insn(2, 0x0f, Format::F11x, vec![0], None)), // return v0
        ];
        let cfg = build_cfg(&units);
        let ssa = build_ssa(&cfg);
        let block = &ssa.blocks[&ENTRY];
        assert!(block.phis.is_empty());
        assert_eq!(block.instructions[0].defs[0].version, 1);
        assert_eq!(block.instructions[1].defs[0].version, 2);
        assert_eq!(
            block.instructions[2].uses[0].version, 2,
            "must reference the second def, not the first"
        );
    }

    /// A vreg read with no preceding def anywhere in the method (e.g. a
    /// parameter) must resolve to version 0, not panic or fabricate a def.
    #[test]
    fn undefined_read_resolves_to_entry_version_zero() {
        let units = vec![CodeUnit::Insn(insn(0, 0x0f, Format::F11x, vec![2], None))]; // return v2, never defined
        let cfg = build_cfg(&units);
        let ssa = build_ssa(&cfg);
        let block = &ssa.blocks[&ENTRY];
        assert_eq!(
            block.instructions[0].uses,
            vec![SsaValue {
                vreg: 2,
                version: 0
            }]
        );
    }

    /// Loop: v0 = const 0 (preheader); header: if (v0 >= N) exit; v0 = v0 +
    /// 1 (body); goto header. The header's use of v0 must be a phi merging
    /// the preheader's def with the body's def — the loop-carried-value
    /// case, which needs a back-edge in `predecessors` to work at all.
    #[test]
    fn loop_header_phi_merges_preheader_and_back_edge() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0x12, Format::F11n, vec![0], None)), // const/4 v0, #0 (preheader)
            CodeUnit::Insn(insn(1, 0x38, Format::F21t, vec![0], Some(5))), // header: if-eqz v0 -> 6 (exit)
            CodeUnit::Insn(insn(3, 0xd8, Format::F22b, vec![0, 0], None)), // body: v0 = v0 + #1 (add-int/lit8, width 2)
            CodeUnit::Insn(insn(5, 0x28, Format::F10t, vec![], Some(-4))), // goto -> header (1)
            CodeUnit::Insn(insn(6, 0x0e, Format::F10x, vec![], None)),     // exit: return-void
        ];
        let cfg = build_cfg(&units);
        let header_id = cfg.blocks.iter().find(|b| b.start == 1).unwrap().id;
        assert_eq!(
            cfg.blocks[header_id as usize].predecessors.len(),
            2,
            "preheader + back-edge"
        );

        let ssa = build_ssa(&cfg);
        let header = &ssa.blocks[&header_id];
        assert_eq!(header.phis.len(), 1);
        assert_eq!(header.phis[0].vreg, 0);
        assert_ne!(header.phis[0].operands[0], header.phis[0].operands[1]);

        // The header's own if-eqz must use the phi's result, not the raw preheader def.
        assert_eq!(header.instructions[0].uses, vec![header.phis[0].result]);
    }

    /// Degenerate but real shape: a single block that is its own entire
    /// body, unconditionally looping to itself (`while(true) { v0 = v0+1; }`
    /// with no exit compiles to exactly this — one block, one back-edge).
    /// v0's read at the top of the block must merge the entry value (first
    /// iteration) with the previous iteration's def (from the back-edge)
    /// via a phi — this is the exact case dominators.rs's dominance-frontier
    /// computation initially missed (entry whose only predecessor is
    /// itself), caught by this test failing before that fix.
    #[test]
    fn self_loop_with_carried_register_gets_entry_phi() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0xd8, Format::F22b, vec![0, 0], None)), // v0 = v0 + #1
            CodeUnit::Insn(insn(2, 0x28, Format::F10t, vec![], Some(-2))), // goto -> 0
        ];
        let cfg = build_cfg(&units);
        assert_eq!(cfg.blocks.len(), 1);
        assert_eq!(cfg.blocks[0].predecessors, vec![0]);

        let ssa = build_ssa(&cfg);
        let block = &ssa.blocks[&ENTRY];
        assert_eq!(
            block.phis.len(),
            1,
            "v0's cross-iteration merge needs a phi at the block's own top"
        );
        assert_eq!(block.phis[0].vreg, 0);
        assert_eq!(
            block.phis[0].operands.len(),
            1,
            "one operand: the back-edge from this same block"
        );

        // The add's use of v0 must be the phi's result (the merged value),
        // and the back-edge operand must be THIS iteration's def, not the
        // entry value — i.e. the loop genuinely carries the incremented value.
        assert_eq!(block.instructions[0].uses, vec![block.phis[0].result]);
        assert_eq!(block.phis[0].operands[0], block.instructions[0].defs[0]);
    }
}
