"""Copy base.apk (from aapt2 link) and add classes.dex — aapt2 link only
packages resources + manifest, so the dex has to be added as a separate step
before signing."""
import shutil
import sys
import zipfile


def main() -> None:
    base_apk, dex_path, out_apk = sys.argv[1], sys.argv[2], sys.argv[3]
    shutil.copyfile(base_apk, out_apk)
    with zipfile.ZipFile(out_apk, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.write(dex_path, "classes.dex")


if __name__ == "__main__":
    main()
