//! Integration test against a real classes.dex — compiled by the actual
//! Android d8 tool from tools/mobile_test_app (see core/dex_parser/tests/fixtures/README.md
//! for provenance). Not a synthetic/hand-built fixture: this is genuine
//! Dalvik bytecode output, so a passing test here means the header/
//! class_def/class_data parsing survives real toolchain output, not just a
//! shape I made up myself.

const CLASSES_DEX: &[u8] = include_bytes!("fixtures/classes.dex");

#[test]
fn parses_real_classes_dex_header() {
    let dex = apex_dex_parser::parse(CLASSES_DEX).expect("real classes.dex should parse");

    assert_eq!(&dex.header.magic[0..4], b"dex\n");
    assert_eq!(dex.header.file_size as usize, CLASSES_DEX.len());
    assert_eq!(dex.header.header_size, 0x70);

    // 3 classes we wrote (MainActivity, BackgroundService, BootReceiver) plus
    // 4 R.java-derived holder classes (R, R$id, R$layout, R$string) that d8
    // generates for the R.layout.activity_main / R.string.hello_label
    // references in MainActivity.java — genuine d8 output, not hand-picked.
    assert_eq!(dex.header.class_defs_size, 7);
}

#[test]
fn resolves_real_class_names() {
    let dex = apex_dex_parser::parse(CLASSES_DEX).expect("parse");

    let mut names: Vec<&str> = dex
        .class_defs
        .iter()
        .filter_map(|def| dex.type_name(def.class_idx))
        .collect();
    names.sort();

    assert_eq!(
        names,
        vec![
            "Lcom/apex/testapp/BackgroundService;",
            "Lcom/apex/testapp/BootReceiver;",
            "Lcom/apex/testapp/MainActivity;",
            "Lcom/apex/testapp/R$id;",
            "Lcom/apex/testapp/R$layout;",
            "Lcom/apex/testapp/R$string;",
            "Lcom/apex/testapp/R;",
        ]
    );
}

#[test]
fn main_activity_has_oncreate_method_with_real_index() {
    let dex = apex_dex_parser::parse(CLASSES_DEX).expect("parse");

    let main_activity = dex
        .class_defs
        .iter()
        .find(|def| dex.type_name(def.class_idx) == Some("Lcom/apex/testapp/MainActivity;"))
        .expect("MainActivity class_def present");

    // superclass must resolve to android.app.Activity
    assert_eq!(dex.type_name(main_activity.superclass_idx), Some("Landroid/app/Activity;"));

    let data = dex.class_data(main_activity).expect("class_data parses");
    let method_names: Vec<&str> = data
        .virtual_methods
        .iter()
        .chain(data.direct_methods.iter())
        .filter_map(|m| {
            // method_ids_off table: method_id_item { class_idx:u16, proto_idx:u16, name_idx:u32 }
            let entry = dex.header.method_ids_off as usize + (m.method_idx as usize) * 8;
            let name_idx = u32::from_le_bytes(dex.data[entry + 4..entry + 8].try_into().ok()?);
            dex.strings.get(name_idx as usize).map(|s| s.as_str())
        })
        .collect();

    assert!(
        method_names.contains(&"onCreate"),
        "expected onCreate among MainActivity's methods, got {method_names:?}"
    );
}

#[test]
fn every_method_instruction_width_sums_to_insns_len() {
    // The critical self-consistency invariant for the instruction decoder:
    // if any opcode's format/width were wrong, the sum of decoded
    // instruction widths would not exactly equal the code_item's declared
    // insns_size for at least one real method. Checked across every method
    // in every real class in this fixture (constructors, onBind, onCreate).
    use apex_dex_parser::code::CodeUnit;

    let dex = apex_dex_parser::parse(CLASSES_DEX).expect("parse");
    let mut methods_checked = 0;

    for def in &dex.class_defs {
        let data = dex.class_data(def).expect("class_data");
        for m in data.direct_methods.iter().chain(data.virtual_methods.iter()) {
            if m.code_off == 0 {
                continue; // abstract/native: no code_item
            }
            let (item, units) = dex.decode_method(m.code_off).expect("decode_method");
            let width_sum: u32 = units
                .iter()
                .map(|u| match u {
                    CodeUnit::Insn(i) => i.format.width(),
                    CodeUnit::PackedSwitchPayload { targets, .. } => 4 + 2 * targets.len() as u32,
                    CodeUnit::SparseSwitchPayload { keys, .. } => 2 + 4 * keys.len() as u32,
                    // ident(1) + element_width(1) + size(2) + ceil(data_bytes/2)
                    CodeUnit::FillArrayDataPayload { data, .. } => 4 + (data.len() as u32).div_ceil(2),
                })
                .sum();
            assert_eq!(
                width_sum, item.insns.len() as u32,
                "method_idx={} decoded width sum != insns_size (desync)",
                m.method_idx
            );
            methods_checked += 1;
        }
    }
    assert!(methods_checked >= 8, "expected at least 8 methods with code across the fixture, found {methods_checked}");
}

#[test]
fn oncreate_decodes_to_expected_real_bytecode_shape() {
    // MainActivity.onCreate() source is exactly:
    //   super.onCreate(savedInstanceState);
    //   setContentView(R.layout.activity_main);
    // This asserts the decoder recovers that shape from raw bytecode:
    // invoke-super, const/high16 (loading the R.layout resource id),
    // invoke-virtual, return-void.
    use apex_dex_parser::code::CodeUnit;
    use apex_dex_parser::opcode::Format;

    let dex = apex_dex_parser::parse(CLASSES_DEX).expect("parse");
    let main_activity = dex
        .class_defs
        .iter()
        .find(|def| dex.type_name(def.class_idx) == Some("Lcom/apex/testapp/MainActivity;"))
        .expect("MainActivity present");
    let data = dex.class_data(main_activity).expect("class_data");

    let on_create = data
        .virtual_methods
        .iter()
        .find(|m| dex.method_name(m.method_idx).unwrap_or("") == "onCreate")
        .expect("onCreate present");

    let (item, units) = dex.decode_method(on_create.code_off).expect("decode");
    let insns: Vec<_> = units
        .iter()
        .filter_map(|u| match u {
            CodeUnit::Insn(i) => Some(i),
            _ => None,
        })
        .collect();

    assert_eq!(insns.len(), 4, "expected exactly 4 real instructions in onCreate, got {insns:?}");
    assert_eq!((insns[0].opcode, insns[0].format), (0x6f, Format::F35c)); // invoke-super
    assert_eq!((insns[1].opcode, insns[1].format), (0x15, Format::F21h)); // const/high16
    // Top 32 bits of the 21h literal are the real resource ID; AAPT's
    // convention for app-local resources is a 0x7f package prefix.
    let resource_id = (insns[1].literal.unwrap() >> 32) as u32;
    assert_eq!(resource_id >> 24, 0x7f, "expected AAPT app-local resource-id prefix 0x7f, got 0x{resource_id:08x}");
    assert_eq!((insns[2].opcode, insns[2].format), (0x6e, Format::F35c)); // invoke-virtual
    assert_eq!((insns[3].opcode, insns[3].format), (0x0e, Format::F10x)); // return-void

    // Whole-method width self-consistency, restated concretely for this method.
    let width_sum: u32 = insns.iter().map(|i| i.format.width()).sum();
    assert_eq!(width_sum, item.insns.len() as u32);
}

#[test]
fn every_class_data_offset_parses_without_desync() {
    // Regression guard for the exact bug found in dex-hybrid: if class_def
    // parsing desyncs (e.g. from a missing struct field), class_data_off
    // points at garbage and this either errors or produces an absurd
    // member count. Assert every real class here parses cleanly with a
    // sane (small) member count.
    let dex = apex_dex_parser::parse(CLASSES_DEX).expect("parse");
    for def in &dex.class_defs {
        let data = dex.class_data(def).expect("class_data_off should be valid for every real class_def");
        let total = data.static_fields.len() + data.instance_fields.len() + data.direct_methods.len() + data.virtual_methods.len();
        assert!(total < 50, "class had implausibly many members ({total}) — likely a parser desync");
    }
}
