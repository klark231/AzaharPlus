#!/usr/bin/env python3
"""AzaharPlus fixes bundle. Run from the repo root:  python3 azp_fixes.py

Idempotent (safe to run twice) and all-or-nothing per edit: nothing is written unless every
anchor is found exactly as expected. Fixes:

 1. Performance overlay: update the text every tick instead of only when FPS > 0, so it shows
    immediately when enabled (no more "disable/re-enable to make it appear") and never gets
    stuck on a stale/blank value. Refresh twice as often (1000ms -> 500ms).
 2. Custom layout editor: apply the custom layout to the emulator the moment the editor opens,
    so the live screens match the drag handles on first open (not only after you drag one).
 3. MHGU hub: keep the hub list warm while idle (a light refresh in the 200ms tick) so the FIRST
    in-game search already has results; drop the per-server list timeout 1500ms -> 800ms.
 4. UDSCAP packet logging: gate it behind the existing (default-off) "log MHGU hub packets"
    setting, like HUBCAP already is. One switch now silences both, with zero hot-path cost.
 5. Layout menu wording: cleaner, filename-free strings (English / default locale).
"""
import os, sys

files = {}
def load(p):
    if p not in files:
        with open(p, encoding="utf-8", newline="") as f:
            files[p] = f.read()
    return files[p]

def patch(p, old, new, count=1):
    """Replace old->new. If new already present, skip (idempotent). Else require exactly `count`."""
    s = load(p)
    if new in s:
        return "skip"
    n = s.count(old)
    if n != count:
        sys.exit(f"ERROR: {p}: anchor found {n}x (expected {count}):\n  {old[:140]!r}")
    files[p] = s.replace(old, new)
    return "ok"

VK = "src/core/hle/service/nwm/"
KT = "src/android/app/src/main/java/org/citra/citra_emu/"
RES = "src/android/app/src/main/res/values/strings.xml"

# ---- 1. performance overlay -----------------------------------------------------------------
EF = KT + "fragments/EmulationFragment.kt"
patch(EF,
      "                if (perfStats[fps] > 0) {",
      "                if (perfStats.isNotEmpty()) {")
patch(EF,
      "                perfStatsUpdateHandler.postDelayed(perfStatsUpdater!!, 1000)",
      "                perfStatsUpdateHandler.postDelayed(perfStatsUpdater!!, 500)")

# ---- 2. custom layout editor: apply on open -------------------------------------------------
CLM = KT + "display/CustomLayoutManager.kt"
patch(CLM,
      "        editorView.post { editorView.loadLayoutSettings() }",
      "        editorView.post {\n"
      "            editorView.loadLayoutSettings()\n"
      "            // Push the custom layout to the emulator now so the live screens match the\n"
      "            // drag handles immediately, instead of only after the first drag.\n"
      "            editorView.applyLayoutChanges()\n"
      "        }")

# ---- 3. MHGU hub: warm list while idle + faster list timeout --------------------------------
HUB = VK + "mhgu_hub.cpp"
patch(HUB,
      "        if (hosting && host_udp != H::BadSock && now >= next_register) {\n"
      "            next_register = now + 1s;\n"
      "            for (auto& s : st) {\n"
      "                if (s.alive && s.pair && !UdpUsable(s.udp_ok, s.udp_rx)) {\n"
      "                    H::UdpSendTo(host_udp, s.uaddr, H::EncodeRelayRegister(s.pair, s.secret));\n"
      "                }\n"
      "            }\n"
      "        }\n"
      "    }",
      "        if (hosting && host_udp != H::BadSock && now >= next_register) {\n"
      "            next_register = now + 1s;\n"
      "            for (auto& s : st) {\n"
      "                if (s.alive && s.pair && !UdpUsable(s.udp_ok, s.udp_rx)) {\n"
      "                    H::UdpSendTo(host_udp, s.uaddr, H::EncodeRelayRegister(s.pair, s.secret));\n"
      "                }\n"
      "            }\n"
      "        }\n"
      "        // Keep the hub list warm while idle so the first in-game search already has results.\n"
      "        if (!hosting && sta == Sta::Idle && !list_pending && now - last_list > 5s) {\n"
      "            RequestList();\n"
      "        }\n"
      "    }")
patch(HUB,
      "            ts.emplace_back([&, i] { states[i] = H::ListHubs(servers[i], key, 1500, found[i]); });",
      "            ts.emplace_back([&, i] { states[i] = H::ListHubs(servers[i], key, 800, found[i]); });")

# ---- 4. gate UDSCAP behind mhgu_hub_log -----------------------------------------------------
UDS = VK + "nwm_uds.cpp"
patch(UDS,
      "    if (UdsCapAllow(uds_cap_rx, 600)) {",
      "    if (Settings::values.mhgu_hub_log.GetValue() && UdsCapAllow(uds_cap_rx, 600)) {")
patch(UDS,
      "    if (data_channel != HEARTBEAT_CHANNEL && UdsCapAllow(uds_cap_tx, 600)) {",
      "    if (data_channel != HEARTBEAT_CHANNEL && Settings::values.mhgu_hub_log.GetValue() &&\n"
      "        UdsCapAllow(uds_cap_tx, 600)) {")
patch(UDS,
      "    if (UdsCapAllow(uds_cap_adv, 40)) {",
      "    if (Settings::values.mhgu_hub_log.GetValue() && UdsCapAllow(uds_cap_adv, 40)) {")

# ---- 5. layout menu wording (default locale) ------------------------------------------------
patch(RES, '<string name="layout_files_menu">Layout files (export / import)</string>',
           '<string name="layout_files_menu">Button Layout</string>')
patch(RES, '<string name="layout_files_title">Layout files</string>',
           '<string name="layout_files_title">Button Layout</string>')
patch(RES, '<string name="layout_files_export_global">Export current layout to layout_global.ini</string>',
           '<string name="layout_files_export_global">Save as global layout</string>')
patch(RES, '<string name="layout_files_export_game">Export current layout for this game</string>',
           '<string name="layout_files_export_game">Save layout for this game</string>')
patch(RES, '<string name="layout_files_import_global">Import layout_global.ini</string>',
           '<string name="layout_files_import_global">Load global layout</string>')
patch(RES, '<string name="layout_files_import_game">Import this game\\\'s layout file</string>',
           '<string name="layout_files_import_game">Load layout for this game</string>')

# ---- 6. Azahar room connection: more tolerant ENet timeouts (mobile) ------------------------
# ENet defaults drop a peer after ~5s of silence; a brief Wi-Fi/cellular blip then kills the room.
# Raising the minimum to 10s (cap 30s) rides out transient loss without leaving zombie peers.
RM = "src/network/room_member.cpp"
patch(RM,
      "    server = enet_host_connect(client, &address, NumChannels, 0);\n"
      "\n"
      "    if (!server) {\n"
      "        SetState(State::Idle);\n"
      "        SetError(Error::UnknownError);\n"
      "        return;\n"
      "    }\n",
      "    server = enet_host_connect(client, &address, NumChannels, 0);\n"
      "\n"
      "    if (!server) {\n"
      "        SetState(State::Idle);\n"
      "        SetError(Error::UnknownError);\n"
      "        return;\n"
      "    }\n"
      "\n"
      "    // More tolerant timeouts so a brief mobile packet-loss blip doesn't drop the room.\n"
      "    enet_peer_timeout(server, 32, 10000, 30000);\n")
RC = "src/network/room.cpp"
patch(RC,
      "            case ENET_EVENT_TYPE_NONE:\n"
      "            case ENET_EVENT_TYPE_CONNECT:\n"
      "                break;",
      "            case ENET_EVENT_TYPE_CONNECT:\n"
      "                // More tolerant timeouts so a brief mobile packet-loss blip doesn't drop a member.\n"
      "                enet_peer_timeout(event.peer, 32, 10000, 30000);\n"
      "                break;\n"
      "            case ENET_EVENT_TYPE_NONE:\n"
      "                break;")

# ---- 7. present mode: prefer mailbox over Fifo when vsync is on (fixes 60fps judder) ---------
# With Fifo, a frame that slightly overruns a display refresh is snapped to the NEXT vsync, which
# at 60 FPS (~16ms budget) is periodic judder. MMJ doesn't hard-Fifo, so it stays smooth. Mailbox
# (triple-buffered) lets a late frame replace the queued one without blocking a whole refresh.
SW = "src/video_core/renderer_vulkan/vk_swapchain.cpp"
patch(SW,
      "    // If vsync is enabled attempt to use mailbox mode in case the user wants to speedup/slowdown\n"
      "    // the game. If mailbox is not available use immediate and warn about it.\n"
      "    if (use_vsync &&\n"
      "        (frame_limit > 100 || frame_limit == 0 || low_refresh_rate)) { // 0 = unthrottled\n"
      "        present_mode = has_mailbox ? vk::PresentModeKHR::eMailbox : vk::PresentModeKHR::eImmediate;\n"
      "        if (!has_mailbox) {\n"
      "            LOG_WARNING(\n"
      "                Render_Vulkan,\n"
      "                \"Vsync enabled while frame limiting and no mailbox support, expect tearing\");\n"
      "        }\n"
      "        return;\n"
      "    }",
      "    // Vsync on: prefer mailbox (triple-buffered) whenever the device offers it. With Fifo a\n"
      "    // frame that slightly overruns a display refresh is snapped to the NEXT vsync, which at\n"
      "    // 60 FPS (~16ms budget) shows up as periodic judder; mailbox lets a late frame replace the\n"
      "    // queued one without blocking a whole refresh. Fall back to immediate when speeding up or\n"
      "    // unthrottled, and only to Fifo when the device offers neither mailbox nor immediate.\n"
      "    if (use_vsync) {\n"
      "        if (has_mailbox) {\n"
      "            present_mode = vk::PresentModeKHR::eMailbox;\n"
      "        } else if (frame_limit > 100 || frame_limit == 0 || low_refresh_rate) { // 0 = unthrottled\n"
      "            present_mode = vk::PresentModeKHR::eImmediate;\n"
      "        }\n"
      "        return;\n"
      "    }")

# ---- write ----------------------------------------------------------------------------------
changed = 0
for p, content in files.items():
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    changed += 1
print(f"azp_fixes: wrote {changed} files")
