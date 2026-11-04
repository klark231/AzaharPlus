#!/usr/bin/env python3
"""AzaharPlus desktop CI: disable FFmpeg on MSVC, fix the nfc C4388. Run from the repo root:
    python3 ci_desktop_fix.py
Idempotent. Independent of azp_fixes.py (works on a diverged tree)."""
import sys, os

def patch(path, old, new):
    if not os.path.exists(path):
        print(f"  MISSING: {path} (skipped)"); return
    s = open(path, encoding="utf-8").read()
    if new in s:
        print(f"  skip: {path}"); return
    n = s.count(old)
    if n != 1:
        sys.exit(f"ERROR {path}: anchor {n}x (want 1):\n  {old[:100]!r}")
    open(path, "w", encoding="utf-8").write(s.replace(old, new))
    print(f"  patched: {path}")

# 1. FFmpeg off for the MSVC windows builds (the runner has no FFmpeg; win7 already disables it)
patch(".ci/windows.sh",
      "cmake .. -G Ninja \\",
      'if [ "$TARGET" != "msys2" ]; then\n'
      "\tEXTRA_CMAKE_FLAGS+=(-DENABLE_FFMPEG=OFF)\n"
      "fi\n\n"
      "cmake .. -G Ninja \\")

# 2. nfc_device.cpp C4388 signed/unsigned (MSVC /we4388 /WX makes it an error)
patch("src/core/hle/service/nfc/nfc_device.cpp",
      "\tfor (int i = 0; i < amiibo_name.length(); i++) {",
      "\tfor (std::size_t i = 0; i < amiibo_name.length(); i++) {")

print("ci_desktop_fix: done")
