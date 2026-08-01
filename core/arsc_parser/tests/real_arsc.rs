//! Integration tests against a genuinely `aapt2`-compiled resources.arsc
//! (see `tests/fixtures/README.md` for provenance and regeneration). Every
//! assertion here is a known value read directly off the real binary with a
//! hand-written Python decoder before this parser was written, not a value
//! back-derived from the parser's own output.

use apex_arsc_parser::entry::EntryValue;
use apex_arsc_parser::value::{TYPE_INT_BOOLEAN, TYPE_INT_COLOR_ARGB8, TYPE_INT_DEC, TYPE_STRING};

fn fixture() -> apex_arsc_parser::ResourceTable {
    let data = include_bytes!("fixtures/resources.arsc");
    apex_arsc_parser::parse(data).expect("real aapt2-compiled resources.arsc must parse")
}

#[test]
fn global_string_pool_has_expected_values_and_one_style_span() {
    let table = fixture();
    assert_eq!(
        table.global_strings.strings,
        vec!["Hello World!", "APEX Test App", "APEX debug fixture — real aapt2 output", "Mon", "Tue", "Wed", "b",]
    );
    // "Hello <b>World</b>!" -> the "b" span covers "World" (chars 6..=10).
    assert_eq!(table.global_strings.styles[0].len(), 1);
    let span = &table.global_strings.styles[0][0];
    assert_eq!(span.name, 6); // index of "b" in the same pool
    assert_eq!((span.first_char, span.last_char), (6, 10));
    for i in 1..table.global_strings.strings.len() {
        assert!(table.global_strings.styles[i].is_empty(), "only string 0 is styled");
    }
}

#[test]
fn package_identity_and_name_pools() {
    let table = fixture();
    assert_eq!(table.packages.len(), 1);
    let pkg = &table.packages[0];
    assert_eq!(pkg.id, 127);
    assert_eq!(pkg.name, "com.apex.arscfixture");
    assert_eq!(pkg.type_strings.strings, vec!["array", "bool", "color", "dimen", "integer", "string"]);
    assert_eq!(
        pkg.key_strings.strings,
        vec!["days", "feature_enabled", "brand_primary", "margin_default", "max_retries", "app_name", "hello_label", "styled_text",]
    );
    assert_eq!(pkg.types.len(), 6, "array, bool, color, dimen, integer, string");
}

fn find_type<'a>(pkg: &'a apex_arsc_parser::package::Package, name: &str) -> &'a apex_arsc_parser::package::ResType {
    pkg.types.iter().find(|t| t.name == name).unwrap_or_else(|| panic!("no type named {name}"))
}

#[test]
fn simple_string_entries_resolve_through_the_global_pool() {
    let table = fixture();
    let pkg = &table.packages[0];
    let string_type = find_type(pkg, "string");
    assert_eq!(string_type.id, 6);
    let config = &string_type.configs[0];
    assert!(config.is_default_config());
    assert_eq!(config.entries.len(), 3);

    let by_key_name: std::collections::HashMap<&str, &apex_arsc_parser::entry::ResourceEntry> =
        config.entries.iter().map(|(_, e)| (pkg.key_name(e.key_index).unwrap(), e)).collect();

    let app_name = by_key_name["app_name"];
    let EntryValue::Simple(v) = &app_name.value else { panic!("app_name should be a simple entry") };
    assert_eq!(v.data_type, TYPE_STRING);
    assert_eq!(table.resolve_string(v.data).unwrap(), "APEX Test App");

    let hello = by_key_name["hello_label"];
    let EntryValue::Simple(v) = &hello.value else { panic!("hello_label should be a simple entry") };
    assert_eq!(table.resolve_string(v.data).unwrap(), "APEX debug fixture — real aapt2 output");

    let styled = by_key_name["styled_text"];
    let EntryValue::Simple(v) = &styled.value else { panic!("styled_text should be a simple entry") };
    assert_eq!(table.resolve_string(v.data).unwrap(), "Hello World!");
}

#[test]
fn simple_non_string_entries_carry_the_right_data_type_and_raw_data() {
    let table = fixture();
    let pkg = &table.packages[0];

    let bool_type = find_type(pkg, "bool");
    let (_, entry) = &bool_type.configs[0].entries[0];
    assert_eq!(pkg.key_name(entry.key_index).unwrap(), "feature_enabled");
    let EntryValue::Simple(v) = &entry.value else { panic!() };
    assert_eq!(v.data_type, TYPE_INT_BOOLEAN);
    assert_eq!(v.data, 0xffff_ffff, "true is encoded as all-ones, not 1");

    let color_type = find_type(pkg, "color");
    let (_, entry) = &color_type.configs[0].entries[0];
    assert_eq!(pkg.key_name(entry.key_index).unwrap(), "brand_primary");
    let EntryValue::Simple(v) = &entry.value else { panic!() };
    assert_eq!(v.data_type, TYPE_INT_COLOR_ARGB8);
    assert_eq!(v.data, 0xFF3366CC);

    let integer_type = find_type(pkg, "integer");
    let (_, entry) = &integer_type.configs[0].entries[0];
    assert_eq!(pkg.key_name(entry.key_index).unwrap(), "max_retries");
    let EntryValue::Simple(v) = &entry.value else { panic!() };
    assert_eq!(v.data_type, TYPE_INT_DEC);
    assert_eq!(v.data, 3);
}

/// The one complex/map entry in the fixture: a `<string-array>`. Its items
/// are `ResTable_map`s with synthetic sequential `name`s (`0x01000001`,
/// `0x01000002`, `0x01000003`) rather than real attribute references — this
/// is the shape that would be silently misparsed as a simple entry (or as
/// three unrelated attribute overrides) by code that doesn't check
/// `FLAG_COMPLEX` before reading `ResTable_entry`'s tail as a `Res_value`.
#[test]
fn complex_array_entry_has_synthetic_item_names_and_ordered_string_values() {
    let table = fixture();
    let pkg = &table.packages[0];
    let array_type = find_type(pkg, "array");
    assert_eq!(array_type.id, 1);
    let (_, entry) = &array_type.configs[0].entries[0];
    assert_eq!(pkg.key_name(entry.key_index).unwrap(), "days");

    let EntryValue::Complex { parent, entries } = &entry.value else { panic!("string-array must be a complex entry") };
    assert_eq!(*parent, 0);
    assert_eq!(entries.len(), 3);
    assert_eq!(entries[0].name, 0x0100_0001);
    assert_eq!(entries[1].name, 0x0100_0002);
    assert_eq!(entries[2].name, 0x0100_0003);

    let resolved: Vec<&str> = entries.iter().map(|m| table.resolve_string(m.value.data).unwrap()).collect();
    assert_eq!(resolved, vec!["Mon", "Tue", "Wed"]);
}

#[test]
fn type_spec_flags_are_all_default_for_a_single_config_fixture() {
    let table = fixture();
    let pkg = &table.packages[0];
    for t in &pkg.types {
        assert_eq!(t.spec_flags.len(), t.configs[0].entries.len(), "no holes in this fixture: typeSpec entryCount matches the dense entry count");
        assert!(t.spec_flags.iter().all(|&f| f == 0), "no per-config variation in this fixture");
    }
}
