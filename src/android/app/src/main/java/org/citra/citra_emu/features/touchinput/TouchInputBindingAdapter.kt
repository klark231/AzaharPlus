// Copyright Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version.
// Refer to the license.txt file included.

package org.citra.citra_emu.features.touchinput

import android.graphics.Color
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.appcompat.widget.PopupMenu
import androidx.core.graphics.ColorUtils
import androidx.recyclerview.widget.DiffUtil
import androidx.recyclerview.widget.ListAdapter
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.color.MaterialColors
import org.citra.citra_emu.R
import org.citra.citra_emu.databinding.ItemTouchInputBindingBinding

class TouchInputBindingAdapter(
    private val onRowClicked: (TouchInputBinding) -> Unit,
    private val onEditClicked: (TouchInputBinding) -> Unit,
    private val onDeleteClicked: (TouchInputBinding) -> Unit
) : ListAdapter<TouchInputBinding, TouchInputBindingAdapter.ViewHolder>(DiffCallback) {
    /** The binding whose row is highlighted, or null for none. */
    var selectedBinding: TouchInputBinding? = null
        set(value) {
            if (field == value) return
            field = value
            notifyItemRangeChanged(0, itemCount, PAYLOAD_REFRESH)
        }

    /**
     * Row numbers and dividers depend on the position in the list, so rows that only moved still
     * need refreshing. The payload keeps that refresh silent, without a change animation.
     */
    override fun submitList(list: List<TouchInputBinding>?) {
        super.submitList(list) {
            notifyItemRangeChanged(0, itemCount, PAYLOAD_REFRESH)
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val binding = ItemTouchInputBindingBinding.inflate(
            LayoutInflater.from(parent.context),
            parent,
            false
        )
        return ViewHolder(binding)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        holder.bind(position, getItem(position))
    }

    override fun onBindViewHolder(
        holder: ViewHolder,
        position: Int,
        payloads: MutableList<Any>
    ) {
        if (payloads.isEmpty()) {
            super.onBindViewHolder(holder, position, payloads)
        } else {
            holder.refresh(position, getItem(position))
        }
    }

    inner class ViewHolder(
        private val binding: ItemTouchInputBindingBinding
    ) : RecyclerView.ViewHolder(binding.root) {
        private val selectedColor = ColorUtils.setAlphaComponent(
            MaterialColors.getColor(binding.root, androidx.appcompat.R.attr.colorPrimary),
            SELECTED_ALPHA
        )

        fun bind(position: Int, touchBinding: TouchInputBinding) {
            refresh(position, touchBinding)

            binding.bindingName.text = touchBinding.displayName()
            binding.bindingCoordinates.text = touchBinding.positionLabel()
            binding.root.setOnClickListener { onRowClicked(touchBinding) }
            binding.menuButton.setOnClickListener { showMenu(touchBinding) }
        }

        /** Updates what depends on the position in the list and on the selection. */
        fun refresh(position: Int, touchBinding: TouchInputBinding) {
            binding.bindingNumber.text = (position + 1).toString()
            binding.divider.visibility = if (position == 0) View.GONE else View.VISIBLE
            binding.root.setBackgroundColor(
                if (touchBinding == selectedBinding) selectedColor else Color.TRANSPARENT
            )
        }

        private fun showMenu(touchBinding: TouchInputBinding) {
            PopupMenu(binding.root.context, binding.menuButton).apply {
                menu.add(0, MENU_EDIT, 0, R.string.edit)
                menu.add(0, MENU_DELETE, 1, R.string.delete)

                setOnMenuItemClickListener { item ->
                    when (item.itemId) {
                        MENU_EDIT -> onEditClicked(touchBinding)
                        MENU_DELETE -> onDeleteClicked(touchBinding)
                        else -> return@setOnMenuItemClickListener false
                    }
                    true
                }
                show()
            }
        }
    }

    private object DiffCallback : DiffUtil.ItemCallback<TouchInputBinding>() {
        // A binding is identified by the physical input it listens to
        override fun areItemsTheSame(
            oldItem: TouchInputBinding,
            newItem: TouchInputBinding
        ): Boolean = oldItem.hasSameInputAs(newItem)

        override fun areContentsTheSame(
            oldItem: TouchInputBinding,
            newItem: TouchInputBinding
        ): Boolean = oldItem == newItem
    }

    private companion object {
        const val PAYLOAD_REFRESH = "refresh"
        const val SELECTED_ALPHA = 36

        const val MENU_EDIT = 1
        const val MENU_DELETE = 2
    }
}
