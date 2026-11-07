// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#include <QCheckBox>
#include <QHBoxLayout>
#include <QIcon>
#include <QLineEdit>
#include <QMessageBox>
#include <QRegularExpression>
#include <QToolButton>
#include <QtConcurrent/QtConcurrentRun>
#include "citra_qt/configuration/configure_network.h"
#include "citra_qt/uisettings.h"
#include "core/hle/service/nwm/mhgu_hub_proto.h"
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
    connect(ui->mhgu_hub_add_server, &QPushButton::clicked, this, [this] {
        AddHubServerRow({});
        UpdateHubServerButton();
    });
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
    while (auto* item = ui->mhgu_hub_servers_rows->takeAt(0)) {
        delete item->widget();
        delete item;
    }
    const auto names = QString::fromStdString(Settings::values.mhgu_hub_servers.GetValue())
                           .split(QRegularExpression(QStringLiteral("[\\s,;]+")), Qt::SkipEmptyParts);
    for (const QString& name : names) {
        if (static_cast<std::size_t>(ui->mhgu_hub_servers_rows->count()) < MhguHub::MaxServers) {
            AddHubServerRow(name);
        }
    }
    if (ui->mhgu_hub_servers_rows->count() == 0) {
        AddHubServerRow({});
    }
    UpdateHubServerButton();
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
    Settings::values.mhgu_hub_servers = HubServers().toStdString();
    Settings::values.mhgu_hub_key = ui->mhgu_hub_key->text().toStdString();
    Settings::values.mhgu_hub_convert = ui->mhgu_hub_convert->isChecked();
    Settings::values.mhgu_hub_log = ui->mhgu_hub_log->isChecked();
}

void ConfigureWeb::UpdateMultiplayerEnabled() {
    ui->netsync_timeout_spinbox->setEnabled(ui->netsync_enabled->isChecked());
    ui->auto_rejoin_window_spinbox->setEnabled(ui->auto_rejoin->isChecked());
    ui->auto_rejoin_pause->setEnabled(ui->auto_rejoin->isChecked());
    const bool hub = ui->mhgu_hub_enabled->isChecked();
    for (int i = 0; i < ui->mhgu_hub_servers_rows->count(); i++) {
        ui->mhgu_hub_servers_rows->itemAt(i)->widget()->setEnabled(hub);
    }
    ui->mhgu_hub_add_server->setEnabled(
        hub && static_cast<std::size_t>(ui->mhgu_hub_servers_rows->count()) < MhguHub::MaxServers);
    ui->mhgu_hub_key->setEnabled(hub);
    ui->mhgu_hub_convert->setEnabled(hub);
    ui->mhgu_hub_log->setEnabled(hub);
}

void ConfigureWeb::AddHubServerRow(const QString& name) {
    auto* row = new QWidget(this);
    auto* layout = new QHBoxLayout(row);
    layout->setContentsMargins(0, 0, 0, 0);
    auto* edit = new QLineEdit(name, row);
    edit->setPlaceholderText(tr("Server"));
    auto* remove = new QToolButton(row);
    remove->setText(QStringLiteral("\u2715"));
    layout->addWidget(edit, 1);
    layout->addWidget(remove);
    connect(remove, &QToolButton::clicked, this, [this, row] {
        ui->mhgu_hub_servers_rows->removeWidget(row);
        row->deleteLater();
        UpdateHubServerButton();
    });
    ui->mhgu_hub_servers_rows->addWidget(row);
    row->setEnabled(ui->mhgu_hub_enabled->isChecked());
}

void ConfigureWeb::UpdateHubServerButton() {
    const int count = ui->mhgu_hub_servers_rows->count();
    ui->mhgu_hub_add_server->setText(tr("Add server (%1/%2)").arg(count).arg(static_cast<int>(MhguHub::MaxServers)));
    ui->mhgu_hub_add_server->setEnabled(ui->mhgu_hub_enabled->isChecked() &&
                                        static_cast<std::size_t>(count) < MhguHub::MaxServers);
}

QString ConfigureWeb::HubServers() const {
    QStringList names;
    for (int i = 0; i < ui->mhgu_hub_servers_rows->count(); i++) {
        const auto* edit = ui->mhgu_hub_servers_rows->itemAt(i)->widget()->findChild<QLineEdit*>();
        const QString name = edit ? edit->text().simplified().remove(QLatin1Char(' ')) : QString{};
        if (!name.isEmpty()) {
            names << name;
        }
    }
    return names.join(QLatin1Char(' '));
}

void ConfigureWeb::RetranslateUI() {
    ui->retranslateUi(this);
    UpdateHubServerButton();
}
