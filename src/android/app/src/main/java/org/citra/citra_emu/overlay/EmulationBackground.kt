// Copyright Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

package org.citra.citra_emu.overlay

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.widget.Toast
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import java.io.File
import org.citra.citra_emu.NativeLibrary
import org.citra.citra_emu.R
import org.citra.citra_emu.utils.Log

/** Stores the custom image that is shown behind the emulated screens. */
object EmulationBackground {
    private const val FILE_NAME = "emulation_background.png"
    private const val MAX_SIZE = 2048

    private fun file(context: Context) = File(context.filesDir, FILE_NAME)

    fun exists(context: Context): Boolean = file(context).isFile

    /** Loads the saved image, or null if none is set. */
    fun load(context: Context): Bitmap? {
        val f = file(context)
        if (!f.isFile) return null
        return try {
            BitmapFactory.decodeFile(f.absolutePath)
        } catch (e: Exception) {
            Log.error("[EmulationBackground] Cannot load image: ${e.message}")
            null
        }
    }

    /** Copies a picked image into app storage (downscaled if huge). */
    fun save(context: Context, source: Uri): Boolean {
        return try {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            context.contentResolver.openInputStream(source)?.use {
                BitmapFactory.decodeStream(it, null, bounds)
            }
            var sample = 1
            while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= MAX_SIZE) {
                sample *= 2
            }
            val options = BitmapFactory.Options().apply { inSampleSize = sample }
            val bitmap = context.contentResolver.openInputStream(source)?.use {
                BitmapFactory.decodeStream(it, null, options)
            } ?: return false
            file(context).outputStream().use {
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)
            }
            true
        } catch (e: Exception) {
            Log.error("[EmulationBackground] Cannot save image: ${e.message}")
            false
        }
    }

    fun clear(context: Context) {
        file(context).delete()
        applyToRenderer(context)
    }

    /** Sends the saved image (or none) to the renderer. Safe to call at any time. */
    fun applyToRenderer(context: Context) {
        try {
            val bitmap = load(context)
            if (bitmap == null) {
                NativeLibrary.setBackgroundImage(null, 0, 0)
                return
            }
            val width = bitmap.width
            val height = bitmap.height
            val pixels = IntArray(width * height)
            bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
            bitmap.recycle()
            NativeLibrary.setBackgroundImage(pixels, width, height)
        } catch (e: Throwable) {
            Log.error("[EmulationBackground] Cannot apply image: ${e.message}")
        }
    }

    /** Opens the system picker and stores the chosen image. */
    fun pick(activity: AppCompatActivity, onDone: () -> Unit) {
        var launcher: ActivityResultLauncher<Array<String>>? = null
        launcher = activity.activityResultRegistry.register(
            "emulation_background_${System.nanoTime()}",
            ActivityResultContracts.OpenDocument()
        ) { uri ->
            launcher?.unregister()
            if (uri != null) {
                Thread {
                    val ok = save(activity, uri)
                    if (ok) applyToRenderer(activity)
                    activity.runOnUiThread {
                        Toast.makeText(
                            activity,
                            if (ok) R.string.emulation_background_set
                            else R.string.emulation_background_failed,
                            Toast.LENGTH_SHORT
                        ).show()
                        onDone()
                    }
                }.start()
            }
        }
        launcher.launch(arrayOf("image/*"))
    }
}
