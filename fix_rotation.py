#!/usr/bin/env python3
"""Fix: custom landscape layout not applied after rotating the device,
and the game being paused (killing multiplayer) while the device rotates.
Usage (Termux):  python fix_rotation.py /path/to/AzaharPlus-overlay-theme
Safe to run twice; makes .orig backups on first change."""
import sys, os, shutil

root = sys.argv[1] if len(sys.argv) > 1 else "."
main = os.path.join(root, "src/android/app/src/main")

EDITS = [
 (os.path.join(main, "jni/emu_window/emu_window.cpp"),
  "const bool is_portrait_mode = (AndroidUtils::IsPortraitMode() && !is_secondary);",
  "// Use the real surface size; the Java-side config can still be stale during rotation\n"
  "    const bool is_portrait_mode = (window_height > window_width) && !is_secondary;"),
 (os.path.join(main, "java/org/citra/citra_emu/NativeLibrary.kt"),
  "    fun isPortraitMode(): Boolean = (\n"
  "        CitraApplication.appContext.resources.configuration.orientation ==\n"
  "            Configuration.ORIENTATION_PORTRAIT\n"
  "        )",
  "    fun isPortraitMode(): Boolean {\n"
  "        // Prefer the live display size of the activity; the application context\n"
  "        // configuration can lag behind a rotation.\n"
  "        val dm = sEmulationActivity.get()?.resources?.displayMetrics\n"
  "        if (dm != null) return dm.heightPixels > dm.widthPixels\n"
  "        return CitraApplication.appContext.resources.configuration.orientation ==\n"
  "            Configuration.ORIENTATION_PORTRAIT\n"
  "    }"),
 (os.path.join(main, "java/org/citra/citra_emu/fragments/EmulationFragment.kt"),
  "        emulationState.newSurface(holder.surface)\n    }",
  "        emulationState.newSurface(holder.surface)\n"
  "        // Re-apply the layout for the new orientation (fixes stale layout after rotating)\n"
  "        NativeLibrary.updateFramebuffer(height > width)\n    }"),
 (os.path.join(main, "java/org/citra/citra_emu/fragments/EmulationFragment.kt"),
  "            if (BooleanSetting.KEEP_EMULATION_RUNNING.boolean) {\n"
  "                // Keep the game running in the background.",
  "            // Rotating recreates the activity and calls onPause: never pause for that,\n"
  "            // only stop presenting, so the emulation/network threads keep running.\n"
  "            if (BooleanSetting.KEEP_EMULATION_RUNNING.boolean ||\n"
  "                activity?.isChangingConfigurations == true\n"
  "            ) {\n"
  "                // Keep the game running in the background."),
]

for path, old, new in EDITS:
    if not os.path.exists(path):
        sys.exit(f"NOT FOUND: {path}\nPass the repo root as argument.")
    s = open(path, encoding="utf-8").read()
    if new in s:
        print("already patched:", os.path.basename(path)); continue
    if s.count(old) != 1:
        sys.exit(f"Pattern not found exactly once in {path}; file differs from expected.")
    if not os.path.exists(path + ".orig"):
        shutil.copy(path, path + ".orig")
    open(path, "w", encoding="utf-8").write(s.replace(old, new))
    print("patched:", os.path.basename(path))
print("Done. Rebuild the app.")
