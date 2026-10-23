#!/usr/bin/env python3
"""Chat button size slider: minimum 40 -> 30 dp. Idempotent. Run from repo root."""
import re
p = "src/android/app/src/main/java/org/citra/citra_emu/features/settings/ui/SettingsFragmentPresenter.kt"
s = open(p, encoding="utf-8").read()
pat = re.compile(r'(IntSetting\.CHAT_FAB_SIZE,\s*R\.string\.chat_fab_size,\s*R\.string\.chat_fab_size_description,\s*)(\d+)(,)')
m = pat.search(s)
if not m: raise SystemExit("slider not found")
if m.group(2) == "30": print("already 30")
else:
    open(p, "w", encoding="utf-8").write(pat.sub(r"\g<1>30\3", s, 1)); print("min set to 30")
