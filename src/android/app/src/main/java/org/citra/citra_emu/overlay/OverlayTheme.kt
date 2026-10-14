// Copyright Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

package org.citra.citra_emu.overlay

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.net.Uri
import androidx.core.content.ContextCompat
import androidx.documentfile.provider.DocumentFile
import androidx.preference.PreferenceManager
import java.util.WeakHashMap
import org.citra.citra_emu.CitraApplication
import org.citra.citra_emu.R
import org.citra.citra_emu.utils.DirectoryInitialization
import org.citra.citra_emu.utils.FileUtil
import org.citra.citra_emu.utils.Log

object OverlayTheme {
    private const val PREF_KEY = "OverlayButtonTheme"
    private const val THEME_DIR = "theme"
    private const val NO_MEDIA = ".nomedia"
    private const val TEMPLATE_THEME = "Template"
    private const val CUSTOM_THEME = "Custom"
    private const val MAX_IMAGE_SIZE = 512
    private const val TEMPLATE_MIN_SIZE = 256f

    private val TEMPLATE_DRAWABLES = intArrayOf(
        R.drawable.button_a,
        R.drawable.button_a_pressed,
        R.drawable.button_b,
        R.drawable.button_b_pressed,
        R.drawable.button_x,
        R.drawable.button_x_pressed,
        R.drawable.button_y,
        R.drawable.button_y_pressed,
        R.drawable.button_l,
        R.drawable.button_l_pressed,
        R.drawable.button_r,
        R.drawable.button_r_pressed,
        R.drawable.button_zl,
        R.drawable.button_zl_pressed,
        R.drawable.button_zr,
        R.drawable.button_zr_pressed,
        R.drawable.button_start,
        R.drawable.button_start_pressed,
        R.drawable.button_select,
        R.drawable.button_select_pressed,
        R.drawable.dpad,
        R.drawable.dpad_pressed_one_direction,
        R.drawable.dpad_pressed_two_directions,
        R.drawable.stick_main_range,
        R.drawable.stick_main,
        R.drawable.stick_main_pressed,
        R.drawable.stick_c_range,
        R.drawable.stick_c,
        R.drawable.stick_c_pressed,
        R.drawable.button_home,
        R.drawable.button_home_pressed,
        R.drawable.button_swap,
        R.drawable.button_swap_pressed,
        R.drawable.button_turbo,
        R.drawable.button_turbo_pressed,
        R.drawable.button_combo_1,
        R.drawable.button_combo_1_pressed,
        R.drawable.button_combo_2,
        R.drawable.button_combo_2_pressed,
        R.drawable.button_combo_3,
        R.drawable.button_combo_3_pressed,
        R.drawable.button_combo_4,
        R.drawable.button_combo_4_pressed,
        R.drawable.button_combo_5,
        R.drawable.button_combo_5_pressed,
    )

    private var files: Map<String, Uri> = emptyMap()
    private val bitmaps = HashMap<String, Bitmap>()
    private val controlImages = WeakHashMap<Any, List<Pair<Int, Int>>>()

    var selected: String
        get() = PreferenceManager.getDefaultSharedPreferences(CitraApplication.appContext)
            .getString(PREF_KEY, "") ?: ""
        set(value) {
            PreferenceManager.getDefaultSharedPreferences(CitraApplication.appContext)
                .edit()
                .putString(PREF_KEY, value)
                .apply()
            refresh()
        }

    /** Remembers which images (drawable id to label string id) a control uses. */
    fun register(control: Any, images: List<Pair<Int, Int>>) {
        controlImages[control] = images
    }

    fun imagesOf(control: Any): List<Pair<Int, Int>> = controlImages[control] ?: emptyList()

    private fun userRoot(): Uri? = DirectoryInitialization.userPath?.let { Uri.parse(it) }

    private fun childDir(parent: Uri, name: String, create: Boolean): Uri? {
        FileUtil.listFiles(parent).firstOrNull { it.isDirectory && it.filename == name }
            ?.let { return it.uri }
        if (!create) return null
        return FileUtil.createDir(parent.toString(), name)?.uri
    }

    private fun themeRoot(create: Boolean): Uri? {
        val root = userRoot() ?: return null
        return childDir(root, THEME_DIR, create)
    }

    private fun themeFolder(name: String, create: Boolean): Uri? {
        val dir = themeRoot(create) ?: return null
        return childDir(dir, name, create)
    }

    fun ensureThemeFolder(): Boolean {
        val dir = themeRoot(true) ?: return false
        if (FileUtil.listFiles(dir).none { it.filename == NO_MEDIA }) {
            FileUtil.createFile(dir.toString(), NO_MEDIA)
        }
        return true
    }

    fun listThemes(): List<String> {
        val dir = themeRoot(false) ?: return emptyList()
        return FileUtil.listFiles(dir)
            .filter { it.isDirectory }
            .map { it.filename }
            .sortedBy { it.lowercase() }
    }

    /** Rescans the selected theme folder. Called whenever the overlay is built. */
    fun refresh() {
        files = emptyMap()
        bitmaps.clear()
        val name = selected
        if (name.isEmpty()) return
        val themeUri = themeFolder(name, false) ?: return
        files = FileUtil.listFiles(themeUri)
            .filter { !it.isDirectory }
            .associate { it.filename.lowercase() to it.uri }
    }

    /** Returns the themed image for a built-in drawable, or null to use the default one. */
    fun loadBitmap(context: Context, drawableId: Int): Bitmap? {
        if (files.isEmpty()) return null
        val name = context.resources.getResourceEntryName(drawableId)
        bitmaps[name]?.let { return it }
        val uri = files["$name.png"] ?: return null
        return try {
            context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) }
                ?.also { bitmaps[name] = it }
        } catch (e: Exception) {
            Log.error("[OverlayTheme] Cannot load $name.png: ${e.message}")
            null
        }
    }

    /** Saves the built-in images as PNG files in theme/Template. */
    fun exportTemplate(context: Context): Boolean {
        if (!ensureThemeFolder()) return false
        val dir = themeFolder(TEMPLATE_THEME, true) ?: return false
        val existing = FileUtil.listFiles(dir).map { it.filename.lowercase() }.toSet()
        var success = true
        for (id in TEMPLATE_DRAWABLES) {
            val name = context.resources.getResourceEntryName(id)
            if ("$name.png" in existing) continue
            val bitmap = renderDefault(context, id)
            success = (bitmap != null && writePng(context, dir, "$name.png", bitmap)) && success
        }
        return success
    }

    private fun renderDefault(context: Context, drawableId: Int): Bitmap? {
        val drawable = ContextCompat.getDrawable(context, drawableId) ?: return null
        val width = drawable.intrinsicWidth.takeIf { it > 0 } ?: TEMPLATE_MIN_SIZE.toInt()
        val height = drawable.intrinsicHeight.takeIf { it > 0 } ?: TEMPLATE_MIN_SIZE.toInt()
        val scale = maxOf(1f, TEMPLATE_MIN_SIZE / maxOf(width, height))
        val bitmap = Bitmap.createBitmap(
            (width * scale).toInt(),
            (height * scale).toInt(),
            Bitmap.Config.ARGB_8888
        )
        val canvas = Canvas(bitmap)
        drawable.setBounds(0, 0, canvas.width, canvas.height)
        drawable.draw(canvas)
        return bitmap
    }

    private fun writePng(context: Context, dir: Uri, name: String, bitmap: Bitmap): Boolean {
        return try {
            val parent = DocumentFile.fromTreeUri(context, dir) ?: return false
            parent.findFile(name)?.delete()
            val file = parent.createFile("image/png", name) ?: return false
            context.contentResolver.openOutputStream(file.uri)?.use {
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)
            } ?: false
        } catch (e: Exception) {
            Log.error("[OverlayTheme] Cannot write $name: ${e.message}")
            false
        }
    }

    /** The theme to edit: the selected one, or a new "Custom" theme if none is selected. */
    private fun editableTheme(): String? {
        if (!ensureThemeFolder()) return null
        val name = selected.ifEmpty { CUSTOM_THEME }
        themeFolder(name, true) ?: return null
        if (selected.isEmpty()) selected = name
        return name
    }

    /** Copies a picked image into the theme as a square PNG. Returns the theme name or null. */
    fun saveImage(context: Context, drawableId: Int, source: Uri): String? {
        val name = editableTheme() ?: return null
        val dir = themeFolder(name, false) ?: return null
        val bitmap = decodeSquare(context, source) ?: return null
        val entry = context.resources.getResourceEntryName(drawableId)
        val saved = writePng(context, dir, "$entry.png", bitmap)
        refresh()
        return if (saved) name else null
    }

    private fun decodeSquare(context: Context, uri: Uri): Bitmap? {
        return try {
            val source = context.contentResolver.openInputStream(uri)?.use {
                BitmapFactory.decodeStream(it)
            } ?: return null
            val ratio = MAX_IMAGE_SIZE.toFloat() / maxOf(source.width, source.height)
            val size = minOf(MAX_IMAGE_SIZE, maxOf(source.width, source.height))
            val width = if (ratio < 1f) source.width * ratio else source.width.toFloat()
            val height = if (ratio < 1f) source.height * ratio else source.height.toFloat()
            val result = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
            val left = (size - width) / 2f
            val top = (size - height) / 2f
            Canvas(result).drawBitmap(
                source,
                null,
                RectF(left, top, left + width, top + height),
                Paint(Paint.FILTER_BITMAP_FLAG)
            )
            result
        } catch (e: Exception) {
            Log.error("[OverlayTheme] Cannot read picked image: ${e.message}")
            null
        }
    }

    /** Removes custom images from the selected theme so the default ones show again. */
    fun resetImages(context: Context, drawableIds: List<Int>) {
        val name = selected
        if (name.isEmpty()) return
        val dir = themeFolder(name, false) ?: return
        val names = drawableIds.map { context.resources.getResourceEntryName(it) + ".png" }
        FileUtil.listFiles(dir)
            .filter { doc -> names.any { it.equals(doc.filename, ignoreCase = true) } }
            .forEach { DocumentFile.fromSingleUri(context, it.uri)?.delete() }
        refresh()
    }
}
