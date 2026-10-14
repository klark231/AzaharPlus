// Copyright 2023-2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv3 or any later version
// Refer to the LICENSE.txt file included.

package org.citra.citra_emu.overlay

import android.os.Handler
import android.os.Looper
import android.view.ViewConfiguration
import kotlin.math.hypot
import org.citra.citra_emu.utils.OverlayProfile
import android.app.Activity
import android.content.Context
import android.content.SharedPreferences
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Rect
import android.graphics.drawable.VectorDrawable
import android.os.Build
import android.util.AttributeSet
import android.util.DisplayMetrics
import android.view.MotionEvent
import android.view.SurfaceView
import android.view.View
import android.view.View.OnTouchListener
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.preference.PreferenceManager
import java.lang.NullPointerException
import kotlin.math.min
import org.citra.citra_emu.CitraApplication
import org.citra.citra_emu.NativeLibrary
import org.citra.citra_emu.R
import org.citra.citra_emu.features.hotkeys.Hotkey
import org.citra.citra_emu.features.settings.model.BooleanSetting
import org.citra.citra_emu.utils.ComboHelper
import org.citra.citra_emu.utils.EmulationMenuSettings
import org.citra.citra_emu.utils.TurboHelper

/**
 * Draws the interactive input overlay on top of the
 * [SurfaceView] that is rendering emulation.
 *
 * @param context The current [Context].
 * @param attrs   [AttributeSet] for parsing XML attributes.
 */
class InputOverlay(context: Context?, attrs: AttributeSet?) :
    SurfaceView(context, attrs),
    OnTouchListener {
    private val overlayButtons: MutableSet<InputOverlayDrawableButton> = HashSet()
    private val overlayDpads: MutableSet<InputOverlayDrawableDpad> = HashSet()
    private val overlayJoysticks: MutableSet<InputOverlayDrawableJoystick> = HashSet()
    private var isInEditMode = false
    private var buttonBeingConfigured: InputOverlayDrawableButton? = null
    private var dpadBeingConfigured: InputOverlayDrawableDpad? = null
    private var joystickBeingConfigured: InputOverlayDrawableJoystick? = null

    private val longPressHandler = Handler(Looper.getMainLooper())
    private var longPressTarget: Any? = null
    private var longPressDownX = 0f
    private var longPressDownY = 0f
    private val longPressRunnable = Runnable {
        val target = longPressTarget ?: return@Runnable
        longPressTarget = null
        buttonBeingConfigured = null
        dpadBeingConfigured = null
        joystickBeingConfigured = null
        val activity = NativeLibrary.sEmulationActivity.get() ?: return@Runnable
        OverlayThemeDialog.show(activity, target) { refreshControls() }
    }

    private val longPressHandler = Handler(Looper.getMainLooper())
    private var longPressTarget: Any? = null
    private var longPressDownX = 0f
    private var longPressDownY = 0f
    private val longPressRunnable = Runnable {
        val target = longPressTarget ?: return@Runnable
        longPressTarget = null
        buttonBeingConfigured = null
        dpadBeingConfigured = null
        joystickBeingConfigured = null
        val activity = NativeLibrary.sEmulationActivity.get() ?: return@Runnable
        OverlayThemeDialog.show(activity, target) { refreshControls() }
    }
    private val settingsViewModel = NativeLibrary.sEmulationActivity.get()!!.settingsViewModel

    // Stores the ID of the pointer that interacted with the 3DS touchscreen.
    private var touchscreenPointerId = -1

    init {
        if (!preferences.getBoolean("OverlayInit", false)) {
            defaultOverlay()
        }

        // Reset 3ds touchscreen pointer ID
        touchscreenPointerId = -1

        // Load the controls.
        refreshControls()

        // Set the on touch listener.
        setOnTouchListener(this)

        // Force draw
        setWillNotDraw(false)

        // Request focus for the overlay so it has priority on presses.
        requestFocus()
    }

    override fun draw(canvas: Canvas) {
        super.draw(canvas)
        overlayButtons.forEach { it.draw(canvas) }
        overlayDpads.forEach { it.draw(canvas) }
        overlayJoysticks.forEach { it.draw(canvas) }
    }

    private fun swapScreen() {
        val isEnabled = !EmulationMenuSettings.swapScreens
        EmulationMenuSettings.swapScreens = isEnabled
        val displayRotation = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            context.display.rotation
        } else {
            @Suppress("DEPRECATION")
            (context as Activity).windowManager.defaultDisplay.rotation
        }
        NativeLibrary.swapScreens(
            isEnabled,
            displayRotation
        )
    }

    fun hapticFeedback(type: Int) {
        if (EmulationMenuSettings.hapticFeedback) {
            performHapticFeedback(type)
        }
    }

    /**
     * Precise hit test for a finger that just landed at (x, y).
     *
     * A button reacts only where its icon really is (its visible shape, not the square around it).
     * A finger on one icon presses that button. A finger where two or more icons overlap presses
     * every button whose icon is under the finger, and they stay held until the finger lifts.
     *
     * @return 0 if [button] is not hit, otherwise how many buttons this touch presses together
     *         (1 = a normal single press, 2+ = a multi-press that stays held until release).
     */
    fun buttonTouchGroupSize(button: InputOverlayDrawableButton, x: Int, y: Int): Int {
        if (!button.containsPoint(x, y)) {
            return 0
        }
        return overlayButtons.count { it.containsPoint(x, y) }
    }

    override fun onTouch(v: View, event: MotionEvent): Boolean {
        if (isInEditMode) {
            return onTouchWhileEditing(event)
        }

        val motionEvent = event.action and MotionEvent.ACTION_MASK
        val isActionDown =
            motionEvent == MotionEvent.ACTION_DOWN || motionEvent == MotionEvent.ACTION_POINTER_DOWN
        val isActionMove = motionEvent == MotionEvent.ACTION_MOVE
        val isActionUp =
            motionEvent == MotionEvent.ACTION_UP || motionEvent == MotionEvent.ACTION_POINTER_UP

        val pointerList = (0 until event.pointerCount).toMutableList()
        // Move the pointer that triggered the most recent event to the front
        // of the list so that it is processed first
        val currentActionPointer = event.actionIndex
        pointerList.remove(pointerList.indexOf(currentActionPointer))
        pointerList.add(0, currentActionPointer)

        // Set up a loop for if we need to check touches other than the most recent one
        // (Only happens if we're dragging the touch)
        for (pointerIndex in pointerList) {
            val pointerId = event.getPointerId(pointerIndex)

            var xPosition = event.getX(pointerIndex).toInt()
            var yPosition = event.getY(pointerIndex).toInt()

            if (BooleanSetting.EXPAND_TO_CUTOUT_AREA.boolean) {
                val cutout = ViewCompat.getRootWindowInsets(this)?.displayCutout
                val marginsX = (cutout?.safeInsetLeft?.plus(cutout.safeInsetRight)) ?: 0
                val marginsY = (cutout?.safeInsetTop?.plus(cutout.safeInsetBottom)) ?: 0
                xPosition += marginsX
                yPosition += marginsY
            }

            // Which controls are already tracking this finger. These are computed once, before any
            // control had a chance to claim the finger. So on ACTION_DOWN (nothing tracks it yet)
            // a finger landing where e.g. a joystick and a button overlap is offered to both and
            // presses both. Afterwards each control that owns the finger keeps receiving its
            // MOVE/UP events, so none of them can get stuck.
            val hasActiveButtons = overlayButtons.any { it.trackId == pointerId }
            val hasActiveDpad = overlayDpads.any { it.trackId == pointerId }
            val hasActiveJoystick = overlayJoysticks.any { it.trackId == pointerId }

            val hasActiveOverlay = hasActiveButtons || hasActiveDpad || hasActiveJoystick

            if (preferences.getBoolean("isTouchEnabled", true) && !hasActiveOverlay) {
                if (isActionMove) {
                    NativeLibrary.onTouchMoved(xPosition.toFloat(), yPosition.toFloat())
                    continue
                } else if (isActionUp) {
                    NativeLibrary.onTouchEvent(0f, 0f, false)
                    break // Up and down actions shouldn't loop
                }
            }

            var anyOverlayStateChanged = false
            var shouldUpdateView = false
            // A finger that only drives a dpad/joystick must not slide into buttons, but a finger
            // that also owns a button (overlap press) must keep updating it.
            if (hasActiveButtons || (!hasActiveDpad && !hasActiveJoystick)) {
                for (button in overlayButtons) {
                    val stateChanged = button.updateStatus(
                        event,
                        pointerIndex,
                        hasActiveButtons,
                        this
                    )
                    if (!stateChanged) {
                        continue
                    }
                    anyOverlayStateChanged = true

                    if (button.id == NativeLibrary.ButtonType.BUTTON_SWAP &&
                        button.status == NativeLibrary.ButtonState.PRESSED
                    ) {
                        swapScreen()
                    } else if (button.id == NativeLibrary.ButtonType.BUTTON_TURBO &&
                        button.status == NativeLibrary.ButtonState.PRESSED
                    ) {
                        TurboHelper.toggleTurbo(true)
                    } else if (button.id >= Hotkey.COMBO_BUTTON.button &&
                        button.id < Hotkey.COMBO_BUTTON.button + ComboHelper.COMBO_COUNT
                    ) {
                        ComboHelper.comboActivate(
                            button.status,
                            button.id - Hotkey.COMBO_BUTTON.button
                        )
                    }

                    NativeLibrary.onGamePadEvent(
                        NativeLibrary.TOUCHSCREEN_DEVICE,
                        button.id,
                        button.status
                    )

                    shouldUpdateView = true
                }
            }

            if (hasActiveDpad || (!hasActiveButtons && !hasActiveJoystick)) {
                for (dpad in overlayDpads) {
                    val stateChanged = dpad.updateStatus(
                        event,
                        pointerIndex,
                        hasActiveDpad,
                        EmulationMenuSettings.dpadSlide,
                        this
                    )
                    if (!stateChanged) {
                        continue
                    }
                    anyOverlayStateChanged = true

                    NativeLibrary.onGamePadEvent(
                        NativeLibrary.TOUCHSCREEN_DEVICE,
                        dpad.upId,
                        dpad.upStatus
                    )
                    NativeLibrary.onGamePadEvent(
                        NativeLibrary.TOUCHSCREEN_DEVICE,
                        dpad.downId,
                        dpad.downStatus
                    )
                    NativeLibrary.onGamePadEvent(
                        NativeLibrary.TOUCHSCREEN_DEVICE,
                        dpad.leftId,
                        dpad.leftStatus
                    )
                    NativeLibrary.onGamePadEvent(
                        NativeLibrary.TOUCHSCREEN_DEVICE,
                        dpad.rightId,
                        dpad.rightStatus
                    )

                    shouldUpdateView = true
                }
            }

            if (hasActiveJoystick || (!hasActiveButtons && !hasActiveDpad)) {
                for (joystick in overlayJoysticks) {
                    val stateChanged = joystick.updateStatus(
                        event,
                        pointerIndex,
                        hasActiveJoystick,
                        this
                    )
                    if (!stateChanged) {
                        continue
                    }
                    anyOverlayStateChanged = true

                    val axisID = joystick.joystickId
                    NativeLibrary.onGamePadMoveEvent(
                        NativeLibrary.TOUCHSCREEN_DEVICE,
                        axisID,
                        joystick.xAxis,
                        joystick.yAxis
                    )

                    shouldUpdateView = true
                }
            }

            if (shouldUpdateView) {
                invalidate()
            }

            if (preferences.getBoolean("isTouchEnabled", true) &&
                isActionDown &&
                !anyOverlayStateChanged
            ) {
                // These need to be recalculated because touching the area
                // right in the middle of the dpad (between the "buttons") or
                // tapping a joystick in a certain way both don't cause
                // `anyOverlayStateChanged` to be set to true
                var isDpadPressed = false
                for (dpad in overlayDpads) {
                    if (dpad.trackId == pointerId) {
                        isDpadPressed = true
                        break
                    }
                }
                var isJoystickPressed = false
                for (joystick in overlayJoysticks) {
                    if (joystick.trackId == pointerId) {
                        isJoystickPressed = true
                        break
                    }
                }

                if (!isDpadPressed && !isJoystickPressed) {
                    NativeLibrary.onTouchEvent(xPosition.toFloat(), yPosition.toFloat(), true)
                }
            }

            // We should only loop here if touch is being dragged
            if (!isActionMove) {
                break
            }
        }
        return true
    }

    private fun findControlAt(x: Int, y: Int): Any? =
        overlayButtons.firstOrNull { it.bounds.contains(x, y) }
            ?: overlayDpads.firstOrNull { it.bounds.contains(x, y) }
            ?: overlayJoysticks.firstOrNull { it.bounds.contains(x, y) }

    private fun cancelLongPress() {
        longPressHandler.removeCallbacks(longPressRunnable)
        longPressTarget = null
    }

    private fun findControlAt(x: Int, y: Int): Any? =
        overlayButtons.firstOrNull { it.bounds.contains(x, y) }
            ?: overlayDpads.firstOrNull { it.bounds.contains(x, y) }
            ?: overlayJoysticks.firstOrNull { it.bounds.contains(x, y) }

    private fun cancelThemeLongPress() {
        longPressHandler.removeCallbacks(longPressRunnable)
        longPressTarget = null
    }

    fun onTouchWhileEditing(event: MotionEvent): Boolean {
        val pointerIndex = event.actionIndex
        val fingerPositionX = event.getX(pointerIndex).toInt()
        val fingerPositionY = event.getY(pointerIndex).toInt()
        val orientation =
            if (resources.configuration.orientation ==
                Configuration.ORIENTATION_PORTRAIT
            ) {
                "-Portrait"
            } else {
                ""
            }

        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                longPressDownX = event.x
                longPressDownY = event.y
                longPressTarget = findControlAt(fingerPositionX, fingerPositionY)
                if (longPressTarget != null) {
                    longPressHandler.postDelayed(
                        longPressRunnable,
                        ViewConfiguration.getLongPressTimeout().toLong()
                    )
                }
            }

            MotionEvent.ACTION_MOVE -> if (longPressTarget != null &&
                hypot(event.x - longPressDownX, event.y - longPressDownY) >
                ViewConfiguration.get(context).scaledTouchSlop
            ) {
                cancelLongPress()
            }

            MotionEvent.ACTION_UP,
            MotionEvent.ACTION_CANCEL,
            MotionEvent.ACTION_POINTER_DOWN -> cancelLongPress()
        }

        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                longPressDownX = event.x
                longPressDownY = event.y
                longPressTarget = findControlAt(fingerPositionX, fingerPositionY)
                if (longPressTarget != null) {
                    longPressHandler.postDelayed(
                        longPressRunnable,
                        ViewConfiguration.getLongPressTimeout().toLong()
                    )
                }
            }

            MotionEvent.ACTION_MOVE -> if (longPressTarget != null &&
                hypot(event.x - longPressDownX, event.y - longPressDownY) >
                ViewConfiguration.get(context).scaledTouchSlop
            ) {
                cancelThemeLongPress()
            }

            MotionEvent.ACTION_UP,
            MotionEvent.ACTION_CANCEL,
            MotionEvent.ACTION_POINTER_DOWN -> cancelThemeLongPress()
        }

        // Maybe combine Button and Joystick as subclasses of the same parent?
        // Or maybe create an interface like IMoveableHUDControl?
        overlayButtons.forEach {
            // Determine the button state to apply based on the MotionEvent action flag.
            when (event.action and MotionEvent.ACTION_MASK) {
                MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN ->
                    // If no button is being moved now, remember the currently touched button to move.
                    if (buttonBeingConfigured == null &&
                        it.bounds.contains(fingerPositionX, fingerPositionY)
                    ) {
                        buttonBeingConfigured = it
                        buttonBeingConfigured!!.onConfigureTouch(event)
                    }

                MotionEvent.ACTION_MOVE -> if (buttonBeingConfigured != null) {
                    buttonBeingConfigured!!.onConfigureTouch(event)
                    invalidate()
                    return true
                }

                MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP -> if (buttonBeingConfigured ==
                    it
                ) {
                    // Persist button position by saving new place.
                    saveControlPosition(
                        buttonBeingConfigured!!.id,
                        buttonBeingConfigured!!.bounds.left,
                        buttonBeingConfigured!!.bounds.top,
                        orientation
                    )
                    buttonBeingConfigured = null
                }
            }
        }
        overlayDpads.forEach {
            // Determine the button state to apply based on the MotionEvent action flag.
            when (event.action and MotionEvent.ACTION_MASK) {
                MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN ->
                    // If no button is being moved now, remember the currently touched button to move.
                    if (buttonBeingConfigured == null &&
                        it.bounds.contains(fingerPositionX, fingerPositionY)
                    ) {
                        dpadBeingConfigured = it
                        dpadBeingConfigured!!.onConfigureTouch(event)
                    }

                MotionEvent.ACTION_MOVE -> if (dpadBeingConfigured != null) {
                    dpadBeingConfigured!!.onConfigureTouch(event)
                    invalidate()
                    return true
                }

                MotionEvent.ACTION_UP,
                MotionEvent.ACTION_POINTER_UP -> if (dpadBeingConfigured == it) {
                    // Persist button position by saving new place.
                    saveControlPosition(
                        dpadBeingConfigured!!.upId,
                        dpadBeingConfigured!!.bounds.left,
                        dpadBeingConfigured!!.bounds.top,
                        orientation
                    )
                    dpadBeingConfigured = null
                }
            }
        }
        overlayJoysticks.forEach {
            when (event.action) {
                MotionEvent.ACTION_DOWN,
                MotionEvent.ACTION_POINTER_DOWN -> if (joystickBeingConfigured == null &&
                    it.bounds.contains(fingerPositionX, fingerPositionY)
                ) {
                    joystickBeingConfigured = it
                    joystickBeingConfigured!!.onConfigureTouch(event)
                }

                MotionEvent.ACTION_MOVE -> if (joystickBeingConfigured != null) {
                    joystickBeingConfigured!!.onConfigureTouch(event)
                    invalidate()
                }

                MotionEvent.ACTION_UP,
                MotionEvent.ACTION_POINTER_UP -> if (joystickBeingConfigured != null) {
                    saveControlPosition(
                        joystickBeingConfigured!!.joystickId,
                        joystickBeingConfigured!!.bounds.left,
                        joystickBeingConfigured!!.bounds.top,
                        orientation
                    )
                    joystickBeingConfigured = null
                }
            }
        }
        return true
    }

    private fun addOverlayControls(orientation: String) {
        OverlayTheme.refresh()
        OverlayTheme.refresh()
        if (preferences.getBoolean("buttonToggle0", true)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_a,
                    R.drawable.button_a_pressed,
                    NativeLibrary.ButtonType.BUTTON_A,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle1", true)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_b,
                    R.drawable.button_b_pressed,
                    NativeLibrary.ButtonType.BUTTON_B,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle2", true)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_x,
                    R.drawable.button_x_pressed,
                    NativeLibrary.ButtonType.BUTTON_X,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle3", true)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_y,
                    R.drawable.button_y_pressed,
                    NativeLibrary.ButtonType.BUTTON_Y,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle4", true)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_l,
                    R.drawable.button_l_pressed,
                    NativeLibrary.ButtonType.TRIGGER_L,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle5", true)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_r,
                    R.drawable.button_r_pressed,
                    NativeLibrary.ButtonType.TRIGGER_R,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle6", false)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_zl,
                    R.drawable.button_zl_pressed,
                    NativeLibrary.ButtonType.BUTTON_ZL,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle7", false)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_zr,
                    R.drawable.button_zr_pressed,
                    NativeLibrary.ButtonType.BUTTON_ZR,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle8", true)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_start,
                    R.drawable.button_start_pressed,
                    NativeLibrary.ButtonType.BUTTON_START,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle9", true)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_select,
                    R.drawable.button_select_pressed,
                    NativeLibrary.ButtonType.BUTTON_SELECT,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle10", true)) {
            overlayDpads.add(
                initializeOverlayDpad(
                    context,
                    R.drawable.dpad,
                    R.drawable.dpad_pressed_one_direction,
                    R.drawable.dpad_pressed_two_directions,
                    NativeLibrary.ButtonType.DPAD_UP,
                    NativeLibrary.ButtonType.DPAD_DOWN,
                    NativeLibrary.ButtonType.DPAD_LEFT,
                    NativeLibrary.ButtonType.DPAD_RIGHT,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle11", true)) {
            overlayJoysticks.add(
                initializeOverlayJoystick(
                    context,
                    R.drawable.stick_main_range,
                    R.drawable.stick_main,
                    R.drawable.stick_main_pressed,
                    NativeLibrary.ButtonType.STICK_LEFT,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle12", false)) {
            overlayJoysticks.add(
                initializeOverlayJoystick(
                    context,
                    R.drawable.stick_c_range,
                    R.drawable.stick_c,
                    R.drawable.stick_c_pressed,
                    NativeLibrary.ButtonType.STICK_C,
                    orientation
                )
            )
        }
        if (preferences.getBoolean("buttonToggle13", false)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_home,
                    R.drawable.button_home_pressed,
                    NativeLibrary.ButtonType.BUTTON_HOME,
                    orientation
                )
            )
        }

        if (preferences.getBoolean("buttonToggle14", false)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_swap,
                    R.drawable.button_swap_pressed,
                    NativeLibrary.ButtonType.BUTTON_SWAP,
                    orientation
                )
            )
        }

        if (preferences.getBoolean("buttonToggle15", false)) {
            overlayButtons.add(
                initializeOverlayButton(
                    context,
                    R.drawable.button_turbo,
                    R.drawable.button_turbo_pressed,
                    NativeLibrary.ButtonType.BUTTON_TURBO,
                    orientation
                )
            )
        }

        // Combo buttons: 5 independent buttons, IDs Hotkey.COMBO_BUTTON.button + 0..4,
        // toggled by buttonToggle16..20 in the shared preferences.
        for (comboIndex in 0 until ComboHelper.COMBO_COUNT) {
            if (preferences.getBoolean("buttonToggle${16 + comboIndex}", false)) {
                if (comboIndex > 0) ensureComboDefaultPosition(comboIndex, orientation)
                overlayButtons.add(
                    initializeOverlayButton(
                        context,
                        COMBO_DRAWABLES[comboIndex],
                        COMBO_DRAWABLES_PRESSED[comboIndex],
                        Hotkey.COMBO_BUTTON.button + comboIndex,
                        orientation
                    )
                )
            }
        }
    }

    /**
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

    fun refreshControls() {
        // Remove all the overlay buttons from the HashSet.
        overlayButtons.clear()
        overlayDpads.clear()
        overlayJoysticks.clear()
        val orientation =
            if (resources.configuration.orientation == Configuration.ORIENTATION_PORTRAIT) {
                "-Portrait"
            } else {
                ""
            }

        // Add all the enabled overlay items back to the HashSet.
        if (EmulationMenuSettings.showOverlay) {
            addOverlayControls(orientation)
        }
        invalidate()
    }

    private fun saveControlPosition(sharedPrefsId: Int, x: Int, y: Int, orientation: String) {
        preferences.edit()
            .putFloat("$sharedPrefsId$orientation-X", x.toFloat())
            .putFloat("$sharedPrefsId$orientation-Y", y.toFloat())
            .apply()
    }

    fun setIsInEditMode(isInEditMode: Boolean) {
        this.isInEditMode = isInEditMode
    }

    private fun defaultOverlay() {
        if (!preferences.getBoolean("OverlayInit", false)) {
            // It's possible that a user has created their overlay before this was added
            // Only change the overlay if the 'A' button is not in the upper corner.
            val aButtonPosition = preferences.getFloat(
                NativeLibrary.ButtonType.BUTTON_A.toString() + "-X",
                0f
            )
            if (aButtonPosition == 0f) {
                defaultOverlayLandscape()
            }

            val aButtonPositionPortrait = preferences.getFloat(
                NativeLibrary.ButtonType.BUTTON_A.toString() + "-Portrait" + "-X",
                0f
            )
            if (aButtonPositionPortrait == 0f) {
                defaultOverlayPortrait()
            }
        }

        preferences.edit()
            .putBoolean("OverlayInit", true)
            .apply()
    }

    fun resetButtonPlacement() {
        val isLandscape = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
        if (isLandscape) {
            defaultOverlayLandscape()
        } else {
            defaultOverlayPortrait()
        }
        refreshControls()
    }

    private fun defaultOverlayLandscape() {
        // Get screen size
        val display = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            context.display
        } else {
            @Suppress("DEPRECATION")
            (context as Activity).windowManager.defaultDisplay
        }
        var displayWidth: Float
        var displayHeight: Float
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val displayMetrics = (context as Activity).windowManager.maximumWindowMetrics.bounds
            displayWidth = displayMetrics.width().toFloat()
            displayHeight = displayMetrics.height().toFloat()
        } else {
            val displayMetrics = DisplayMetrics()
            @Suppress("DEPRECATION")
            display.getMetrics(displayMetrics)
            displayWidth = displayMetrics.widthPixels.toFloat()
            displayHeight = displayMetrics.heightPixels.toFloat()
        }
        val cutout = ViewCompat.getRootWindowInsets(this)?.displayCutout
        val marginsX = (cutout?.safeInsetLeft?.plus(cutout.safeInsetRight)) ?: 0
        val marginsY = (cutout?.safeInsetTop?.plus(cutout.safeInsetBottom)) ?: 0
        var maxX = displayWidth - marginsX
        var maxY = displayHeight - marginsY
        // Height and width changes depending on orientation. Use the larger value for height.
        if (maxY > maxX) {
            val tmp = maxX
            maxX = maxY
            maxY = tmp
        }

        // Each value is a percent from max X/Y stored as an int. Have to bring that value down
        // to a decimal before multiplying by MAX X/Y.
        preferences.edit()
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_A.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_A_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_A.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_A_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_B.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_B_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_B.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_B_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_X.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_X_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_X.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_X_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_Y.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_Y_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_Y.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_Y_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_ZL.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_ZL_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_ZL.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_ZL_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_ZR.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_ZR_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_ZR.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_ZR_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.DPAD_UP.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_UP_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.DPAD_UP.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_UP_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.TRIGGER_L.toString() + "-X",
                resources.getInteger(R.integer.N3DS_TRIGGER_L_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.TRIGGER_L.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_TRIGGER_L_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.TRIGGER_R.toString() + "-X",
                resources.getInteger(R.integer.N3DS_TRIGGER_R_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.TRIGGER_R.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_TRIGGER_R_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_START.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_START_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_START.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_START_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_SELECT.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_SELECT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_SELECT.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_SELECT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_HOME.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_HOME_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_HOME.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_HOME_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.STICK_C.toString() + "-X",
                resources.getInteger(R.integer.N3DS_STICK_C_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.STICK_C.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_STICK_C_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.STICK_LEFT.toString() + "-X",
                resources.getInteger(R.integer.N3DS_STICK_MAIN_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.STICK_LEFT.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_STICK_MAIN_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_SWAP.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_SWAP_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_SWAP.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_SWAP_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_TURBO.toString() + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_TURBO_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_TURBO.toString() + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_TURBO_Y).toFloat() / 1000 * maxY
            )
            .apply()

        // COMBO_DEFAULTS: combo 1..5 in a row (1 on the left) at the top centre, above the screen.
        // Spacing is 11% of the height so the buttons touch without overlapping.
        val comboEditor = preferences.edit()
        val comboStepLandscape = 0.11f * maxY
        for (i in 0 until ComboHelper.COMBO_COUNT) {
            val id = Hotkey.COMBO_BUTTON.button + i
            comboEditor
                .putFloat(
                    id.toString() + "-X",
                    resources.getInteger(R.integer.N3DS_BUTTON_COMBO_X).toFloat() / 1000 * maxX +
                        i * comboStepLandscape
                )
                .putFloat(
                    id.toString() + "-Y",
                    resources.getInteger(R.integer.N3DS_BUTTON_COMBO_Y).toFloat() / 1000 * maxY
                )
        }
        comboEditor.apply()
    }

    private fun defaultOverlayPortrait() {
        // Get screen size
        val display = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            context.display
        } else {
            @Suppress("DEPRECATION")
            (context as Activity).windowManager.defaultDisplay
        }
        var displayWidth: Float
        var displayHeight: Float
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val displayMetrics = (context as Activity).windowManager.maximumWindowMetrics.bounds
            displayWidth = displayMetrics.width().toFloat()
            displayHeight = displayMetrics.height().toFloat()
        } else {
            val displayMetrics = DisplayMetrics()
            @Suppress("DEPRECATION")
            display.getMetrics(displayMetrics)
            displayWidth = displayMetrics.widthPixels.toFloat()
            displayHeight = displayMetrics.heightPixels.toFloat()
        }
        val cutout = ViewCompat.getRootWindowInsets(this)?.displayCutout
        val marginsX = (cutout?.safeInsetLeft?.plus(cutout.safeInsetRight)) ?: 0
        val marginsY = (cutout?.safeInsetTop?.plus(cutout.safeInsetBottom)) ?: 0
        var maxX = displayWidth - marginsX
        var maxY = displayHeight - marginsY
        // Height and width changes depending on orientation. Use the larger value for height.
        if (maxY < maxX) {
            val tmp = maxX
            maxX = maxY
            maxY = tmp
        }
        val portrait = "-Portrait"

        // Each value is a percent from max X/Y stored as an int. Have to bring that value down
        // to a decimal before multiplying by MAX X/Y.
        preferences.edit()
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_A.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_A_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_A.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_A_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_B.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_B_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_B.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_B_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_X.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_X_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_X.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_X_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_Y.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_Y_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_Y.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_Y_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_ZL.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_ZL_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_ZL.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_ZL_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_ZR.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_ZR_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_ZR.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_ZR_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.DPAD_UP.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_UP_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.DPAD_UP.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_UP_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.TRIGGER_L.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_TRIGGER_L_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.TRIGGER_L.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_TRIGGER_L_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.TRIGGER_R.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_TRIGGER_R_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.TRIGGER_R.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_TRIGGER_R_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_START.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_START_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_START.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_START_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_SELECT.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_SELECT_PORTRAIT_X)
                    .toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_SELECT.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_SELECT_PORTRAIT_Y)
                    .toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_HOME.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_HOME_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_HOME.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_HOME_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.STICK_C.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_STICK_C_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.STICK_C.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_STICK_C_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.STICK_LEFT.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_STICK_MAIN_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.STICK_LEFT.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_STICK_MAIN_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_SWAP.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_SWAP_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_SWAP.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_SWAP_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_TURBO.toString() + portrait + "-X",
                resources.getInteger(R.integer.N3DS_BUTTON_TURBO_PORTRAIT_X).toFloat() / 1000 * maxX
            )
            .putFloat(
                NativeLibrary.ButtonType.BUTTON_TURBO.toString() + portrait + "-Y",
                resources.getInteger(R.integer.N3DS_BUTTON_TURBO_PORTRAIT_Y).toFloat() / 1000 * maxY
            )
            .apply()

        // COMBO_DEFAULTS: combo 1..5 in a row (1 on the left) just above L, ZL, ZR and R.
        // Spacing is 11% of the width so the buttons touch without overlapping.
        val comboEditor = preferences.edit()
        val comboStep = 0.11f * maxX
        for (i in 0 until ComboHelper.COMBO_COUNT) {
            val id = Hotkey.COMBO_BUTTON.button + i
            comboEditor
                .putFloat(
                    id.toString() + portrait + "-X",
                    resources.getInteger(R.integer.N3DS_BUTTON_COMBO_PORTRAIT_X).toFloat() / 1000 * maxX +
                        i * comboStep
                )
                .putFloat(
                    id.toString() + portrait + "-Y",
                    resources.getInteger(R.integer.N3DS_BUTTON_COMBO_PORTRAIT_Y).toFloat() / 1000 * maxY
                )
        }
        comboEditor.apply()
    }

    override fun isInEditMode(): Boolean = isInEditMode

    companion object {
        // Must live here (not as instance properties declared after init {}), otherwise they
        // are still null when init calls refreshControls().
        private val COMBO_DRAWABLES = intArrayOf(
            R.drawable.button_combo_1, R.drawable.button_combo_2, R.drawable.button_combo_3,
            R.drawable.button_combo_4, R.drawable.button_combo_5
        )
        private val COMBO_DRAWABLES_PRESSED = intArrayOf(
            R.drawable.button_combo_1_pressed, R.drawable.button_combo_2_pressed,
            R.drawable.button_combo_3_pressed, R.drawable.button_combo_4_pressed,
            R.drawable.button_combo_5_pressed
        )

        private val preferences
            get() = OverlayProfile.prefs()

        /**
         * Resizes a [Bitmap] by a given scale factor
         *
         * @param context       Context for getting the drawable/vector drawable
         * @param drawableId    The ID of the drawable to scale.
         * @param scale         The scale factor for the bitmap.
         * @return The scaled [Bitmap]
         */
        private fun getBitmap(context: Context, drawableId: Int, scale: Float): Bitmap {
            OverlayTheme.loadBitmap(context, drawableId)?.let {
                return resizeBitmap(context, it, scale)
            }
            OverlayTheme.loadBitmap(context, drawableId)?.let {
                return resizeBitmap(context, it, scale)
            }
            try {
                val bitmap = BitmapFactory.decodeResource(context.resources, drawableId)
                return resizeBitmap(context, bitmap, scale)
            } catch (_: NullPointerException) {
            }

            val vectorDrawable = ContextCompat.getDrawable(context, drawableId) as VectorDrawable

            val bitmap = Bitmap.createBitmap(
                (vectorDrawable.intrinsicWidth * scale).toInt(),
                (vectorDrawable.intrinsicHeight * scale).toInt(),
                Bitmap.Config.ARGB_8888
            )

            val scaledBitmap = resizeBitmap(context, bitmap, scale)
            val canvas = Canvas(scaledBitmap)
            vectorDrawable.setBounds(0, 0, canvas.width, canvas.height)
            vectorDrawable.draw(canvas)
            return scaledBitmap
        }

        /**
         * Resizes a [Bitmap] by a given scale factor
         *
         * @param context The current [Context]
         * @param bitmap  The [Bitmap] to scale.
         * @param scale   The scale factor for the bitmap.
         * @return The scaled [Bitmap]
         */
        private fun resizeBitmap(context: Context, bitmap: Bitmap, scale: Float): Bitmap {
            // Determine the button size based on the smaller screen dimension.
            // This makes sure the buttons are the same size in both portrait and landscape.
            val dm = context.resources.displayMetrics
            val minDimension = min(dm.widthPixels, dm.heightPixels)
            return Bitmap.createScaledBitmap(
                bitmap,
                (minDimension * scale).toInt(),
                (minDimension * scale).toInt(),
                true
            )
        }

        /**
         * Initializes an InputOverlayDrawableButton, given by resId, with all of the
         * parameters set for it to be properly shown on the InputOverlay.
         *
         *
         * This works due to the way the X and Y coordinates are stored within
         * the [SharedPreferences].
         *
         *
         * In the input overlay configuration menu,
         * once a touch event begins and then ends (ie. Organizing the buttons to one's own liking for the overlay).
         * the X and Y coordinates of the button at the END of its touch event
         * (when you remove your finger/stylus from the touchscreen) are then stored
         * within a SharedPreferences instance so that those values can be retrieved here.
         *
         *
         * This has a few benefits over the conventional way of storing the values
         * (ie. within the Citra ini file).
         *
         *  * No native calls
         *  * Keeps Android-only values inside the Android environment
         *
         *
         *
         * Technically no modifications should need to be performed on the returned
         * InputOverlayDrawableButton. Simply add it to the HashSet of overlay items and wait
         * for Android to call the onDraw method.
         *
         * @param context      The current [Context].
         * @param defaultResId The resource ID of the [Drawable] to get the [Bitmap] of (Default State).
         * @param pressedResId The resource ID of the [Drawable] to get the [Bitmap] of (Pressed State).
         * @param buttonId     Identifier for determining what type of button the initialized InputOverlayDrawableButton represents.
         * @return An [InputOverlayDrawableButton] with the correct drawing bounds set.
         */
        private fun initializeOverlayButton(
            context: Context,
            defaultResId: Int,
            pressedResId: Int,
            buttonId: Int,
            orientation: String
        ): InputOverlayDrawableButton {
            // Resources handle for fetching the initial Drawable resource.
            val res = context.resources

            // Decide scale based on button ID and user preference
            var scale: Float = when (buttonId) {
                NativeLibrary.ButtonType.BUTTON_HOME,
                NativeLibrary.ButtonType.BUTTON_START,
                NativeLibrary.ButtonType.BUTTON_SELECT,
                NativeLibrary.ButtonType.BUTTON_SWAP -> 0.08f

                NativeLibrary.ButtonType.BUTTON_TURBO -> 0.10f

                NativeLibrary.ButtonType.TRIGGER_L,
                NativeLibrary.ButtonType.TRIGGER_R,
                NativeLibrary.ButtonType.BUTTON_ZL,
                NativeLibrary.ButtonType.BUTTON_ZR -> 0.18f

                else -> 0.11f
            }
            scale *= (preferences.getInt("controlScale", 50) + 50).toFloat()
            scale /= 100f

            scale *= (preferences.getInt("controlScale-$buttonId", 50) + 50).toFloat()
            scale /= 100f

            val opacity: Int = preferences.getInt("controlOpacity", 50) * 255 / 100

            // Initialize the InputOverlayDrawableButton.
            val defaultStateBitmap = getBitmap(context, defaultResId, scale)
            val pressedStateBitmap = getBitmap(context, pressedResId, scale)
            val overlayDrawable =
                InputOverlayDrawableButton(
                    res,
                    defaultStateBitmap,
                    pressedStateBitmap,
                    buttonId,
                    opacity
                )

            // The X and Y coordinates of the InputOverlayDrawableButton on the InputOverlay.
            // These were set in the input overlay configuration menu.
            val xKey = "$buttonId$orientation-X"
            val yKey = "$buttonId$orientation-Y"
            val drawableX = preferences.getFloat(xKey, 0f).toInt()
            val drawableY = preferences.getFloat(yKey, 0f).toInt()
            val width = overlayDrawable.width
            val height = overlayDrawable.height

            // Now set the bounds for the InputOverlayDrawableButton.
            // This will dictate where on the screen (and the what the size) the InputOverlayDrawableButton will be.
            overlayDrawable.setBounds(drawableX, drawableY, drawableX + width, drawableY + height)

            // Need to set the image's position
            overlayDrawable.setPosition(drawableX, drawableY)
            OverlayTheme.register(
                overlayDrawable,
                listOf(
                    defaultResId to R.string.overlay_theme_image_normal,
                    pressedResId to R.string.overlay_theme_image_pressed
                )
            )
            OverlayTheme.register(
                overlayDrawable,
                listOf(
                    defaultResId to R.string.overlay_theme_image_normal,
                    pressedResId to R.string.overlay_theme_image_pressed
                )
            )
            return overlayDrawable
        }

        /**
         * Initializes an [InputOverlayDrawableDpad]
         *
         * @param context                   The current [Context].
         * @param defaultResId              The [Bitmap] resource ID of the default sate.
         * @param pressedOneDirectionResId  The [Bitmap] resource ID of the pressed sate in one direction.
         * @param pressedTwoDirectionsResId The [Bitmap] resource ID of the pressed sate in two directions.
         * @param buttonUp                  Identifier for the up button.
         * @param buttonDown                Identifier for the down button.
         * @param buttonLeft                Identifier for the left button.
         * @param buttonRight               Identifier for the right button.
         * @return the initialized [InputOverlayDrawableDpad]
         */
        private fun initializeOverlayDpad(
            context: Context,
            defaultResId: Int,
            pressedOneDirectionResId: Int,
            pressedTwoDirectionsResId: Int,
            buttonUp: Int,
            buttonDown: Int,
            buttonLeft: Int,
            buttonRight: Int,
            orientation: String
        ): InputOverlayDrawableDpad {
            // Resources handle for fetching the initial Drawable resource.
            val res = context.resources

            // Decide scale based on button ID and user preference
            var scale = 0.22f
            scale *= (preferences.getInt("controlScale", 50) + 50).toFloat()
            scale /= 100f

            scale *= (
                preferences.getInt(
                    "controlScale-" + NativeLibrary.ButtonType.DPAD,
                    50
                ) + 50
                ).toFloat()

            scale /= 100f

            val opacity: Int = preferences.getInt("controlOpacity", 50) * 255 / 100

            // Initialize the InputOverlayDrawableDpad.
            val defaultStateBitmap = getBitmap(context, defaultResId, scale)
            val pressedOneDirectionStateBitmap = getBitmap(context, pressedOneDirectionResId, scale)
            val pressedTwoDirectionsStateBitmap =
                getBitmap(context, pressedTwoDirectionsResId, scale)
            val overlayDrawable = InputOverlayDrawableDpad(
                res,
                defaultStateBitmap,
                pressedOneDirectionStateBitmap,
                pressedTwoDirectionsStateBitmap,
                buttonUp,
                buttonDown,
                buttonLeft,
                buttonRight,
                opacity
            )

            // The X and Y coordinates of the InputOverlayDrawableDpad on the InputOverlay.
            // These were set in the input overlay configuration menu.
            val drawableX = preferences.getFloat("$buttonUp$orientation-X", 0f).toInt()
            val drawableY = preferences.getFloat("$buttonUp$orientation-Y", 0f).toInt()
            val width = overlayDrawable.width
            val height = overlayDrawable.height

            // Now set the bounds for the InputOverlayDrawableDpad.
            // This will dictate where on the screen (and the what the size) the InputOverlayDrawableDpad will be.
            overlayDrawable.setBounds(drawableX, drawableY, drawableX + width, drawableY + height)

            // Need to set the image's position
            overlayDrawable.setPosition(drawableX, drawableY)
            OverlayTheme.register(
                overlayDrawable,
                listOf(
                    defaultResId to R.string.overlay_theme_image_normal,
                    pressedOneDirectionResId to R.string.overlay_theme_image_dpad_one,
                    pressedTwoDirectionsResId to R.string.overlay_theme_image_dpad_two
                )
            )
            OverlayTheme.register(
                overlayDrawable,
                listOf(
                    defaultResId to R.string.overlay_theme_image_normal,
                    pressedOneDirectionResId to R.string.overlay_theme_image_dpad_one,
                    pressedTwoDirectionsResId to R.string.overlay_theme_image_dpad_two
                )
            )
            return overlayDrawable
        }

        /**
         * Initializes an [InputOverlayDrawableJoystick]
         *
         * @param context         The current [Context]
         * @param resOuter        Resource ID for the outer image of the joystick (the static image that shows the circular bounds).
         * @param defaultResInner Resource ID for the default inner image of the joystick (the one you actually move around).
         * @param pressedResInner Resource ID for the pressed inner image of the joystick.
         * @param joystick        Identifier for which joystick this is.
         * @return the initialized [InputOverlayDrawableJoystick].
         */
        private fun initializeOverlayJoystick(
            context: Context,
            resOuter: Int,
            defaultResInner: Int,
            pressedResInner: Int,
            joystick: Int,
            orientation: String
        ): InputOverlayDrawableJoystick {
            // Resources handle for fetching the initial Drawable resource.
            val res = context.resources

            // Decide scale based on user preference
            var scale = 0.275f
            scale *= (preferences.getInt("controlScale", 50) + 50).toFloat()
            scale /= 100f

            scale *= (preferences.getInt("controlScale-$joystick", 50) + 50).toFloat()
            scale /= 100f

            val opacity: Int = preferences.getInt("controlOpacity", 50) * 255 / 100

            // Initialize the InputOverlayDrawableJoystick.
            val bitmapOuter = getBitmap(context, resOuter, scale)
            val bitmapInnerDefault = getBitmap(context, defaultResInner, scale)
            val bitmapInnerPressed = getBitmap(context, pressedResInner, scale)

            // The X and Y coordinates of the InputOverlayDrawableButton on the InputOverlay.
            // These were set in the input overlay configuration menu.
            val drawableX = preferences.getFloat("$joystick$orientation-X", 0f).toInt()
            val drawableY = preferences.getFloat("$joystick$orientation-Y", 0f).toInt()

            // C-stick uses the same size as the main stick (was 2f = half size).
            // Raise this above 1f to make it smaller, e.g. 1.5f for 2/3 size.
            val outerScale = 1f

            // Now set the bounds for the InputOverlayDrawableJoystick.
            // This will dictate where on the screen (and the what the size) the InputOverlayDrawableJoystick will be.
            val outerSize = bitmapOuter.width
            val outerRect = Rect(
                drawableX,
                drawableY,
                drawableX + (outerSize / outerScale).toInt(),
                drawableY + (outerSize / outerScale).toInt()
            )
            val innerRect =
                Rect(0, 0, (outerSize / outerScale).toInt(), (outerSize / outerScale).toInt())

            // Send the drawableId to the joystick so it can be referenced when saving control position.
            val overlayDrawable = InputOverlayDrawableJoystick(
                res,
                bitmapOuter,
                bitmapInnerDefault,
                bitmapInnerPressed,
                outerRect,
                innerRect,
                joystick,
                opacity
            )

            // Need to set the image's position
            overlayDrawable.setPosition(drawableX, drawableY)
            OverlayTheme.register(
                overlayDrawable,
                listOf(
                    resOuter to R.string.overlay_theme_image_range,
                    defaultResInner to R.string.overlay_theme_image_stick,
                    pressedResInner to R.string.overlay_theme_image_stick_pressed
                )
            )
            OverlayTheme.register(
                overlayDrawable,
                listOf(
                    resOuter to R.string.overlay_theme_image_range,
                    defaultResInner to R.string.overlay_theme_image_stick,
                    pressedResInner to R.string.overlay_theme_image_stick_pressed
                )
            )
            return overlayDrawable
        }
    }
}
