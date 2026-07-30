# classes.dex

Real DEX bytecode, extracted from `tests/fixtures/apex_mobile_test.apk`
(itself built by `tools/mobile_test_app/build.sh` via the actual Android
`d8` compiler — see that directory's README). Not hand-crafted or
synthetic: this is genuine toolchain output, including the `R`, `R$id`,
`R$layout`, `R$string` holder classes `d8` generates for resource
references, which is why `core/dex_parser/tests/real_dex.rs` expects 7
classes, not just the 3 (`MainActivity`, `BackgroundService`,
`BootReceiver`) that were actually hand-written.

Regenerate with:

```bash
bash tools/mobile_test_app/build.sh
python3 -c "
import zipfile
with zipfile.ZipFile('tests/fixtures/apex_mobile_test.apk') as zf:
    open('core/dex_parser/tests/fixtures/classes.dex', 'wb').write(zf.read('classes.dex'))
"
```
