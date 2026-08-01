//! Per-instruction register def/use extraction.
//!
//! `Instruction.registers` (from code.rs) is already ordered per the
//! format's bit layout (vA, vB, vC...), but *which* position is written vs.
//! read — and whether it's a single register or the low half of a 64-bit
//! pair — depends on the opcode's semantics, not the format alone: e.g.
//! F12x covers `move vA, vB` (A=def, B=use, both narrow), `neg-long vA, vB`
//! (A=def, B=use, both wide pairs), *and* `add-int/2addr vA, vB` (A is BOTH
//! def and use: `vA = vA op vB`). This is organized as one match over the
//! opcode byte (same ranges as opcode.rs's `format_of`) so it can be audited
//! directly against the Dalvik bytecode reference table, rather than
//! inferring semantics from format shape.
//!
//! Wide (64-bit) values occupy a register *pair* (`vA` and `vA+1`); such an
//! operand contributes both registers to `defs`/`uses` so a caller never has
//! to separately ask "was that def wide?" — the pair is already there.
//!
//! Field/array/static accesses (iget/iput/sget/sput/aget/aput) read or write
//! *memory*, not a second virtual register, so only operands that are
//! actually vreg reads/writes are reported — e.g. `iput vA, vB, field` uses
//! vA (value) and vB (object ref) but defines no register at all (the def
//! lands in a field, not a vreg).

use crate::code::Instruction;

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct DefUse {
    /// Registers this instruction writes (0, 1, or 2 — 2 for a wide/64-bit
    /// destination, as `[low, low+1]`). Dalvik instructions never define
    /// more than one *logical* value; multi-value results (invoke) go
    /// through a separate move-result* instruction instead.
    pub defs: Vec<u16>,
    /// Registers this instruction reads (a wide operand contributes both
    /// halves). A register that is both read and written (e.g. a `/2addr`
    /// binop) appears in both `defs` and `uses`.
    pub uses: Vec<u16>,
}

fn n(reg: u16) -> Vec<u16> {
    vec![reg]
}
fn w(reg: u16) -> Vec<u16> {
    vec![reg, reg.wrapping_add(1)]
}
fn none() -> DefUse {
    DefUse::default()
}
fn def(regs: Vec<u16>) -> DefUse {
    DefUse { defs: regs, uses: Vec::new() }
}
fn uses_only(regs: Vec<u16>) -> DefUse {
    DefUse { defs: Vec::new(), uses: regs }
}
fn def_uses(defs: Vec<u16>, uses: Vec<u16>) -> DefUse {
    DefUse { defs, uses }
}

/// Determine the registers `insn` defines and uses. Best-effort for the
/// quickened/ODEX-only range (0xe3-0xf9): those opcodes never appear in
/// build-time/APK-shipped DEX (see opcode.rs), so their exact def/use split
/// is unverified against real bytecode — conservatively treated as
/// use-only rather than guessing which register is written.
pub fn def_use(insn: &Instruction) -> DefUse {
    let r = &insn.registers;
    match insn.opcode {
        // --- move family ---
        0x01..=0x03 => def_uses(n(r[0]), n(r[1])), // move, move/from16, move/16
        0x04..=0x06 => def_uses(w(r[0]), w(r[1])), // move-wide (+from16/16)
        0x07..=0x09 => def_uses(n(r[0]), n(r[1])), // move-object (+from16/16)
        0x0a => def(n(r[0])),                              // move-result
        0x0b => def(w(r[0])),                               // move-result-wide
        0x0c => def(n(r[0])),                               // move-result-object
        0x0d => def(n(r[0])),                               // move-exception
        0x0e => none(),                                     // return-void
        0x0f | 0x11 => uses_only(n(r[0])),                  // return, return-object
        0x10 => uses_only(w(r[0])),                         // return-wide

        // --- const family (all defs, no uses) ---
        0x12..=0x15 => def(n(r[0])), // const/4, const/16, const, const/high16
        0x16..=0x19 => def(w(r[0])), // const-wide/16, /32, const-wide, /high16
        0x1a..=0x1c => def(n(r[0])),        // const-string(+jumbo), const-class

        0x1d | 0x1e => uses_only(n(r[0])), // monitor-enter/exit
        0x1f => uses_only(n(r[0])),        // check-cast: verifies in place, defines nothing
        0x20 => def_uses(n(r[0]), n(r[1])), // instance-of
        0x21 => def_uses(n(r[0]), n(r[1])), // array-length
        0x22 => def(n(r[0])),               // new-instance
        0x23 => def_uses(n(r[0]), n(r[1])), // new-array: vA = new T[vB]
        0x24 | 0x25 => uses_only(r.clone()), // filled-new-array(-range): result via move-result-object
        0x26 => uses_only(n(r[0])),         // fill-array-data
        0x27 => uses_only(n(r[0])),         // throw
        0x28..=0x2a => none(),       // goto, goto/16, goto/32
        0x2b | 0x2c => uses_only(n(r[0])),  // packed-switch, sparse-switch

        // --- compares: cmpl/cmpg-float narrow, cmpl/cmpg-double + cmp-long wide ---
        0x2d | 0x2e => def_uses(n(r[0]), [n(r[1]), n(r[2])].concat()),
        0x2f..=0x31 => def_uses(n(r[0]), [w(r[1]), w(r[2])].concat()),

        0x32..=0x37 => uses_only([n(r[0]), n(r[1])].concat()), // if-eq..if-le
        0x38..=0x3d => uses_only(n(r[0])),                     // if-eqz..if-lez
        0x3e..=0x43 => none(),                                 // unused

        // aget family: 0x44 aget .. 0x4a aget-short; only aget-wide (0x45) is wide
        0x44 | 0x46..=0x4a => def_uses(n(r[0]), [n(r[1]), n(r[2])].concat()),
        0x45 => def_uses(w(r[0]), [n(r[1]), n(r[2])].concat()),
        // aput family: 0x4b aput .. 0x51 aput-short; only aput-wide (0x4c) is wide
        0x4b | 0x4d..=0x51 => uses_only([n(r[0]), n(r[1]), n(r[2])].concat()),
        0x4c => uses_only([w(r[0]), n(r[1]), n(r[2])].concat()),

        // iget family: 0x52 iget .. 0x58 iget-short; only iget-wide (0x53) is wide
        0x52 | 0x54..=0x58 => def_uses(n(r[0]), n(r[1])),
        0x53 => def_uses(w(r[0]), n(r[1])),
        // iput family: 0x59 iput .. 0x5f iput-short; only iput-wide (0x5a) is wide
        0x59 | 0x5b..=0x5f => uses_only([n(r[0]), n(r[1])].concat()),
        0x5a => uses_only([w(r[0]), n(r[1])].concat()),

        // sget family: 0x60 sget .. 0x66 sget-short; only sget-wide (0x61) is wide
        0x60 | 0x62..=0x66 => def(n(r[0])),
        0x61 => def(w(r[0])),
        // sput family: 0x67 sput .. 0x6d sput-short; only sput-wide (0x68) is wide
        0x67 | 0x69..=0x6d => uses_only(n(r[0])),
        0x68 => uses_only(w(r[0])),

        0x6e..=0x72 => uses_only(r.clone()), // invoke-virtual/super/direct/static/interface
        0x73 => none(),                      // unused
        0x74..=0x78 => uses_only(r.clone()), // invoke-*/range
        0x79 | 0x7a => none(),                // unused

        // --- unary ops (F12x): vA = op(vB) ---
        0x7b | 0x7c => def_uses(n(r[0]), n(r[1])), // neg-int, not-int
        0x7d | 0x7e => def_uses(w(r[0]), w(r[1])), // neg-long, not-long
        0x7f => def_uses(n(r[0]), n(r[1])),        // neg-float
        0x80 => def_uses(w(r[0]), w(r[1])),        // neg-double
        0x81 => def_uses(w(r[0]), n(r[1])),        // int-to-long
        0x82 => def_uses(n(r[0]), n(r[1])),        // int-to-float
        0x83 => def_uses(w(r[0]), n(r[1])),        // int-to-double
        0x84 => def_uses(n(r[0]), w(r[1])),        // long-to-int
        0x85 => def_uses(n(r[0]), w(r[1])),        // long-to-float
        0x86 => def_uses(w(r[0]), w(r[1])),        // long-to-double
        0x87 => def_uses(n(r[0]), n(r[1])),        // float-to-int
        0x88 => def_uses(w(r[0]), n(r[1])),        // float-to-long
        0x89 => def_uses(w(r[0]), n(r[1])),        // float-to-double
        0x8a => def_uses(n(r[0]), w(r[1])),        // double-to-int
        0x8b => def_uses(w(r[0]), w(r[1])),        // double-to-long
        0x8c => def_uses(n(r[0]), w(r[1])),        // double-to-float
        0x8d..=0x8f => def_uses(n(r[0]), n(r[1])), // int-to-byte/char/short

        // --- binop (F23x): vAA = vBB op vCC ---
        0x90..=0x9a => def_uses(n(r[0]), [n(r[1]), n(r[2])].concat()), // *-int
        0x9b..=0xa2 => def_uses(w(r[0]), [w(r[1]), w(r[2])].concat()), // add..xor-long
        0xa3..=0xa5 => def_uses(w(r[0]), [w(r[1]), n(r[2])].concat()), // shl/shr/ushr-long (int shift amount)
        0xa6..=0xaa => def_uses(n(r[0]), [n(r[1]), n(r[2])].concat()), // *-float
        0xab..=0xaf => def_uses(w(r[0]), [w(r[1]), w(r[2])].concat()), // *-double

        // --- binop/2addr (F12x): vA = vA op vB ---
        0xb0..=0xba => def_uses(n(r[0]), [n(r[0]), n(r[1])].concat()), // *-int/2addr
        0xbb..=0xc2 => def_uses(w(r[0]), [w(r[0]), w(r[1])].concat()), // add..xor-long/2addr
        0xc3..=0xc5 => def_uses(w(r[0]), [w(r[0]), n(r[1])].concat()), // shl/shr/ushr-long/2addr
        0xc6..=0xca => def_uses(n(r[0]), [n(r[0]), n(r[1])].concat()), // *-float/2addr
        0xcb..=0xcf => def_uses(w(r[0]), [w(r[0]), w(r[1])].concat()), // *-double/2addr

        // --- binop/lit16, binop/lit8 (int-only) ---
        0xd0..=0xd7 => def_uses(n(r[0]), n(r[1])), // vA = vB op #+CCCC
        0xd8..=0xe2 => def_uses(n(r[0]), n(r[1])), // vAA = vBB op #+CC

        // --- quickened/ODEX-only (0xe3-0xf9): never present in APK-shipped
        // DEX (see opcode.rs); def/use split across iget-quick vs
        // iput-quick within this range is unverified, so treated
        // conservatively as use-only rather than guessing a def.
        0xe3..=0xf9 => uses_only(r.clone()),

        0xfa | 0xfb => uses_only(r.clone()), // invoke-polymorphic(-range)
        0xfc | 0xfd => uses_only(r.clone()), // invoke-custom(-range)
        0xfe | 0xff => def(n(r[0])),         // const-method-handle, const-method-type

        _ => none(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::opcode::Format;

    fn insn(opcode: u8, format: Format, registers: Vec<u16>) -> Instruction {
        Instruction { code_unit_offset: 0, opcode, format, registers, literal: None, branch_offset: None, index: None }
    }

    #[test]
    fn move_is_def_a_use_b() {
        let du = def_use(&insn(0x01, Format::F12x, vec![1, 2])); // move v1, v2
        assert_eq!(du.defs, vec![1]);
        assert_eq!(du.uses, vec![2]);
    }

    #[test]
    fn move_wide_expands_both_sides_to_pairs() {
        let du = def_use(&insn(0x04, Format::F12x, vec![2, 4])); // move-wide v2, v4
        assert_eq!(du.defs, vec![2, 3]);
        assert_eq!(du.uses, vec![4, 5]);
    }

    #[test]
    fn binop_2addr_int_reads_and_writes_a_uses_b() {
        let du = def_use(&insn(0xb0, Format::F12x, vec![1, 2])); // add-int/2addr v1, v2 (v1 = v1+v2)
        assert_eq!(du.defs, vec![1]);
        assert_eq!(du.uses, vec![1, 2], "the destination is also read: vA = vA op vB");
    }

    #[test]
    fn binop_2addr_long_expands_both_operands_to_pairs() {
        let du = def_use(&insn(0xbb, Format::F12x, vec![2, 4])); // add-long/2addr v2, v4
        assert_eq!(du.defs, vec![2, 3]);
        assert_eq!(du.uses, vec![2, 3, 4, 5]);
    }

    #[test]
    fn shl_long_2addr_shift_amount_is_narrow_not_wide() {
        let du = def_use(&insn(0xc3, Format::F12x, vec![2, 6])); // shl-long/2addr v2, v6
        assert_eq!(du.defs, vec![2, 3]);
        assert_eq!(du.uses, vec![2, 3, 6], "shift amount (v6) is a plain int, not a pair");
    }

    #[test]
    fn iput_uses_value_and_object_defines_no_register() {
        let du = def_use(&insn(0x59, Format::F22c, vec![1, 2])); // iput v1, v2, field
        assert!(du.defs.is_empty(), "iput writes to a field, not a vreg");
        assert_eq!(du.uses, vec![1, 2]);
    }

    #[test]
    fn iput_wide_expands_only_the_value_operand() {
        let du = def_use(&insn(0x5a, Format::F22c, vec![1, 5])); // iput-wide v1, v5, field
        assert!(du.defs.is_empty());
        assert_eq!(du.uses, vec![1, 2, 5], "value (v1) is wide; object ref (v5) is not");
    }

    #[test]
    fn iget_wide_defines_a_pair_uses_object_ref() {
        let du = def_use(&insn(0x53, Format::F22c, vec![0, 3])); // iget-wide v0, v3, field
        assert_eq!(du.defs, vec![0, 1]);
        assert_eq!(du.uses, vec![3]);
    }

    #[test]
    fn aget_wide_defines_pair_uses_array_and_index_narrow() {
        let du = def_use(&insn(0x45, Format::F23x, vec![0, 1, 2])); // aget-wide v0, v1, v2
        assert_eq!(du.defs, vec![0, 1]);
        assert_eq!(du.uses, vec![1, 2]);
    }

    #[test]
    fn aput_uses_all_three_defines_nothing() {
        let du = def_use(&insn(0x4b, Format::F23x, vec![0, 1, 2])); // aput v0, v1, v2
        assert!(du.defs.is_empty());
        assert_eq!(du.uses, vec![0, 1, 2]);
    }

    #[test]
    fn invoke_uses_every_argument_register_defines_nothing() {
        // invoke-virtual {v1, v2, v3}, method — result (if any) comes via a
        // following move-result*, so invoke itself defines no register.
        let du = def_use(&insn(0x6e, Format::F35c, vec![1, 2, 3]));
        assert!(du.defs.is_empty());
        assert_eq!(du.uses, vec![1, 2, 3]);
    }

    #[test]
    fn move_result_wide_defines_a_pair_with_no_uses() {
        let du = def_use(&insn(0x0b, Format::F11x, vec![4])); // move-result-wide v4
        assert_eq!(du.defs, vec![4, 5]);
        assert!(du.uses.is_empty());
    }

    #[test]
    fn check_cast_uses_but_does_not_define() {
        let du = def_use(&insn(0x1f, Format::F21c, vec![2])); // check-cast v2, type
        assert!(du.defs.is_empty());
        assert_eq!(du.uses, vec![2]);
    }

    #[test]
    fn quickened_range_is_conservatively_use_only() {
        let du = def_use(&insn(0xe3, Format::F22cs, vec![1, 2]));
        assert!(du.defs.is_empty(), "unverified split of iget-quick vs iput-quick; must not guess a def");
        assert_eq!(du.uses, vec![1, 2]);
    }
}
