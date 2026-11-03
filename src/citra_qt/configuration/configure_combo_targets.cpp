// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the license.txt file included.

#include <initializer_list>
#include <QCheckBox>
#include <QDialogButtonBox>
#include <QGridLayout>
#include <QGroupBox>
#include <QLabel>
#include <QPushButton>
#include <QStringList>
#include <QVBoxLayout>
#include "citra_qt/configuration/configure_combo_targets.h"

using Input::Combo::Target;

ConfigureComboTargets::ConfigureComboTargets(int combo_index, const std::string& targets,
                                             QWidget* parent)
    : QDialog(parent) {
    setWindowTitle(tr("Combo %1").arg(combo_index + 1));

    auto* layout = new QVBoxLayout(this);
    auto* hint = new QLabel(tr("Holding the combo's input presses all the buttons checked here."));
    hint->setWordWrap(true);
    layout->addWidget(hint);

    // one group per part of the console, laid out like the button mapping page
    const auto add_group = [&](const QString& title, std::initializer_list<Target> members,
                               int columns) {
        auto* box = new QGroupBox(title);
        auto* grid = new QGridLayout(box);
        int n = 0;
        for (const Target t : members) {
            auto* check = new QCheckBox(TargetText(t));
            boxes[static_cast<std::size_t>(t)] = check;
            grid->addWidget(check, n / columns, n % columns);
            n++;
        }
        return box;
    };

    auto* top = new QGridLayout;
    top->addWidget(add_group(tr("Face Buttons"), {Target::A, Target::B, Target::X, Target::Y}, 2),
                   0, 0);
    top->addWidget(add_group(tr("Directional Pad"),
                             {Target::Up, Target::Down, Target::Left, Target::Right}, 2),
                   0, 1);
    top->addWidget(
        add_group(tr("Shoulder Buttons"), {Target::L, Target::R, Target::ZL, Target::ZR}, 2), 1, 0);
    top->addWidget(add_group(tr("Misc."), {Target::Start, Target::Select}, 2), 1, 1);
    top->addWidget(
        add_group(tr("Circle Pad"),
                  {Target::CircleUp, Target::CircleDown, Target::CircleLeft, Target::CircleRight},
                  2),
        2, 0);
    top->addWidget(
        add_group(tr("C-Stick"),
                  {Target::CStickUp, Target::CStickDown, Target::CStickLeft, Target::CStickRight},
                  2),
        2, 1);
    layout->addLayout(top);

    for (const Target t : Input::Combo::ParseTargets(targets)) {
        boxes[static_cast<std::size_t>(t)]->setChecked(true);
    }

    auto* buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);
    auto* clear = buttons->addButton(tr("Clear"), QDialogButtonBox::ResetRole);
    connect(clear, &QPushButton::clicked, this, [this] {
        for (auto* check : boxes) {
            check->setChecked(false);
        }
    });
    connect(buttons, &QDialogButtonBox::accepted, this, &QDialog::accept);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
    layout->addWidget(buttons);
}

std::string ConfigureComboTargets::Targets() const {
    std::vector<Target> chosen;
    for (std::size_t i = 0; i < boxes.size(); i++) {
        if (boxes[i]->isChecked()) {
            chosen.push_back(static_cast<Target>(i));
        }
    }
    return Input::Combo::JoinTargets(chosen);
}

QString ConfigureComboTargets::TargetsToText(const std::string& targets) {
    QStringList parts;
    for (const Target t : Input::Combo::ParseTargets(targets)) {
        parts << TargetText(t);
    }
    return parts.isEmpty() ? tr("None") : parts.join(QStringLiteral(" + "));
}

QString ConfigureComboTargets::TargetText(Target target) {
    switch (target) {
    case Target::A:
        return QStringLiteral("A");
    case Target::B:
        return QStringLiteral("B");
    case Target::X:
        return QStringLiteral("X");
    case Target::Y:
        return QStringLiteral("Y");
    case Target::Up:
        return tr("Up");
    case Target::Down:
        return tr("Down");
    case Target::Left:
        return tr("Left");
    case Target::Right:
        return tr("Right");
    case Target::L:
        return QStringLiteral("L");
    case Target::R:
        return QStringLiteral("R");
    case Target::ZL:
        return QStringLiteral("ZL");
    case Target::ZR:
        return QStringLiteral("ZR");
    case Target::Start:
        return tr("Start");
    case Target::Select:
        return tr("Select");
    case Target::CircleUp:
        return tr("Circle Up");
    case Target::CircleDown:
        return tr("Circle Down");
    case Target::CircleLeft:
        return tr("Circle Left");
    case Target::CircleRight:
        return tr("Circle Right");
    case Target::CStickUp:
        return tr("C-Stick Up");
    case Target::CStickDown:
        return tr("C-Stick Down");
    case Target::CStickLeft:
        return tr("C-Stick Left");
    case Target::CStickRight:
        return tr("C-Stick Right");
    default:
        return {};
    }
}
