// Copyright 2017-2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#include <algorithm>
#include <chrono>
#include <future>
#include <vector>
#include "announce_multiplayer_session.h"
#include "common/announce_multiplayer_room.h"
#include "common/assert.h"
#include "network/network.h"

#ifdef ENABLE_WEB_SERVICE
#include "web_service/announce_room_json.h"
#endif

namespace Network {

// Time between room is announced to web_service
static constexpr std::chrono::seconds announce_time_interval(15);

AnnounceMultiplayerSession::AnnounceMultiplayerSession(const std::string& username_)
    : username(username_) {
#ifdef ENABLE_WEB_SERVICE
    backend =
        std::make_unique<WebService::RoomJson>(Settings::values.web_api_url.GetValue(), username,
                                               Settings::values.network_token.GetValue());
#else
    backend = std::make_unique<AnnounceMultiplayerRoom::NullBackend>();
#endif
}

Common::WebResult AnnounceMultiplayerSession::Register() {
    std::shared_ptr<Network::Room> room = Network::GetRoom().lock();
    if (!room) {
        return Common::WebResult{Common::WebResult::Code::LibError, "Network is not initialized"};
    }
    if (room->GetState() != Network::Room::State::Open) {
        return Common::WebResult{Common::WebResult::Code::LibError, "Room is not open"};
    }
    UpdateBackendData(room);
    Common::WebResult result = backend->Register();
    if (result.result_code != Common::WebResult::Code::Success) {
        return result;
    }
    LOG_INFO(WebService, "Room has been registered");
    room->SetVerifyUID(result.returned_data);
    registered = true;
    return Common::WebResult{Common::WebResult::Code::Success};
}

void AnnounceMultiplayerSession::Start() {
    if (announce_multiplayer_thread) {
        Stop();
    }
    shutdown_event.Reset();
    announce_multiplayer_thread =
        std::make_unique<std::thread>(&AnnounceMultiplayerSession::AnnounceMultiplayerLoop, this);
}

void AnnounceMultiplayerSession::Stop() {
    if (announce_multiplayer_thread) {
        shutdown_event.Set();
        announce_multiplayer_thread->join();
        announce_multiplayer_thread.reset();
        backend->Delete();
        registered = false;
    }
}

AnnounceMultiplayerSession::CallbackHandle AnnounceMultiplayerSession::BindErrorCallback(
    std::function<void(const Common::WebResult&)> function) {
    std::lock_guard lock(callback_mutex);
    auto handle = std::make_shared<std::function<void(const Common::WebResult&)>>(function);
    error_callbacks.insert(handle);
    return handle;
}

void AnnounceMultiplayerSession::UnbindErrorCallback(CallbackHandle handle) {
    std::lock_guard lock(callback_mutex);
    error_callbacks.erase(handle);
}

AnnounceMultiplayerSession::~AnnounceMultiplayerSession() {
    Stop();
}

void AnnounceMultiplayerSession::UpdateBackendData(std::shared_ptr<Network::Room> room) {
    Network::RoomInformation room_information = room->GetRoomInformation();
    std::vector<Network::Room::Member> memberlist = room->GetRoomMemberList();
    backend->SetRoomInformation(
        room_information.name, room_information.description, room_information.port,
        room_information.member_slots, Network::network_version, room->HasPassword(),
        room_information.preferred_game, room_information.preferred_game_id);
    backend->ClearPlayers();
    for (const auto& member : memberlist) {
        backend->AddPlayer(member.username, member.nickname, member.avatar_url, member.mac_address,
                           member.game_info.id, member.game_info.name);
    }
}

void AnnounceMultiplayerSession::AnnounceMultiplayerLoop() {
    // Invokes all current bound error callbacks.
    const auto ErrorCallback = [this](Common::WebResult result) {
        std::lock_guard<std::mutex> lock(callback_mutex);
        for (auto callback : error_callbacks) {
            (*callback)(result);
        }
    };

    if (!registered) {
        Common::WebResult result = Register();
        if (result.result_code != Common::WebResult::Code::Success) {
            ErrorCallback(result);
            return;
        }
    }

    auto update_time = std::chrono::steady_clock::now();
    std::future<Common::WebResult> future;
    while (!shutdown_event.WaitUntil(update_time)) {
        update_time += announce_time_interval;
        std::shared_ptr<Network::Room> room = Network::GetRoom().lock();
        if (!room) {
            break;
        }
        if (room->GetState() != Network::Room::State::Open) {
            break;
        }
        UpdateBackendData(room);
        Common::WebResult result = backend->Update();
        if (result.result_code != Common::WebResult::Code::Success) {
            ErrorCallback(result);
        }
        if (result.result_string == "404") {
            registered = false;
            // Needs to register the room again
            Common::WebResult new_result = Register();
            if (new_result.result_code != Common::WebResult::Code::Success) {
                ErrorCallback(new_result);
            }
        }
    }
}

AnnounceMultiplayerRoom::RoomList AnnounceMultiplayerSession::GetRoomList() {
#ifdef ENABLE_WEB_SERVICE
    using AnnounceMultiplayerRoom::RoomList;

    // Query the secondary server (if configured) in parallel so a slow or dead server doesn't add
    // to the wait of the primary one.
    const std::string primary_url = Settings::values.web_api_url.GetValue();
    const std::string secondary_url = Settings::values.web_api_url_2.GetValue();
    std::future<RoomList> secondary;
    if (!secondary_url.empty() && secondary_url != primary_url) {
        secondary = std::async(
            std::launch::async,
            [secondary_url, name = username, token = Settings::values.network_token.GetValue()] {
                try {
                    return WebService::RoomJson{secondary_url, name, token}.GetRoomList();
                } catch (const std::exception& e) {
                    LOG_ERROR(WebService, "Failed to get room list from {}: {}", secondary_url,
                              e.what());
                    return RoomList{};
                }
            });
    }

    // A failing server must never hide the rooms of the other one.
    RoomList rooms;
    try {
        rooms = backend->GetRoomList();
    } catch (const std::exception& e) {
        LOG_ERROR(WebService, "Failed to get room list from {}: {}", primary_url, e.what());
    }

    if (secondary.valid()) {
        for (auto& room : secondary.get()) {
            // The same room can be announced to both servers, only show it once.
            const bool duplicate =
                std::any_of(rooms.begin(), rooms.end(), [&room](const auto& existing) {
                    return existing.ip == room.ip && existing.port == room.port;
                });
            if (!duplicate) {
                rooms.push_back(std::move(room));
            }
        }
    }
    return rooms;
#else
    return backend->GetRoomList();
#endif
}

bool AnnounceMultiplayerSession::IsRunning() const {
    return announce_multiplayer_thread != nullptr;
}

void AnnounceMultiplayerSession::UpdateCredentials(const std::string& new_username) {
    ASSERT_MSG(!IsRunning(), "Credentials can only be updated when session is not running");

    username = new_username;

#ifdef ENABLE_WEB_SERVICE
    backend =
        std::make_unique<WebService::RoomJson>(Settings::values.web_api_url.GetValue(), username,
                                               Settings::values.network_token.GetValue());
#endif
}

} // namespace Network
