// Copyright Azahar Emulator Project / AzaharPlus
// Licensed under GPLv2 or any later version
//
// Net sync: keeps two emulators that play together from drifting apart in emulated time.
//
// Problem: when one emulator stalls (shader compilation, heavy frames, a paused app), its emulated
// clock stands still while the other's keeps running. The game on the running side then sees
// "silence" from the peer and drops it (NEX host migration, the game's own watchdog).
//
// Idea (after MH4U-Android's netsync): every console sends the room a small report 20 times a
// second *of its own emulated time*. A stalled console sends nothing. A console that has advanced
// more than kLeadLimitUs of its own emulated time since the last report of a peer it is playing
// with simply waits (in wall time) until the next report arrives. Reports say whom the sender is
// waiting for, so two consoles that each think they are ahead do not wait for each other forever.
// A peer that is silent for Timeout() of wall time (paused, gone) is left to the game.
//
// Reports are Wi-Fi packets of type 0x4D, which no 3DS frame uses: room servers relay Wi-Fi
// packets without looking at the type and the UDS service ignores types it does not know, so
// consoles without this code are unaffected (they just never send reports, and are never waited for).
#pragma once

#include <array>
#include <chrono>
#include <cstdint>
#include <functional>
#include <map>
#include <mutex>
#include <optional>
#include <vector>
#include "common/common_types.h"

namespace Core {
class System;
}
namespace Network {
struct WifiPacket;
}

namespace Service::NWM::NetSync {

using Mac = std::array<u8, 6>;
using Clock = std::chrono::steady_clock;

/// Master switch, from the "Net Sync" setting (read live, so it can be toggled while playing).
bool IsEnabled();
/// How long (wall time) we wait for a stalled peer / treat a peer as gone, from the "Net Sync
/// Timeout" setting (1-60 s, default 6 s).
std::chrono::milliseconds Timeout();

constexpr u8 kPacketType = 0x4D;
constexpr std::chrono::milliseconds kReportInterval{50};  ///< emulated time between reports
constexpr s64 kLeadLimitUs = 300'000;                      ///< wait when this far ahead (own emulated time)
constexpr s64 kPlayWindowUs = 3'000'000;                   ///< "playing with us": game data within this
// A peer silent for Timeout() of wall time (paused, gone) is ignored, and we never wait longer
// than Timeout() in one go.
constexpr std::chrono::milliseconds kCooldown{3000};       ///< after giving up, free-run this long
constexpr std::chrono::milliseconds kSlice{100};           ///< max block per RunLoop call (wall)

/// Pure bookkeeping, no I/O: easy to test.
class Tracker {
public:
    /// Receive thread: a report from a peer arrived.
    void OnReport(const Mac& peer, bool peer_waiting, const Mac& waiting_for,
                  Clock::time_point wall) {
        std::scoped_lock lock{mtx};
        Peer& p = peers[peer];
        ++p.report_seq;
        p.last_report_wall = wall;
        p.peer_waiting = peer_waiting;
        p.waiting_for = waiting_for;
    }

    /// Receive thread: game data arrived from a peer (it is playing with us).
    void OnGameData(const Mac& peer) {
        std::scoped_lock lock{mtx};
        ++peers[peer].game_seq;
    }

    /// Emulation thread: the peer we must wait for right now, if any. Arrival times of reports and
    /// game data are stamped here, with our own emulated clock, the first time we look after they
    /// arrived: while our own emulation is stalled that clock does not move, so a report that
    /// arrives during our own stall never makes us wait afterwards.
    std::optional<Mac> Evaluate(s64 now_us, const Mac& my_mac, Clock::time_point wall,
                                std::chrono::milliseconds silence) {
        std::scoped_lock lock{mtx};
        std::optional<Mac> result;
        s64 worst = 0;
        for (auto& [mac, p] : peers) {
            if (p.report_seq != p.seen_report_seq) {
                p.seen_report_seq = p.report_seq;
                p.stamp_report_us = now_us;
            }
            if (p.game_seq != p.seen_game_seq) {
                p.seen_game_seq = p.game_seq;
                p.stamp_game_us = now_us;
            }
            if (p.stamp_game_us < 0 || now_us - p.stamp_game_us > kPlayWindowUs) {
                continue; // not playing with us
            }
            if (p.stamp_report_us < 0) {
                continue; // never heard a report: peer has no net sync
            }
            if (wall - p.last_report_wall > silence) {
                continue; // silent (paused, gone): leave it to the game
            }
            if (p.peer_waiting && p.waiting_for == my_mac &&
                wall - p.last_report_wall < std::chrono::seconds(1)) {
                continue; // it waits for us: do not wait for it (breaks cycles)
            }
            const s64 lead = now_us - p.stamp_report_us;
            if (lead > kLeadLimitUs && lead > worst) {
                worst = lead;
                result = mac;
            }
        }
        return result;
    }

    void Clear() {
        std::scoped_lock lock{mtx};
        peers.clear();
    }

private:
    struct Peer {
        u64 report_seq = 0, seen_report_seq = 0;
        u64 game_seq = 0, seen_game_seq = 0;
        s64 stamp_report_us = -1; ///< our emulated clock when we first saw the latest report
        s64 stamp_game_us = -1;   ///< same, for the latest game data
        Clock::time_point last_report_wall{};
        bool peer_waiting = false;
        Mac waiting_for{};
    };
    std::mutex mtx;
    std::map<Mac, Peer> peers;
};

/// Installs/removes the function used to send a report (a broadcast Wi-Fi packet) to the room.
void SetSender(std::function<void(const std::vector<u8>&)> sender);
void ClearSender();

/// A type-0x4D packet arrived (any thread).
void HandleReport(const Network::WifiPacket& packet, const Mac& my_mac);
/// Game data from a peer was accepted by the UDS service (any thread).
void NoteGameData(const Mac& peer);
/// Sends one report now (emulation thread, from a core-timing event). `clock_us` = emulated time.
void SendReport(s64 clock_us);
/// Run-loop hook: blocks (bounded) while we are too far ahead of a peer we are playing with.
/// Returns true if the caller should skip running emulation this iteration (we are waiting).
bool WaitIfAhead(Core::System& system);
/// Forget all peers (connection ended).
void Reset();

} // namespace Service::NWM::NetSync
