// Native ETC1 upload support (experimental).
// Converts 3DS Morton-tiled ETC1 data into linear, vertically flipped, standard-endian
// ETC1 blocks that Vulkan can sample directly as VK_FORMAT_ETC2_R8G8B8_UNORM_BLOCK.
// Licensed under GPLv2 or any later version.

#pragma once

#include <cstdlib>
#include <cstring>
#include <span>
#include "common/common_types.h"

// Set to 1 to use the native path by default. Env var AZAHAR_NATIVE_ETC1=0/1 overrides.
#ifndef AZAHAR_NATIVE_ETC1_DEFAULT
#define AZAHAR_NATIVE_ETC1_DEFAULT 1
#endif

namespace VideoCore {

/// Returns whether the user/build asked for native ETC1 textures.
inline bool NativeEtc1Requested() {
    static const bool requested = [] {
        if (const char* env = std::getenv("AZAHAR_NATIVE_ETC1")) {
            return env[0] == '1';
        }
        return AZAHAR_NATIVE_ETC1_DEFAULT != 0;
    }();
    return requested;
}

namespace detail {

/// Reverses the y order of a 16-bit ETC1 index plane (bit = 4 * x + y).
constexpr u32 FlipPlaneVertically(u32 plane) {
    u32 result = 0;
    for (u32 x = 0; x < 4; x++) {
        const u32 nib = (plane >> (4 * x)) & 0xF;
        const u32 rev = ((nib & 1) << 3) | ((nib & 2) << 1) | ((nib & 4) >> 1) | ((nib & 8) >> 3);
        result |= rev << (4 * x);
    }
    return result;
}

constexpr u64 SetField(u64 value, u32 shift, u32 bits, u64 field) {
    const u64 mask = ((1ull << bits) - 1) << shift;
    return (value & ~mask) | ((field << shift) & mask);
}

/// Takes a 3DS ETC1 block (little endian u64 value) and returns the same block mirrored
/// vertically (y -> 3 - y), still in the 3DS u64 layout.
constexpr u64 FlipETC1BlockVertically(u64 raw) {
    u64 out = raw & ~0xFFFFFFFFull;
    out |= FlipPlaneVertically(static_cast<u32>(raw & 0xFFFF));
    out |= static_cast<u64>(FlipPlaneVertically(static_cast<u32>((raw >> 16) & 0xFFFF))) << 16;

    const bool flip_bit = ((raw >> 32) & 1) != 0;
    if (!flip_bit) {
        // Sub-blocks are the left/right halves, mirroring vertically leaves them in place.
        return out;
    }

    // Sub-blocks are the top/bottom halves, so they trade places.
    const u64 table2 = (raw >> 34) & 7;
    const u64 table1 = (raw >> 37) & 7;
    out = SetField(out, 34, 3, table1);
    out = SetField(out, 37, 3, table2);

    const bool differential = ((raw >> 33) & 1) != 0;
    if (differential) {
        constexpr u32 base_shift[3] = {59, 51, 43};
        constexpr u32 delta_shift[3] = {56, 48, 40};
        for (u32 c = 0; c < 3; c++) {
            const int base = static_cast<int>((raw >> base_shift[c]) & 31);
            int delta = static_cast<int>((raw >> delta_shift[c]) & 7);
            if (delta >= 4) {
                delta -= 8;
            }
            int second = base + delta;
            second = second < 0 ? 0 : (second > 31 ? 31 : second);
            // -delta can be +4 which does not fit the 3 bit signed field; clamp (tiny error).
            int new_delta = base - second;
            new_delta = new_delta < -4 ? -4 : (new_delta > 3 ? 3 : new_delta);
            out = SetField(out, base_shift[c], 5, static_cast<u64>(second));
            out = SetField(out, delta_shift[c], 3, static_cast<u64>(new_delta & 7));
        }
    } else {
        constexpr u32 first_shift[3] = {60, 52, 44};
        constexpr u32 second_shift[3] = {56, 48, 40};
        for (u32 c = 0; c < 3; c++) {
            const u64 first = (raw >> first_shift[c]) & 0xF;
            const u64 second = (raw >> second_shift[c]) & 0xF;
            out = SetField(out, first_shift[c], 4, second);
            out = SetField(out, second_shift[c], 4, first);
        }
    }
    return out;
}

} // namespace detail

/**
 * Converts tiled 3DS ETC1 data into a linear grid of standard ETC1 blocks.
 *
 * Output layout matches what the regular decode path produces: rows are stored bottom-up and
 * every block is mirrored vertically, so the result can be uploaded with the same
 * VkBufferImageCopy as the decoded RGBA8 data (bufferRowLength = width).
 *
 * @param width, height Dimensions in pixels of the rectangle being uploaded (multiples of 8)
 * @param start_offset, end_offset Byte range of the tiled source (relative to the rectangle)
 * @param linear_buffer Output, (width / 4) * (height / 4) * 8 bytes
 * @param tiled_buffer Input, the 3DS tiled ETC1 data beginning at start_offset
 */
inline void ConvertETC1ToNative(u32 width, u32 height, u32 start_offset, u32 end_offset,
                                std::span<u8> linear_buffer, std::span<u8> tiled_buffer) {
    constexpr u32 TILE_BYTES = 32; // 8x8 pixels, 4 blocks of 8 bytes
    constexpr u32 BLOCK_BYTES = 8;

    if (width < 8 || height < 8) {
        return;
    }
    const u32 tiles_per_row = width / 8;
    const u32 blocks_per_row = width / 4;
    const u32 block_rows = height / 4;

    const u32 first_tile = start_offset / TILE_BYTES;
    const u32 last_tile = end_offset / TILE_BYTES;

    for (u32 tile = first_tile; tile < last_tile; tile++) {
        const u32 tx = tile % tiles_per_row;
        const u32 ty = tile / tiles_per_row;
        for (u32 s = 0; s < 4; s++) {
            const u32 bx = tx * 2 + (s & 1);
            const u32 by = ty * 2 + (s >> 1);
            if (by >= block_rows) {
                continue;
            }
            const std::size_t src_offset = std::size_t(tile - first_tile) * TILE_BYTES +
                                           std::size_t(s) * BLOCK_BYTES;
            const std::size_t dst_offset =
                (std::size_t(block_rows - 1 - by) * blocks_per_row + bx) * BLOCK_BYTES;
            if (src_offset + BLOCK_BYTES > tiled_buffer.size() ||
                dst_offset + BLOCK_BYTES > linear_buffer.size()) {
                continue;
            }

            u64 raw = 0;
            for (u32 i = 0; i < 8; i++) { // little endian read, endian independent
                raw |= static_cast<u64>(tiled_buffer[src_offset + i]) << (8 * i);
            }
            raw = detail::FlipETC1BlockVertically(raw);

            // Standard ETC1 stores the same 64 bits big endian.
            u8* dst = linear_buffer.data() + dst_offset;
            for (u32 i = 0; i < 8; i++) {
                dst[i] = static_cast<u8>(raw >> (8 * (7 - i)));
            }
        }
    }
}

} // namespace VideoCore
