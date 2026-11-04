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
      "        }",
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
      "        }")
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

# ---- 5. layout menu wording (ALL locales) ---------------------------------------------------
# The layout files hold the screen layout AND the on-screen controls, so the name is just
# "Layout" (not "Button Layout"). Replaced by string NAME via regex, so it is locale-independent
# and idempotent. Any locale without a translation below falls back to English.
import re, glob
RESDIR = "src/android/app/src/main/res"
KEYS = ("layout_files_menu", "layout_files_title", "layout_files_export_global",
        "layout_files_export_game", "layout_files_import_global", "layout_files_import_game")
EN = {
 "layout_files_menu": "Save / Load Layout", "layout_files_title": "Layout",
 "layout_files_export_global": "Save as global layout",
 "layout_files_export_game": "Save layout for this game",
 "layout_files_import_global": "Load global layout",
 "layout_files_import_game": "Load layout for this game"}
L = {
 "values": EN, "values-b+en+GB": EN,
 "values-es": dict(zip(KEYS,["Guardar / Cargar diseño","Diseño","Guardar como diseño global","Guardar diseño para este juego","Cargar diseño global","Cargar diseño de este juego"])),
 "values-b+es+419": dict(zip(KEYS,["Guardar / Cargar diseño","Diseño","Guardar como diseño global","Guardar diseño para este juego","Cargar diseño global","Cargar diseño de este juego"])),
 "values-b+ca+ES+valencia": dict(zip(KEYS,["Guardar / Carregar disposició","Disposició","Guardar com a disposició global","Guardar la disposició d\\'este joc","Carregar la disposició global","Carregar la disposició d\\'este joc"])),
 "values-b+pt+BR": dict(zip(KEYS,["Salvar / Carregar disposição","Disposição","Salvar como disposição global","Salvar disposição deste jogo","Carregar disposição global","Carregar disposição deste jogo"])),
 "values-b+zh+CN": dict(zip(KEYS,["保存 / 加载布局","布局","保存为全局布局","保存此游戏的布局","加载全局布局","加载此游戏的布局"])),
 "values-b+zh+TW": dict(zip(KEYS,["儲存 / 載入版面配置","版面配置","儲存為全域版面配置","儲存此遊戲的版面配置","載入全域版面配置","載入此遊戲的版面配置"])),
 "values-da": dict(zip(KEYS,["Gem / indlæs layout","Layout","Gem som globalt layout","Gem layout for dette spil","Indlæs globalt layout","Indlæs layout for dette spil"])),
 "values-de": dict(zip(KEYS,["Layout speichern / laden","Layout","Als globales Layout speichern","Layout für dieses Spiel speichern","Globales Layout laden","Layout für dieses Spiel laden"])),
 "values-el": dict(zip(KEYS,["Αποθήκευση / Φόρτωση διάταξης","Διάταξη","Αποθήκευση ως γενική διάταξη","Αποθήκευση διάταξης για αυτό το παιχνίδι","Φόρτωση γενικής διάταξης","Φόρτωση διάταξης για αυτό το παιχνίδι"])),
 "values-fi": dict(zip(KEYS,["Tallenna / Lataa asettelu","Asettelu","Tallenna yleisasetteluksi","Tallenna tämän pelin asettelu","Lataa yleisasettelu","Lataa tämän pelin asettelu"])),
 "values-fr": dict(zip(KEYS,["Enregistrer / Charger la disposition","Disposition","Enregistrer comme disposition globale","Enregistrer la disposition de ce jeu","Charger la disposition globale","Charger la disposition de ce jeu"])),
 "values-hu": dict(zip(KEYS,["Elrendezés mentése / betöltése","Elrendezés","Mentés globális elrendezésként","Elrendezés mentése ehhez a játékhoz","Globális elrendezés betöltése","A játék elrendezésének betöltése"])),
 "values-id": dict(zip(KEYS,["Simpan / Muat tata letak","Tata letak","Simpan sebagai tata letak global","Simpan tata letak untuk game ini","Muat tata letak global","Muat tata letak game ini"])),
 "values-it": dict(zip(KEYS,["Salva / Carica layout","Layout","Salva come layout globale","Salva il layout per questo gioco","Carica layout globale","Carica il layout di questo gioco"])),
 "values-ja": dict(zip(KEYS,["レイアウトの保存 / 読み込み","レイアウト","全体レイアウトとして保存","このゲームのレイアウトを保存","全体レイアウトを読み込み","このゲームのレイアウトを読み込み"])),
 "values-ko": dict(zip(KEYS,["레이아웃 저장 / 불러오기","레이아웃","전역 레이아웃으로 저장","이 게임의 레이아웃 저장","전역 레이아웃 불러오기","이 게임의 레이아웃 불러오기"])),
 "values-lt": dict(zip(KEYS,["Įrašyti / Įkelti išdėstymą","Išdėstymas","Įrašyti kaip bendrą išdėstymą","Įrašyti šio žaidimo išdėstymą","Įkelti bendrą išdėstymą","Įkelti šio žaidimo išdėstymą"])),
 "values-nb": dict(zip(KEYS,["Lagre / last inn oppsett","Oppsett","Lagre som globalt oppsett","Lagre oppsett for dette spillet","Last inn globalt oppsett","Last inn oppsett for dette spillet"])),
 "values-nl": dict(zip(KEYS,["Indeling opslaan / laden","Indeling","Opslaan als globale indeling","Indeling voor dit spel opslaan","Globale indeling laden","Indeling van dit spel laden"])),
 "values-pl": dict(zip(KEYS,["Zapisz / Wczytaj układ","Układ","Zapisz jako układ globalny","Zapisz układ dla tej gry","Wczytaj układ globalny","Wczytaj układ tej gry"])),
 "values-ro": dict(zip(KEYS,["Salvează / Încarcă aranjamentul","Aranjament","Salvează ca aranjament global","Salvează aranjamentul pentru acest joc","Încarcă aranjamentul global","Încarcă aranjamentul acestui joc"])),
 "values-ru": dict(zip(KEYS,["Сохранить / Загрузить макет","Макет","Сохранить как общий макет","Сохранить макет для этой игры","Загрузить общий макет","Загрузить макет этой игры"])),
 "values-sv": dict(zip(KEYS,["Spara / Läs in layout","Layout","Spara som global layout","Spara layout för det här spelet","Läs in global layout","Läs in det här spelets layout"])),
 "values-th": dict(zip(KEYS,["บันทึก / โหลดเลย์เอาต์","เลย์เอาต์","บันทึกเป็นเลย์เอาต์ส่วนกลาง","บันทึกเลย์เอาต์ของเกมนี้","โหลดเลย์เอาต์ส่วนกลาง","โหลดเลย์เอาต์ของเกมนี้"])),
 "values-tr": dict(zip(KEYS,["Düzeni kaydet / yükle","Düzen","Genel düzen olarak kaydet","Bu oyun için düzeni kaydet","Genel düzeni yükle","Bu oyunun düzenini yükle"])),
 "values-vi": dict(zip(KEYS,["Lưu / Tải bố cục","Bố cục","Lưu làm bố cục chung","Lưu bố cục cho game này","Tải bố cục chung","Tải bố cục của game này"])),
}
for sx in glob.glob(RESDIR + "/values*/strings.xml"):
    locale = os.path.basename(os.path.dirname(sx))
    tr = L.get(locale, EN)
    s = load(sx)
    if "layout_files_menu" not in s:
        continue
    for k in KEYS:
        s = re.sub(r'(<string name="' + k + r'">).*?(</string>)',
                   lambda m, v=tr[k]: m.group(1) + v + m.group(2), s)
    files[sx] = s

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

# ---- 9. MHGU hub: pre-fill the beacon buffer so the FIRST in-game search shows hubs --------
# RecvBeaconBroadcastData calls MhguBridge::Scan() then GetReceivedBeacons() right away, but
# Scan() only POSTS the delivery to the worker, so the first read drains an empty buffer and the
# 2nd read gets the 1st scan's beacons. Deliver every tick while idle (scan_comm defaults to
# MhxxCommId, scan_id to 0) so the buffer is always pre-filled before the game reads it.
patch(HUB,
      "        // Keep the hub list warm while idle so the first in-game search already has results.\n"
      "        if (!hosting && sta == Sta::Idle && !list_pending && now - last_list > 5s) {\n"
      "            RequestList();\n"
      "        }",
      "        // Keep the hub list warm while idle so the first in-game search already has results.\n"
      "        if (!hosting && sta == Sta::Idle && !list_pending && now - last_list > 5s) {\n"
      "            RequestList();\n"
      "        }\n"
      "        // Pre-fill the game's beacon buffer every tick while it can scan, so the FIRST search\n"
      "        // already shows hubs (RecvBeaconBroadcastData reads the buffer right after triggering\n"
      "        // Scan(), before the per-scan delivery Scan() posts to this worker would run).\n"
      "        if (!hosting && sta == Sta::Idle && !listed.empty()) {\n"
      "            DeliverBeacons();\n"
      "        }")

# ---- 8. CI: give the Windows runners zlib so libzip (ZipPass dep) configures --------------
# libzip is REQUIRED by ZipPass (used on desktop via citra_qt + networking), and it needs zlib.
# Linux/macOS/Android toolchains ship zlib; the Windows runners don't -> all 3 Windows jobs fail
# at CMake configure. MSYS2 gets zlib from pacboy; MSVC gets it from vcpkg (preinstalled).
BY = ".github/workflows/build.yml"
patch(BY,
      "            toolchain:p ccache:p cmake:p ninja:p spirv-tools:p",
      "            toolchain:p ccache:p cmake:p ninja:p spirv-tools:p zlib:p")
patch(BY,
      "          D:/a/_temp/vulkan.exe --accept-licenses --default-answer --confirm-command install\n"
      "      - name: Set up MSYS2",
      "          D:/a/_temp/vulkan.exe --accept-licenses --default-answer --confirm-command install\n"
      "      - name: Install zlib (MSVC)\n"
      "        if: ${{ startsWith(matrix.target, 'msvc') }}\n"
      "        run: vcpkg install zlib:x64-windows-static-md\n"
      "        shell: bash\n"
      "      - name: Set up MSYS2")
WSH = ".ci/windows.sh"
patch(WSH,
      "fi\n\ncmake .. -G Ninja \\\n    -DCMAKE_BUILD_TYPE=Release \\",
      "fi\n\n"
      "# libzip (ZipPass dependency) needs zlib. MSVC runners have none, so point CMake at the\n"
      "# vcpkg one; MSYS2 gets zlib from pacboy instead.\n"
      "if [ \"$TARGET\" != \"msys2\" ]; then\n"
      "\tEXTRA_CMAKE_FLAGS+=(-DZLIB_USE_STATIC_LIBS=ON \\\n"
      "\t                    -DZLIB_ROOT=\"$VCPKG_INSTALLATION_ROOT/installed/x64-windows-static-md\")\n"
      "fi\n\n"
      "cmake .. -G Ninja \\\n    -DCMAKE_BUILD_TYPE=Release \\")

# ---- 10. MSVC build: fix signed/unsigned comparison (C4388 -> error under /we4388 /WX) -------
# AzaharPlus' amiibo generator loops `int i < amiibo_name.length()` (size_t). clang/gcc tolerate
# it; MSVC with /we4388 /WX makes it a hard error. Use size_t for the index.
patch("src/core/hle/service/nfc/nfc_device.cpp",
      "\tfor (int i = 0; i < amiibo_name.length(); i++) {",
      "\tfor (std::size_t i = 0; i < amiibo_name.length(); i++) {")

# ---- write ----------------------------------------------------------------------------------
changed = 0
for p, content in files.items():
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    changed += 1
print(f"azp_fixes: wrote {changed} files")
