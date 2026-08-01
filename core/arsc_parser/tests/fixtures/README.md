# resources.arsc

Real `resources.arsc`, produced by the actual `aapt2` binary (not
hand-crafted or synthetic bytes) — `aapt2 compile` + `aapt2 link` over the
`res/` and `AndroidManifest.xml` in this directory, extracted from the
resulting `base.apk`.

The manifest here is deliberately minimal (`<manifest package="..."/>`, no
`android:` attributes): `aapt2 link` needs an Android framework jar
(`-I android.jar`) to resolve `android:`-namespaced attributes, and no
Android SDK is available in this environment (`dl.google.com` is blocked by
the outbound proxy; only `pip install aapt2`, which bundles just the `aapt2`
binary itself, was reachable). This limitation is about the *manifest*
only — resources.arsc's own structure (string pools, package/type/entry
chunks) is entirely unaffected by it, and every byte in this fixture is
genuine `aapt2` output, not approximated.

`res/values/strings.xml` includes a styled string
(`Hello <b>World</b>!`) specifically to get real `ResStringPool` style-span
bytes (`styleCount > 0`) into the fixture, and a `<string-array>` to get a
real complex/map entry (`ResTable_map`, `FLAG_COMPLEX`) — both exercised by
`core/arsc_parser/tests/real_arsc.rs`. `values.xml`/`colors.xml`/
`dimens.xml` add non-string simple-entry data types (`bool`, `color`,
`integer`, `dimen`) so the parser is checked against more than one
`Res_value.dataType`.

Regenerate with:

```bash
pip install aapt2
AAPT2=$(python3 -c "import aapt2,os;print(os.path.join(os.path.dirname(aapt2.__file__),'bin','Linux','aapt2'))")
chmod +x "$AAPT2"
cd core/arsc_parser/tests/fixtures
"$AAPT2" compile --dir res -o /tmp/res.zip
"$AAPT2" link -o /tmp/base.apk --manifest AndroidManifest.xml /tmp/res.zip
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/base.apk') as zf:
    open('resources.arsc', 'wb').write(zf.read('resources.arsc'))
"
```
