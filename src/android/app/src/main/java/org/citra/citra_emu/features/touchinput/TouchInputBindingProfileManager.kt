// Copyright Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version.
// Refer to the license.txt file included.

package org.citra.citra_emu.features.touchinput

import android.content.Context
import android.content.SharedPreferences
import androidx.preference.PreferenceManager
import org.citra.citra_emu.CitraApplication
import org.json.JSONArray
import org.json.JSONException

/**
 * Stores named sets of touch input bindings. Every profile is equally editable and deletable —
 * there's no special "Default" that's pinned in place. At least one profile always exists: a
 * fresh install starts with "Profile 1", and deleting the last remaining profile replaces it with
 * a new "Profile N" rather than leaving nothing to select.
 */
class TouchInputBindingProfileManager(context: Context) {
    private val preferences: SharedPreferences =
        PreferenceManager.getDefaultSharedPreferences(
            context.applicationContext ?: CitraApplication.appContext
        )

    init {
        if (getProfiles().isEmpty()) {
            replaceAllProfilesWithFreshOne()
        }
    }

    fun getCurrentProfile(): String =
        preferences.getString(KEY_CURRENT_PROFILE, null) ?: getProfiles().first()

    fun setCurrentProfile(profileName: String) {
        preferences.edit().putString(KEY_CURRENT_PROFILE, profileName).apply()
    }

    fun getProfiles(): List<String> {
        val json = preferences.getString(KEY_PROFILES_LIST, null) ?: return emptyList()

        return try {
            val array = JSONArray(json)
            List(array.length()) { array.getString(it) }
        } catch (_: JSONException) {
            emptyList()
        }
    }

    /** "Profile 1", or the next number not already taken by an existing profile. */
    fun suggestNextProfileName(): String = nextAvailableProfileName(getProfiles())

    fun createProfile(profileName: String): Boolean {
        val name = profileName.trim()
        if (name.isEmpty()) return false

        val profiles = getProfiles()
        if (profiles.contains(name)) return false

        saveProfilesList(profiles + name)
        saveProfile(name, emptyList())
        return true
    }

    fun deleteProfile(profileName: String): Boolean {
        val profiles = getProfiles()
        if (!profiles.contains(profileName)) return false

        preferences.edit().remove(getStorageKey(profileName)).apply()

        val remaining = profiles - profileName
        if (remaining.isEmpty()) {
            // Never leave the screen with nothing to select.
            replaceAllProfilesWithFreshOne()
        } else {
            saveProfilesList(remaining)
            if (getCurrentProfile() == profileName) {
                setCurrentProfile(remaining.first())
            }
        }
        return true
    }

    fun renameProfile(oldName: String, newName: String): Boolean {
        val trimmedName = newName.trim()
        if (trimmedName.isEmpty() || oldName == trimmedName) return false

        val profiles = getProfiles()
        val index = profiles.indexOf(oldName)
        if (index == -1 || profiles.contains(trimmedName)) return false

        val bindings = loadProfile(oldName)

        saveProfilesList(profiles.toMutableList().also { it[index] = trimmedName })
        saveProfile(trimmedName, bindings)
        preferences.edit().remove(getStorageKey(oldName)).apply()

        if (getCurrentProfile() == oldName) {
            setCurrentProfile(trimmedName)
        }
        return true
    }

    fun saveProfile(profileName: String, bindings: List<TouchInputBinding>) {
        preferences.edit()
            .putString(getStorageKey(profileName), TouchInputBinding.listToJson(bindings))
            .apply()
    }

    fun loadProfile(profileName: String): List<TouchInputBinding> =
        TouchInputBinding.listFromJson(preferences.getString(getStorageKey(profileName), null))

    /** Wipes every profile and starts over with a single freshly-named, empty one. */
    private fun replaceAllProfilesWithFreshOne() {
        val freshName = nextAvailableProfileName(emptyList())
        saveProfilesList(listOf(freshName))
        saveProfile(freshName, emptyList())
        setCurrentProfile(freshName)
    }

    private fun nextAvailableProfileName(existing: Collection<String>): String {
        val taken = existing.toHashSet()
        var number = 1
        while ("$PROFILE_NAME_PREFIX $number" in taken) number++
        return "$PROFILE_NAME_PREFIX $number"
    }

    private fun saveProfilesList(profiles: List<String>) {
        val array = JSONArray()
        profiles.forEach { array.put(it) }
        preferences.edit().putString(KEY_PROFILES_LIST, array.toString()).apply()
    }

    private fun getStorageKey(profileName: String): String = "$KEY_BINDINGS_PREFIX$profileName"

    companion object {
        private const val PROFILE_NAME_PREFIX = "Profile"

        private const val KEY_CURRENT_PROFILE = "current_profile"
        private const val KEY_PROFILES_LIST = "profiles_list"
        private const val KEY_BINDINGS_PREFIX = "bindings_profile_"
    }
}
