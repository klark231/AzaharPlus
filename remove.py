#!/usr/bin/env python3
"""Removes the "(optional)" wording from the second Web API URL hint in every language.
Run from the repo root after tweaks_and_network.py:  python3 remove_optional.py
The string is renamed web_api_url_2_optional -> web_api_url_2_hint. Safe to run twice."""
import glob
import re
import sys

RES = "src/android/app/src/main/res/"
PRESENTER = "src/android/app/src/main/java/org/citra/citra_emu/features/settings/ui/SettingsFragmentPresenter.kt"

paths = sorted(glob.glob(RES + "values*/strings.xml"))
out = {}
pattern = re.compile(r'<string name="web_api_url_2_optional">(.*?)</string>', re.S)
changed = 0
for p in paths:
    s = open(p, encoding="utf-8", newline="").read()
    m = pattern.search(s)
    if not m:
        continue
    text = re.sub(r"\s*[（(][^）)]*[）)]\s*$", "", m.group(1))
    out[p] = s[:m.start()] + f'<string name="web_api_url_2_hint">{text}</string>' + s[m.end():]
    changed += 1

if changed == 0:
    print("already patched")
    sys.exit(0)

k = open(PRESENTER, encoding="utf-8", newline="").read()
if "R.string.web_api_url_2_optional" not in k:
    sys.exit("ERROR: presenter reference not found")
out[PRESENTER] = k.replace("R.string.web_api_url_2_optional", "R.string.web_api_url_2_hint")

for p, c in out.items():
    open(p, "w", encoding="utf-8", newline="").write(c)
print(f"patched {len(out)} files")
