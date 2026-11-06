// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

package org.citra.citra_emu.overlay

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.text.InputFilter
import android.view.LayoutInflater
import android.view.WindowManager
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import org.citra.citra_emu.NativeLibrary
import org.citra.citra_emu.R

/**
 * Monster Hunter XX has its own touch keyboard, which is slow. While the game is waiting for text,
 * this shows an Android text box instead and types the result into the game's keyboard.
 *
 * Text longer than the game's limit is sent as several messages: the first goes in, then START is
 * pressed to open the game's keyboard again (as in the chat menu) and the next part goes in.
 *
 * Cancel leaves the game's keyboard open to use as usual (or to cancel in the game).
 */
class MhxxKeyboardWatcher(private val context: Context) {
    private val handler = Handler(Looper.getMainLooper())
    private var dialog: AlertDialog? = null
    private var keyboardWasOpen = false

    // Parts of a long message that still have to be typed.
    private val queue = ArrayDeque<String>()
    private var awaitingClose = false // the last part was queued but the game has not taken it yet
    private var startPressed = false
    private var stepSince = 0L

    private val poll = object : Runnable {
        override fun run() {
            check()
            handler.postDelayed(this, POLL_INTERVAL_MS)
        }
    }

    fun start() {
        handler.post(poll)
    }

    fun stop() {
        handler.removeCallbacks(poll)
        dialog?.dismiss()
        dialog = null
        keyboardWasOpen = false
        abandonQueue()
    }

    private fun check() {
        val open = NativeLibrary.mhxxKeyboardOpen()
        if (awaitingClose || queue.isNotEmpty()) {
            continueMessage(open)
            keyboardWasOpen = open
            return
        }
        if (open && !keyboardWasOpen) {
            showDialog()
        } else if (!open) {
            dialog?.dismiss() // the game closed its keyboard, e.g. from its own cancel button
        }
        keyboardWasOpen = open
    }

    /** Drives the remaining parts of a long message. */
    private fun continueMessage(open: Boolean) {
        val now = System.currentTimeMillis()
        if (awaitingClose) {
            // The game takes the text a moment after it is queued; wait until the keyboard closes.
            if (!open) {
                awaitingClose = false
                startPressed = false
                stepSince = now
            } else if (now - stepSince > TAKE_TIMEOUT_MS) {
                abandonQueue()
            }
            return
        }
        if (open) {
            typeNextPart()
            return
        }
        if (!startPressed && now - stepSince >= START_DELAY_MS) {
            pressStart()
            startPressed = true
            stepSince = now
        } else if (startPressed && now - stepSince > REOPEN_TIMEOUT_MS) {
            abandonQueue()
            Toast.makeText(
                context,
                "The game keyboard did not open again, so the rest was not sent",
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    private fun typeNextPart() {
        if (NativeLibrary.mhxxInjectText(queue.removeFirst())) {
            awaitingClose = true
            stepSince = System.currentTimeMillis()
        } else {
            abandonQueue()
        }
    }

    private fun abandonQueue() {
        queue.clear()
        awaitingClose = false
        startPressed = false
    }

    private fun pressStart() {
        val start = NativeLibrary.ButtonType.BUTTON_START
        NativeLibrary.onGamePadEvent("", start, NativeLibrary.ButtonState.PRESSED)
        handler.postDelayed({
            NativeLibrary.onGamePadEvent("", start, NativeLibrary.ButtonState.RELEASED)
        }, START_HOLD_MS)
    }

    private fun showDialog() {
        val view = LayoutInflater.from(context).inflate(R.layout.dialog_mhxx_keyboard, null)
        view.findViewById<TextInputLayout>(R.id.mhxx_input_layout).apply {
            isCounterEnabled = true
            counterMaxLength = MAX_TOTAL_CHARS
        }
        val input = view.findViewById<TextInputEditText>(R.id.mhxx_input).apply {
            filters = arrayOf(InputFilter.LengthFilter(MAX_TOTAL_CHARS))
        }

        val newDialog = MaterialAlertDialogBuilder(context)
            .setTitle(R.string.mhxx_keyboard_title)
            .setView(view)
            .setPositiveButton(android.R.string.ok) { _, _ -> send(input.text.toString()) }
            .setNegativeButton(android.R.string.cancel, null)
            .setOnDismissListener { dialog = null }
            .create()
        input.setOnEditorActionListener { _, _, _ ->
            send(input.text.toString())
            newDialog.dismiss()
            true
        }

        dialog = newDialog
        newDialog.show()
        newDialog.window?.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE)
        input.requestFocus()
    }

    private fun send(text: String) {
        val parts = split(text.trim())
        if (parts.isEmpty()) return
        queue.clear()
        queue.addAll(parts.drop(1))
        if (NativeLibrary.mhxxInjectText(parts.first())) {
            awaitingClose = true
            startPressed = false
            stepSince = System.currentTimeMillis()
        } else {
            queue.clear()
        }
    }

    /** Cuts the text into parts the game accepts, at spaces where possible. */
    private fun split(text: String): List<String> {
        val parts = mutableListOf<String>()
        var rest = text
        while (rest.isNotEmpty() && parts.size < MAX_PARTS) {
            if (rest.length <= MAX_PART_CHARS) {
                parts.add(rest)
                break
            }
            var cut = rest.lastIndexOf(' ', MAX_PART_CHARS)
            if (cut < MIN_PART_CHARS) cut = MAX_PART_CHARS
            if (Character.isHighSurrogate(rest[cut - 1])) cut--
            parts.add(rest.substring(0, cut).trim())
            rest = rest.substring(cut).trim()
        }
        return parts.filter { it.isNotEmpty() }
    }

    private companion object {
        const val POLL_INTERVAL_MS = 250L
        const val MAX_PART_CHARS = 28 // what fits in the game's result buffer
        const val MIN_PART_CHARS = 10 // do not cut a part shorter than this at a space
        const val MAX_PARTS = 4
        const val MAX_TOTAL_CHARS = MAX_PART_CHARS * MAX_PARTS
        const val START_DELAY_MS = 700L   // let the game finish the message before the next one
        const val START_HOLD_MS = 120L
        const val TAKE_TIMEOUT_MS = 3000L
        const val REOPEN_TIMEOUT_MS = 4500L
    }
}
