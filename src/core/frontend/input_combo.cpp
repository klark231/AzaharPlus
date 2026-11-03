// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

#include <array>
#include <cmath>
#include <tuple>
#include <utility>
#include "common/settings.h"
#include "core/frontend/input_combo.h"

namespace Input::Combo {

namespace {

constexpr std::array<std::string_view, static_cast<std::size_t>(Target::NumTargets)> names = {
    "a",     "b",      "x",         "y",           "up",          "down",
    "left",  "right",  "l",         "r",           "zl",          "zr",
    "start", "select", "circle_up", "circle_down", "circle_left", "circle_right",
    "c_up",  "c_down", "c_left",    "c_right",
};

/// The combo target a native button corresponds to, or NumTargets
Target ButtonTarget(int native_button) {
    using namespace Settings::NativeButton;
    switch (native_button) {
    case A:
        return Target::A;
    case B:
        return Target::B;
    case X:
        return Target::X;
    case Y:
        return Target::Y;
    case Up:
        return Target::Up;
    case Down:
        return Target::Down;
    case Left:
        return Target::Left;
    case Right:
        return Target::Right;
    case L:
        return Target::L;
    case R:
        return Target::R;
    case ZL:
        return Target::ZL;
    case ZR:
        return Target::ZR;
    case Start:
        return Target::Start;
    case Select:
        return Target::Select;
    default:
        return Target::NumTargets;
    }
}

bool Includes(const std::vector<Target>& targets, Target t) {
    for (const Target x : targets) {
        if (x == t) {
            return true;
        }
    }
    return false;
}

/// The bindings of the current profile's combos that press `t`
std::vector<std::unique_ptr<ButtonDevice>> CombosFor(Target t) {
    std::vector<std::unique_ptr<ButtonDevice>> out;
    const auto& profile = Settings::values.current_input_profile;
    for (std::size_t i = 0; i < profile.combo_buttons.size(); i++) {
        if (profile.combo_buttons[i].empty() ||
            !Includes(ParseTargets(profile.combo_targets[i]), t)) {
            continue;
        }
        out.push_back(CreateDevice<ButtonDevice>(profile.combo_buttons[i]));
    }
    return out;
}

bool AnyPressed(const std::vector<std::unique_ptr<ButtonDevice>>& devices) {
    for (const auto& d : devices) {
        if (d->GetStatus()) {
            return true;
        }
    }
    return false;
}

class ComboButton final : public ButtonDevice {
public:
    ComboButton(std::unique_ptr<ButtonDevice> own_,
                std::vector<std::unique_ptr<ButtonDevice>> combos_)
        : own(std::move(own_)), combos(std::move(combos_)) {}

    bool GetStatus() const override {
        return own->GetStatus() || AnyPressed(combos);
    }

private:
    std::unique_ptr<ButtonDevice> own;
    std::vector<std::unique_ptr<ButtonDevice>> combos;
};

class ComboAnalog final : public AnalogDevice {
public:
    ComboAnalog(std::unique_ptr<AnalogDevice> own_,
                std::array<std::vector<std::unique_ptr<ButtonDevice>>, 4> dirs_)
        : own(std::move(own_)), dirs(std::move(dirs_)) {}

    std::tuple<float, float> GetStatus() const override {
        const bool up = AnyPressed(dirs[0]);
        const bool down = AnyPressed(dirs[1]);
        const bool left = AnyPressed(dirs[2]);
        const bool right = AnyPressed(dirs[3]);
        if (!up && !down && !left && !right) {
            return own->GetStatus();
        }
        float x = static_cast<float>(right) - static_cast<float>(left);
        float y = static_cast<float>(up) - static_cast<float>(down);
        if (x != 0.0f && y != 0.0f) {
            // keep diagonals on the unit circle, like a stick bound to keys
            x *= std::sqrt(0.5f);
            y *= std::sqrt(0.5f);
        }
        return {x, y};
    }

private:
    std::unique_ptr<AnalogDevice> own;
    std::array<std::vector<std::unique_ptr<ButtonDevice>>, 4> dirs; // up, down, left, right
};

} // namespace

std::string_view TargetName(Target target) {
    const auto i = static_cast<std::size_t>(target);
    return i < names.size() ? names[i] : std::string_view{};
}

std::vector<Target> ParseTargets(std::string_view list) {
    std::vector<Target> out;
    while (!list.empty()) {
        const std::size_t comma = list.find(',');
        std::string_view item = list.substr(0, comma);
        list = comma == std::string_view::npos ? std::string_view{} : list.substr(comma + 1);
        while (!item.empty() && item.front() == ' ') {
            item.remove_prefix(1);
        }
        while (!item.empty() && item.back() == ' ') {
            item.remove_suffix(1);
        }
        for (std::size_t i = 0; i < names.size(); i++) {
            if (item == names[i] && !Includes(out, static_cast<Target>(i))) {
                out.push_back(static_cast<Target>(i));
            }
        }
    }
    return out;
}

std::string JoinTargets(const std::vector<Target>& targets) {
    std::string out;
    for (const Target t : targets) {
        if (!out.empty()) {
            out += ',';
        }
        out += TargetName(t);
    }
    return out;
}

std::string DefaultTargets(int index) {
    switch (index) {
    case 0:
        return "l,r";
    case 1:
        return "a,b";
    case 2:
        return "x,y";
    case 3:
        return "zl,zr";
    default:
        return "";
    }
}

std::unique_ptr<ButtonDevice> CreateButton(int native_button) {
    auto own =
        CreateDevice<ButtonDevice>(Settings::values.current_input_profile.buttons[native_button]);
    const Target t = ButtonTarget(native_button);
    if (t == Target::NumTargets) {
        return own;
    }
    auto combos = CombosFor(t);
    if (combos.empty()) {
        return own;
    }
    return std::make_unique<ComboButton>(std::move(own), std::move(combos));
}

std::unique_ptr<AnalogDevice> CreateAnalog(int native_analog) {
    auto own =
        CreateDevice<AnalogDevice>(Settings::values.current_input_profile.analogs[native_analog]);
    const bool circle = native_analog == Settings::NativeAnalog::CirclePad;
    const Target first = circle ? Target::CircleUp : Target::CStickUp;
    std::array<std::vector<std::unique_ptr<ButtonDevice>>, 4> dirs;
    bool any = false;
    for (std::size_t i = 0; i < dirs.size(); i++) {
        dirs[i] = CombosFor(static_cast<Target>(static_cast<int>(first) + static_cast<int>(i)));
        any = any || !dirs[i].empty();
    }
    if (!any) {
        return own;
    }
    return std::make_unique<ComboAnalog>(std::move(own), std::move(dirs));
}

} // namespace Input::Combo
