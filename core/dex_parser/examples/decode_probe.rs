fn main() {
    let data = std::fs::read("core/dex_parser/tests/fixtures/classes.dex").unwrap();
    let dex = apex_dex_parser::parse(&data).unwrap();
    for def in &dex.class_defs {
        let name = dex.type_name(def.class_idx).unwrap_or("?");
        let data = dex.class_data(def).unwrap();
        for m in data.direct_methods.iter().chain(data.virtual_methods.iter()) {
            if m.code_off == 0 { continue; }
            let mname = dex.method_name(m.method_idx).unwrap_or("?");
            let (item, units) = dex.decode_method(m.code_off).unwrap();
            let total_width: u32 = units.iter().map(|u| match u {
                apex_dex_parser::code::CodeUnit::Insn(i) => i.format.width(),
                _ => 0,
            }).sum();
            println!("{name}::{mname}  regs={} ins={} insns_len={} decoded_units={} width_sum={}",
                item.registers_size, item.ins_size, item.insns.len(), units.len(), total_width);
            for u in &units {
                if let apex_dex_parser::code::CodeUnit::Insn(i) = u {
                    println!("  [{:03}] op=0x{:02x} {:?} regs={:?} lit={:?} branch={:?} idx={:?}",
                        i.code_unit_offset, i.opcode, i.format, i.registers, i.literal, i.branch_offset, i.index);
                }
            }
        }
    }
}
