#!/usr/bin/env python3
"""Reword Touch Input Bindings strings from 'gamepad/keyboard' to 'external device'. Idempotent. Run from repo root."""
import re
p = "src/android/app/src/main/res/values/strings.xml"
s = open(p, encoding="utf-8").read()
rep = {
 "touch_input_bindings_description": "Press a point on the 3DS bottom screen with any button, key or stick from an external device (gamepad, keyboard, controller clone, …), or with an on-screen Touch button added to the input overlay.",
 "bind_touch_input_message": "Press any button or key, or move a stick, on a connected external device.",
 "touch_input_empty_message": "Tap the preview to choose a spot, then bind an input from an external device, or add an on-screen Touch button.",
 "touch_input_source_controller": "External device",
}
for k, v in rep.items():
    s, n = re.subn(r'(<string name="%s">).*?(</string>)' % k, lambda m: m.group(1) + v + m.group(2), s, flags=re.S)
    print(("updated " if n else "MISSING ") + k)
open(p, "w", encoding="utf-8").write(s)
