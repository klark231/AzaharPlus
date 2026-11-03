// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

#pragma once

#include <array>
#include <string>
#include <QDialog>
#include "core/frontend/input_combo.h"

class QCheckBox;

/// Picks the 3DS buttons a combo button presses.
class ConfigureComboTargets : public QDialog {
    Q_OBJECT

public:
    /// targets: the combo's current list, as stored in the input profile ("l,r")
    ConfigureComboTargets(int combo_index, const std::string& targets, QWidget* parent = nullptr);

    /// The chosen list, in the same form
    std::string Targets() const;

    /// "L + R", or "None"
    static QString TargetsToText(const std::string& targets);

private:
    static QString TargetText(Input::Combo::Target target);

    std::array<QCheckBox*, static_cast<std::size_t>(Input::Combo::Target::NumTargets)> boxes{};
};
