#!/usr/bin/env python3
"""Restores the missing ensureComboDefaultPosition() in InputOverlay.kt. Idempotent. Run from repo root."""
import sys
p = "src/android/app/src/main/java/org/citra/citra_emu/overlay/InputOverlay.kt"
s = open(p, encoding="utf-8").read()
if "fun ensureComboDefaultPosition" in s:
    print("already present"); sys.exit(0)
fn = '''    /**
     * Combo buttons 2..5 have no stored position the first time they are enabled; place them
     * relative to combo button 1 using the same layout as the defaults (a row going right) so they don't overlap other controls.
     */
    private fun ensureComboDefaultPosition(comboIndex: Int, orientation: String) {
        val id = Hotkey.COMBO_BUTTON.button + comboIndex
        val xKey = "$id$orientation-X"
        val yKey = "$id$orientation-Y"
        if (preferences.contains(xKey) && preferences.contains(yKey)) return
        val baseX = preferences.getFloat("${Hotkey.COMBO_BUTTON.button}$orientation-X", 0f)
        val baseY = preferences.getFloat("${Hotkey.COMBO_BUTTON.button}$orientation-Y", 0f)
        val metrics = resources.displayMetrics
        val editor = preferences.edit()
        val step = if (orientation.isEmpty()) {
            0.11f * metrics.heightPixels
        } else {
            0.11f * metrics.widthPixels
        }
        editor.putFloat(xKey, baseX + step * comboIndex).putFloat(yKey, baseY)
        editor.apply()
    }

'''
for marker in ("    /**\n     * A Touch button that has no stored position yet",
               "    private fun ensureTouchButtonDefaultPosition",
               "    private fun sendButtonState"):
    if marker in s:
        s = s.replace(marker, fn + marker, 1); break
else:
    sys.exit("marker not found")
open(p, "w", encoding="utf-8").write(s); print("restored")
