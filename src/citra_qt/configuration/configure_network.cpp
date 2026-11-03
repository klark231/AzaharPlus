// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#include <QCheckBox>
#include <QIcon>
#include <QMessageBox>
#include <QtConcurrent/QtConcurrentRun>
#include "citra_qt/configuration/configure_network.h"
#include "citra_qt/uisettings.h"
#include "ui_configure_network.h"

ConfigureWeb::ConfigureWeb(QWidget* parent)
    : QWidget(parent), ui(std::make_unique<Ui::ConfigureWeb>()) {
    ui->setupUi(this);

#ifndef USE_DISCORD_PRESENCE
    ui->discord_group->setEnabled(false);
#endif
#ifndef ENABLE_WEB_SERVICE
    ui->web_api_url_lineedit->setEnabled(false);
    ui->web_api_url_2_lineedit->setEnabled(false);
    ui->token_lineedit->setEnabled(false);
#endif
    SetConfiguration();

    for (QCheckBox* box : {ui->netsync_enabled, ui->auto_rejoin, ui->mhgu_hub_enabled}) {
        connect(box, &QCheckBox::toggled, this, &ConfigureWeb::UpdateMultiplayerEnabled);
    }
}

ConfigureWeb::~ConfigureWeb() = default;

void ConfigureWeb::SetConfiguration() {

    ui->web_api_url_lineedit->setText(
        QString::fromStdString(Settings::values.web_api_url.GetValue()));
    ui->web_api_url_2_lineedit->setText(
        QString::fromStdString(Settings::values.web_api_url_2.GetValue()));
    ui->token_lineedit->setText(QString::fromStdString(Settings::values.network_token.GetValue()));

    ui->netsync_enabled->setChecked(Settings::values.netsync_enabled.GetValue());
    ui->netsync_timeout_spinbox->setValue(Settings::values.netsync_timeout.GetValue());
    ui->auto_rejoin->setChecked(Settings::values.auto_rejoin.GetValue());
    ui->auto_rejoin_window_spinbox->setValue(Settings::values.auto_rejoin_window.GetValue());
    ui->auto_rejoin_pause->setChecked(Settings::values.auto_rejoin_pause.GetValue());
    ui->mhgu_hub_enabled->setChecked(Settings::values.mhgu_hub_enabled.GetValue());
    ui->mhgu_hub_servers->setText(
        QString::fromStdString(Settings::values.mhgu_hub_servers.GetValue()));
    ui->mhgu_hub_key->setText(QString::fromStdString(Settings::values.mhgu_hub_key.GetValue()));
    ui->mhgu_hub_convert->setChecked(Settings::values.mhgu_hub_convert.GetValue());
    ui->mhgu_hub_log->setChecked(Settings::values.mhgu_hub_log.GetValue());
    UpdateMultiplayerEnabled();

#ifdef ENABLE_DISCORD_RPC
    ui->toggle_discordrpc->setChecked(UISettings::values.enable_discord_presence.GetValue());
#endif
}

void ConfigureWeb::ApplyConfiguration() {
#ifdef USE_DISCORD_PRESENCE
    UISettings::values.enable_discord_presence = ui->toggle_discordrpc->isChecked();
#endif

    Settings::values.web_api_url = ui->web_api_url_lineedit->text().toStdString();
    Settings::values.web_api_url_2 = ui->web_api_url_2_lineedit->text().toStdString();
    Settings::values.network_token = ui->token_lineedit->text().toStdString();

    Settings::values.netsync_enabled = ui->netsync_enabled->isChecked();
    Settings::values.netsync_timeout = static_cast<u16>(ui->netsync_timeout_spinbox->value());
    Settings::values.auto_rejoin = ui->auto_rejoin->isChecked();
    Settings::values.auto_rejoin_window = static_cast<u16>(ui->auto_rejoin_window_spinbox->value());
    Settings::values.auto_rejoin_pause = ui->auto_rejoin_pause->isChecked();
    Settings::values.mhgu_hub_enabled = ui->mhgu_hub_enabled->isChecked();
    Settings::values.mhgu_hub_servers = ui->mhgu_hub_servers->text().trimmed().toStdString();
    Settings::values.mhgu_hub_key = ui->mhgu_hub_key->text().toStdString();
    Settings::values.mhgu_hub_convert = ui->mhgu_hub_convert->isChecked();
    Settings::values.mhgu_hub_log = ui->mhgu_hub_log->isChecked();
}

void ConfigureWeb::UpdateMultiplayerEnabled() {
    ui->netsync_timeout_spinbox->setEnabled(ui->netsync_enabled->isChecked());
    ui->auto_rejoin_window_spinbox->setEnabled(ui->auto_rejoin->isChecked());
    ui->auto_rejoin_pause->setEnabled(ui->auto_rejoin->isChecked());
    const bool hub = ui->mhgu_hub_enabled->isChecked();
    ui->mhgu_hub_servers->setEnabled(hub);
    ui->mhgu_hub_key->setEnabled(hub);
    ui->mhgu_hub_convert->setEnabled(hub);
    ui->mhgu_hub_log->setEnabled(hub);
}

void ConfigureWeb::RetranslateUI() {
    ui->retranslateUi(this);
}
