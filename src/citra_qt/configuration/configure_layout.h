// Copyright 2019-2024 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#pragma once

#include <memory>
#include <QWidget>
#include "common/common_types.h"

namespace Settings {
enum class StereoRenderOption : u32;
}

namespace ConfigurationShared {
enum class CheckState;
}

namespace Ui {
class ConfigureLayout;
}

class CustomLayoutPreview;

class ConfigureLayout : public QWidget {
    Q_OBJECT

public:
    explicit ConfigureLayout(QWidget* parent = nullptr);
    ~ConfigureLayout();

    void ApplyConfiguration();
    void RetranslateUI();
    void SetConfiguration();

    void SetupPerGameUI();

private:
    /// Keeps the drag-and-drop picture and the number boxes of the custom layout in step
    void SetupCustomLayoutPreview();

    void updateShaders(Settings::StereoRenderOption stereo_option);
    void updateTextureFilter(int index);

    std::unique_ptr<Ui::ConfigureLayout> ui;
    CustomLayoutPreview* custom_layout_preview = nullptr;
    ConfigurationShared::CheckState swap_screen;
    ConfigurationShared::CheckState upright_screen;
    QColor bg_color;
};
