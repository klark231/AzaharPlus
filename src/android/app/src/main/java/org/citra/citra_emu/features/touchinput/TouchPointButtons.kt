// Copyright Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version.
// Refer to the license.txt file included.

package org.citra.citra_emu.features.touchinput

import androidx.preference.PreferenceManager
import org.citra.citra_emu.CitraApplication
import org.citra.citra_emu.R

/**
 * On-screen "Touch" buttons. They are not 3DS buttons: holding one presses the point on the
 * bottom screen that it was created for in the Touch Input Bindings screen. A Touch button
 * exists for every binding that has an [TouchInputBinding.overlayButton] id, so there is no
 * fixed number of them. They show up in Toggle Controls and Adjust Overlay once created.
 */
object TouchPointButtons {
    /** Overlay button ids start here, above every hotkey and combo button id. */
    const val BASE_ID = 10100

    private const val PREF_NEXT_ID = "TouchButtonNextId"

    val DRAWABLE = R.drawable.button_touch
    val DRAWABLE_PRESSED = R.drawable.button_touch_pressed

    fun isTouchButton(id: Int): Boolean = id >= BASE_ID

    // ---- per-button images ------------------------------------------------------------------
    // Button themes are keyed by drawable name, but Touch buttons are created at run time and all
    // use the same built-in drawable. Every Touch button therefore gets a "virtual image id"
    // (below the range of real resource ids) that maps to its own theme file:
    //   button_touch_<n>.png / button_touch_<n>_pressed.png   -> only Touch button n
    //   button_touch.png / button_touch_pressed.png           -> every Touch button without its own
    private const val IMAGE_BASE = 0x7E000000
    private const val IMAGE_END = 0x7F000000

    /** Virtual image id for Touch button number [number] (1, 2, ...). */
    fun imageId(number: Int, pressed: Boolean): Int = IMAGE_BASE + number * 2 + if (pressed) 1 else 0

    fun isImageId(id: Int): Boolean = id in IMAGE_BASE until IMAGE_END

    /** Theme file names (without .png) to try for a virtual image id, most specific first. */
    fun imageNames(id: Int): List<String> {
        val number = (id - IMAGE_BASE) / 2
        val suffix = if ((id - IMAGE_BASE) % 2 == 1) "_pressed" else ""
        return listOf("button_touch_$number$suffix", "button_touch$suffix")
    }

    /** The built-in drawable that stands in for a virtual image id. */
    fun builtInDrawable(id: Int): Int =
        if ((id - IMAGE_BASE) % 2 == 1) DRAWABLE_PRESSED else DRAWABLE

    /** A new id that has not been used before, so no old position or size can come back. */
    fun allocateId(): Int {
        val prefs = PreferenceManager.getDefaultSharedPreferences(CitraApplication.appContext)
        val used = buttons().maxOfOrNull { it.overlayButton } ?: (BASE_ID - 1)
        val id = maxOf(prefs.getInt(PREF_NEXT_ID, BASE_ID), used + 1, BASE_ID)
        prefs.edit().putInt(PREF_NEXT_ID, id + 1).apply()
        return id
    }

    /** The bindings of the active profile that have a Touch button, oldest first. */
    fun buttons(): List<TouchInputBinding> =
        TouchInputBindingManager.getBindings()
            .filter { it.isOverlayBinding }
            .sortedBy { it.overlayButton }

    /** 1, 2, 3... in the order the buttons were created, for names and labels. */
    fun numberOf(id: Int): Int {
        val index = buttons().indexOfFirst { it.overlayButton == id }
        return if (index >= 0) index + 1 else id - BASE_ID + 1
    }

    /** Key in the overlay preferences that says if the button is shown (on by default). */
    fun toggleKey(id: Int): String = "buttonToggle$id"
}
