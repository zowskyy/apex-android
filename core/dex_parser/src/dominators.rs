//! Dominator tree and dominance frontier computation over a `cfg::ControlFlowGraph`.
//!
//! Standard Cooper/Harvey/Kennedy "A Simple, Fast Dominance Algorithm"
//! iterative dataflow for immediate dominators, followed by the Cytron et
//! al. dominance-frontier algorithm. Both need a reverse-postorder walk from
//! the entry block (always block 0 — `cfg::build_cfg` puts the method's
//! first instruction in the first leader, which is always the entry) rather
//! than assuming block-id order already is RPO: block ids are assigned in
//! ascending code-offset order, which is NOT the same as RPO once a forward
//! branch jumps over a block that a later, earlier-offset predecessor
//! doesn't dominate through.

use std::collections::{HashMap, HashSet};

use crate::cfg::ControlFlowGraph;

pub const ENTRY: u32 = 0;

/// Reverse postorder over blocks reachable from `ENTRY`. Unreachable blocks
/// (dead code — no path from the method's entry) are excluded; they have no
/// well-defined dominator and SSA construction has nothing to say about
/// them.
pub fn reverse_postorder(cfg: &ControlFlowGraph) -> Vec<u32> {
    let mut visited: HashSet<u32> = HashSet::new();
    let mut postorder: Vec<u32> = Vec::new();

    if cfg.blocks.is_empty() {
        return postorder;
    }

    // Explicit stack DFS (not recursive) so a pathologically deep CFG from
    // malformed/adversarial bytecode can't blow the stack.
    enum Frame {
        Enter(u32),
        Finish(u32),
    }
    let mut stack = vec![Frame::Enter(ENTRY)];
    while let Some(frame) = stack.pop() {
        match frame {
            Frame::Enter(b) => {
                if !visited.insert(b) {
                    continue;
                }
                stack.push(Frame::Finish(b));
                for &succ in &cfg.blocks[b as usize].successors {
                    if !visited.contains(&succ) {
                        stack.push(Frame::Enter(succ));
                    }
                }
            }
            Frame::Finish(b) => postorder.push(b),
        }
    }

    postorder.reverse();
    postorder
}

/// Immediate dominator of every block reachable from `ENTRY` (`ENTRY` maps
/// to itself, per convention). Blocks not reachable from `ENTRY` are absent.
pub fn immediate_dominators(cfg: &ControlFlowGraph, rpo: &[u32]) -> HashMap<u32, u32> {
    let rpo_index: HashMap<u32, usize> = rpo.iter().enumerate().map(|(i, &b)| (b, i)).collect();

    let mut idom: HashMap<u32, u32> = HashMap::new();
    if rpo.is_empty() {
        return idom;
    }
    idom.insert(ENTRY, ENTRY);

    let intersect = |mut u: u32,
                     mut v: u32,
                     idom: &HashMap<u32, u32>,
                     rpo_index: &HashMap<u32, usize>|
     -> u32 {
        while u != v {
            while rpo_index[&u] > rpo_index[&v] {
                u = idom[&u];
            }
            while rpo_index[&v] > rpo_index[&u] {
                v = idom[&v];
            }
        }
        u
    };

    let mut changed = true;
    while changed {
        changed = false;
        for &b in rpo.iter().skip(1) {
            let preds = &cfg.blocks[b as usize].predecessors;
            let mut processed_preds = preds.iter().copied().filter(|p| idom.contains_key(p));
            let Some(first) = processed_preds.next() else {
                continue;
            };
            let mut new_idom = first;
            for p in processed_preds {
                new_idom = intersect(new_idom, p, &idom, &rpo_index);
            }
            if idom.get(&b) != Some(&new_idom) {
                idom.insert(b, new_idom);
                changed = true;
            }
        }
    }

    idom
}

/// Dominance frontier of every reachable block: `DF[b]` is the set of blocks
/// where `b`'s dominance ends but control can still reach directly from
/// somewhere `b` dominates — exactly where a phi for a value defined at (or
/// dominated by) `b` must be placed to merge with values from other paths.
pub fn dominance_frontiers(
    cfg: &ControlFlowGraph,
    idom: &HashMap<u32, u32>,
) -> HashMap<u32, HashSet<u32>> {
    let mut df: HashMap<u32, HashSet<u32>> = idom.keys().map(|&b| (b, HashSet::new())).collect();

    for &b in idom.keys() {
        let preds = &cfg.blocks[b as usize].predecessors;
        if preds.len() < 2 {
            continue;
        }
        for &p in preds {
            if !idom.contains_key(&p) {
                continue; // unreachable predecessor, no dominator info
            }
            let mut runner = p;
            while runner != idom[&b] {
                df.entry(runner).or_default().insert(b);
                if runner == idom[&runner] {
                    break; // reached ENTRY without hitting idom[b]; stop rather than loop forever
                }
                runner = idom[&runner];
            }
        }
    }

    // Special case: entry with a direct self-loop (its only real predecessor
    // is itself). The loop above never adds ENTRY to its own frontier here,
    // because `idom(ENTRY) == ENTRY == p`, so the "walk from p up to
    // idom(b)" loop's stop condition is already satisfied before it starts
    // — and the `preds.len() < 2` gate independently blocks it too, since
    // there's exactly one real predecessor. Both of those fire because the
    // standard algorithm implicitly assumes ENTRY has an "outside" (caller)
    // predecessor it never models as a graph edge. That implicit edge is
    // exactly what makes this a real merge point: at runtime, control
    // reaches ENTRY either from the method's actual entry (a second source,
    // just not one we track as a block) or from the back-edge — so a value
    // redefined inside the loop and read at the top genuinely needs a phi
    // there. Every other self-loop (one with an additional real, non-self
    // predecessor) already gets this correctly from the general algorithm.
    if idom.contains_key(&ENTRY) && cfg.blocks[ENTRY as usize].predecessors.contains(&ENTRY) {
        df.entry(ENTRY).or_default().insert(ENTRY);
    }

    df
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cfg::build_cfg;
    use crate::code::{CodeUnit, Instruction};
    use crate::opcode::Format;

    fn insn(offset: u32, opcode: u8, format: Format, branch_offset: Option<i32>) -> Instruction {
        Instruction {
            code_unit_offset: offset,
            opcode,
            format,
            registers: Vec::new(),
            literal: None,
            branch_offset,
            index: None,
        }
    }

    /// Same if/else diamond as cfg.rs's test: entry -> {then, else} -> join.
    /// The textbook case a dominance frontier must get right: idom(join) is
    /// entry (not then or else, since neither alone dominates it), and
    /// DF(then) = DF(else) = {join} (each dominates itself and nothing past
    /// join), while DF(entry) = {} (entry dominates everything).
    #[test]
    fn diamond_dominance_frontier() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0x38, Format::F21t, Some(4))), // if-eqz v0 -> 4
            CodeUnit::Insn(insn(2, 0x00, Format::F10x, None)),    // then
            CodeUnit::Insn(insn(3, 0x28, Format::F10t, Some(2))), // goto -> 5
            CodeUnit::Insn(insn(4, 0x00, Format::F10x, None)),    // else
            CodeUnit::Insn(insn(5, 0x0e, Format::F10x, None)),    // join: return-void
        ];
        let cfg = build_cfg(&units);
        let rpo = reverse_postorder(&cfg);
        assert_eq!(rpo.len(), 4, "all 4 blocks reachable");
        assert_eq!(rpo[0], ENTRY);

        let idom = immediate_dominators(&cfg, &rpo);
        let entry = cfg.blocks.iter().find(|b| b.start == 0).unwrap().id;
        let then_b = cfg.blocks.iter().find(|b| b.start == 2).unwrap().id;
        let else_b = cfg.blocks.iter().find(|b| b.start == 4).unwrap().id;
        let join = cfg.blocks.iter().find(|b| b.start == 5).unwrap().id;

        assert_eq!(idom[&then_b], entry);
        assert_eq!(idom[&else_b], entry);
        assert_eq!(
            idom[&join], entry,
            "join is dominated by entry, not by either branch alone"
        );

        let df = dominance_frontiers(&cfg, &idom);
        assert_eq!(df[&then_b], HashSet::from([join]));
        assert_eq!(df[&else_b], HashSet::from([join]));
        assert!(
            df[&entry].is_empty(),
            "entry dominates the whole graph, so it has no dominance frontier"
        );
        assert!(df[&join].is_empty());
    }

    /// Self-looping single block: idom(entry)=entry, DF(entry) must include
    /// itself — the classic "a block can be in its own dominance frontier"
    /// case for a back-edge loop with no other exit.
    #[test]
    fn self_loop_is_own_dominance_frontier() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0x00, Format::F10x, None)), // nop
            CodeUnit::Insn(insn(1, 0x28, Format::F10t, Some(-1))), // goto -1 -> 0
        ];
        let cfg = build_cfg(&units);
        let rpo = reverse_postorder(&cfg);
        let idom = immediate_dominators(&cfg, &rpo);
        assert_eq!(idom[&ENTRY], ENTRY);
        let df = dominance_frontiers(&cfg, &idom);
        assert_eq!(df[&ENTRY], HashSet::from([ENTRY]));
    }

    #[test]
    fn straight_line_has_trivial_dominators() {
        let units = vec![
            CodeUnit::Insn(insn(0, 0x12, Format::F11n, None)),
            CodeUnit::Insn(insn(1, 0x0e, Format::F10x, None)),
        ];
        let cfg = build_cfg(&units);
        let rpo = reverse_postorder(&cfg);
        assert_eq!(rpo, vec![0]);
        let idom = immediate_dominators(&cfg, &rpo);
        assert_eq!(idom[&ENTRY], ENTRY);
        let df = dominance_frontiers(&cfg, &idom);
        assert!(df[&ENTRY].is_empty());
    }
}
