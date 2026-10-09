// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

package org.citra.citra_emu.features.settings.utils

import org.citra.citra_emu.features.settings.SettingKeys
import org.citra.citra_emu.features.settings.model.Settings
import org.citra.citra_emu.features.settings.model.AbstractSetting
import org.citra.citra_emu.features.settings.model.BooleanSetting
import org.citra.citra_emu.features.settings.model.FloatSetting
import org.citra.citra_emu.features.settings.model.IntListSetting
import org.citra.citra_emu.features.settings.model.IntSetting
import org.citra.citra_emu.features.settings.model.ScaledFloatSetting
import org.citra.citra_emu.features.settings.model.StringSetting

/**
 * Describes which settings can be overridden for a single application.
 *
 * Every setting that lives in one of [allowedSections] can be overridden: the native loader
 * (Config in jni/config.cpp) merges the overrides into the global ini before reading it, and
 * frontend only settings (orientation, cutout, layouts to cycle, ...) are applied by [applyOverlay]
 * when the game starts. Controls, cameras, network and storage settings are global only.
 */
object PerGameSettings {
    val allowedSections: Set<String> = setOf(
        Settings.SECTION_CORE,
        Settings.SECTION_SYSTEM,
        Settings.SECTION_RENDERER,
        Settings.SECTION_LAYOUT,
        Settings.SECTION_AUDIO,
        Settings.SECTION_DEBUG,
        Settings.SECTION_UTILITY
    )

    /** Menus (and their sub menus) that are shown while editing a single game. */
    val allowedMenus: Set<String> = allowedSections + setOf(
        Settings.SECTION_PERFORMANCE_OVERLAY,
        Settings.SECTION_CUSTOM_LANDSCAPE,
        Settings.SECTION_CUSTOM_PORTRAIT
    )

    /**
     * Keys that are only meaningful together. The android frontend has a separate on/off switch for
     * the frame limiter, so overriding one has to carry the other.
     */
    private val linkedKeys: Map<String, String> = mapOf(
        SettingKeys.frame_limit() to SettingKeys.use_frame_limit(),
        SettingKeys.use_frame_limit() to SettingKeys.frame_limit()
    )

    private val overridableKeys: Set<String> by lazy {
        allSettings().filter { it.section in allowedSections }.mapNotNull { it.key }.toSet()
    }

    fun isOverridable(key: String?): Boolean = key != null && key in overridableKeys

    fun linkedKey(key: String): String? = linkedKeys[key]

    /** Same naming the desktop frontend uses: 16 digit upper case hex title id. */
    fun fileName(titleId: Long): String = "%016X".format(titleId)

    /** Every setting object that is backed by a key/value pair in the ini files. */
    fun allSettings(): List<AbstractSetting> =
        BooleanSetting.values().toList<AbstractSetting>() +
            IntSetting.values().toList() +
            FloatSetting.values().toList() +
            ScaledFloatSetting.values().toList() +
            StringSetting.values().toList() +
            IntListSetting.values().toList()

    fun allOverridableSettings(): List<AbstractSetting> =
        allSettings().filter { isOverridable(it.key) }

    /**
     * Applies the overrides of a game to the in memory settings. The native side does the same on
     * its own for the settings it reads; this covers the ones only the frontend uses.
     */
    fun applyOverlay(titleId: Long) {
        if (titleId == 0L) {
            return
        }
        for (entry in SettingsFile.readPerGameSettings(fileName(titleId))) {
            if (isOverridable(entry.key)) {
                SettingsFile.settingFromLine("${entry.key}=${entry.value}")
            }
        }
    }

    /** Reloads the global config into the (process wide) setting objects. */
    fun restoreGlobal() {
        for (name in Settings.configFileNames) {
            SettingsFile.readFile(name)
        }
    }
}
