// Copyright 2026 Eden Emulator Project / lsfg-vk (2025)
// Adapted for Azahar Plus. Licensed under GPLv3 or any later version.

#pragma once

#include <span>
#include <vector>

#include "common/common_types.h"

namespace VideoCore::FrameGen {

[[nodiscard]] bool IsSpirvModule(std::span<const u8> blob);

[[nodiscard]] std::vector<u32> AdoptSpirvModule(std::span<const u8> blob);

} // namespace VideoCore::FrameGen
