#!/usr/bin/env python3
"""Fix aapt 'Multiple substitutions specified in non-positional format' errors
by adding formatted="false" to the flagged strings (text is left untouched,
so literal '%' signs still display correctly). Idempotent.
Usage (repo root): python3 fix_formats.py [res_dir]"""
import re, sys, glob, os
res = sys.argv[1] if len(sys.argv) > 1 else "src/android/app/src/main/res"
LOOSE = re.compile(r'%(?!%)(?:(\d+)\$)?[-#+ 0,(]*\d*(?:\.\d+)?[a-zA-Z]')
changed = 0
for f in sorted(glob.glob(os.path.join(res, "values*", "strings.xml"))):
    s = open(f, encoding="utf-8").read()
    def sub(m):
        head, body = m.group(1), m.group(2)
        if 'formatted=' in head or body.lstrip().startswith('<![CDATA['): return m.group(0)
        specs = [x for x in LOOSE.finditer(body)]
        if len(specs) > 1 and any(x.group(1) is None for x in specs):
            return head[:-1] + ' formatted="false">' + body + m.group(3)
        return m.group(0)
    n = re.sub(r'(<string\b[^>]*>)(.*?)(</string>)', sub, s, flags=re.S)
    if n != s:
        open(f, "w", encoding="utf-8").write(n); changed += 1; print("fixed", f)
print("files changed:", changed)
