# APEX Benchmarks

Measured on the Cursor Cloud Linux VM for branch `cursor/complete-apex-2eb0`.
The earlier full two-APK apktool/jadx suite terminated the pod, so this records
the requested short comparison set instead.

| APK | Size | APEX inspect engine | Inspect <100ms | apktool manifest-only | APEX first DEX->Java | jadx APK->Java | Notes |
| --- | ---: | ---: | :---: | ---: | ---: | ---: | --- |
| F-Droid | 11.9 MB | 64.3 ms | yes | 1.02 s | not run | not run | inspect process median 96.5 ms |
| NewPipe 0.28.8 | 10.4 MB | 69.8 ms | yes | 1.02 s | 1.29 s | failed after 18.28 s | inspect process median 103.5 ms; jadx exited with 47 decompile errors |

## Commands

```bash
python benchmarks/run_benchmarks.py --runs 7 --jadx-apk "NewPipe 0.28.8"
```

The benchmark runner downloads nothing; the local ignored corpus/tool layout used
for the run was:

- `benchmarks/corpus/fdroid_latest.apk` from `https://f-droid.org/F-Droid.apk`
- `benchmarks/corpus/newpipe_v0.28.8.apk` from the NewPipe v0.28.8 release
- `benchmarks/tools/apktool.jar` from apktool 3.0.3
- `benchmarks/tools/jadx/` from jadx 1.5.6

## Notes

- `apex inspect` reports engine time after process startup. The full Python
  process median is also shown because command startup is visible to users.
- `apktool` was run as `java -jar apktool.jar d -f -s --only-manifest`, which is
  the nearest manifest metadata comparison to `apex inspect`.
- `jadx` was run once on NewPipe with a 180 second timeout. It processed the APK
  for 18.28 seconds and exited nonzero with `ERROR - finished with errors,
  count: 47`.
- `apex decompile --first-dex-only` wrote 7,830 Java files for NewPipe's first
  DEX in 1.29 seconds.
