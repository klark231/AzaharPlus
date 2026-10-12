#!/usr/bin/env python3
"""
Run from the AzaharPlus repo root (the folder that has src/):   python3 cheats_and_combo.py

Adds three things:
  1. Settings > "Built-in cheats" switch (OFF by default). OFF = the cheats AzaharPlus pulls from its
     built-in database (the long Monster Hunter list etc.) are not loaded. Only your own cheats show.
  2. Cheats screen > "Edit as text" button: the whole cheat file as one notepad box. Paste many
     cheats at once ([Name] line then code lines), press Save.
  3. Combo Button settings can be opened and changed while a game is running (the overlay refreshes
     when you come back).
Nothing is written unless every step finds its place. Safe to run twice.
"""
import sys

ROOT = "src"
A = f"{ROOT}/android/app/src/main"
J = f"{A}/java/org/citra/citra_emu"
FILES = {}


def read(p):
    if p in FILES:
        return FILES[p]
    with open(p, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def edit(p, marker, old, new):
    s = read(p)
    if marker in s:
        return
    if s.count(old) != 1:
        sys.exit(f"STOP: cannot find the right place in {p}\n  looking for: {old[:80]!r}\nNothing was changed.")
    FILES[p] = s.replace(old, new)


# ---------- native core ----------
GH = f"{ROOT}/core/cheats/gateway_cheat.h"
edit(GH, "SetBuiltInEnabled",
     "    static std::vector<std::shared_ptr<CheatBase>> LoadFile(const std::string& filepath);",
     "    static std::vector<std::shared_ptr<CheatBase>> LoadFile(const std::string& filepath);\n"
     "    /// Turns the built-in cheat database on/off (used by LoadFile).\n"
     "    static void SetBuiltInEnabled(bool enabled);\n"
     "    static bool IsBuiltInEnabled();")

GC = f"{ROOT}/core/cheats/gateway_cheat.cpp"
edit(GC, "g_builtin_enabled", "#include <algorithm>\n", "#include <algorithm>\n#include <atomic>\n")
edit(GC, "static std::atomic<bool> g_builtin_enabled",
     "std::vector<std::shared_ptr<CheatBase>> GatewayCheat::LoadFile(const std::string& filepath) {",
     "static std::atomic<bool> g_builtin_enabled{true};\n\n"
     "void GatewayCheat::SetBuiltInEnabled(bool enabled) {\n    g_builtin_enabled = enabled;\n}\n\n"
     "bool GatewayCheat::IsBuiltInEnabled() {\n    return g_builtin_enabled;\n}\n\n"
     "std::vector<std::shared_ptr<CheatBase>> GatewayCheat::LoadFile(const std::string& filepath) {")
edit(GC, "g_builtin_enabled && cheats_json",
     "if (cheats_json.contains(titleId)) {",
     "if (g_builtin_enabled && cheats_json.contains(titleId)) {")

CH = f"{ROOT}/core/cheats/cheats.h"
edit(CH, "InvalidateLoaded",
     "    /// Saves currently active cheats to file for the specified title id.",
     "    /// Forgets which title is loaded so the next LoadCheatFile really reads the file again.\n"
     "    void InvalidateLoaded();\n\n"
     "    /// Saves currently active cheats to file for the specified title id.")
CC = f"{ROOT}/core/cheats/cheats.cpp"
edit(CC, "CheatEngine::InvalidateLoaded",
     "void CheatEngine::LoadCheatFile(u64 title_id) {",
     "void CheatEngine::InvalidateLoaded() {\n    std::unique_lock lock{cheats_list_mutex};\n"
     "    loaded_title_id.reset();\n}\n\nvoid CheatEngine::LoadCheatFile(u64 title_id) {")

# ---------- JNI ----------
JN = f"{A}/jni/cheats/cheat_engine.cpp"
edit(JN, "setCheatFileText", '#include "core/cheats/cheats.h"\n',
     '#include <string>\n#include <fmt/format.h>\n#include "android_common/android_common.h"\n'
     '#include "common/file_util.h"\n#include "core/cheats/cheats.h"\n#include "core/cheats/gateway_cheat.h"\n')
edit(JN, "setCheatFileText", "JNIEXPORT void JNICALL Java_org_citra_citra_1emu_features_cheats_model_CheatEngine_loadCheatFile(",
     '''static std::string CheatFilePath(jlong title_id) {
    return fmt::format("{}{:016X}.txt", FileUtil::GetUserPath(FileUtil::UserPath::CheatsDir),
                       static_cast<u64>(title_id));
}

JNIEXPORT void JNICALL
Java_org_citra_citra_1emu_features_cheats_model_CheatEngine_setBuiltInCheatsEnabled(
    JNIEnv* env, jclass, jboolean enabled) {
    const bool value = enabled == JNI_TRUE;
    if (Cheats::GatewayCheat::IsBuiltInEnabled() != value) {
        Cheats::GatewayCheat::SetBuiltInEnabled(value);
        GetEngine().InvalidateLoaded();
    }
}

JNIEXPORT jstring JNICALL Java_org_citra_citra_1emu_features_cheats_model_CheatEngine_getCheatFileText(
    JNIEnv* env, jclass, jlong title_id) {
    std::string text;
    const std::string path = CheatFilePath(title_id);
    if (FileUtil::Exists(path)) {
        FileUtil::ReadFileToString(true, path, text);
    }
    return ToJString(env, text);
}

JNIEXPORT void JNICALL Java_org_citra_citra_1emu_features_cheats_model_CheatEngine_setCheatFileText(
    JNIEnv* env, jclass, jlong title_id, jstring j_text) {
    std::string text = GetJString(env, j_text);
    text.erase(std::remove(text.begin(), text.end(), '\\r'), text.end());
    // Pasted codes without a [Name] line get a default name so they are not lost.
    const auto first = text.find_first_not_of(" \\t\\n");
    if (first != std::string::npos && text[first] != '[') {
        text = "[Cheat]\\n" + text;
    }
    const std::string dir = FileUtil::GetUserPath(FileUtil::UserPath::CheatsDir);
    if (!FileUtil::IsDirectory(dir)) {
        FileUtil::CreateDir(dir);
    }
    FileUtil::WriteStringToFile(true, CheatFilePath(title_id), text);
    GetEngine().InvalidateLoaded();
    GetEngine().LoadCheatFile(title_id);
}

JNIEXPORT void JNICALL Java_org_citra_citra_1emu_features_cheats_model_CheatEngine_loadCheatFile(''')
edit(JN, "<algorithm>", "#include <utility>\n", "#include <algorithm>\n#include <utility>\n")

# ---------- Kotlin ----------
edit(f"{J}/features/cheats/model/CheatEngine.kt", "setCheatFileText",
     "    external fun saveCheatFile(titleId: Long)\n",
     "    external fun saveCheatFile(titleId: Long)\n\n"
     "    external fun setBuiltInCheatsEnabled(enabled: Boolean)\n"
     "    external fun getCheatFileText(titleId: Long): String\n"
     "    external fun setCheatFileText(titleId: Long, text: String)\n")

VM = f"{J}/features/cheats/model/CheatsViewModel.kt"
edit(VM, "replaceCheatFileText", "import kotlinx.coroutines.flow.asStateFlow\n",
     "import kotlinx.coroutines.flow.asStateFlow\nimport org.citra.citra_emu.features.settings.model.BooleanSetting\n")
edit(VM, "setBuiltInCheatsEnabled", "        titleId = titleId_\n        load()",
     "        titleId = titleId_\n"
     "        CheatEngine.setBuiltInCheatsEnabled(BooleanSetting.BUILTIN_CHEATS.boolean)\n        load()")
edit(VM, "replaceCheatFileText", "    fun setSelectedCheat(cheat: Cheat?, position: Int) {",
     '''    /** The whole cheat file as text, for the notepad editor. */
    fun getCheatFileText(): String {
        saveIfNeeded()
        return CheatEngine.getCheatFileText(titleId)
    }

    /** Replaces the whole cheat file with the text from the notepad editor and reloads. */
    fun replaceCheatFileText(text: String) {
        setSelectedCheat(null, -1)
        CheatEngine.setCheatFileText(titleId, text)
        cheatsNeedSaving = false
        load()
    }

    fun setSelectedCheat(cheat: Cheat?, position: Int) {''')

edit(f"{J}/features/settings/model/BooleanSetting.kt", "BUILTIN_CHEATS",
     '    KEEP_EMULATION_RUNNING("keep_emulation_running", Settings.SECTION_CORE, false),\n',
     '    KEEP_EMULATION_RUNNING("keep_emulation_running", Settings.SECTION_CORE, false),\n'
     '    BUILTIN_CHEATS("builtin_cheats", Settings.SECTION_CORE, false),\n')

edit(f"{J}/features/settings/ui/SettingsFragmentPresenter.kt", "BUILTIN_CHEATS",
     '''                    BooleanSetting.KEEP_EMULATION_RUNNING.defaultValue
                )
            )
''',
     '''                    BooleanSetting.KEEP_EMULATION_RUNNING.defaultValue
                )
            )

            add(
                SwitchSetting(
                    BooleanSetting.BUILTIN_CHEATS,
                    R.string.builtin_cheats,
                    R.string.builtin_cheats_description,
                    BooleanSetting.BUILTIN_CHEATS.key,
                    BooleanSetting.BUILTIN_CHEATS.defaultValue
                )
            )
''')

edit(f"{J}/fragments/EmulationFragment.kt", "setBuiltInCheatsEnabled",
     "                        NativeLibrary.run(gamePath)",
     "                        org.citra.citra_emu.features.cheats.model.CheatEngine\n"
     "                            .setBuiltInCheatsEnabled(BooleanSetting.BUILTIN_CHEATS.boolean)\n"
     "                        NativeLibrary.run(gamePath)")

CL = f"{J}/features/cheats/ui/CheatListFragment.kt"
edit(CL, "showTextEditor", "import android.os.Bundle\n",
     "import android.graphics.Typeface\nimport android.os.Bundle\nimport android.text.InputType\n"
     "import android.view.Gravity\nimport android.widget.EditText\nimport android.widget.ScrollView\n"
     "import com.google.android.material.dialog.MaterialAlertDialogBuilder\n")
edit(CL, "showTextEditor", "        setInsets()\n    }\n\n    private fun setInsets() {",
     '''        binding.toolbarCheatList.inflateMenu(R.menu.menu_cheat_list)
        binding.toolbarCheatList.setOnMenuItemClickListener {
            if (it.itemId == R.id.cheats_edit_text) {
                showTextEditor()
                true
            } else {
                false
            }
        }

        setInsets()
    }

    /** Notepad-style editor for the whole cheat file. */
    private fun showTextEditor() {
        val ctx = requireContext()
        val edit = EditText(ctx).apply {
            setText(cheatsViewModel.getCheatFileText())
            typeface = Typeface.MONOSPACE
            textSize = 13f
            gravity = Gravity.TOP or Gravity.START
            minLines = 14
            hint = ctx.getString(R.string.cheats_text_hint)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or
                InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
        }
        val pad = (16 * resources.displayMetrics.density).toInt()
        val scroll = ScrollView(ctx).apply {
            setPadding(pad, pad / 2, pad, 0)
            addView(edit)
        }
        MaterialAlertDialogBuilder(ctx)
            .setTitle(R.string.cheats_edit_text)
            .setView(scroll)
            .setPositiveButton(R.string.cheats_text_save) { _, _ ->
                cheatsViewModel.replaceCheatFileText(edit.text.toString())
                @Suppress("NotifyDataSetChanged")
                binding.cheatList.adapter?.notifyDataSetChanged()
            }
            .setNegativeButton(R.string.cheats_text_cancel, null)
            .show()
    }

    private fun setInsets() {''')


# ---------- combo button config usable while a game is running ----------
edit(f"{J}/features/settings/ui/SettingsFragmentPresenter.kt", "combo_runtime_ok",
'''                    R.string.combo_button_settings_description,
                    false,
                    0,
                    {
                        settingsActivity.supportFragmentManager.let { fm ->''',
'''                    R.string.combo_button_settings_description,
                    true, // combo_runtime_ok: may be opened while a game is running
                    0,
                    {
                        fragmentView.onSettingChanged() // make sure the combos get saved
                        settingsActivity.supportFragmentManager.let { fm ->''')
edit(f"{J}/fragments/EmulationFragment.kt", "refresh_after_settings",
'''            val position = IntSetting.PERFORMANCE_OVERLAY_POSITION.int
            updateStatsPosition(position)
''',
'''            val position = IntSetting.PERFORMANCE_OVERLAY_POSITION.int
            updateStatsPosition(position)

            // refresh_after_settings: combo buttons enabled/disabled in Settings show up right away
            _binding?.surfaceInputOverlay?.refreshControls()
''')

# ---------- new files / strings ----------
MENU = f"{A}/res/menu/menu_cheat_list.xml"
import os
if not os.path.exists(MENU):
    FILES[MENU] = '''<?xml version="1.0" encoding="utf-8"?>
<menu xmlns:android="http://schemas.android.com/apk/res/android">
    <item
        android:id="@+id/cheats_edit_text"
        android:title="@string/cheats_edit_text"
        android:showAsAction="always" />
</menu>
'''

SX = f"{A}/res/values/strings.xml"
if "name=\"builtin_cheats\"" not in read(SX):
    new = '''    <string name="builtin_cheats">Built-in cheats</string>
    <string name="builtin_cheats_description">Also show the cheats AzaharPlus ships in its own database (for example the long Monster Hunter lists). Off = only your own cheats.</string>
    <string name="cheats_edit_text">Edit as text</string>
    <string name="cheats_text_hint">[Cheat name]\\n01234567 89ABCDEF</string>
    <string name="cheats_text_save">Save</string>
    <string name="cheats_text_cancel">Cancel</string>
'''
    s = read(SX)
    if s.count("</resources>") != 1:
        sys.exit("STOP: strings.xml has no single </resources>. Nothing was changed.")
    FILES[SX] = s.replace("</resources>", new + "</resources>")

for p, t in FILES.items():
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(t)
print("Done. Changed:" if FILES else "Already applied.")
for p in FILES:
    print("  ", p)
