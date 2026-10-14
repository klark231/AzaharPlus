// Copyright Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

package org.citra.citra_emu.overlay

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.os.Build
import android.util.AttributeSet
import android.view.View
import org.citra.citra_emu.NativeLibrary

/**
 * Draws the user's background image above the emulation surface, with the two 3DS screens cut
 * out so the game still shows through. The image is scaled to fill the view (center crop).
 */
class EmulationBackgroundView(context: Context, attrs: AttributeSet?) : View(context, attrs) {
    private var bitmap: Bitmap? = null
    private var layout = FloatArray(0)
    private var lastBounds = IntArray(4)

    /**
     * The emulation SurfaceView. The 3DS screens are positioned inside this view, and it can be
     * inset by the display cutout, so the cut-out holes must be offset and scaled to it instead
     * of to this full-screen view. Without this the image covers part of the game.
     */
    var target: View? = null

    /** The input overlay is drawn above the game surface, so it also paints the background. */
    var overlay: View? = null
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG or Paint.ANTI_ALIAS_FLAG)
    private val src = RectF()
    private val dst = RectF()

    private val poll = object : Runnable {
        override fun run() {
            val current = NativeLibrary.getFramebufferLayout()
            val bounds = currentBounds()
            if (!current.contentEquals(layout) || !bounds.contentEquals(lastBounds)) {
                layout = current
                lastBounds = bounds
                invalidate()
                overlay?.invalidate()
            }
            postDelayed(this, POLL_MS)
        }
    }

    init {
        reload()
    }

    private fun currentBounds(): IntArray {
        val t = target
        return if (t != null) {
            intArrayOf(t.left, t.top, t.width, t.height)
        } else {
            intArrayOf(0, 0, width, height)
        }
    }

    /** Re-reads the saved image. Call after it was changed. */
    fun reload() {
        bitmap = EmulationBackground.load(context)
        visibility = if (bitmap != null) VISIBLE else GONE
        layout = FloatArray(0)
        invalidate()
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        removeCallbacks(poll)
        post(poll)
    }

    override fun onDetachedFromWindow() {
        removeCallbacks(poll)
        super.onDetachedFromWindow()
    }

    override fun onDraw(canvas: Canvas) {
        drawBackground(canvas)
    }

    /** Paints the image with the screens cut out. Canvas must match this view's coordinates. */
    fun drawBackground(canvas: Canvas) {
        val image = bitmap ?: return
        // Not known yet: draw nothing so the game is never hidden.
        if (layout.size < LAYOUT_SIZE || layout[0] <= 0f || layout[1] <= 0f) return

        val b = currentBounds()
        val ox = b[0].toFloat()
        val oy = b[1].toFloat()
        // Surface not laid out yet: draw nothing so the game is never hidden.
        if (b[2] <= 0 || b[3] <= 0) return
        val sx = b[2] / layout[0]
        val sy = b[3] / layout[1]

        canvas.save()
        clipOut(canvas, ox + layout[6] * sx, oy + layout[7] * sy, ox + layout[8] * sx, oy + layout[9] * sy)
        clipOut(canvas, ox + layout[2] * sx, oy + layout[3] * sy, ox + layout[4] * sx, oy + layout[5] * sy)

        val scale = maxOf(width.toFloat() / image.width, height.toFloat() / image.height)
        val w = image.width * scale
        val h = image.height * scale
        src.set(0f, 0f, image.width.toFloat(), image.height.toFloat())
        dst.set((width - w) / 2f, (height - h) / 2f, (width + w) / 2f, (height + h) / 2f)
        canvas.drawBitmap(image, null, dst, paint)
        canvas.restore()
    }

    private fun clipOut(canvas: Canvas, l: Float, t: Float, r: Float, b: Float) {
        if (r <= l || b <= t) return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            canvas.clipOutRect(l, t, r, b)
        } else {
            @Suppress("DEPRECATION")
            canvas.clipRect(l, t, r, b, android.graphics.Region.Op.DIFFERENCE)
        }
    }

    private companion object {
        const val POLL_MS = 100L
        const val LAYOUT_SIZE = 10
    }
}
