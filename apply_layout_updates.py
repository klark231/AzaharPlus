#!/usr/bin/env python3
"""
Run from the root of the AzaharPlus repo:   python3 apply_layout_updates.py

What it adds (all in one go, nothing is written unless every step matches):
  1. Custom layout editor: frames/handles line up with the game when "Expand to cutout area" is off.
  2. Custom layout Done: asks "Only this game / All games / Discard"; Cancel puts the old layout back.
  3. Scale, opacity and toggle-controls OK: ask "Only this game / All games / Discard".
  4. New in-game overlay menu entry "Layout files": export / import the custom screen layout and the
     on-screen controls layout as plain .ini files next to config.ini (layout_global.ini and
     layout_<TitleID>.ini), for all games or for one game.
"""
import os
import sys

ROOT = "src/android/app/src/main"
J = f"{ROOT}/java/org/citra/citra_emu"

FILES = {}      # path -> new text, written only at the very end


def read(path):
    if path in FILES:
        return FILES[path]
    with open(path, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def edit(path, pairs):
    s = read(path)
    for old, new in pairs:
        n = s.count(old)
        if n != 1:
            sys.exit(f"STOP: in {path} I expected to find this exactly once but found {n}x:\n"
                     f"-----\n{old[:300]}\n-----\nNothing was changed. Send me this message.")
        s = s.replace(old, new)
    FILES[path] = s


def create(path, text):
    if os.path.exists(path):
        sys.exit(f"STOP: {path} already exists (is this patch already applied?). Nothing was changed.")
    FILES[path] = text


for p in (f"{J}/display/CustomLayoutManager.kt", f"{J}/fragments/EmulationFragment.kt",
          f"{J}/utils/OverlayProfile.kt", f"{ROOT}/res/menu/menu_overlay_options.xml"):
    if not os.path.exists(p):
        sys.exit(f"STOP: {p} not found. Run this from the root of the AzaharPlus repo.")
if "showCustomLayoutEditor" in read(f"{J}/fragments/EmulationFragment.kt"):
    sys.exit("This patch looks like it was already applied. Nothing was changed.")

# ====================================================================================
# CustomLayoutManager.kt
# ====================================================================================
edit(f"{J}/display/CustomLayoutManager.kt", [
("""    private val toolbar: View
) {
""", """    private val toolbar: View
) {
    /** The custom layout numbers as they were when the editor was opened. */
    private var layoutBefore: List<Int> = emptyList()

    /** Orientation that was being edited when the editor was opened. */
    private var editedPortrait = false

    /**
     * Called after Done with the layout from before the edit. The listener decides where the
     * change is kept (this game or all games). Without a listener the layout is saved globally.
     */
    var onDone: ((before: List<Int>, portrait: Boolean) -> Unit)? = null

    /** The eight settings (top and bottom: x, y, width, height) of one orientation. */
    fun layoutSettings(portrait: Boolean = NativeLibrary.isPortraitMode()): List<IntSetting> =
        if (portrait) {
            listOf(
                IntSetting.PORTRAIT_TOP_X, IntSetting.PORTRAIT_TOP_Y,
                IntSetting.PORTRAIT_TOP_WIDTH, IntSetting.PORTRAIT_TOP_HEIGHT,
                IntSetting.PORTRAIT_BOTTOM_X, IntSetting.PORTRAIT_BOTTOM_Y,
                IntSetting.PORTRAIT_BOTTOM_WIDTH, IntSetting.PORTRAIT_BOTTOM_HEIGHT
            )
        } else {
            listOf(
                IntSetting.LANDSCAPE_TOP_X, IntSetting.LANDSCAPE_TOP_Y,
                IntSetting.LANDSCAPE_TOP_WIDTH, IntSetting.LANDSCAPE_TOP_HEIGHT,
                IntSetting.LANDSCAPE_BOTTOM_X, IntSetting.LANDSCAPE_BOTTOM_Y,
                IntSetting.LANDSCAPE_BOTTOM_WIDTH, IntSetting.LANDSCAPE_BOTTOM_HEIGHT
            )
        }

    /** Puts a layout that was read with [layoutSettings] back, in the settings and the renderer. */
    fun restoreLayout(values: List<Int>, portrait: Boolean) {
        if (values.size != 8) return
        layoutSettings(portrait).zip(values).forEach { (setting, value) -> setting.int = value }
        NativeLibrary.setCustomLayout(
            values[0], values[1], values[2], values[3],
            values[4], values[5], values[6], values[7],
            portrait
        )
        editorView.loadLayoutSettings()
        editorView.invalidate()
    }

"""),
("""    fun showEditor() {
        editorView.visibility = View.VISIBLE""", """    fun showEditor() {
        editedPortrait = NativeLibrary.isPortraitMode()
        layoutBefore = layoutSettings(editedPortrait).map { it.int }
        editorView.visibility = View.VISIBLE"""),
("""        doneButton.setOnClickListener {
            editorView.applyLayoutChanges()
            saveLayoutSettings()
            hideEditor()
        }""", """        doneButton.setOnClickListener {
            editorView.applyLayoutChanges()
            hideEditor()
            val listener = onDone
            if (listener != null) {
                listener(layoutBefore, editedPortrait)
            } else {
                saveLayoutSettings()
            }
        }"""),
("""        cancelButton.setOnClickListener { hideEditor() }""",
"""        cancelButton.setOnClickListener {
            // The layout is applied live while editing, so put the old one back
            restoreLayout(layoutBefore, editedPortrait)
            hideEditor()
        }"""),
("""    fun saveLayoutSettings() {
        if (NativeLibrary.isPortraitMode()) {""", """    fun saveLayoutSettings(portrait: Boolean = NativeLibrary.isPortraitMode()) {
        if (portrait) {"""),
])

# ====================================================================================
# OverlayProfile.kt  (import helpers)
# ====================================================================================
edit(f"{J}/utils/OverlayProfile.kt", [
("""    /** Throws the game's own layout away. */""", """    /** True if [key] is one of the preference keys that make up the on-screen controls layout. */
    fun isLayoutKey(key: String): Boolean = layoutKey.matches(key)

    private fun globalLayout(): Map<String, Any> =
        globalPrefs().all.filter { layoutKey.matches(it.key) && it.value != null }
            .mapValues { it.value!! }

    /** Imported keys must keep the defaults from being laid out again over the positions. */
    private fun withInit(imported: Map<String, Any>): Map<String, Any> =
        if (imported.keys.any { it.endsWith("-X") || it.endsWith("-Y") }) {
            imported + ("OverlayInit" to true)
        } else {
            imported
        }

    /** Keeps an imported layout for [gameId] alone; keys that were not imported stay as they are. */
    fun importForGame(gameId: String, imported: Map<String, Any>) {
        val target = gamePrefs(gameId)
        write(target, snapshot() + withInit(imported))
        target.edit().putBoolean(KEY_CUSTOM, true).apply()
    }

    /**
     * Keeps an imported layout for every game; keys that were not imported stay as they are. A
     * layout of the game's own is dropped so the game follows the global one.
     */
    fun importForAllGames(gameId: String?, imported: Map<String, Any>) {
        write(globalPrefs(), globalLayout() + withInit(imported))
        if (gameId != null) {
            reset(gameId)
        }
    }

    /** Throws the game's own layout away. */"""),
])

# ====================================================================================
# New Kotlin files
# ====================================================================================
create(f"{J}/utils/CustomLayoutProfile.kt", r'''// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

package org.citra.citra_emu.utils

import org.citra.citra_emu.features.settings.model.IntSetting
import org.citra.citra_emu.features.settings.utils.SettingsFile

/**
 * Keeps the custom screen layout (top and bottom screen position and size) for one game or for
 * every game. The numbers are ordinary per-game settings, so a game's own copy lives in its
 * per-game ini and the global copy in the config file.
 */
object CustomLayoutProfile {
    private fun withoutThese(gameId: String, settings: List<IntSetting>) =
        SettingsFile.readPerGameSettings(gameId).filter { entry ->
            settings.none { it.key == entry.key }
        }

    /** Keeps [settings] for [gameId] alone. The global config is not touched. */
    fun saveForThisGame(gameId: String, settings: List<IntSetting>) {
        val own = settings.map {
            SettingsFile.PerGameEntry(it.section!!, it.key!!, it.valueAsString)
        }
        SettingsFile.savePerGameSettings(gameId, withoutThese(gameId, settings) + own, null)
    }

    /**
     * Keeps [settings] for every game. If the game had a layout of its own it is dropped, so the
     * game follows the global one like the rest.
     */
    fun saveForAllGames(gameId: String?, settings: List<IntSetting>) {
        settings.forEach { SettingsFile.saveFile(SettingsFile.FILE_NAME_CONFIG, it) }
        if (gameId != null) {
            SettingsFile.savePerGameSettings(gameId, withoutThese(gameId, settings), null)
        }
    }
}
''')

create(f"{J}/utils/LayoutFiles.kt", r'''// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

package org.citra.citra_emu.utils

import android.net.Uri
import androidx.documentfile.provider.DocumentFile
import org.citra.citra_emu.CitraApplication
import org.citra.citra_emu.NativeLibrary
import org.citra.citra_emu.features.hotkeys.Hotkey
import org.citra.citra_emu.utils.DirectoryInitialization.userDirectory

/**
 * Layout files: plain .ini files in the config folder (next to config.ini) that hold the custom
 * screen layout and the layout of the on-screen controls, so they can be edited by hand, copied
 * between games or kept as a backup.
 *
 * layout_global.ini is the shared file, layout_<title id>.ini belongs to one game.
 */
object LayoutFiles {
    const val GLOBAL_NAME = "layout_global"

    fun gameName(gameId: String) = "layout_$gameId"

    /** What a layout file contains. Screen maps go from the value index (0..7) to the number. */
    class Layout(
        val controls: Map<String, Any>,
        val landscape: Map<Int, Int>,
        val portrait: Map<Int, Int>
    ) {
        val isEmpty: Boolean get() = controls.isEmpty() && landscape.isEmpty() && portrait.isEmpty()
    }

    private const val SECTION_LANDSCAPE = "Screens Landscape"
    private const val SECTION_PORTRAIT = "Screens Portrait"
    private const val SECTION_CONTROLS = "Controls"

    /** Same order as CustomLayoutManager.layoutSettings(). */
    private val screenNames = listOf(
        "top_x", "top_y", "top_width", "top_height",
        "bottom_x", "bottom_y", "bottom_width", "bottom_height"
    )

    private val positionKey = Regex("^\\d+(-[A-Za-z]+)?-[XY]$")
    private val boolKey = Regex("^buttonToggle\\d+$|^OverlayInit$|^isTouchEnabled$")

    /** Only used for the comments in the file, so a wrong name can not break anything. */
    private val controlNames: Map<Int, String> = mapOf(
        NativeLibrary.ButtonType.BUTTON_A to "A",
        NativeLibrary.ButtonType.BUTTON_B to "B",
        NativeLibrary.ButtonType.BUTTON_X to "X",
        NativeLibrary.ButtonType.BUTTON_Y to "Y",
        NativeLibrary.ButtonType.BUTTON_START to "Start",
        NativeLibrary.ButtonType.BUTTON_SELECT to "Select",
        NativeLibrary.ButtonType.BUTTON_HOME to "Home",
        NativeLibrary.ButtonType.BUTTON_ZL to "ZL",
        NativeLibrary.ButtonType.BUTTON_ZR to "ZR",
        NativeLibrary.ButtonType.DPAD_UP to "D-pad",
        NativeLibrary.ButtonType.STICK_LEFT to "Circle pad",
        NativeLibrary.ButtonType.STICK_C to "C-stick",
        NativeLibrary.ButtonType.TRIGGER_L to "L",
        NativeLibrary.ButtonType.TRIGGER_R to "R",
        NativeLibrary.ButtonType.BUTTON_SWAP to "Swap screens",
        NativeLibrary.ButtonType.BUTTON_TURBO to "Turbo",
        Hotkey.COMBO_BUTTON.button to "Combo button 1",
        Hotkey.COMBO_BUTTON_2.button to "Combo button 2",
        Hotkey.COMBO_BUTTON_3.button to "Combo button 3",
        Hotkey.COMBO_BUTTON_4.button to "Combo button 4",
        Hotkey.COMBO_BUTTON_5.button to "Combo button 5"
    )

    private fun configDir(): DocumentFile? {
        val root = DocumentFile.fromTreeUri(CitraApplication.appContext, Uri.parse(userDirectory))
            ?: return null
        return root.findFile("config")
    }

    fun exists(name: String): Boolean = configDir()?.findFile("$name.ini") != null

    private fun numericId(key: String): Int = key.takeWhile { it.isDigit() }.toIntOrNull() ?: Int.MAX_VALUE

    private fun build(controls: Map<String, Any>, landscape: List<Int>, portrait: List<Int>) =
        buildString {
            append("; AzaharPlus layout file.\n")
            append("; Edit the numbers, then use \"Layout files\" in the in-game overlay menu to import it.\n")
            append("; Screens: pixels from the top left of the game area. Lines you delete keep their current value.\n")
            append("; Controls: positions are pixels, scale and opacity are percent (50 is the default),\n")
            append(";           buttonToggleN=true means that button is shown.\n\n")
            fun screens(title: String, values: List<Int>) {
                append("[").append(title).append("]\n")
                screenNames.forEachIndexed { i, name ->
                    append(name).append('=').append(values.getOrElse(i) { 0 }).append('\n')
                }
                append('\n')
            }
            screens(SECTION_LANDSCAPE, landscape)
            screens(SECTION_PORTRAIT, portrait)
            append("[").append(SECTION_CONTROLS).append("]\n")
            controls.entries
                .sortedWith(compareBy<Map.Entry<String, Any>>({ numericId(it.key) }, { it.key }))
                .forEach { (key, value) ->
                    if (key.endsWith("-X")) {
                        controlNames[numericId(key)]?.let {
                            append("; ").append(it)
                            if (key.contains("Portrait")) append(" (portrait)")
                            append('\n')
                        }
                    }
                    append(key).append('=').append(value.toString()).append('\n')
                }
        }

    /** Writes (or overwrites) config/<name>.ini. Returns false if the file could not be written. */
    fun write(name: String, controls: Map<String, Any>, landscape: List<Int>, portrait: List<Int>): Boolean {
        val dir = configDir() ?: return false
        val file = dir.findFile("$name.ini")
            ?: dir.createFile("application/octet-stream", "$name.ini")
            ?: return false
        val text = build(controls, landscape, portrait)
        return try {
            CitraApplication.appContext.contentResolver.openOutputStream(file.uri, "wt")?.use {
                it.write(text.toByteArray())
                it.flush()
            } != null
        } catch (e: Exception) {
            Log.error("[LayoutFiles] Could not write $name.ini: ${e.message}")
            false
        }
    }

    private fun parseScreen(key: String, value: String): Pair<Int, Int>? {
        val index = screenNames.indexOf(key.lowercase())
        val number = value.toIntOrNull() ?: value.toFloatOrNull()?.toInt()
        return if (index < 0 || number == null) null else index to number.coerceIn(0, 65535)
    }

    private fun parseControl(key: String, value: String): Any? {
        if (!OverlayProfile.isLayoutKey(key)) return null
        return when {
            positionKey.matches(key) -> value.toFloatOrNull()
            boolKey.matches(key) -> when (value.lowercase()) {
                "true", "1", "yes", "on" -> true
                "false", "0", "no", "off" -> false
                else -> null
            }
            else -> value.toIntOrNull() ?: value.toFloatOrNull()?.toInt()
        }
    }

    private fun readText(file: DocumentFile, name: String): String? {
        return try {
            CitraApplication.appContext.contentResolver.openInputStream(file.uri)
                ?.bufferedReader()?.use { it.readText() }
        } catch (e: Exception) {
            Log.error("[LayoutFiles] Could not read $name.ini: ${e.message}")
            null
        }
    }

    /** Reads config/<name>.ini. Lines that make no sense are skipped. Null if it can not be read. */
    fun read(name: String): Layout? {
        val file = configDir()?.findFile("$name.ini") ?: return null
        val text = readText(file, name) ?: return null

        val controls = LinkedHashMap<String, Any>()
        val landscape = LinkedHashMap<Int, Int>()
        val portrait = LinkedHashMap<Int, Int>()
        var section = ""
        for (raw in text.lineSequence()) {
            val line = raw.trim()
            if (line.isEmpty() || line.startsWith(";") || line.startsWith("#")) continue
            if (line.startsWith("[") && line.endsWith("]")) {
                section = line.substring(1, line.length - 1).trim().lowercase()
                continue
            }
            val split = line.indexOf('=')
            if (split <= 0) continue
            val key = line.substring(0, split).trim()
            val value = line.substring(split + 1).trim()
            when (section) {
                SECTION_LANDSCAPE.lowercase() ->
                    parseScreen(key, value)?.let { (index, number) -> landscape[index] = number }
                SECTION_PORTRAIT.lowercase() ->
                    parseScreen(key, value)?.let { (index, number) -> portrait[index] = number }
                SECTION_CONTROLS.lowercase() ->
                    parseControl(key, value)?.let { controls[key] = it }
            }
        }
        return Layout(controls, landscape, portrait)
    }
}
''')

create(f"{ROOT}/res/values/strings_layout_scope.xml", """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="custom_layout_save_scope_title">Save the screen layout</string>
    <string name="custom_layout_save_scope_message">You changed the custom screen layout. Keep the change only for %1$s, or for every game?</string>
    <string name="custom_layout_saved_for_game">Screen layout saved for %1$s</string>

    <string name="layout_files_menu">Layout files (export / import)</string>
    <string name="layout_files_title">Layout files</string>
    <string name="layout_files_export_global">Export current layout to layout_global.ini</string>
    <string name="layout_files_export_game">Export current layout for this game</string>
    <string name="layout_files_import_global">Import layout_global.ini</string>
    <string name="layout_files_import_game">Import this game\\'s layout file</string>
    <string name="layout_files_exported">Saved to config/%1$s.ini</string>
    <string name="layout_files_export_failed">Could not write config/%1$s.ini</string>
    <string name="layout_files_missing">config/%1$s.ini was not found. Export a layout first.</string>
    <string name="layout_files_bad">Could not read any layout from config/%1$s.ini</string>
    <string name="layout_files_import_title">Import layout</string>
    <string name="layout_files_import_message">Use the layout from %1$s.ini only for %2$s, or for every game?</string>
    <string name="layout_files_imported">Layout imported</string>
</resources>
""")

# ====================================================================================
# Menu entry
# ====================================================================================
edit(f"{ROOT}/res/menu/menu_overlay_options.xml", [
("""    <item
        android:id="@+id/menu_emulation_reset_overlay"
        android:title="@string/emulation_touch_overlay_reset" />
""", """    <item
        android:id="@+id/menu_emulation_reset_overlay"
        android:title="@string/emulation_touch_overlay_reset" />

    <item
        android:id="@+id/menu_emulation_layout_files"
        android:title="@string/layout_files_menu" />
"""),
])

# ====================================================================================
# EmulationFragment.kt
# ====================================================================================
FRAG = f"{J}/fragments/EmulationFragment.kt"

# the editor must be opened on the same area as the game surface (cutout fix)
s = read(FRAG)
if s.count("customLayoutManager.showEditor()") != 2:
    sys.exit("STOP: expected customLayoutManager.showEditor() twice in EmulationFragment.kt, found "
             f"{s.count('customLayoutManager.showEditor()')}x. Nothing was changed.")
FILES[FRAG] = s.replace("customLayoutManager.showEditor()", "showCustomLayoutEditor()")

edit(FRAG, [
("""import org.citra.citra_emu.utils.OverlayProfile
""", """import org.citra.citra_emu.utils.CustomLayoutProfile
import org.citra.citra_emu.utils.LayoutFiles
import org.citra.citra_emu.utils.OverlayProfile
"""),
("""        customLayoutManager.bindControls()
""", """        customLayoutManager.bindControls()
        customLayoutManager.onDone = { before, portrait -> finishCustomLayoutEdit(before, portrait) }
"""),
("""    private fun setInsets() {""", """    /**
     * Opens the custom layout editor on exactly the same area the emulation surface occupies.
     *
     * With "Expand to cutout area" off the surface is inset by the display cutout, so the renderer
     * measures the custom layout from the safe area, not from the screen corner. The editor view is
     * full screen, so without this its frames and handles are shifted by the cutout size.
     */
    private fun showCustomLayoutEditor() {
        val surfaceParams = binding.surfaceEmulation.layoutParams as? ViewGroup.MarginLayoutParams
        val editorParams = binding.customLayoutEditor.layoutParams as? ViewGroup.MarginLayoutParams
        if (surfaceParams != null && editorParams != null) {
            editorParams.setMargins(
                surfaceParams.leftMargin,
                surfaceParams.topMargin,
                surfaceParams.rightMargin,
                surfaceParams.bottomMargin
            )
            binding.customLayoutEditor.layoutParams = editorParams
        }
        customLayoutManager.showEditor()
    }

    private fun setInsets() {"""),
("""    private fun editControlsPlacement() {""", """    /** Starts remembering the layout for a dialog that edits it (scale, opacity, toggles). */
    private fun beginOverlayDialogEdit() {
        if (overlayEditBefore == null) {
            beginOverlayEdit()
        }
    }

    /**
     * Ends such a dialog: asks where to keep the change, or forgets it when it was cancelled.
     * While the controls are being moved around, the Done button of that edit asks instead.
     */
    private fun endOverlayDialogEdit(keep: Boolean) {
        if (_binding?.surfaceInputOverlay?.isInEditMode == true) {
            return
        }
        if (keep) finishOverlayEdit() else overlayEditBefore = null
    }

    /**
     * Asks whether the custom screen layout that was just edited is for every game or only for
     * this one. The numbers are per-game settings, so "only this game" goes to the game's own ini.
     */
    private fun finishCustomLayoutEdit(before: List<Int>, portrait: Boolean) {
        val settings = customLayoutManager.layoutSettings(portrait)
        if (settings.map { it.int } == before) {
            return
        }
        val gameId = OverlayProfile.activeGameId
        if (gameId == null || _binding == null) {
            customLayoutManager.saveLayoutSettings(portrait)
            return
        }
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.custom_layout_save_scope_title)
            .setMessage(getString(R.string.custom_layout_save_scope_message, game.title))
            .setPositiveButton(R.string.overlay_save_this_game) { _, _ ->
                CustomLayoutProfile.saveForThisGame(gameId, settings)
                Toast.makeText(
                    requireContext(),
                    getString(R.string.custom_layout_saved_for_game, game.title),
                    Toast.LENGTH_SHORT
                ).show()
            }
            .setNegativeButton(R.string.overlay_save_all_games) { _, _ ->
                CustomLayoutProfile.saveForAllGames(gameId, settings)
            }
            .setNeutralButton(R.string.overlay_discard_changes) { _, _ ->
                customLayoutManager.restoreLayout(before, portrait)
            }
            .setCancelable(false)
            .show()
    }

    /** Menu with the export and import actions for layout files (config/layout_*.ini). */
    private fun showLayoutFilesDialog() {
        val gameId = OverlayProfile.activeGameId
        val gameFile = gameId?.let { LayoutFiles.gameName(it) }
        val labels = ArrayList<String>()
        val actions = ArrayList<() -> Unit>()
        labels.add(getString(R.string.layout_files_export_global))
        actions.add { exportLayoutFile(LayoutFiles.GLOBAL_NAME) }
        if (gameFile != null) {
            labels.add(getString(R.string.layout_files_export_game))
            actions.add { exportLayoutFile(gameFile) }
        }
        labels.add(getString(R.string.layout_files_import_global))
        actions.add { importLayoutFile(LayoutFiles.GLOBAL_NAME) }
        if (gameFile != null) {
            labels.add(getString(R.string.layout_files_import_game))
            actions.add { importLayoutFile(gameFile) }
        }
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.layout_files_title)
            .setItems(labels.toTypedArray()) { _, which -> actions[which]() }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    /** Writes the layout that is in use right now (screens and on-screen controls) to a file. */
    private fun exportLayoutFile(name: String) {
        val saved = LayoutFiles.write(
            name,
            OverlayProfile.snapshot(),
            customLayoutManager.layoutSettings(false).map { it.int },
            customLayoutManager.layoutSettings(true).map { it.int }
        )
        Toast.makeText(
            requireContext(),
            getString(
                if (saved) R.string.layout_files_exported else R.string.layout_files_export_failed,
                name
            ),
            Toast.LENGTH_LONG
        ).show()
    }

    /** Reads a layout file and asks whether it is for this game only or for every game. */
    private fun importLayoutFile(name: String) {
        if (!LayoutFiles.exists(name)) {
            Toast.makeText(
                requireContext(),
                getString(R.string.layout_files_missing, name),
                Toast.LENGTH_LONG
            ).show()
            return
        }
        val layout = LayoutFiles.read(name)
        if (layout == null || layout.isEmpty) {
            Toast.makeText(
                requireContext(),
                getString(R.string.layout_files_bad, name),
                Toast.LENGTH_LONG
            ).show()
            return
        }
        val gameId = OverlayProfile.activeGameId
        if (gameId == null) {
            applyImportedLayout(layout, null, false)
            return
        }
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.layout_files_import_title)
            .setMessage(getString(R.string.layout_files_import_message, name, game.title))
            .setPositiveButton(R.string.overlay_save_this_game) { _, _ ->
                applyImportedLayout(layout, gameId, true)
            }
            .setNegativeButton(R.string.overlay_save_all_games) { _, _ ->
                applyImportedLayout(layout, gameId, false)
            }
            .setNeutralButton(android.R.string.cancel, null)
            .show()
    }

    private fun applyImportedLayout(layout: LayoutFiles.Layout, gameId: String?, forGame: Boolean) {
        if (layout.controls.isNotEmpty()) {
            if (forGame && gameId != null) {
                OverlayProfile.importForGame(gameId, layout.controls)
            } else {
                OverlayProfile.importForAllGames(gameId, layout.controls)
            }
        }
        for ((portrait, values) in listOf(false to layout.landscape, true to layout.portrait)) {
            if (values.isEmpty()) {
                continue
            }
            val settings = customLayoutManager.layoutSettings(portrait)
            val merged = settings.mapIndexed { index, setting -> values[index] ?: setting.int }
            settings.zip(merged).forEach { (setting, value) -> setting.int = value }
            if (portrait == NativeLibrary.isPortraitMode()) {
                customLayoutManager.restoreLayout(merged, portrait)
            }
            if (forGame && gameId != null) {
                CustomLayoutProfile.saveForThisGame(gameId, settings)
            } else {
                CustomLayoutProfile.saveForAllGames(gameId, settings)
            }
        }
        _binding?.surfaceInputOverlay?.refreshControls()
        Toast.makeText(requireContext(), R.string.layout_files_imported, Toast.LENGTH_SHORT).show()
    }

    private fun editControlsPlacement() {"""),
# --- toggle controls
("""    private fun showToggleControlsDialog() {
        val editor = OverlayProfile.prefs().edit()""", """    private fun showToggleControlsDialog() {
        beginOverlayDialogEdit()
        val editor = OverlayProfile.prefs().edit()"""),
("""            .setPositiveButton(android.R.string.ok) { _: DialogInterface?, _: Int ->
                editor.apply()
                binding.surfaceInputOverlay.refreshControls()
            }
            .show()""", """            .setPositiveButton(android.R.string.ok) { _: DialogInterface?, _: Int ->
                editor.apply()
                binding.surfaceInputOverlay.refreshControls()
                endOverlayDialogEdit(keep = true)
            }
            .setNegativeButton(android.R.string.cancel) { _: DialogInterface?, _: Int ->
                endOverlayDialogEdit(keep = false)
            }
            .setOnCancelListener { endOverlayDialogEdit(keep = false) }
            .show()"""),
# --- scale
("""    private fun showAdjustScaleDialog(target: String) {
        val sliderBinding""", """    private fun showAdjustScaleDialog(target: String) {
        beginOverlayDialogEdit()
        val sliderBinding"""),
("""            .setNegativeButton(android.R.string.cancel) { _: DialogInterface?, _: Int ->
                setControlScale(previousProgress, target)
            }
            .setPositiveButton(android.R.string.ok) { _: DialogInterface?, _: Int ->
                setControlScale(sliderBinding.slider.value.toInt(), target)
            }
            .setNeutralButton(R.string.slider_default) { _: DialogInterface?, _: Int ->
                setControlScale(50, target)
            }
            .show()""", """            .setNegativeButton(android.R.string.cancel) { _: DialogInterface?, _: Int ->
                setControlScale(previousProgress, target)
                endOverlayDialogEdit(keep = false)
            }
            .setPositiveButton(android.R.string.ok) { _: DialogInterface?, _: Int ->
                setControlScale(sliderBinding.slider.value.toInt(), target)
                endOverlayDialogEdit(keep = true)
            }
            .setNeutralButton(R.string.slider_default) { _: DialogInterface?, _: Int ->
                setControlScale(50, target)
                endOverlayDialogEdit(keep = true)
            }
            .setOnCancelListener {
                setControlScale(previousProgress, target)
                endOverlayDialogEdit(keep = false)
            }
            .show()"""),
# --- opacity
("""    private fun showAdjustOpacityDialog() {
        val sliderBinding""", """    private fun showAdjustOpacityDialog() {
        beginOverlayDialogEdit()
        val sliderBinding"""),
("""            .setNegativeButton(android.R.string.cancel) { _: DialogInterface?, _: Int ->
                setControlOpacity(previousProgress)
            }
            .setPositiveButton(android.R.string.ok) { _: DialogInterface?, _: Int ->
                setControlOpacity(sliderBinding.slider.value.toInt())
            }
            .setNeutralButton(R.string.slider_default) { _: DialogInterface?, _: Int ->
                setControlOpacity(50)
            }
            .show()""", """            .setNegativeButton(android.R.string.cancel) { _: DialogInterface?, _: Int ->
                setControlOpacity(previousProgress)
                endOverlayDialogEdit(keep = false)
            }
            .setPositiveButton(android.R.string.ok) { _: DialogInterface?, _: Int ->
                setControlOpacity(sliderBinding.slider.value.toInt())
                endOverlayDialogEdit(keep = true)
            }
            .setNeutralButton(R.string.slider_default) { _: DialogInterface?, _: Int ->
                setControlOpacity(50)
                endOverlayDialogEdit(keep = true)
            }
            .setOnCancelListener {
                setControlOpacity(previousProgress)
                endOverlayDialogEdit(keep = false)
            }
            .show()"""),
# --- menu dispatch
("""                R.id.menu_emulation_reset_overlay -> {""", """                R.id.menu_emulation_layout_files -> {
                    showLayoutFilesDialog()
                    true
                }

                R.id.menu_emulation_reset_overlay -> {"""),
])

# ====================================================================================
# write everything (only reached if every anchor matched)
# ====================================================================================
for path, text in FILES.items():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", path)
print("\nDone. Now: git add -A && git commit -m \"Layout scope dialogs, cutout fix, layout files\"")
