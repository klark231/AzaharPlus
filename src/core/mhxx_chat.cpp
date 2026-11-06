// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#include <array>
#include <atomic>
#include <chrono>
#include <memory>
#include <mutex>
#include <optional>
#include "core/core.h"
#include "core/hle/kernel/kernel.h"
#include "core/hle/kernel/process.h"
#include "core/memory.h"
#include "core/mhxx_chat.h"

namespace MhxxChat {

namespace {

// The keyboard manager, as found in MHXX JP 1.4.0's code.bin (virtual addresses):
//   [0xD3FD04]  pointer to the manager object
//   +0x11  u8   request state: 4 while a keyboard is open, 2 when finished
//   +0x14  u32  request parameters, +0x18 u32 max length, +0x1C.. 0x84 bytes initial text etc.
//   +0xF9  u8   UI mode: 4 while a keyboard is open (touch buttons disabled)
//   +0xFA  u8   the mode the keyboard replaced
//   +0x150 u8   1 while a keyboard request is running (polled every frame)
//   +0x151 u8   result: 0 none yet, 1 cancelled / finished, 2 OK, 3 OK (text was checked)
//   +0x152 u16  result text, UTF-16
//   +0x18C      an embedded object whose first word is its vtable; the keyboard module calls it when
//               keys are pressed. The text buffer must stop before it: clobbering the vtable makes
//               the next keyboard crash on its first key press (call through a null vtable).
// When the keyboard module reports OK, the game (0x8295DC..0x829680) copies the text to +0x152,
// sets result 2 and running 0, then ends the request: state 2, parameters cleared, UI mode put
// back. Whoever asked for the keyboard (chat at 0x29946C, and others) reads the result and calls
// 0x829D98, which closes the keyboard module. Type() does what the OK path does, minus the module.
constexpr VAddr ManagerPointer = 0x00D3FD04;
constexpr u32 OffState = 0x11;
constexpr u32 OffParams = 0x14;
constexpr u32 OffMaxLength = 0x18;
constexpr u32 OffInitial = 0x1C;
constexpr u32 InitialSize = 0x84;
constexpr u32 OffMode = 0xF9;
constexpr u32 OffSavedMode = 0xFA;
constexpr u32 OffRunning = 0x150;
constexpr u32 OffResult = 0x151;
constexpr u32 OffText = 0x152;
constexpr u32 OffVtable = 0x18C;
constexpr u32 TextChars = (OffVtable - OffText) / sizeof(u16); // 29: 28 chars and the NUL
static_assert(TextChars == MaxChars + 1);

constexpr u8 KeyboardMode = 4;
constexpr u8 StateFinished = 2;
constexpr u8 ResultNone = 0;
constexpr u8 ResultOk = 2;

constexpr const char* KeyboardModule = "roSwkbd";
constexpr s64 SettleMs = 250; // the game needs a moment after the module loads
constexpr s64 PollMs = 16;    // how often the manager is looked at

using GameBuffer = std::array<u16, TextChars>;

// Shared with the UI thread.
std::atomic<bool> g_keyboard_open{false};
std::mutex g_pending_mutex;
std::optional<GameBuffer> g_pending_text;

// Set by the loader, which runs on the emulation thread like everything below.
std::atomic<bool> g_module_loaded{false};
std::atomic<s64> g_module_loaded_ms{0};

// Emulation thread only.
std::weak_ptr<Kernel::Process> g_game_process;
s64 g_last_poll_ms = 0;

s64 NowMs() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

bool ModuleReady() {
    return g_module_loaded.load() && NowMs() - g_module_loaded_ms.load() >= SettleMs;
}

struct Manager {
    std::shared_ptr<Kernel::Process> process;
    VAddr address;
};

std::shared_ptr<Kernel::Process> FindGameProcess(Core::System& system) {
    if (auto process = g_game_process.lock()) {
        return process;
    }
    auto& kernel = system.Kernel();
    for (u32 pid = 0; pid < 0x100; pid++) {
        auto process = kernel.GetProcessById(pid);
        if (process && process->codeset && process->codeset->program_id == TitleId) {
            g_game_process = process;
            return process;
        }
    }
    return nullptr;
}

/// The game's process and its keyboard manager, if it exists (yet).
std::optional<Manager> FindManager(Core::System& system) {
    auto process = FindGameProcess(system);
    if (!process) {
        return std::nullopt;
    }
    auto& memory = system.Memory();
    if (!memory.IsValidVirtualAddress(*process, ManagerPointer)) {
        return std::nullopt;
    }
    const VAddr address = memory.Read32(*process, ManagerPointer);
    if (address == 0 || !memory.IsValidVirtualAddress(*process, address + OffVtable)) {
        return std::nullopt;
    }
    return Manager{std::move(process), address};
}

/// The text as the game's buffer wants it, or nothing when it is blank (the game's own keyboard
/// refuses blank text too).
std::optional<GameBuffer> ToGameBuffer(const std::u16string& text) {
    GameBuffer buffer{}; // the unused rest stays zero, so the text ends with a NUL
    u32 length = 0;
    bool blank = true;
    for (const char16_t c : text) {
        if (length == MaxChars) {
            break;
        }
        if (c == u'\r' || c == u'\n') {
            continue;
        }
        const bool surrogate = c >= 0xD800 && c <= 0xDFFF; // the game's font has no use for these
        buffer[length++] = surrogate ? u'?' : static_cast<u16>(c);
        blank = blank && (c == u' ' || c == 0x3000);
    }
    if (blank) {
        return std::nullopt;
    }
    return buffer;
}

/// Hands the text to the game exactly as the keyboard's OK path does.
void Type(Core::System& system, const Manager& manager, const GameBuffer& text) {
    auto& memory = system.Memory();
    const Kernel::Process& process = *manager.process;
    const VAddr base = manager.address;

    memory.WriteBlock(process, base + OffText, text.data(), text.size() * sizeof(u16));
    memory.Write8(process, base + OffResult, ResultOk);
    memory.Write8(process, base + OffRunning, 0);

    // The end of the request, as in the game's OK path.
    memory.Write8(process, base + OffState, StateFinished);
    const std::array<u8, InitialSize> zeros{};
    memory.WriteBlock(process, base + OffParams, zeros.data(), sizeof(u32));
    memory.WriteBlock(process, base + OffMaxLength, zeros.data(), sizeof(u32));
    memory.WriteBlock(process, base + OffInitial, zeros.data(), zeros.size());
    const u8 mode = memory.Read8(process, base + OffMode);
    memory.Write8(process, base + OffMode,
                  mode == KeyboardMode ? memory.Read8(process, base + OffSavedMode) : 0);
}

} // namespace

bool KeyboardOpen() {
    return g_keyboard_open.load();
}

bool InjectText(const std::u16string& text) {
    const auto buffer = ToGameBuffer(text);
    if (!buffer || !g_keyboard_open.load()) {
        return false;
    }
    std::scoped_lock lock{g_pending_mutex};
    g_pending_text = buffer;
    return true;
}

void OnModuleLoaded(const std::string& name) {
    if (name == KeyboardModule) {
        g_module_loaded_ms = NowMs();
        g_module_loaded = true;
    }
}

void OnModuleUnloaded(const std::string& name) {
    if (name == KeyboardModule) {
        g_module_loaded = false;
    }
}

void RunOnEmulationThread(Core::System& system) {
    if (!ModuleReady()) {
        g_keyboard_open = false;
        return;
    }
    const s64 now = NowMs();
    if (now - g_last_poll_ms < PollMs) {
        return;
    }
    g_last_poll_ms = now;

    const auto manager = FindManager(system);
    if (!manager) {
        g_keyboard_open = false;
        return;
    }
    auto& memory = system.Memory();
    const Kernel::Process& process = *manager->process;
    const bool open = memory.Read8(process, manager->address + OffRunning) == 1 &&
                      memory.Read8(process, manager->address + OffResult) == ResultNone;
    g_keyboard_open = open;

    std::optional<GameBuffer> text;
    {
        std::scoped_lock lock{g_pending_mutex};
        text.swap(g_pending_text);
    }
    if (open && text) {
        Type(system, *manager, *text);
        g_keyboard_open = false;
    }
    // Text queued for a keyboard that has since closed is dropped.
}

void Reset() {
    g_keyboard_open = false;
    g_module_loaded = false;
    g_game_process.reset();
    g_last_poll_ms = 0;
    std::scoped_lock lock{g_pending_mutex};
    g_pending_text.reset();
}

} // namespace MhxxChat
