// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

// Combo buttons: one input that presses several 3DS buttons at once (for example L + R).
// Each combo of the input profile has its own binding (Settings::InputProfile::combo_buttons) and a
// list of what it presses (combo_targets). The HID and IR services create their buttons and sticks
// through these functions, so a combo shows up as if every one of its buttons was pressed.

#pragma once

#include <memory>
#include <string>
#include <string_view>
#include <vector>
#include "core/frontend/input.h"

namespace Input::Combo {

/// What a combo can press. Names are stored in the config, so don't rename them.
enum class Target {
    A,
    B,
    X,
    Y,
    Up,
    Down,
    Left,
    Right,
    L,
    R,
    ZL,
    ZR,
    Start,
    Select,
    CircleUp,
    CircleDown,
    CircleLeft,
    CircleRight,
    CStickUp,
    CStickDown,
    CStickLeft,
    CStickRight,
    NumTargets,
};

std::string_view TargetName(Target target);

/// "a,b,circle_up" -> targets (unknown names are skipped)
std::vector<Target> ParseTargets(std::string_view list);
std::string JoinTargets(const std::vector<Target>& targets);

/// Default combos: L + R, A + B, X + Y, ZL + ZR, none
std::string DefaultTargets(int index);

/// A button of the current input profile (Settings::NativeButton value), pressed by its own
/// binding or by any combo that includes it.
std::unique_ptr<ButtonDevice> CreateButton(int native_button);

/// The circle pad or C-stick of the current input profile (Settings::NativeAnalog value). While a
/// combo that includes one of its directions is held, that direction wins.
std::unique_ptr<AnalogDevice> CreateAnalog(int native_analog);

} // namespace Input::Combo
