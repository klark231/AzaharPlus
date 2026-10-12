#!/usr/bin/env python3
"""
Run from the root of the AzaharPlus repo:   python3 dedupe_combo_strings.py

The combo buttons had their names written twice: button_combo .. button_combo_5 (menus, toggle
list, hotkeys) and combo_button_n_1 .. combo_button_n_5 (only the "Configure Combo Buttons" dialog),
plus combo_button_settings_2 .. _5 that nothing uses. Now everything uses button_combo .. _5.
Nothing is written unless every step matches. Safe to run twice.
"""
import os
import re
import sys

RES = "src/android/app/src/main/res"
STRINGS = f"{RES}/values/strings.xml"
LAYOUT = f"{RES}/layout/dialog_combo_buttons.xml"
for p in (STRINGS, LAYOUT):
    if not os.path.exists(p):
        sys.exit(f"STOP: {p} not found. Run this from the root of the AzaharPlus repo.")

with open(LAYOUT, encoding="utf-8", newline="") as f:
    layout = f.read()
with open(STRINGS, encoding="utf-8", newline="") as f:
    strings = f.read()

# 1. the dialog uses the shared names
names = {1: "button_combo", 2: "button_combo_2", 3: "button_combo_3", 4: "button_combo_4", 5: "button_combo_5"}
for i, new in names.items():
    layout = layout.replace(f"@string/combo_button_n_{i}\"", f"@string/{new}\"")
if re.search(r"@string/combo_button_n_[1-5]\b", layout):
    sys.exit("STOP: dialog_combo_buttons.xml still has an unexpected combo_button_n_ reference. Nothing was changed.")

# 2. make sure nothing else still uses the strings that are about to go
doomed = [f"combo_button_n_{i}" for i in range(1, 6)] + [f"combo_button_settings_{i}" for i in range(2, 6)]
use = re.compile(r"(?:@string/|R\.string\.)(%s)\b" % "|".join(doomed))
for base, dirs, files in os.walk("src/android"):
    for fn in files:
        if not fn.endswith((".kt", ".java", ".xml")) or "/values" in base and fn == "strings.xml":
            continue
        path = os.path.join(base, fn)
        if path == LAYOUT:
            continue
        with open(path, encoding="utf-8", errors="ignore") as f:
            m = use.search(f.read())
        if m:
            doomed.remove(m.group(1))     # still in use: keep that one

# 3. remove them from the default strings.xml (translations never had them)
removed = []
for name in doomed:
    strings, n = re.subn(r'[ \t]*<string name="%s">[^<]*</string>[ \t]*\n' % re.escape(name), "", strings)
    if n:
        removed.append(name)

with open(LAYOUT, "w", encoding="utf-8", newline="") as f:
    f.write(layout)
with open(STRINGS, "w", encoding="utf-8", newline="") as f:
    f.write(strings)
print("dialog now uses button_combo .. button_combo_5")
print("removed from strings.xml:", ", ".join(removed) if removed else "nothing (already done)")
print("\nDone. Now: git add src && git commit -m \"Use one set of combo button names\"")
