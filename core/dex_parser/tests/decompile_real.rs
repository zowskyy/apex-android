const CLASSES_DEX: &[u8] = include_bytes!("fixtures/classes.dex");

#[test]
fn main_activity_decompiles_to_readable_java() {
    let dex = apex_dex_parser::parse(CLASSES_DEX).expect("parse real classes.dex");
    let main_activity = dex
        .class_defs
        .iter()
        .find(|def| dex.type_name(def.class_idx) == Some("Lcom/apex/testapp/MainActivity;"))
        .expect("MainActivity class_def present");

    let java = apex_dex_parser::java::decompile_class(&dex, main_activity);
    assert!(
        java.contains("public class MainActivity extends Activity {"),
        "{java}"
    );
    assert!(
        java.contains("public MainActivity() {\n        super();\n    }"),
        "{java}"
    );
    assert!(
        java.contains("protected void onCreate(Bundle p0) {"),
        "{java}"
    );
    assert!(java.contains("super.onCreate(p0);"), "{java}");
    assert!(
        java.contains("setContentView(R.layout.activity_main);"),
        "{java}"
    );
}
