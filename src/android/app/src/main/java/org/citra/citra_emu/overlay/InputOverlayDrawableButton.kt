// Copyright 2023-2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

package org.citra.citra_emu.overlay

import android.content.res.Resources
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Rect
import android.graphics.drawable.BitmapDrawable
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import kotlin.math.hypot
import org.citra.citra_emu.NativeLibrary
import org.citra.citra_emu.utils.EmulationMenuSettings

enum class ButtonSlidingMode(val int: Int) {
    // Disabled, buttons can only be triggered by pressing them directly.
    Disabled(0),

    // Additionally to pressing buttons directly, they can be activated and released by sliding into
    // and out of their area.
    Enabled(1),

    // The first button is kept activated until released, further buttons use the simple button
    // sliding method.
    Alternative(2)
}

/** Pixels of the icon that are at least this opaque (0..255) count as part of the button. */
private const val BUTTON_HIT_ALPHA = 32

/**
 * Custom [BitmapDrawable] that is capable
 * of storing it's own ID.
 *
 * @param res                [Resources] instance.
 * @param defaultStateBitmap [Bitmap] to use with the default state Drawable.
 * @param pressedStateBitmap [Bitmap] to use with the pressed state Drawable.
 * @param id                 Identifier for this type of button.
 */
class InputOverlayDrawableButton(
    res: Resources,
    defaultStateBitmap: Bitmap,
    pressedStateBitmap: Bitmap,
    val id: Int,
    val opacity: Int
) {
    var trackId: Int

    // Part of a multi-press: stays pressed until the finger lifts, never released by sliding off
    private var heldUntilRelease = false

    private var isMotionFirstButton = false
    // ^- mark the first activated button with the current motion

    private var previousTouchX = 0
    private var previousTouchY = 0
    private var controlPositionX = 0
    private var controlPositionY = 0
    val width: Int
    val height: Int
    private val defaultStateBitmap: BitmapDrawable
    private val pressedStateBitmap: BitmapDrawable
    private var pressedState = false

    // The default icon, kept to tell the visible shape from the empty corners of its square
    private val hitMask: Bitmap

    init {
        this.defaultStateBitmap = BitmapDrawable(res, defaultStateBitmap)
        this.pressedStateBitmap = BitmapDrawable(res, pressedStateBitmap)
        hitMask = defaultStateBitmap
        trackId = -1
        width = this.defaultStateBitmap.intrinsicWidth
        height = this.defaultStateBitmap.intrinsicHeight
    }

    /**
     * Updates button status based on the motion event.
     *
     * @return true if value was changed
     */
    fun updateStatus(
        event: MotionEvent,
        pointerIndex: Int,
        hasActiveButtons: Boolean,
        overlay: InputOverlay
    ): Boolean {
        val buttonSliding = EmulationMenuSettings.buttonSlide
        val xPosition = event.getX(pointerIndex).toInt()
        val yPosition = event.getY(pointerIndex).toInt()
        val pointerId = event.getPointerId(pointerIndex)
        val motionEvent = event.action and MotionEvent.ACTION_MASK
        val isActionDown =
            motionEvent == MotionEvent.ACTION_DOWN || motionEvent == MotionEvent.ACTION_POINTER_DOWN
        val isActionUp =
            motionEvent == MotionEvent.ACTION_UP || motionEvent == MotionEvent.ACTION_POINTER_UP
        if (isActionDown) {
            // Multi-press: a touch between two buttons presses both (see InputOverlay)
            val groupSize = overlay.buttonTouchGroupSize(this, xPosition, yPosition)
            if (groupSize == 0) {
                return false
            }
            buttonDown(true, pointerId, overlay)
            // Like Citra MMJ: buttons pressed together stay held until the finger is lifted,
            // even if the finger jitters or drifts off them
            heldUntilRelease = groupSize > 1
            return true
        }
        if (isActionUp) {
            if (trackId != pointerId) {
                return false
            }
            buttonUp(overlay, false)
            return true
        }

        val isActionMoving = motionEvent == MotionEvent.ACTION_MOVE
        if (buttonSliding != ButtonSlidingMode.Disabled.int && isActionMoving) {
            val inside = containsPoint(xPosition, yPosition)
            if (pressedState) {
                // button is already pressed
                // check whether we moved out of the button area to update the state
                if (inside || trackId != pointerId || heldUntilRelease) {
                    return false
                }

                // prevent the first (directly pressed) button to deactivate when sliding off
                if (buttonSliding == ButtonSlidingMode.Alternative.int && isMotionFirstButton) {
                    return false
                }

                val preserveTrackId = (buttonSliding != ButtonSlidingMode.Disabled.int)
                buttonUp(overlay, preserveTrackId)
                return true
            } else {
                // button was not yet pressed
                // check whether we moved into the button area to update the state
                if (!inside) {
                    return false
                }
                buttonDown(!hasActiveButtons, pointerId, overlay)
                return true
            }
        }

        return false
    }

    private fun buttonDown(firstBtn: Boolean, pointerId: Int, overlay: InputOverlay) {
        pressedState = true
        heldUntilRelease = false
        isMotionFirstButton = firstBtn
        trackId = pointerId
        overlay.hapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
    }

    private fun buttonUp(overlay: InputOverlay, preserveTrackId: Boolean) {
        pressedState = false
        heldUntilRelease = false
        isMotionFirstButton = false
        if (!preserveTrackId) {
            trackId = -1
        }
        overlay.hapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY_RELEASE)
    }

    fun onConfigureTouch(event: MotionEvent): Boolean {
        val pointerIndex = event.actionIndex
        val fingerPositionX = event.getX(pointerIndex).toInt()
        val fingerPositionY = event.getY(pointerIndex).toInt()
        when (event.action) {
            MotionEvent.ACTION_DOWN -> {
                previousTouchX = fingerPositionX
                previousTouchY = fingerPositionY
            }

            MotionEvent.ACTION_MOVE -> {
                controlPositionX += fingerPositionX - previousTouchX
                controlPositionY += fingerPositionY - previousTouchY
                setBounds(
                    controlPositionX,
                    controlPositionY,
                    width + controlPositionX,
                    height + controlPositionY
                )
                previousTouchX = fingerPositionX
                previousTouchY = fingerPositionY
            }
        }
        return true
    }

    fun setPosition(x: Int, y: Int) {
        controlPositionX = x
        controlPositionY = y
    }

    fun draw(canvas: Canvas) {
        val bitmapDrawable: BitmapDrawable = currentStateBitmapDrawable
        bitmapDrawable.alpha = opacity
        bitmapDrawable.draw(canvas)
    }

    private val currentStateBitmapDrawable: BitmapDrawable
        get() = if (pressedState) pressedStateBitmap else defaultStateBitmap

    fun setBounds(left: Int, top: Int, right: Int, bottom: Int) {
        defaultStateBitmap.setBounds(left, top, right, bottom)
        pressedStateBitmap.setBounds(left, top, right, bottom)
    }

    val status: Int
        get() = if (pressedState) {
            NativeLibrary.ButtonState.PRESSED
        } else {
            NativeLibrary.ButtonState.RELEASED
        }
    val bounds: Rect
        get() = defaultStateBitmap.bounds

    /**
     * True if (x, y) is on the visible icon, not just inside the square around it. A round button
     * does not react in the corners of its square, so buttons that are close together never
     * share a touch.
     */
    fun containsPoint(x: Int, y: Int): Boolean {
        val r = bounds
        if (r.width() <= 0 || r.height() <= 0 || !r.contains(x, y)) {
            return false
        }
        val px = ((x - r.left) * hitMask.width / r.width()).coerceIn(0, hitMask.width - 1)
        val py = ((y - r.top) * hitMask.height / r.height()).coerceIn(0, hitMask.height - 1)
        return try {
            (hitMask.getPixel(px, py) ushr 24) >= BUTTON_HIT_ALPHA
        } catch (_: Exception) {
            true
        }
    }

    /** Distance in pixels from (x, y) to the centre of this button. */
    fun centerDistance(x: Int, y: Int): Float {
        val r = bounds
        return hypot(x - r.exactCenterX(), y - r.exactCenterY())
    }

    /** Distance in pixels from (x, y) to this button's bounds, 0 when the point is inside. */
    fun distanceTo(x: Int, y: Int): Float {
        val r = bounds
        val dx = maxOf(r.left - x, 0, x - r.right)
        val dy = maxOf(r.top - y, 0, y - r.bottom)
        return hypot(dx.toFloat(), dy.toFloat())
    }
}
