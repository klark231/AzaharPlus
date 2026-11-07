// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#pragma once

#include <memory>
#include <QString>
#include <QWidget>

namespace Ui {
class ConfigureWeb;
}

class ConfigureWeb : public QWidget {
    Q_OBJECT

public:
    explicit ConfigureWeb(QWidget* parent = nullptr);
    ~ConfigureWeb() override;

    void ApplyConfiguration();
    void RetranslateUI();
    void SetConfiguration();

private:
    /// Greys out the options of a feature that is switched off
    void UpdateMultiplayerEnabled();

    /// The hub servers: one row each (the setting is the names separated by spaces)
    void AddHubServerRow(const QString& name);
    void UpdateHubServerButton();
    QString HubServers() const;

    std::unique_ptr<Ui::ConfigureWeb> ui;
};
