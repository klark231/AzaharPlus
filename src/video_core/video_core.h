// Copyright 2014 Citra Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#pragma once

#include <memory>
#include <vector>
#include "common/common_types.h"

namespace Frontend {
class EmuWindow;
}

namespace Core {
class System;
}

namespace Pica {
class PicaCore;
}

namespace VideoCore {

class RendererBase;

/// User supplied background image, drawn behind the emulated screens (RGBA8, row 0 = top).
struct BackgroundImageData {
    std::vector<u32> pixels;
    u32 width = 0;
    u32 height = 0;
};

/// Sets the background image. Passing nullptr or a zero size removes it. Thread safe.
void SetBackgroundImage(const u32* rgba_pixels, u32 width, u32 height);

/// Increases every time the background image changes; renderers compare it to know when to
/// re-upload.
u64 GetBackgroundImageGeneration();

/// Copies the current background image.
void GetBackgroundImage(BackgroundImageData& out);

std::unique_ptr<RendererBase> CreateRenderer(Frontend::EmuWindow& emu_window,
                                             Frontend::EmuWindow* secondary_window,
                                             Pica::PicaCore& pica, Core::System& system);

} // namespace VideoCore
