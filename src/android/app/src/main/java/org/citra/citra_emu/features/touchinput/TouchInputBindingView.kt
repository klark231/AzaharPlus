// Copyright Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version.
// Refer to the license.txt file included.

package org.citra.citra_emu.features.touchinput

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.RectF
import android.text.TextPaint
import android.util.AttributeSet
import android.util.TypedValue
import android.view.MotionEvent
import android.view.View
import androidx.annotation.AttrRes
import androidx.core.graphics.ColorUtils
import com.google.android.material.color.MaterialColors
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.min
import com.google.android.material.R as MaterialR

/**
 * Full-width preview of the 3DS bottom screen, always 4:3. Each binding is drawn as a labeled
 * pill at its position; the selected one gets crosshair guides and can be dragged. A tap on empty
 * space is reported through [onEmptySpotTapped] so the host can start binding a new input there;
 * a tap on an existing pill is reported through [onBindingTapped] so the host can select it.
 *
 * In [testMode] the canvas ignores touch entirely and only shows whichever binding is passed to
 * [setTestHighlight], so a controller or keyboard press can be confirmed without risk of moving
 * or adding anything.
 */
class TouchInputBindingView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {
    /** Called when an empty part of the screen is tapped, with the normalized (x, y) position. */
    var onEmptySpotTapped: ((Float, Float) -> Unit)? = null

    /** Called when an existing binding's pill is tapped. */
    var onBindingTapped: ((TouchInputBinding) -> Unit)? = null

    /**
     * Called while the selected binding is being dragged, with its new normalized position.
     * [committed] is false for in-progress movement and true once the drag ends.
     */
    var onSelectedMoved: ((x: Float, y: Float, committed: Boolean) -> Unit)? = null

    /** When true, taps and drags are ignored and only the test highlight is drawn. */
    var testMode: Boolean = false
        set(value) {
            field = value
            cancelDrag()
            testHighlight = null
            invalidate()
        }

    private val density = resources.displayMetrics.density
    private val inset = INSET_DP * density

    private val screenRect = RectF()
    private val pillRect = RectF()

    private val bindings = mutableListOf<TouchInputBinding>()
    private var selectedBinding: TouchInputBinding? = null
    private var testHighlight: TouchInputBinding? = null

    // Hit rectangles for the currently drawn pills, in view coordinates, parallel to [bindings]
    private val hitRects = mutableListOf<RectF>()

    private var draggingBinding: TouchInputBinding? = null
    private var dragDownX = 0f
    private var dragDownY = 0f
    private var dragMoved = false

    // View-space position the dragged pill is drawn at, ahead of the host committing it
    private var dragLiveX = 0f
    private var dragLiveY = 0f

    private val surfaceColor = themeColor(MaterialR.attr.colorSurface)
    private val outlineColor = themeColor(MaterialR.attr.colorOutline)
    private val primaryColor = themeColor(androidx.appcompat.R.attr.colorPrimary)
    private val onPrimaryColor = themeColor(MaterialR.attr.colorOnPrimary)
    private val primaryContainerColor = themeColor(MaterialR.attr.colorPrimaryContainer)
    private val onPrimaryContainerColor = themeColor(MaterialR.attr.colorOnPrimaryContainer)
    private val successColor = themeColor(MaterialR.attr.colorTertiary)
    private val onSuccessColor = themeColor(MaterialR.attr.colorOnTertiary)

    private val screenPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
        color = surfaceColor
    }

    private val outlinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = OUTLINE_WIDTH_DP * density
        color = ColorUtils.setAlphaComponent(outlineColor, OUTLINE_ALPHA)
    }

    private val gridPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
        color = ColorUtils.setAlphaComponent(outlineColor, GRID_ALPHA)
    }

    private val crosshairPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = CROSSHAIR_WIDTH_DP * density
        color = ColorUtils.setAlphaComponent(primaryColor, CROSSHAIR_ALPHA)
        pathEffect = DashPathEffect(floatArrayOf(4 * density, 3 * density), 0f)
    }

    private val pillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }

    // Reused across the several concentric rects drawPillGlow() draws each frame.
    private val pillGlowPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }
    private val pillGlowRect = RectF()

    private val pillOutlinePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = PILL_OUTLINE_WIDTH_DP * density
        color = ColorUtils.setAlphaComponent(surfaceColor, PILL_OUTLINE_ALPHA)
    }

    private val pillTextPaint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
        textAlign = Paint.Align.CENTER
        textSize = spToPx(PILL_TEXT_SIZE_SP)
        isFakeBoldText = true
    }

    /** The view fills its width and is always 4:3, whatever height its parent gives it. */
    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val widthPx = MeasureSpec.getSize(widthMeasureSpec)
        val naturalHeight = (widthPx - 2 * inset) * SCREEN_HEIGHT / SCREEN_WIDTH + 2 * inset

        val heightPx = when (MeasureSpec.getMode(heightMeasureSpec)) {
            MeasureSpec.EXACTLY -> MeasureSpec.getSize(heightMeasureSpec).toFloat()
            MeasureSpec.AT_MOST -> min(naturalHeight, MeasureSpec.getSize(heightMeasureSpec).toFloat())
            else -> naturalHeight
        }
        setMeasuredDimension(widthPx, heightPx.toInt())
    }

    override fun onSizeChanged(width: Int, height: Int, oldWidth: Int, oldHeight: Int) {
        super.onSizeChanged(width, height, oldWidth, oldHeight)
        updateScreenRect()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (screenRect.isEmpty) return

        val corner = SCREEN_CORNER_RADIUS_DP * density
        canvas.drawRoundRect(screenRect, corner, corner, screenPaint)
        drawGrid(canvas)

        val selected = selectedBinding
        if (selected != null && !testMode) {
            val liveOverride = if (draggingBinding == selected && dragMoved) {
                dragLiveX to dragLiveY
            } else {
                null
            }
            drawCrosshair(canvas, selected, liveOverride)
        }

        canvas.drawRoundRect(screenRect, corner, corner, outlinePaint)

        hitRects.clear()
        bindings.forEach { binding ->
            val isSelected = !testMode && binding == selected
            if (!isSelected) {
                val isTestHit = testMode && binding == testHighlight
                hitRects.add(drawPill(canvas, binding, selected = false, testHit = isTestHit))
            } else {
                // Placeholder so hitRects stays index-aligned with bindings; replaced below
                hitRects.add(RectF())
            }
        }
        // The selected pill is drawn last so it ends up on top of its neighbors
        if (selected != null && !testMode) {
            val index = bindings.indexOf(selected)
            val liveOverride = if (draggingBinding == selected && dragMoved) {
                dragLiveX to dragLiveY
            } else {
                null
            }
            val rect = drawPill(canvas, selected, selected = true, testHit = false, liveOverride)
            if (index >= 0) hitRects[index] = rect
        }
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (testMode) return false

        when (event.action) {
            MotionEvent.ACTION_DOWN -> {
                if (!screenRect.contains(event.x, event.y)) return false

                // Every branch below consumes the gesture, and any of them can end in a vertical
                // drag. Without this, the screen's NestedScrollView will grab the gesture the
                // moment the finger moves far enough vertically, mid-drag, which both scrolls the
                // page out from under the finger and makes the pill look like it's moving the
                // wrong way (it isn't — the canvas is sliding, not the pill).
                parent?.requestDisallowInterceptTouchEvent(true)

                val hitBinding = hitTest(event.x, event.y)

                if (hitBinding != null && hitBinding == selectedBinding) {
                    // Only the already-selected pill can be picked up and dragged
                    draggingBinding = hitBinding
                    dragDownX = event.x
                    dragDownY = event.y
                    dragMoved = false
                    return true
                }
                if (hitBinding != null) {
                    onBindingTapped?.invoke(hitBinding)
                    return true
                }
                onEmptySpotTapped?.invoke(
                    normalizedX(event.x).coerceIn(0f, 1f),
                    normalizedY(event.y).coerceIn(0f, 1f)
                )
                return true
            }

            MotionEvent.ACTION_MOVE -> {
                draggingBinding ?: return false
                if (!dragMoved) {
                    val moved = abs(event.x - dragDownX) > DRAG_SLOP_DP * density ||
                        abs(event.y - dragDownY) > DRAG_SLOP_DP * density
                    if (!moved) return true
                    dragMoved = true
                }
                dragLiveX = event.x.coerceIn(screenRect.left, screenRect.right)
                dragLiveY = event.y.coerceIn(screenRect.top, screenRect.bottom)
                invalidate()
                val x = normalizedX(dragLiveX)
                val y = normalizedY(dragLiveY)
                onSelectedMoved?.invoke(x.coerceIn(0f, 1f), y.coerceIn(0f, 1f), false)
                return true
            }

            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                val dragging = draggingBinding
                if (dragging != null && dragMoved) {
                    val x = normalizedX(event.x.coerceIn(screenRect.left, screenRect.right))
                    val y = normalizedY(event.y.coerceIn(screenRect.top, screenRect.bottom))
                    onSelectedMoved?.invoke(x.coerceIn(0f, 1f), y.coerceIn(0f, 1f), true)
                } else if (dragging != null) {
                    // A tap on the already-selected pill, with no movement: treat as a re-tap
                    onBindingTapped?.invoke(dragging)
                }
                cancelDrag()
                return true
            }
        }
        return super.onTouchEvent(event)
    }

    fun setBindings(newBindings: List<TouchInputBinding>) {
        bindings.clear()
        bindings.addAll(newBindings)
        invalidate()
    }

    /** Highlights [binding] in edit mode, or clears the selection if null. */
    fun setSelectedBinding(binding: TouchInputBinding?) {
        selectedBinding = binding
        cancelDrag()
        invalidate()
    }

    /** Highlights [binding] in test mode, or clears the highlight if null. Ignored outside test mode. */
    fun setTestHighlight(binding: TouchInputBinding?) {
        if (!testMode) return
        testHighlight = binding
        invalidate()
    }

    private fun cancelDrag() {
        draggingBinding = null
        dragMoved = false
        parent?.requestDisallowInterceptTouchEvent(false)
    }

    private fun hitTest(x: Float, y: Float): TouchInputBinding? {
        for (index in hitRects.indices.reversed()) {
            if (hitRects[index].contains(x, y)) return bindings.getOrNull(index)
        }
        return null
    }

    private fun normalizedX(viewX: Float): Float = (viewX - screenRect.left) / screenRect.width()
    private fun normalizedY(viewY: Float): Float = (viewY - screenRect.top) / screenRect.height()

    private fun updateScreenRect() {
        val availableWidth = width - 2 * inset
        val availableHeight = height - 2 * inset
        if (availableWidth <= 0f || availableHeight <= 0f) return

        val scale = min(availableWidth / SCREEN_WIDTH, availableHeight / SCREEN_HEIGHT)
        val screenWidth = SCREEN_WIDTH * scale
        val screenHeight = SCREEN_HEIGHT * scale
        val left = (width - screenWidth) / 2f
        val top = (height - screenHeight) / 2f

        screenRect.set(left, top, left + screenWidth, top + screenHeight)
        invalidate()
    }

    private fun drawGrid(canvas: Canvas) {
        val radius = GRID_DOT_RADIUS_DP * density
        val columnWidth = screenRect.width() / GRID_COLUMNS
        val rowHeight = screenRect.height() / GRID_ROWS

        for (column in 1 until GRID_COLUMNS) {
            for (row in 1 until GRID_ROWS) {
                canvas.drawCircle(
                    screenRect.left + column * columnWidth,
                    screenRect.top + row * rowHeight,
                    radius,
                    gridPaint
                )
            }
        }
    }

    /** Dashed guide lines from the selected pill to the top and left edges of the screen. */
    private fun drawCrosshair(
        canvas: Canvas,
        binding: TouchInputBinding,
        liveOverride: Pair<Float, Float>?
    ) {
        val x = liveOverride?.first ?: (screenRect.left + binding.x * screenRect.width())
        val y = liveOverride?.second ?: (screenRect.top + binding.y * screenRect.height())
        canvas.drawLine(x, screenRect.top, x, y, crosshairPaint)
        canvas.drawLine(screenRect.left, y, x, y, crosshairPaint)
    }

    /**
     * Draws [binding]'s pill and returns its hit rectangle in view coordinates. [liveOverride], if
     * given, is a view-space (x, y) to draw at instead of the binding's stored position, used
     * while the pill is being dragged and the host hasn't pushed the new position back yet.
     */
    private fun drawPill(
        canvas: Canvas,
        binding: TouchInputBinding,
        selected: Boolean,
        testHit: Boolean,
        liveOverride: Pair<Float, Float>? = null
    ): RectF {
        val x = liveOverride?.first ?: (screenRect.left + binding.x * screenRect.width())
        val y = liveOverride?.second ?: (screenRect.top + binding.y * screenRect.height())

        val label = binding.shortLabel()
        val textWidth = pillTextPaint.measureText(label)
        val height = PILL_HEIGHT_DP * density
        val width = (textWidth + 2 * PILL_PADDING_DP * density).coerceAtLeast(height)

        pillRect.set(x - width / 2f, y - height / 2f, x + width / 2f, y + height / 2f)
        // Keep the pill fully inside the screen even when its anchor point is near an edge
        val dx = (screenRect.left - pillRect.left).coerceAtLeast(0f) +
            (screenRect.right - pillRect.right).coerceAtMost(0f)
        val dy = (screenRect.top - pillRect.top).coerceAtLeast(0f) +
            (screenRect.bottom - pillRect.bottom).coerceAtMost(0f)
        pillRect.offset(dx, dy)
        pullOutOfRoundedCorners(pillRect, SCREEN_CORNER_RADIUS_DP * density)

        pillPaint.color = when {
            testHit -> successColor
            selected -> primaryColor
            else -> primaryContainerColor
        }
        val textColor = when {
            testHit -> onSuccessColor
            selected -> onPrimaryColor
            else -> onPrimaryContainerColor
        }

        val corner = pillRect.height() / 2f
        if (selected) drawPillGlow(canvas, pillRect, corner)
        canvas.drawRoundRect(pillRect, corner, corner, pillPaint)
        if (selected || testHit) {
            canvas.drawRoundRect(pillRect, corner, corner, pillOutlinePaint)
        }

        pillTextPaint.color = textColor
        val baseline = pillRect.centerY() - (pillTextPaint.ascent() + pillTextPaint.descent()) / 2f
        canvas.drawText(label, pillRect.centerX(), baseline, pillTextPaint)

        // A comfortable touch target even for a very short label like "A"
        val hitRect = RectF(pillRect)
        val minHit = MIN_HIT_DP * density
        if (hitRect.width() < minHit) hitRect.inset(-(minHit - hitRect.width()) / 2f, 0f)
        if (hitRect.height() < minHit) hitRect.inset(0f, -(minHit - hitRect.height()) / 2f)
        return hitRect
    }

    /**
     * The straight-edge clamp in drawPill() can still leave a pill's own corner poking into one
     * of the screen's four rounded corners, where it paints over — and visually breaks — the
     * curve. This nudges the whole rect inward along the diagonal for whichever corner it crowds.
     */
    private fun pullOutOfRoundedCorners(rect: RectF, corner: Float) {
        if (corner <= 0f) return

        // Each entry is which sign of rect corner to check, against the matching screen corner.
        // The rect corner is read fresh on each iteration (not precomputed) in case an earlier
        // pass already shifted the rect.
        val signs = arrayOf(-1f to -1f, 1f to -1f, -1f to 1f, 1f to 1f)

        for ((signX, signY) in signs) {
            val px = if (signX < 0f) rect.left else rect.right
            val py = if (signY < 0f) rect.top else rect.bottom
            val centerX = if (signX < 0f) screenRect.left + corner else screenRect.right - corner
            val centerY = if (signY < 0f) screenRect.top + corner else screenRect.bottom - corner

            // Only relevant if this rect corner actually sits in that corner's square "cut" zone.
            val inCutZone = (if (signX < 0f) px < centerX else px > centerX) &&
                (if (signY < 0f) py < centerY else py > centerY)
            if (!inCutZone) continue

            val vx = px - centerX
            val vy = py - centerY
            val dist = hypot(vx, vy)
            if (dist <= corner || dist == 0f) continue

            // Push the whole rect inward along this diagonal until that corner sits on the curve.
            val excess = dist - corner
            rect.offset(-vx / dist * excess, -vy / dist * excess)
        }
    }

    /**
     * A soft halo behind the selected pill: a few concentric rounded rects, each a little bigger
     * and fainter than the last. Cheaper and crisper under hardware acceleration than a real blur
     * (Paint.setShadowLayer / BlurMaskFilter), and looks the same at this size.
     */
    private fun drawPillGlow(canvas: Canvas, pill: RectF, corner: Float) {
        for (step in GLOW_STEPS downTo 1) {
            val expand = step * GLOW_STEP_DP * density
            pillGlowRect.set(
                pill.left - expand,
                pill.top - expand,
                pill.right + expand,
                pill.bottom + expand
            )
            pillGlowPaint.color = ColorUtils.setAlphaComponent(primaryColor, GLOW_MAX_ALPHA / step)
            canvas.drawRoundRect(pillGlowRect, corner + expand, corner + expand, pillGlowPaint)
        }
    }

    private fun themeColor(@AttrRes attr: Int): Int =
        MaterialColors.getColor(context, attr, Color.TRANSPARENT)

    private fun spToPx(sp: Float): Float =
        TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, sp, resources.displayMetrics)

    companion object {
        // The 3DS bottom screen is 320x240 whatever layout or orientation the emulator uses
        private const val SCREEN_WIDTH = 320f
        private const val SCREEN_HEIGHT = 240f
        private const val SCREEN_CORNER_RADIUS_DP = 16f
        private const val INSET_DP = 2f
        private const val OUTLINE_WIDTH_DP = 1.5f
        private const val OUTLINE_ALPHA = 130

        private const val GRID_COLUMNS = 16
        private const val GRID_ROWS = 12
        private const val GRID_DOT_RADIUS_DP = 1.1f
        private const val GRID_ALPHA = 110

        private const val CROSSHAIR_WIDTH_DP = 1f
        private const val CROSSHAIR_ALPHA = 130

        private const val PILL_HEIGHT_DP = 26f
        private const val PILL_PADDING_DP = 9f
        private const val PILL_TEXT_SIZE_SP = 12f
        private const val PILL_OUTLINE_WIDTH_DP = 1.5f
        private const val PILL_OUTLINE_ALPHA = 200
        private const val MIN_HIT_DP = 40f

        private const val GLOW_STEPS = 4
        private const val GLOW_STEP_DP = 3f
        private const val GLOW_MAX_ALPHA = 70

        private const val DRAG_SLOP_DP = 4f
    }
}
