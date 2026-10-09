// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

package org.citra.citra_emu.features.settings.ui

import android.app.Dialog
import android.os.Bundle
import android.view.LayoutInflater
import androidx.fragment.app.DialogFragment
import com.google.android.material.button.MaterialButton
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.materialswitch.MaterialSwitch
import org.citra.citra_emu.R
import org.citra.citra_emu.utils.ComboHelper

/**
 * Eden-style dialog: one scrollable list with, for each of the 5 combo buttons, an
 * enable switch (the same state as the in-game Toggle Controls menu) and a button that
 * opens a checklist of what the combo presses. Cancel discards everything.
 */
class ComboButtonConfigDialogFragment : DialogFragment() {

    override fun onCreateDialog(savedInstanceState: Bundle?): Dialog {
        val ctx = requireContext()
        val root = LayoutInflater.from(ctx).inflate(R.layout.dialog_combo_buttons, null)

        val switchIds = intArrayOf(
            R.id.switch_combo_1, R.id.switch_combo_2, R.id.switch_combo_3,
            R.id.switch_combo_4, R.id.switch_combo_5
        )
        val buttonIds = intArrayOf(
            R.id.btn_combo_1, R.id.btn_combo_2, R.id.btn_combo_3,
            R.id.btn_combo_4, R.id.btn_combo_5
        )
        val switches = switchIds.map { root.findViewById<MaterialSwitch>(it) }
        val buttons = buttonIds.map { root.findViewById<MaterialButton>(it) }

        // Working copy so Cancel doesn't save
        val working = Array(ComboHelper.COMBO_COUNT) { ComboHelper.getButtons(it).toMutableList() }

        fun refreshLabel(i: Int) {
            buttons[i].text = ComboHelper.describe(ctx, working[i])
        }

        for (i in 0 until ComboHelper.COMBO_COUNT) {
            switches[i].isChecked = ComboHelper.isEnabled(ctx, i)
            refreshLabel(i)
            buttons[i].setOnClickListener { showPicker(i, working[i]) { refreshLabel(i) } }
        }

        return MaterialAlertDialogBuilder(ctx)
            .setTitle(R.string.combo_button_settings)
            .setView(root)
            .setPositiveButton(android.R.string.ok) { _, _ ->
                for (i in 0 until ComboHelper.COMBO_COUNT) {
                    ComboHelper.setEnabled(ctx, i, switches[i].isChecked)
                    ComboHelper.setButtons(ctx, i, working[i])
                }
            }
            .setNegativeButton(android.R.string.cancel, null)
            .setNeutralButton(R.string.reset_to_default) { _, _ ->
                for (i in 0 until ComboHelper.COMBO_COUNT) {
                    ComboHelper.setEnabled(ctx, i, false)
                    ComboHelper.resetButtons(ctx, i)
                }
            }
            .create()
    }

    private fun showPicker(index: Int, target: MutableList<Int>, onUpdate: () -> Unit) {
        val ctx = requireContext()
        val options = ComboHelper.options(ctx)
        val entries = options.map { it.second }.toTypedArray()
        val checked = BooleanArray(entries.size) { target.contains(options[it].first) }

        MaterialAlertDialogBuilder(ctx)
            .setTitle(getString(R.string.combo_button_n, index + 1))
            .setMultiChoiceItems(entries, checked) { _, which, isChecked ->
                val value = options[which].first
                if (isChecked) {
                    if (!target.contains(value)) target.add(value)
                } else {
                    target.remove(value)
                }
            }
            .setPositiveButton(android.R.string.ok) { _, _ -> onUpdate() }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    companion object {
        const val TAG = "ComboButtonConfigDialogFragment"
    }
}
