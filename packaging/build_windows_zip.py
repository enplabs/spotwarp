#!/usr/bin/env python3
"""
Rebuild static/spotwarp-windows-x64.zip from the PUBLISHED GitHub release.

The Windows download served at https://gpu-action.com/static/spotwarp-windows-x64.zip
is a build artifact: it is NOT stored in git. This script regenerates it so the
download can always be restored after a redeploy or a fresh checkout.

It does not compile anything. It downloads the already-released Windows binary,
verifies it against the release's own SHA256SUMS.txt, and repackages it as a ZIP
(Windows browsers and AV routinely block a bare .exe download; a ZIP gets through).

Usage:
    python packaging/build_windows_zip.py                # build for RELEASE_TAG below
    python packaging/build_windows_zip.py --tag v3.5.0   # build for another tag
    python packaging/build_windows_zip.py --check        # verify existing zip only
"""

import argparse
import hashlib
import pathlib
import sys
import urllib.request
import zipfile

RELEASE_TAG = "v3.4.3"
REPO = "enplabs/spotwarp"
ASSET = "spotwarp-windows-x64.exe"

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_ZIP = ROOT / "static" / "spotwarp-windows-x64.zip"
README = pathlib.Path(__file__).resolve().parent / "README.txt"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "spotwarp-packaging"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def expected_sha256(tag):
    """Read the official checksum for ASSET out of the release's SHA256SUMS.txt."""
    base = f"https://github.com/{REPO}/releases/download/{tag}"
    sums = fetch(f"{base}/SHA256SUMS.txt").decode()
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == ASSET:
            return parts[0]
    raise SystemExit(f"[!] {ASSET} not listed in SHA256SUMS.txt for {tag}")


def build(tag):
    base = f"https://github.com/{REPO}/releases/download/{tag}"
    want = expected_sha256(tag)

    print(f"[*] Downloading {ASSET} from release {tag} ...")
    exe = fetch(f"{base}/{ASSET}")
    got = hashlib.sha256(exe).hexdigest()
    if got != want:
        raise SystemExit(f"[!] checksum mismatch\n    expected {want}\n    got      {got}")
    print(f"[+] Checksum verified against release SHA256SUMS.txt ({got})")

    if not README.exists():
        raise SystemExit(f"[!] missing {README}")

    OUT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        # Name it spotwarp.exe inside the archive: README.txt and the docs both
        # tell the user to run `.\spotwarp.exe init` after extracting.
        z.writestr("spotwarp.exe", exe)
        z.writestr("README.txt", README.read_bytes())

    print(f"[+] Wrote {OUT_ZIP} ({OUT_ZIP.stat().st_size:,} bytes)")
    check()


def check():
    if not OUT_ZIP.exists():
        raise SystemExit(f"[!] {OUT_ZIP} does not exist - run without --check to build it")
    with zipfile.ZipFile(OUT_ZIP) as z:
        bad = z.testzip()
        if bad:
            raise SystemExit(f"[!] corrupt entry in zip: {bad}")
        names = z.namelist()
        if "spotwarp.exe" not in names:
            raise SystemExit(f"[!] zip is missing spotwarp.exe (has: {names})")
        inner = hashlib.sha256(z.read("spotwarp.exe")).hexdigest()
    print(f"[+] Zip OK - contents {names}, inner exe sha256={inner}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default=RELEASE_TAG, help=f"release tag to package (default {RELEASE_TAG})")
    ap.add_argument("--check", action="store_true", help="verify the existing zip instead of rebuilding")
    args = ap.parse_args()
    sys.exit(check() if args.check else build(args.tag))
