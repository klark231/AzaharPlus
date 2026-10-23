// Copyright Azahar Emulator Project / AzaharPlus
// Licensed under GPLv2 or any later version

#include <atomic>
#include <cstring>
#include <thread>
#include "common/logging/log.h"
#include "core/core.h"
#include "core/core_timing.h"
#include "core/hle/service/nwm/netsync.h"
#include "network/network.h"
#include "network/room_member.h"

namespace Service::NWM::NetSync {

namespace {
Tracker g_tracker;
std::mutex g_mtx; // guards the fields below
std::function<void(const std::vector<u8>&)> g_sender;
std::optional<Mac> g_waiting_for;
Clock::time_point g_wait_started{};
Clock::time_point g_cooldown_until{};
std::atomic<bool> g_active{false}; // a report has been seen: worth taking the lock in the run loop

std::vector<u8> BuildReport(s64 clock_us) {
    std::vector<u8> d(19);
    std::memcpy(d.data(), "NSY1", 4);
    const u64 c = static_cast<u64>(clock_us);
    for (int i = 0; i < 8; ++i) {
        d[4 + i] = static_cast<u8>(c >> (8 * i));
    }
    std::scoped_lock lock{g_mtx};
    d[12] = g_waiting_for ? 1 : 0;
    if (g_waiting_for) {
        std::memcpy(d.data() + 13, g_waiting_for->data(), 6);
    }
    return d;
}
} // namespace

void SetSender(std::function<void(const std::vector<u8>&)> sender) {
    std::scoped_lock lock{g_mtx};
    g_sender = std::move(sender);
}

void ClearSender() {
    std::scoped_lock lock{g_mtx};
    g_sender = nullptr;
}

void HandleReport(const Network::WifiPacket& packet, const Mac& my_mac) {
    if constexpr (!kEnabled) {
        return;
    }
    const auto& d = packet.data;
    if (d.size() < 19 || std::memcmp(d.data(), "NSY1", 4) != 0) {
        return;
    }
    if (packet.transmitter_address == my_mac) {
        return;
    }
    Mac wf{};
    std::memcpy(wf.data(), d.data() + 13, 6);
    g_tracker.OnReport(packet.transmitter_address, d[12] != 0, wf, Clock::now());
    g_active = true;
}

void NoteGameData(const Mac& peer) {
    if constexpr (kEnabled) {
        g_tracker.OnGameData(peer);
    }
}

void SendReport(s64 clock_us) {
    if constexpr (!kEnabled) {
        return;
    }
    std::function<void(const std::vector<u8>&)> sender;
    {
        std::scoped_lock lock{g_mtx};
        sender = g_sender;
    }
    if (sender) {
        sender(BuildReport(clock_us));
    }
}

void WaitIfAhead(Core::System& system) {
    if constexpr (!kEnabled) {
        return;
    }
    if (!g_active.load(std::memory_order_relaxed)) {
        return;
    }
    Mac my_mac{};
    if (auto room_member = Network::GetRoomMember().lock(); room_member && room_member->IsConnected()) {
        my_mac = room_member->GetMacAddress();
    } else {
        return;
    }

    const auto start = Clock::now();
    auto last_report = start - std::chrono::hours(1);
    while (true) {
        const auto wall = Clock::now();
        {
            std::scoped_lock lock{g_mtx};
            if (wall < g_cooldown_until) {
                return;
            }
        }
        const s64 now_us = system.CoreTiming().GetGlobalTimeUs().count();
        const auto target = g_tracker.Evaluate(now_us, my_mac, wall);
        {
            std::scoped_lock lock{g_mtx};
            if (!target) {
                if (g_waiting_for) {
                    LOG_DEBUG(Service_NWM, "NetSync: released after {} ms",
                              std::chrono::duration_cast<std::chrono::milliseconds>(
                                  wall - g_wait_started).count());
                }
                g_waiting_for.reset();
                return;
            }
            if (!g_waiting_for) {
                g_wait_started = wall;
                LOG_DEBUG(Service_NWM, "NetSync: waiting for a peer (we are ahead of it)");
            }
            g_waiting_for = target;
            if (wall - g_wait_started > kMaxWait) {
                // Waited long enough: leave it to the game and free-run for a while.
                LOG_DEBUG(Service_NWM, "NetSync: gave up waiting after 6 s");
                g_waiting_for.reset();
                g_cooldown_until = wall + kCooldown;
                return;
            }
        }
        if (wall - start >= kSlice) {
            return; // let the run loop do one slice, we look again on the next call
        }
        if (wall - last_report >= kReportInterval) {
            // Our clock is frozen while we wait: tell the peers we are alive and whom we wait for.
            SendReport(now_us);
            last_report = wall;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}

void Reset() {
    g_tracker.Clear();
    g_active = false;
    std::scoped_lock lock{g_mtx};
    g_waiting_for.reset();
    g_cooldown_until = {};
}

} // namespace Service::NWM::NetSync
